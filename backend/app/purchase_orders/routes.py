import asyncio
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
from fastapi import APIRouter, HTTPException, Query

from app.core.config import BASE_URL, PG_DATABASE, PG_HOST, PG_NAME, PG_PASSWORD, PG_PORT
from app.core.crunchtime_api import ct_headers, get_async_client, service_token
from app.purchase_orders.schemas import (
    PurchaseOrderSubmitRequest,
    PurchaseOrderSubmitResponse,
)

router = APIRouter()


def _get_pg_connection():
    """Return psycopg2 connection if credentials set, else None."""
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

SAVE_PURCHASE_ORDERS_PATH = "/purchaseorder/v1/savePurchaseOrders"
# Trigger time within this many minutes of now (Sydney) is treated as "submit now" (user has time to review)
IMMEDIATE_WINDOW_MINUTES = 5
MAX_SCHEDULE_DAYS = 14

try:
    SYDNEY_TZ = ZoneInfo("Australia/Sydney")
except ZoneInfoNotFoundError:
    SYDNEY_TZ = None  # Windows: install tzdata (pip install tzdata)


def _parse_order_datetime_sydney(value: str) -> datetime | None:
    """Parse order_date_time as Sydney local time. Accepts YYYY-MM-DDTHH:mm or YYYY-MM-DDTHH:mm:ss."""
    if SYDNEY_TZ is None:
        return None
    value = (value or "").strip()
    if not value:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            dt = datetime.strptime(value, fmt)
            return dt.replace(tzinfo=SYDNEY_TZ)
        except ValueError:
            continue
    return None


def _expected_delivery_date_to_ct_format(ymd: str) -> str:
    """Convert YYYY-MM-DD to mm/dd/yyyy for Crunchtime."""
    parts = (ymd or "").strip().split("-")
    if len(parts) != 3:
        return ymd
    y, m, d = parts[0], parts[1], parts[2]
    return f"{m}/{d}/{y}"


def _day_of_week_abbrev(ymd: str) -> str:
    """Return Mon, Tue, ... from YYYY-MM-DD."""
    try:
        dt = datetime.strptime((ymd or "").strip()[:10], "%Y-%m-%d")
        return dt.strftime("%a")
    except ValueError:
        return ""


