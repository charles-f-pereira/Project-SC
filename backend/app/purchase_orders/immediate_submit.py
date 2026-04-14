"""Immediate purchase order submit: PostgreSQL batch first, idempotency, then CrunchTime."""

from __future__ import annotations

import asyncio
import time
import uuid
from datetime import datetime, timezone

import httpx
from fastapi import HTTPException
from psycopg2 import IntegrityError

from app.core.config import (
    PG_DATABASE,
    PG_HOST,
    PG_NAME,
    PG_PASSWORD,
    PG_PORT,
)
from app.core.crunchtime_api import ct_headers, get_async_client, service_token
from app.core.purchase_order_logging import po_submit_log
from app.purchase_orders.location_product_pricing import (
    save_location_product_pricing_alt_primary_sync,
    save_location_product_pricing_sync,
)
from app.purchase_orders.schemas import (
    PurchaseOrderSubmitRequest,
    PurchaseOrderSubmitResponse,
)
from app.purchase_orders.vendor_location_account import (
    fetch_account_number_for_location,
)

SAVE_PURCHASE_ORDERS_PATH = "/purchaseorder/v1/savePurchaseOrders"
VO_ACTIVATE_DELAY_SECONDS = 3

STATUS_PENDING_CT = "PENDING_CT"
BATCH_PENDING_CT = "PENDING_CT"
BATCH_SUBMITTED = "SUBMITTED"
BATCH_FAILED = "FAILED"


def _day_of_week_abbrev(ymd: str) -> str:
    try:
        dt = datetime.strptime((ymd or "").strip()[:10], "%Y-%m-%d")
        return dt.strftime("%a")
    except ValueError:
        return ""


def _fail_batch_sync(
    cur, batch_uuid: uuid.UUID, now_utc: datetime, reason: str
) -> None:
    r = (reason or "")[:2000]
    cur.execute(
        """
        UPDATE "CTH"."autoAllocationTransHdr"
        SET status = %s, failure_reason = %s
        WHERE "batch_id" = %s
        """,
        ("FAILED", r, str(batch_uuid)),
    )
    cur.execute(
        """
        UPDATE "CTH"."autoAllocationSubmitBatch"
        SET status = %s, completed_at = %s, failure_reason = %s
        WHERE id = %s
        """,
        (BATCH_FAILED, now_utc, r, str(batch_uuid)),
    )


def _replay_submitted_response(
    cur,
    batch_uuid,
    idempotency_key: str,
    body: PurchaseOrderSubmitRequest,
) -> PurchaseOrderSubmitResponse:
    cur.execute(
        """
        SELECT "transactionNo" FROM "CTH"."autoAllocationTransHdr"
        WHERE "batch_id" = %s
        ORDER BY "locationCode" NULLS LAST
        """,
        (str(batch_uuid),),
    )
    nos = [str(r[0]) for r in cur.fetchall() if r[0]]
    cur.execute(
        """
        SELECT COUNT(*)::int FROM "CTH"."autoAllocationTransDtl" d
        JOIN "CTH"."autoAllocationTransHdr" h ON d."autoAllocateTransID" = h."autoAllocateTransID"
        WHERE h."batch_id" = %s
        """,
        (str(batch_uuid),),
    )
    line_count = cur.fetchone()[0]
    cur.execute(
        """
        SELECT COUNT(*)::int FROM "CTH"."autoAllocationTransHdr"
        WHERE "batch_id" = %s
        """,
        (str(batch_uuid),),
    )
    loc_count = cur.fetchone()[0]
    msg = "Order submitted successfully."
    if nos:
        msg += f" Order number(s): {', '.join(nos)}"
    return PurchaseOrderSubmitResponse(
        success=True,
        message=msg,
        order_date_time=body.order_date_time,
        expected_delivery_date=body.expected_delivery_date,
        location_count=loc_count,
        line_count=line_count,
        batch_id=str(batch_uuid),
        idempotency_key=idempotency_key,
    )


