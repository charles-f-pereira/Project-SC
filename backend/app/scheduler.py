"""
APScheduler job: process SCHEDULED purchase orders when setOrderDateTme <= now.
Uses sync psycopg2 and sync httpx (job runs in a thread).
"""

from __future__ import annotations

import logging
import time
from datetime import date, datetime, timedelta, timezone

import httpx

from app.core.config import (
    BASE_URL,
    PG_DATABASE,
    PG_HOST,
    PG_NAME,
    PG_PASSWORD,
    PG_PORT,
)
from app.core.crunchtime_api import ct_headers, service_token
from app.purchase_orders.location_product_pricing import (
    save_location_product_pricing_sync,
)

logger = logging.getLogger(__name__)

SAVE_PURCHASE_ORDERS_PATH = "/purchaseorder/v1/savePurchaseOrders"
MAX_ATTEMPTS = 5
RETRY_INTERVAL_MINUTES = 5
VO_ACTIVATE_DELAY_SECONDS = 3


def _expected_delivery_date_to_ct_format(ymd: str | date | datetime | None) -> str:
    """Convert YYYY-MM-DD (or date/datetime) to mm/dd/yyyy for Crunchtime."""
    if ymd is None:
        return ""

    if isinstance(ymd, (date, datetime)):
        ymd = ymd.strftime("%Y-%m-%d")

    parts = ymd.strip().split("-")
    if len(parts) != 3:
        return ymd

    y, m, d = parts
    return f"{m}/{d}/{y}"


def _get_connection():
    if not (PG_NAME and PG_PASSWORD):
        return None
    try:
        import psycopg2

        return psycopg2.connect(
            host=PG_HOST,
            port=PG_PORT,
            dbname=PG_DATABASE,
            user=PG_NAME,
            password=PG_PASSWORD,
        )
    except Exception:
        return None