@router.post("/submit", response_model=PurchaseOrderSubmitResponse)
async def submit_purchase_order(body: PurchaseOrderSubmitRequest):
    """
    Schedule/submit a purchase order for the selected locations and vendor.

    Order date/time is interpreted as Sydney time (AEST/AEDT) and must be
    current or future. Accepts order date/time, expected delivery date,
    location codes, vendor code, and line items.
    """
    if SYDNEY_TZ is None:
        raise HTTPException(
            status_code=503,
            detail="Timezone data unavailable. On Windows, install tzdata: pip install tzdata",
        )
    # Order date/time: Sydney time; must be now or future, up to 14 days ahead
    order_dt = _parse_order_datetime_sydney(body.order_date_time)
    if not order_dt:
        raise HTTPException(
            status_code=400,
            detail="Invalid order_date_time format. Use YYYY-MM-DDTHH:mm or YYYY-MM-DDTHH:mm:ss (Sydney time).",
        )
    now_sydney = datetime.now(SYDNEY_TZ)  # type: ignore[arg-type]
    if order_dt < now_sydney:
        raise HTTPException(
            status_code=400,
            detail="Order date and time must be current or future (Sydney time AEST/AEDT).",
        )
    from datetime import timedelta
    max_schedule = now_sydney + timedelta(days=MAX_SCHEDULE_DAYS)
    if order_dt > max_schedule:
        raise HTTPException(
            status_code=400,
            detail=f"Order date and time cannot be more than {MAX_SCHEDULE_DAYS} days in the future (Sydney time).",
        )
    # Within immediate window → submit now (trigger time recorded as actual submit time)
    immediate_threshold = now_sydney + timedelta(minutes=IMMEDIATE_WINDOW_MINUTES)
    submit_immediately = order_dt <= immediate_threshold

    # Expected delivery date must be on or after order date (Sydney), and today or future
    order_date_sydney = order_dt.date()
    today_sydney = now_sydney.date()

    expected_delivery = (body.expected_delivery_date or "").strip()
    if not expected_delivery:
        raise HTTPException(status_code=400, detail="Expected delivery date is required.")
    try:
        delivery_date = datetime.strptime(expected_delivery, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Expected delivery date must be YYYY-MM-DD.",
        )
    if delivery_date < order_date_sydney:
        raise HTTPException(
            status_code=400,
            detail="Expected delivery date cannot be before the order date & time.",
        )
    if delivery_date < today_sydney:
        raise HTTPException(
            status_code=400,
            detail="Expected delivery date must be today or in the future.",
        )

    # Per-location expected delivery dates (optional)
    expected_delivery_dates_list = body.expected_delivery_dates
    if expected_delivery_dates_list is not None:
        if len(expected_delivery_dates_list) != len(body.location_codes):
            raise HTTPException(
                status_code=400,
                detail="expected_delivery_dates length must match location_codes.",
            )
        for i, ed in enumerate(expected_delivery_dates_list):
            ed = (ed or "").strip()
            if not ed:
                raise HTTPException(status_code=400, detail=f"Expected delivery date required for location index {i}.")
            try:
                d = datetime.strptime(ed, "%Y-%m-%d").date()
                if d < order_date_sydney:
                    raise HTTPException(status_code=400, detail=f"Expected delivery date for location index {i} cannot be before the order date & time.")
                if d < today_sydney:
                    raise HTTPException(status_code=400, detail=f"Expected delivery date for location index {i} must be today or future.")
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Expected delivery date for location index {i} must be YYYY-MM-DD.")

    # Per-location line items (optional)
    location_line_items_list = body.location_line_items
    if location_line_items_list is not None:
        if len(location_line_items_list) != len(body.location_codes):
            raise HTTPException(
                status_code=400,
                detail="location_line_items length must match location_codes.",
            )
        for i, loc_lines in enumerate(location_line_items_list):
            valid = [li for li in loc_lines if li.qty > 0]
            if not valid:
                raise HTTPException(status_code=400, detail=f"At least one line item with qty > 0 required for location index {i}.")

    # Validate that at least one line has qty > 0 when not using location_line_items
    valid_lines_default = [li for li in body.line_items if li.qty > 0]
    if not valid_lines_default and location_line_items_list is None:
        raise HTTPException(
            status_code=400,
            detail="At least one line item must have quantity greater than 0.",
        )

    # Crunchtime allows max 1 purchase order per savePurchaseOrders call; one payload per location.
    payloads = []
    per_location_valid_lines = []
    per_location_expected_dates = []
    for i, loc_code in enumerate(body.location_codes):
        if location_line_items_list is not None:
            valid_lines = [li for li in location_line_items_list[i] if li.qty > 0]
        else:
            valid_lines = valid_lines_default
        if expected_delivery_dates_list is not None:
            loc_expected = (expected_delivery_dates_list[i] or "").strip() or expected_delivery
        else:
            loc_expected = expected_delivery
        ct_expected_date = _expected_delivery_date_to_ct_format(loc_expected)
        detail_rows = [
            {"orderQuantity": li.qty, "vendorProductNumber": li.vendor_product_number, "vendorUnit": li.vendor_unit or ""}
            for li in valid_lines
        ]
        payloads.append({
            "purchaseOrderSaveRows": [
                {
                    "purchaseOrderHeaderRow": {
                        "orderStatus": "SUBMITTED",
                        "orderType": "VO",
                        "expectedDeliveryDate": ct_expected_date,
                        "locationCode": loc_code,
                        "vendorCode": body.vendor_code,
                    },
                    "purchaseOrderDetailRows": detail_rows,
                }
            ],
            "locationCode": loc_code,
        })
        per_location_valid_lines.append(valid_lines)
        per_location_expected_dates.append(loc_expected)

    order_numbers = []
    now_utc = datetime.now(timezone.utc)
    if submit_immediately:
        token = service_token("purchaseorder")
        headers = {
            **ct_headers(token_override=token),
            "accept": "application/json",
            "content-type": "application/json",
        }
        try:
            async with get_async_client() as client:
                tasks = [
                    client.post(SAVE_PURCHASE_ORDERS_PATH, json=payload, headers=headers)
                    for payload in payloads
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)
        except httpx.HTTPError as e:
            raise HTTPException(
                status_code=502,
                detail=f"Crunchtime request failed: {e!s}",
            )
        for i, r in enumerate(results):
            loc_code = body.location_codes[i]
            if isinstance(r, Exception):
                raise HTTPException(
                    status_code=502,
                    detail=f"Crunchtime request failed for location {loc_code}: {r!s}",
                )
            if r.status_code != 200:
                detail = f"Crunchtime savePurchaseOrders failed for location {loc_code}."
                try:
                    if r.text:
                        detail = f"{detail} {r.text[:500]}"
                except Exception:
                    pass
                raise HTTPException(status_code=502, detail=detail)
            try:
                data = r.json()
                if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict) and "orderNumber" in data[0]:
                    order_numbers.append(str(data[0]["orderNumber"]))
                elif isinstance(data, dict) and "orderNumber" in data:
                    order_numbers.append(str(data["orderNumber"]))
                else:
                    order_numbers.append(None)
            except Exception as e:
                raise HTTPException(
                    status_code=502,
                    detail=f"Invalid response from Crunchtime for location {loc_code}: {e!s}",
                )

    # For immediate: trigger time recorded as actual submit time (UTC). For scheduled: use user-selected time (UTC).
    if submit_immediately:
        set_order_utc = now_utc
    else:
        order_dt_sydney = _parse_order_datetime_sydney(body.order_date_time)
        set_order_utc = order_dt_sydney.astimezone(timezone.utc) if order_dt_sydney else now_utc

    # Persist to CTH (one header per location; reuse order_number by index or single for all)
    location_details_list = body.location_details or []
    if PG_NAME and PG_PASSWORD:
        try:
            import psycopg2
            conn = psycopg2.connect(
                host=PG_HOST,
                port=PG_PORT,
                dbname=PG_DATABASE,
                user=PG_NAME,
                password=PG_PASSWORD,
            )
            cur = conn.cursor()
            status_val = "SUBMITTED" if submit_immediately else "SCHEDULED"
            submitted_dt = now_utc if submit_immediately else None
            submission_attempts_val = 1 if submit_immediately else 0
            last_attempt_at_val = now_utc if submit_immediately else None
            for i, loc_code in enumerate(body.location_codes):
                trans_no = order_numbers[i] if i < len(order_numbers) else (order_numbers[0] if order_numbers else None)
                loc_detail = location_details_list[i] if i < len(location_details_list) else None
                country = loc_detail.country if loc_detail else None
                state = loc_detail.state if loc_detail else None
                location_name = loc_detail.location_name if loc_detail else None
                market = loc_detail.market if loc_detail else None
                vendor_name = body.vendor_name
                loc_expected_date = per_location_expected_dates[i] if i < len(per_location_expected_dates) else body.expected_delivery_date
                expected_dow = _day_of_week_abbrev(loc_expected_date)
                valid_lines_loc = per_location_valid_lines[i] if i < len(per_location_valid_lines) else valid_lines_default
                cur.execute(
                    """
                    INSERT INTO "CTH"."autoAllocationTransHdr" (
                        country, state, "locationCode", "locationName", market,
                        "vendorCode", "vendorName", "distributionCenter",
                        "createDateTime", "setOrderDateTme", "setExpectedDeliveryDate",
                        "setExpectedDeliveryDOW", "submittedDateTime", "transactionNo",
                        status, "submission_attempts", "last_attempt_at", "failure_reason", "alert_sent_at"
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING "autoAllocateTransID"
                    """,
                    (
                        country, state, loc_code, location_name, market,
                        body.vendor_code, vendor_name, None,
                        now_utc, set_order_utc, loc_expected_date,
                        expected_dow, submitted_dt, trans_no,
                        status_val, submission_attempts_val, last_attempt_at_val, None, None,
                    ),
                )
                row = cur.fetchone()
                hdr_id = row[0] if row else None
                if hdr_id:
                    for li in valid_lines_loc:
                        cur.execute(
                            """
                            INSERT INTO "CTH"."autoAllocationTransDtl" (
                                "autoAllocateTransID", "productNumber", "productName",
                                "vendorUnit", "orderQuantity", "vendorProductNumber"
                            ) VALUES (%s, %s, %s, %s, %s, %s)
                            """,
                            (hdr_id, None if not li.product_number else li.product_number, li.product_name, li.vendor_unit or "", li.qty, li.vendor_product_number or ""),
                        )
            conn.commit()
            cur.close()
            conn.close()
        except Exception as db_err:
            # Log but do not fail the request; Crunchtime already succeeded
            pass

    total_lines = sum(len(v) for v in per_location_valid_lines)
    if submit_immediately:
        message = "Order submitted successfully." + (f" Order number(s): {', '.join(order_numbers)}" if order_numbers else "")
    else:
        message = f"Order scheduled for {body.order_date_time} (Sydney). It will be sent to the vendor at that time."
    return PurchaseOrderSubmitResponse(
        success=True,
        message=message,
        order_date_time=body.order_date_time,
        expected_delivery_date=body.expected_delivery_date,
        location_count=len(body.location_codes),
        line_count=total_lines,
    )