def _handle_existing_batch(
    cur, row, idempotency_key: str, body: PurchaseOrderSubmitRequest
) -> PurchaseOrderSubmitResponse:
    bid, st, fail_reason = row[0], row[1], row[2]
    if st == BATCH_SUBMITTED:
        return _replay_submitted_response(cur, bid, idempotency_key, body)
    if st == BATCH_PENDING_CT:
        raise HTTPException(
            status_code=409,
            detail="This submission is already in progress. Check Review Auto Allocation for status.",
        )
    if st == BATCH_FAILED:
        raise HTTPException(
            status_code=409,
            detail=(
                "This idempotency key already failed. Start a new submit with a new idempotency key. "
                f"Previous reason: {(fail_reason or '')[:500]}"
            ),
        )
    raise HTTPException(
        status_code=409,
        detail=f"Unknown batch status for idempotency key: {st}",
    )


async def run_immediate_submit(
    body: PurchaseOrderSubmitRequest,
    payloads: list,
    per_location_valid_lines: list,
    per_location_expected_dates: list,
    valid_lines_default: list,
    per_location_order_utc: list | None,
    now_utc: datetime,
) -> PurchaseOrderSubmitResponse:
    import psycopg2

    idempotency_key = (body.idempotency_key or "").strip()
    if not idempotency_key:
        raise HTTPException(
            status_code=400,
            detail="idempotency_key is required for immediate submit (send a client-generated UUID).",
        )
    if len(idempotency_key) > 128:
        raise HTTPException(
            status_code=400,
            detail="idempotency_key must be at most 128 characters.",
        )

    if not (PG_NAME and PG_PASSWORD):
        raise HTTPException(
            status_code=503,
            detail=(
                "Database is not configured. Orders cannot be saved or shown on the Review page. "
                "Set pgName and pgPassword (and pgHost, pgDatabase) in backend .env."
            ),
        )

    set_order_utc = now_utc
    location_details_list = body.location_details or []
    vendor_name = body.vendor_name
    total_lines = sum(len(v) for v in per_location_valid_lines)

    conn = None
    batch_uuid: uuid.UUID | None = None
    hdr_ids: list[int] = []
    try:
        conn = psycopg2.connect(
            host=PG_HOST,
            port=PG_PORT,
            dbname=PG_DATABASE,
            user=PG_NAME,
            password=PG_PASSWORD,
        )
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, status, failure_reason
            FROM "CTH"."autoAllocationSubmitBatch"
            WHERE idempotency_key = %s
            """,
            (idempotency_key,),
        )
        existing = cur.fetchone()
        if existing:
            resp = _handle_existing_batch(cur, existing, idempotency_key, body)
            cur.close()
            conn.close()
            return resp

        batch_uuid = uuid.uuid4()
        t0 = time.monotonic()
        try:
            cur.execute(
                """
                INSERT INTO "CTH"."autoAllocationSubmitBatch" (
                    id, idempotency_key, status, location_count, "createDateTime",
                    completed_at, failure_reason
                ) VALUES (%s, %s, %s, %s, %s, NULL, NULL)
                """,
                (
                    str(batch_uuid),
                    idempotency_key,
                    BATCH_PENDING_CT,
                    len(body.location_codes),
                    now_utc,
                ),
            )
        except IntegrityError:
            conn.rollback()
            cur.execute(
                """
                SELECT id, status, failure_reason
                FROM "CTH"."autoAllocationSubmitBatch"
                WHERE idempotency_key = %s
                """,
                (idempotency_key,),
            )
            existing = cur.fetchone()
            if existing:
                resp = _handle_existing_batch(cur, existing, idempotency_key, body)
                cur.close()
                conn.close()
                return resp
            raise HTTPException(
                status_code=409,
                detail="Duplicate submit race; check Review Auto Allocation or retry.",
            )

        po_submit_log(
            "persist_start",
            batch_id=str(batch_uuid),
            idempotency_key=idempotency_key,
            location_count=len(body.location_codes),
        )

        for i, loc_code in enumerate(body.location_codes):
            loc_detail = (
                location_details_list[i] if i < len(location_details_list) else None
            )
            country = loc_detail.country if loc_detail else None
            state = loc_detail.state if loc_detail else None
            location_name = loc_detail.location_name if loc_detail else None
            market = loc_detail.market if loc_detail else None
            loc_expected_date = (
                per_location_expected_dates[i]
                if i < len(per_location_expected_dates)
                else body.expected_delivery_date
            )
            expected_dow = _day_of_week_abbrev(loc_expected_date)
            valid_lines_loc = (
                per_location_valid_lines[i]
                if i < len(per_location_valid_lines)
                else valid_lines_default
            )
            loc_set_order_utc = (
                per_location_order_utc[i]
                if per_location_order_utc is not None
                and i < len(per_location_order_utc)
                else set_order_utc
            )
            account_number = await fetch_account_number_for_location(
                loc_code, body.vendor_code
            )
            cur.execute(
                """
                INSERT INTO "CTH"."autoAllocationTransHdr" (
                    country, state, "locationCode", "locationName", market,
                    "vendorCode", "vendorName", "distributionCenter",
                    "accountNumber",
                    "createDateTime", "setOrderDateTme", "setExpectedDeliveryDate",
                    "setExpectedDeliveryDOW", "submittedDateTime", "transactionNo",
                    status, "submission_attempts", "last_attempt_at", "failure_reason", "alert_sent_at",
                    "batch_id"
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING "autoAllocateTransID"
                """,
                (
                    country,
                    state,
                    loc_code,
                    location_name,
                    market,
                    body.vendor_code,
                    vendor_name,
                    None,
                    account_number,
                    now_utc,
                    loc_set_order_utc,
                    loc_expected_date,
                    expected_dow,
                    None,
                    None,
                    STATUS_PENDING_CT,
                    0,
                    None,
                    None,
                    None,
                    str(batch_uuid),
                ),
            )
            row = cur.fetchone()
            hdr_id = int(row[0]) if row else None
            if hdr_id:
                hdr_ids.append(hdr_id)
                for li in valid_lines_loc:
                    temp_vo = "Y" if getattr(li, "temp_activate_vo", False) else "N"
                    temp_alt_primary = (
                        "Y" if getattr(li, "temp_activate_alt_primary", False) else "N"
                    )
                    cur.execute(
                        """
                        INSERT INTO "CTH"."autoAllocationTransDtl" (
                            "autoAllocateTransID", "productNumber", "productName",
                            "vendorUnit", "orderQuantity", "vendorProductNumber",
                            "TempActivateVO", "TempActivateAltPrimary"
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            hdr_id,
                            None if not li.product_number else li.product_number,
                            li.product_name,
                            li.vendor_unit or "",
                            li.qty,
                            li.vendor_product_number or "",
                            temp_vo,
                            temp_alt_primary,
                        ),
                    )

        conn.commit()
        po_submit_log(
            "persist_end",
            batch_id=str(batch_uuid),
            idempotency_key=idempotency_key,
            duration_ms=int((time.monotonic() - t0) * 1000),
        )
        cur.close()

        locations_to_activate_alt_primary = []
        for i, loc_code in enumerate(body.location_codes):
            valid_lines = (
                per_location_valid_lines[i]
                if i < len(per_location_valid_lines)
                else valid_lines_default
            )
            alt_primary_products = [
                (li.product_number or "").strip()
                for li in valid_lines
                if getattr(li, "temp_activate_alt_primary", False)
                and (li.product_number or "").strip()
            ]
            if alt_primary_products:
                locations_to_activate_alt_primary.append(
                    (loc_code, alt_primary_products)
                )
        for loc_code, product_numbers in locations_to_activate_alt_primary:
            ok, status, msg = await asyncio.to_thread(
                save_location_product_pricing_alt_primary_sync,
                loc_code,
                product_numbers,
                "Y",
            )
            if not ok:
                cur = conn.cursor()
                _fail_batch_sync(
                    cur,
                    batch_uuid,
                    datetime.now(timezone.utc),
                    f"saveLocationProductPricing (activate alternate primary) failed for {loc_code}: status={status} {msg[:500]}",
                )
                conn.commit()
                cur.close()
                po_submit_log(
                    "activate_failed",
                    batch_id=str(batch_uuid),
                    idempotency_key=idempotency_key,
                    location_code=loc_code,
                    phase="alt_primary",
                )
                raise HTTPException(
                    status_code=502,
                    detail=f"Crunchtime saveLocationProductPricing (activate alternate primary) failed for location {loc_code}: status={status} {msg[:300]}",
                )
        if locations_to_activate_alt_primary:
            await asyncio.sleep(VO_ACTIVATE_DELAY_SECONDS)

        locations_to_activate = []
        for i, loc_code in enumerate(body.location_codes):
            valid_lines = (
                per_location_valid_lines[i]
                if i < len(per_location_valid_lines)
                else valid_lines_default
            )
            vo_products = [
                (li.product_number or "").strip()
                for li in valid_lines
                if getattr(li, "temp_activate_vo", False)
                and (li.product_number or "").strip()
            ]
            if vo_products:
                locations_to_activate.append((loc_code, vo_products))
        for loc_code, product_numbers in locations_to_activate:
            ok, status, msg = await asyncio.to_thread(
                save_location_product_pricing_sync,
                loc_code,
                product_numbers,
                "Y",
            )
            if not ok:
                cur = conn.cursor()
                _fail_batch_sync(
                    cur,
                    batch_uuid,
                    datetime.now(timezone.utc),
                    f"saveLocationProductPricing (activate) failed for {loc_code}: status={status} {msg[:500]}",
                )
                conn.commit()
                cur.close()
                po_submit_log(
                    "activate_failed",
                    batch_id=str(batch_uuid),
                    idempotency_key=idempotency_key,
                    location_code=loc_code,
                    phase="vo",
                )
                raise HTTPException(
                    status_code=502,
                    detail=f"Crunchtime saveLocationProductPricing (activate) failed for location {loc_code}: status={status} {msg[:300]}",
                )
        if locations_to_activate:
            await asyncio.sleep(VO_ACTIVATE_DELAY_SECONDS)

        token = service_token("purchaseorder")
        headers = {
            **ct_headers(token_override=token),
            "accept": "application/json",
            "content-type": "application/json",
        }

        ct_t0 = time.monotonic()
        po_submit_log(
            "ct_start",
            batch_id=str(batch_uuid),
            idempotency_key=idempotency_key,
            location_count=len(body.location_codes),
        )

        results: list = []
        try:
            async with get_async_client() as client:
                tasks = [
                    client.post(
                        SAVE_PURCHASE_ORDERS_PATH, json=payload, headers=headers
                    )
                    for payload in payloads
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)
        except httpx.HTTPError as e:
            cur = conn.cursor()
            _fail_batch_sync(
                cur,
                batch_uuid,
                datetime.now(timezone.utc),
                f"Crunchtime request failed: {e!s}",
            )
            conn.commit()
            cur.close()
            po_submit_log(
                "ct_error",
                batch_id=str(batch_uuid),
                idempotency_key=idempotency_key,
                error=str(e),
            )
            raise HTTPException(
                status_code=502,
                detail=f"Crunchtime request failed: {e!s}",
            )

        po_submit_log(
            "ct_end",
            batch_id=str(batch_uuid),
            idempotency_key=idempotency_key,
            duration_ms=int((time.monotonic() - ct_t0) * 1000),
        )

        failed_pairs: list[tuple[str, str]] = []
        order_numbers: list[str | None] = []
        success_by_location: dict[str, bool] = {}

        for i, r in enumerate(results):
            loc_code = body.location_codes[i]
            err_text: str | None = None
            order_no: str | None = None
            http_status: int | None = None

            if isinstance(r, BaseException):
                err_text = str(r)[:1500]
            else:
                http_status = r.status_code
                if r.status_code != 200:
                    err_text = (getattr(r, "text", None) or "")[:1500]
                else:
                    try:
                        data = r.json()
                        if (
                            isinstance(data, list)
                            and len(data) > 0
                            and isinstance(data[0], dict)
                            and "orderNumber" in data[0]
                        ):
                            order_no = str(data[0]["orderNumber"])
                        elif isinstance(data, dict) and "orderNumber" in data:
                            order_no = str(data["orderNumber"])
                        if not order_no:
                            err_text = "Missing orderNumber in Crunchtime response"
                    except Exception as ex:
                        err_text = f"Invalid JSON response: {ex!s}"

            if err_text:
                failed_pairs.append((loc_code, err_text))
                success_by_location[loc_code] = False
                order_numbers.append(None)
            else:
                success_by_location[loc_code] = True
                order_numbers.append(order_no)

            po_submit_log(
                "ct_location",
                batch_id=str(batch_uuid),
                idempotency_key=idempotency_key,
                location_code=loc_code,
                http_status=http_status,
                order_number=order_no,
                error=err_text,
            )

        cur = conn.cursor()
        now_done = datetime.now(timezone.utc)
        for i, loc_code in enumerate(body.location_codes):
            hdr_id = hdr_ids[i] if i < len(hdr_ids) else None
            if not hdr_id:
                continue
            ok = success_by_location.get(loc_code, False)
            on = order_numbers[i] if i < len(order_numbers) else None
            reason = None
            for fl, ft in failed_pairs:
                if fl == loc_code:
                    reason = ft[:2000]
                    break
            if ok and on:
                cur.execute(
                    """
                    UPDATE "CTH"."autoAllocationTransHdr"
                    SET status = %s, "submittedDateTime" = %s, "transactionNo" = %s,
                        failure_reason = NULL, "submission_attempts" = 1, "last_attempt_at" = %s
                    WHERE "autoAllocateTransID" = %s
                    """,
                    ("SUBMITTED", now_done, on, now_done, hdr_id),
                )
            else:
                cur.execute(
                    """
                    UPDATE "CTH"."autoAllocationTransHdr"
                    SET status = %s, failure_reason = %s,
                        "submission_attempts" = 1, "last_attempt_at" = %s
                    WHERE "autoAllocateTransID" = %s
                    """,
                    (
                        "FAILED",
                        reason or "Crunchtime savePurchaseOrders failed",
                        now_done,
                        hdr_id,
                    ),
                )

        batch_ok = len(failed_pairs) == 0
        if batch_ok:
            cur.execute(
                """
                UPDATE "CTH"."autoAllocationSubmitBatch"
                SET status = %s, completed_at = %s, failure_reason = NULL
                WHERE id = %s
                """,
                (BATCH_SUBMITTED, now_done, str(batch_uuid)),
            )
        else:
            summary = "; ".join(f"{a}: {b[:120]}" for a, b in failed_pairs[:15])
            if len(failed_pairs) > 15:
                summary += "; ..."
            cur.execute(
                """
                UPDATE "CTH"."autoAllocationSubmitBatch"
                SET status = %s, completed_at = %s, failure_reason = %s
                WHERE id = %s
                """,
                (BATCH_FAILED, now_done, summary[:2000], str(batch_uuid)),
            )
        conn.commit()
        cur.close()

        for loc_code, product_numbers in locations_to_activate:
            if success_by_location.get(loc_code):
                await asyncio.to_thread(
                    save_location_product_pricing_sync,
                    loc_code,
                    product_numbers,
                    "N",
                )
        for loc_code, product_numbers in locations_to_activate_alt_primary:
            if success_by_location.get(loc_code):
                await asyncio.to_thread(
                    save_location_product_pricing_alt_primary_sync,
                    loc_code,
                    product_numbers,
                    "N",
                )

        if failed_pairs:
            detail = (
                "One or more locations failed at Crunchtime. Check Review Auto Allocation. "
                + "; ".join(f"{a}: {b[:200]}" for a, b in failed_pairs[:5])
            )
            if len(failed_pairs) > 5:
                detail += " ..."
            po_submit_log(
                "submit_partial_failure",
                batch_id=str(batch_uuid),
                idempotency_key=idempotency_key,
                failed_count=len(failed_pairs),
            )
            raise HTTPException(status_code=502, detail=detail)

        nos = [n for n in order_numbers if n]
        message = "Order submitted successfully." + (
            f" Order number(s): {', '.join(nos)}" if nos else ""
        )
        return PurchaseOrderSubmitResponse(
            success=True,
            message=message,
            order_date_time=body.order_date_time,
            expected_delivery_date=body.expected_delivery_date,
            location_count=len(body.location_codes),
            line_count=total_lines,
            batch_id=str(batch_uuid),
            idempotency_key=idempotency_key,
        )

    except HTTPException:
        raise
    except Exception:
        if batch_uuid is not None and conn is not None:
            try:
                cur = conn.cursor()
                _fail_batch_sync(
                    cur,
                    batch_uuid,
                    datetime.now(timezone.utc),
                    "Unexpected error during immediate submit",
                )
                conn.commit()
                cur.close()
            except Exception:
                try:
                    conn.rollback()
                except Exception:
                    pass
        raise
    finally:
        try:
            if conn is not None and not conn.closed:
                conn.close()
        except Exception:
            pass