def run_scheduled_po_job():
    """
    Select SCHEDULED headers with setOrderDateTme <= now and (attempts < 5) and
    (last_attempt_at is null or >= 5 min ago). For each: increment attempts,
    call Crunchtime; on success set SUBMITTED, on failure set failure_reason
    and if attempts >= 5 set FAILED.
    """
    conn = _get_connection()
    if not conn:
        logger.warning(
            "scheduled_po_job: no DB connection (pgName/pgPassword not set?)"
        )
        return

    now_utc = datetime.now(timezone.utc)
    retry_cutoff = now_utc - timedelta(minutes=RETRY_INTERVAL_MINUTES)

    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT "autoAllocateTransID", "locationCode", "vendorCode", "setExpectedDeliveryDate"
            FROM "CTH"."autoAllocationTransHdr"
            WHERE status = 'SCHEDULED'
              AND "setOrderDateTme" <= %s
              AND "submission_attempts" < %s
              AND ("last_attempt_at" IS NULL OR "last_attempt_at" <= %s)
            ORDER BY "setOrderDateTme"
            """,
            (now_utc, MAX_ATTEMPTS, retry_cutoff),
        )
        rows = cur.fetchall()
        due_count = len(rows)
        logger.info(
            "scheduled_po_job: run at %s UTC, due_count=%s",
            now_utc.isoformat(),
            due_count,
        )
        if rows:
            logger.info(
                "scheduled_po_job: processing %s SCHEDULED order(s)",
                due_count,
            )

        for hdr_id, location_code, vendor_code, expected_delivery in rows:
            cur.execute(
                """
                SELECT "vendorProductNumber", "orderQuantity", "vendorUnit", "productNumber", "TempActivateVO"
                FROM "CTH"."autoAllocationTransDtl"
                WHERE "autoAllocateTransID" = %s
                ORDER BY "autoAllocateItmTransID"
                """,
                (hdr_id,),
            )
            detail_rows = cur.fetchall()
            detail_payload = [
                {
                    "orderQuantity": qty or 0,
                    "vendorProductNumber": (vpn or "").strip(),
                    "vendorUnit": (vu or "").strip(),
                }
                for vpn, qty, vu, _pn, _vo in detail_rows
            ]
            vo_product_numbers = [
                (str(pn).strip())
                for _vpn, _qty, _vu, pn, temp_vo in detail_rows
                if pn and (str(temp_vo or "").strip().upper() == "Y")
            ]

            if not detail_payload:
                cur.execute(
                    """
                    UPDATE "CTH"."autoAllocationTransHdr"
                    SET "submission_attempts" = "submission_attempts" + 1,
                        "last_attempt_at" = %s,
                        "failure_reason" = %s,
                        status = 'FAILED'
                    WHERE "autoAllocateTransID" = %s
                    """,
                    (now_utc, "No line items", hdr_id),
                )
                conn.commit()
                continue

            if vo_product_numbers:
                ok, status, msg = save_location_product_pricing_sync(
                    location_code, vo_product_numbers, "Y"
                )
                if not ok:
                    err_msg = f"saveLocationProductPricing (activate) failed: status={status} {msg[:500]}"
                    logger.warning(
                        "scheduled_po_job: autoAllocateTransID=%s %s",
                        hdr_id,
                        err_msg,
                    )
                    cur.execute(
                        """
                        UPDATE "CTH"."autoAllocationTransHdr"
                        SET "failure_reason" = %s, "last_attempt_at" = %s
                        WHERE "autoAllocateTransID" = %s
                        """,
                        (err_msg[:2000], now_utc, hdr_id),
                    )
                    cur.execute(
                        """
                        UPDATE "CTH"."autoAllocationTransHdr"
                        SET status = 'FAILED'
                        WHERE "autoAllocateTransID" = %s AND "submission_attempts" >= %s
                        """,
                        (hdr_id, MAX_ATTEMPTS),
                    )
                    conn.commit()
                    continue
                time.sleep(VO_ACTIVATE_DELAY_SECONDS)

            ct_expected = _expected_delivery_date_to_ct_format(expected_delivery)

            payload = {
                "purchaseOrderSaveRows": [
                    {
                        "purchaseOrderHeaderRow": {
                            "orderStatus": "SUBMITTED",
                            "orderType": "VO",
                            "expectedDeliveryDate": ct_expected,
                            "locationCode": location_code,
                            "vendorCode": vendor_code,
                        },
                        "purchaseOrderDetailRows": detail_payload,
                    }
                ],
                "locationCode": location_code,
            }

            # Mark attempt before calling CT so we don't double-pick
            cur.execute(
                """
                UPDATE "CTH"."autoAllocationTransHdr"
                SET "submission_attempts" = "submission_attempts" + 1,
                    "last_attempt_at" = %s
                WHERE "autoAllocateTransID" = %s
                """,
                (now_utc, hdr_id),
            )
            conn.commit()

            token = service_token("purchaseorder")
            headers = {
                **ct_headers(token_override=token),
                "accept": "application/json",
                "content-type": "application/json",
            }

            try:
                with httpx.Client(base_url=BASE_URL, timeout=30.0) as client:
                    r = client.post(
                        SAVE_PURCHASE_ORDERS_PATH, json=payload, headers=headers
                    )
            except httpx.RequestError as e:
                err_msg = str(e)
                logger.exception(
                    "scheduled_po_job: Crunchtime request failed for autoAllocateTransID=%s: %s",
                    hdr_id,
                    err_msg,
                )
                cur.execute(
                    """
                    UPDATE "CTH"."autoAllocationTransHdr"
                    SET "failure_reason" = %s
                    WHERE "autoAllocateTransID" = %s
                    """,
                    (err_msg[:2000], hdr_id),
                )
                cur.execute(
                    """
                    UPDATE "CTH"."autoAllocationTransHdr"
                    SET status = 'FAILED'
                    WHERE "autoAllocateTransID" = %s AND "submission_attempts" >= %s
                    """,
                    (hdr_id, MAX_ATTEMPTS),
                )
                conn.commit()
                continue

            if r.status_code == 200:
                try:
                    data = r.json()
                    order_no = None
                    if (
                        isinstance(data, list)
                        and data
                        and isinstance(data[0], dict)
                        and "orderNumber" in data[0]
                    ):
                        order_no = str(data[0]["orderNumber"])
                    elif isinstance(data, dict) and "orderNumber" in data:
                        order_no = str(data["orderNumber"])
                except Exception:
                    order_no = None

                if vo_product_numbers:
                    save_location_product_pricing_sync(
                        location_code, vo_product_numbers, "N"
                    )
                    logger.info(
                        "scheduled_po_job: autoAllocateTransID=%s deactivated VO for location=%s",
                        hdr_id,
                        location_code,
                    )

                cur.execute(
                    """
                    UPDATE "CTH"."autoAllocationTransHdr"
                    SET status = 'SUBMITTED', "submittedDateTime" = %s, "transactionNo" = %s, "failure_reason" = NULL
                    WHERE "autoAllocateTransID" = %s
                    """,
                    (now_utc, order_no, hdr_id),
                )
                conn.commit()
                logger.info(
                    "scheduled_po_job: autoAllocateTransID=%s submitted, transactionNo=%s",
                    hdr_id,
                    order_no,
                )
            else:
                err_msg = (r.text or "")[:2000]
                logger.warning(
                    "scheduled_po_job: Crunchtime returned %s for autoAllocateTransID=%s: %s",
                    r.status_code,
                    hdr_id,
                    err_msg[:200],
                )
                cur.execute(
                    """
                    UPDATE "CTH"."autoAllocationTransHdr"
                    SET "failure_reason" = %s
                    WHERE "autoAllocateTransID" = %s
                    """,
                    (err_msg, hdr_id),
                )
                cur.execute(
                    """
                    UPDATE "CTH"."autoAllocationTransHdr"
                    SET status = 'FAILED'
                    WHERE "autoAllocateTransID" = %s AND "submission_attempts" >= %s
                    """,
                    (hdr_id, MAX_ATTEMPTS),
                )
                conn.commit()

        cur.close()

    except Exception as e:
        logger.exception("scheduled_po_job: error %s", e)
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        try:
            conn.close()
        except Exception:
            pass