@router.get("/transactions/filter-options")
def get_transactions_filter_options():
    """
    Return distinct values for State, Market, Vendor, Location for use in review page filters.
    """
    conn = _get_pg_connection()
    if not conn:
        return {"states": [], "markets": [], "vendors": [], "locations": []}
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT DISTINCT state FROM "CTH"."autoAllocationTransHdr" WHERE state IS NOT NULL AND state != '' ORDER BY state
            """
        )
        states = [r[0] for r in cur.fetchall()]
        cur.execute(
            """
            SELECT DISTINCT market FROM "CTH"."autoAllocationTransHdr" WHERE market IS NOT NULL AND market != '' ORDER BY market
            """
        )
        markets = [r[0] for r in cur.fetchall()]
        cur.execute(
            """
            SELECT DISTINCT "vendorName" FROM "CTH"."autoAllocationTransHdr" WHERE "vendorName" IS NOT NULL AND "vendorName" != '' ORDER BY "vendorName"
            """
        )
        vendors = [r[0] for r in cur.fetchall()]
        cur.execute(
            """
            SELECT DISTINCT "locationCode" FROM "CTH"."autoAllocationTransHdr" WHERE "locationCode" IS NOT NULL AND "locationCode" != '' ORDER BY "locationCode"
            """
        )
        locations = [r[0] for r in cur.fetchall()]
        cur.close()
        conn.close()
        return {"states": states, "markets": markets, "vendors": vendors, "locations": locations}
    except Exception as e:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        raise HTTPException(status_code=500, detail=f"Failed to load filter options: {e!s}")


@router.get("/transactions/{transaction_id:int}/details")
def get_transaction_details(transaction_id: int):
    """
    Return product line details (autoAllocationTransDtl) for a given transaction header id.
    """
    conn = _get_pg_connection()
    if not conn:
        return {"data": []}
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT "productNumber", "productName", "vendorUnit", "orderQuantity"
            FROM "CTH"."autoAllocationTransDtl"
            WHERE "autoAllocateTransID" = %s
            ORDER BY "autoAllocateItmTransID"
            """,
            (transaction_id,),
        )
        rows = cur.fetchall()
        colnames = [d[0] for d in cur.description]
        cur.close()
        conn.close()
        data = [dict(zip(colnames, row)) for row in rows]
        return {"data": data}
    except Exception as e:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        raise HTTPException(status_code=500, detail=f"Failed to load transaction details: {e!s}")


@router.get("/transactions")
def get_transactions(
    limit: int = Query(100, ge=1, le=500, description="Max rows to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    state: str | None = Query(None, description="Filter by state"),
    market: str | None = Query(None, description="Filter by market"),
    vendor_name: str | None = Query(None, alias="vendor", description="Filter by vendor name"),
    location_code: str | None = Query(None, alias="location", description="Filter by location code"),
    from_date: str | None = Query(None, description="Filter expected delivery from (YYYY-MM-DD)"),
    to_date: str | None = Query(None, description="Filter expected delivery to (YYYY-MM-DD)"),
    po_number: str | None = Query(None, alias="po", description="Filter by PO number (partial match)"),
    not_submitted: bool = Query(False, description="If true, only return orders not yet submitted (status != 'SUBMITTED')"),
):
    """
    List Auto Allocation transactions from PostgreSQL (CTH.autoAllocationTransHdr).
    Default: last 100 rows ordered by primary key desc. Optional filters.
    Returns one row per transaction with timestamps in ISO UTC (front end converts to local).
    """
    conn = _get_pg_connection()
    if not conn:
        return {"data": []}
    try:
        cur = conn.cursor()
        sql = """
            SELECT
                "autoAllocateTransID",
                state,
                market,
                "vendorName",
                "distributionCenter",
                "locationCode",
                "locationName",
                "setExpectedDeliveryDate",
                "setExpectedDeliveryDOW",
                "setOrderDateTme",
                "submittedDateTime",
                "transactionNo",
                "confirmReceivedStatus",
                status,
                "alert_sent_at"
            FROM "CTH"."autoAllocationTransHdr"
            WHERE 1=1
        """
        params = []
        if state and state.strip():
            params.append(state.strip())
            sql += " AND state = %s"
        if market and market.strip():
            params.append(market.strip())
            sql += " AND market = %s"
        if vendor_name and vendor_name.strip():
            params.append(vendor_name.strip())
            sql += " AND \"vendorName\" = %s"
        if location_code and location_code.strip():
            params.append(location_code.strip())
            sql += " AND \"locationCode\" = %s"
        if from_date and from_date.strip():
            params.append(from_date.strip())
            sql += " AND \"setExpectedDeliveryDate\" >= %s"
        if to_date and to_date.strip():
            params.append(to_date.strip())
            sql += " AND \"setExpectedDeliveryDate\" <= %s"
        if po_number and po_number.strip():
            params.append(f"%{po_number.strip()}%")
            sql += " AND \"transactionNo\" ILIKE %s"
        if not_submitted:
            sql += " AND status != 'SUBMITTED'"
        sql += " ORDER BY (CASE WHEN status = 'SUBMITTED' THEN 1 ELSE 0 END), \"transactionNo\" DESC NULLS LAST, \"setOrderDateTme\" DESC NULLS LAST LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        cur.execute(sql, params)
        rows = cur.fetchall()
        colnames = [d[0] for d in cur.description]
        data = []
        for row in rows:
            rec = dict(zip(colnames, row))
            for key in ("setExpectedDeliveryDate", "setOrderDateTme", "submittedDateTime", "alert_sent_at"):
                if key in rec and rec[key] is not None:
                    v = rec[key]
                    if hasattr(v, "isoformat"):
                        rec[key] = v.isoformat()
                    else:
                        rec[key] = str(v)
            data.append(rec)
        cur.close()
        conn.close()
        return {"data": data}
    except Exception as e:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        raise HTTPException(status_code=500, detail=f"Failed to load transactions: {e!s}")
