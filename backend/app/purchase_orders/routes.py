import asyncio
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
from fastapi import APIRouter, HTTPException, Query

from app.core.config import (
    PG_DATABASE,
    PG_HOST,
    PG_NAME,
    PG_PASSWORD,
    PG_PORT,
)
from app.core.crunchtime_api import ct_headers, get_async_client, service_token
from app.purchase_orders.location_product_pricing import (
    save_location_product_pricing_sync,
)
from app.purchase_orders.schemas import (
    PurchaseOrderSubmitRequest,
    PurchaseOrderSubmitResponse,
)

logger = logging.getLogger(__name__)

# Delay between saveLocationProductPricing (activate) and savePurchaseOrders (seconds)
VO_ACTIVATE_DELAY_SECONDS = 3

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
GET_ALL_VENDOR_LOCATION_PATH = "/vendorlocation/v1/getAllVendorLocation"
CT_VENDOR_LOCATION_FIXED_PARAMS = {
    "activeFlag": "true",
    "includeDetails": "true",
    "includeNull": "false",
}
# Trigger time within this many minutes of now (user's local time) is treated as "submit now" (user has time to review)
IMMEDIATE_WINDOW_MINUTES = 5
MAX_SCHEDULE_DAYS = 14
# Allow order time up to this many seconds in the past (user's local) so "NOW" rounded to the minute still validates after a short delay
ORDER_TIME_TOLERANCE_SECONDS = 600

DEFAULT_ORDER_TZ = "Australia/Sydney"


def _normalize_vendor_location_response(data) -> list:
    """Extract list of vendor-location items from Crunchtime getAllVendorLocation response."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in (
            "data",
            "vendorLocations",
            "VendorLocations",
            "locations",
            "Locations",
        ):
            val = data.get(key)
            if isinstance(val, list):
                return val
        return [data]
    return []


async def _fetch_account_number_for_location(
    location_code: str, vendor_code: str
) -> str | None:
    """
    Call Crunchtime getAllVendorLocation for location_code and return accountNumber
    for the vendor matching vendor_code (from vendorLocationTransmissionDetail.accountNumber).
    Returns None if not found or on error.
    """
    if not (location_code and location_code.strip()) or not (
        vendor_code and vendor_code.strip()
    ):
        return None
    params = dict(CT_VENDOR_LOCATION_FIXED_PARAMS)
    params["locationCode"] = location_code.strip()
    headers = {
        **ct_headers(token_override=service_token("vendorlocation")),
        "accept": "application/json",
    }
    try:
        async with get_async_client() as client:
            resp = await client.get(
                GET_ALL_VENDOR_LOCATION_PATH,
                params=params,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        return None
    items = _normalize_vendor_location_response(data)
    want = (vendor_code or "").strip()
    for raw in items:
        if not isinstance(raw, dict):
            continue
        header = (
            raw.get("vendorLocationHeaderDetails")
            or raw.get("VendorLocationHeaderDetails")
            or {}
        )
        vc = (
            header.get("vendorCode")
            or header.get("VendorCode")
            or raw.get("vendorCode")
            or raw.get("VendorCode")
            or ""
        )
        if (vc or "").strip() != want:
            continue
        trans = (
            raw.get("vendorLocationTransmissionDetail")
            or raw.get("VendorLocationTransmissionDetail")
            or {}
        )
        acc = trans.get("accountNumber") or trans.get("AccountNumber")
        if acc is not None and str(acc).strip():
            return str(acc).strip()
        return None
    return None


def _get_zone(tz_name: str | None):
    """Return ZoneInfo for tz_name, or None if unavailable/invalid."""
    name = (tz_name or DEFAULT_ORDER_TZ or "").strip()
    if not name:
        return None
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, Exception):
        return None


def _parse_order_datetime_local(value: str, tz_name: str | None) -> datetime | None:
    """Parse order_date_time as local time in the given IANA timezone. Accepts YYYY-MM-DDTHH:mm or YYYY-MM-DDTHH:mm:ss."""
    zi = _get_zone(tz_name)
    if zi is None:
        return None
    value = (value or "").strip()
    if not value:
        return None
    for fmt in (
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
    ):
        try:
            dt = datetime.strptime(value, fmt)
            return dt.replace(tzinfo=zi)
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

    Order date/time is interpreted as the user's local time (via order_date_time_zone)
    and must be current or future. Stored in UTC for trigger. Accepts order date/time,
    expected delivery date, location codes, vendor code, and line items.
    """
    tz_name = (body.order_date_time_zone or "").strip() or DEFAULT_ORDER_TZ
    user_tz = _get_zone(tz_name)
    if user_tz is None:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid order_date_time_zone: {tz_name!r}. Use an IANA timezone name (e.g. Australia/Sydney).",
        )
    # Order date/time: user's local time (tz from order_date_time_zone); must be now or future, up to 14 days ahead. Stored as UTC.
    order_dt = _parse_order_datetime_local(body.order_date_time, tz_name)
    if not order_dt:
        raise HTTPException(
            status_code=400,
            detail="Invalid order_date_time format. Use YYYY-MM-DDTHH:mm or YYYY-MM-DDTHH:mm:ss (in your local timezone).",
        )
    now_local = datetime.now(user_tz)  # type: ignore[arg-type]
    # Allow up to ORDER_TIME_TOLERANCE_SECONDS in the past so "NOW" (rounded to the minute) still validates after submit delay
    min_order_time = now_local - timedelta(seconds=ORDER_TIME_TOLERANCE_SECONDS)
    if order_dt < min_order_time:
        raise HTTPException(
            status_code=400,
            detail="Order date and time must be current or future (in your local timezone).",
        )

    max_schedule = now_local + timedelta(days=MAX_SCHEDULE_DAYS)
    if order_dt > max_schedule:
        raise HTTPException(
            status_code=400,
            detail=f"Order date and time cannot be more than {MAX_SCHEDULE_DAYS} days in the future (in your local timezone).",
        )
    # Within immediate window → submit now (trigger time recorded as actual submit time)
    immediate_threshold = now_local + timedelta(minutes=IMMEDIATE_WINDOW_MINUTES)
    submit_immediately = order_dt <= immediate_threshold

    # Expected delivery date must be on or after order date, and today or future (in user's local date)
    order_date_local = order_dt.date()
    today_local = now_local.date()

    expected_delivery = (body.expected_delivery_date or "").strip()
    if not expected_delivery:
        raise HTTPException(
            status_code=400, detail="Expected delivery date is required."
        )
    try:
        delivery_date = datetime.strptime(expected_delivery, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Expected delivery date must be YYYY-MM-DD.",
        )
    if delivery_date < order_date_local:
        raise HTTPException(
            status_code=400,
            detail="Expected delivery date cannot be before the order date & time.",
        )
    if delivery_date < today_local:
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
                raise HTTPException(
                    status_code=400,
                    detail=f"Expected delivery date required for location index {i}.",
                )
            try:
                d = datetime.strptime(ed, "%Y-%m-%d").date()
                if d < order_date_local:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Expected delivery date for location index {i} cannot be before the order date & time.",
                    )
                if d < today_local:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Expected delivery date for location index {i} must be today or future.",
                    )
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Expected delivery date for location index {i} must be YYYY-MM-DD.",
                )

    # Per-location order date/times (optional): when provided, each location gets its own trigger time
    per_location_order_utc = None
    order_date_times_list = body.order_date_times
    if order_date_times_list is not None:
        if len(order_date_times_list) != len(body.location_codes):
            raise HTTPException(
                status_code=400,
                detail="order_date_times length must match location_codes.",
            )
        per_location_order_utc = []
        for i, odt_str in enumerate(order_date_times_list):
            odt_str = (odt_str or "").strip()
            if not odt_str:
                raise HTTPException(
                    status_code=400,
                    detail=f"Order date/time required for location index {i}.",
                )
            loc_dt = _parse_order_datetime_local(odt_str, tz_name)
            if not loc_dt:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid order_date_times[{i}] format. Use YYYY-MM-DDTHH:mm (in your local timezone).",
                )
            if loc_dt < min_order_time:
                raise HTTPException(
                    status_code=400,
                    detail=f"Order date/time for location index {i} must be current or future (in your local timezone).",
                )
            if loc_dt > max_schedule:
                raise HTTPException(
                    status_code=400,
                    detail=f"Order date/time for location index {i} cannot be more than {MAX_SCHEDULE_DAYS} days in the future.",
                )
            per_location_order_utc.append(loc_dt.astimezone(timezone.utc))

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
                raise HTTPException(
                    status_code=400,
                    detail=f"At least one line item with qty > 0 required for location index {i}.",
                )

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
            loc_expected = (
                expected_delivery_dates_list[i] or ""
            ).strip() or expected_delivery
        else:
            loc_expected = expected_delivery
        ct_expected_date = _expected_delivery_date_to_ct_format(loc_expected)
        detail_rows = [
            {
                "orderQuantity": li.qty,
                "vendorProductNumber": li.vendor_product_number,
                "vendorUnit": li.vendor_unit or "",
            }
            for li in valid_lines
        ]
        payloads.append(
            {
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
            }
        )
        per_location_valid_lines.append(valid_lines)
        per_location_expected_dates.append(loc_expected)

    order_numbers = []
    now_utc = datetime.now(timezone.utc)
    if submit_immediately:
        # Activate VO for products with temp_activate_vo (one call per location with such products)
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
            raise HTTPException(
                status_code=502,
                detail=f"Crunchtime request failed: {e!s}",
            )

        for i, r in enumerate(results):
            loc_code = body.location_codes[i]

            # Narrow type for Pyright: gather(return_exceptions=True) can return BaseException
            if isinstance(r, BaseException):
                raise HTTPException(
                    status_code=502,
                    detail=f"Crunchtime request failed for location {loc_code}: {r!s}",
                )

            # From here, r is an httpx.Response
            if r.status_code != 200:
                detail = (
                    f"Crunchtime savePurchaseOrders failed for location {loc_code}."
                )
                if r.text:
                    detail = f"{detail} {r.text[:500]}"
                raise HTTPException(status_code=502, detail=detail)

            try:
                data = r.json()
                if (
                    isinstance(data, list)
                    and len(data) > 0
                    and isinstance(data[0], dict)
                    and "orderNumber" in data[0]
                ):
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

        # Deactivate VO for products that were temporarily activated (after PO success)
        for loc_code, product_numbers in locations_to_activate:
            await asyncio.to_thread(
                save_location_product_pricing_sync,
                loc_code,
                product_numbers,
                "N",
            )

    # For immediate: trigger time recorded as actual submit time (UTC). For scheduled: use user-selected time (UTC).
    if submit_immediately:
        set_order_utc = now_utc
    else:
        set_order_utc = order_dt.astimezone(timezone.utc)

    # Persist to CTH for both immediate and scheduled orders so ALL purchase orders can be reviewed.
    # Immediate ("Now"): status SUBMITTED, submittedDateTime and transactionNo from Crunchtime response.
    # Scheduled: status SCHEDULED; scheduler will submit at trigger time and update the row.
    # If persist fails or is skipped, we return an error so the frontend shows it.
    location_details_list = body.location_details or []
    if not (PG_NAME and PG_PASSWORD):
        logger.warning(
            "Cannot persist to CTH: pgName or pgPassword not set in env. "
            "Set pgName and pgPassword (and pgHost, pgDatabase) in .env or .env.production."
        )
        raise HTTPException(
            status_code=503,
            detail=(
                "Database is not configured. Orders cannot be saved or shown on the Review page. "
                "Set pgName and pgPassword (and pgHost, pgDatabase) in backend .env."
            ),
        )
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
            trans_no = (
                order_numbers[i]
                if i < len(order_numbers)
                else (order_numbers[0] if order_numbers else None)
            )
            loc_detail = (
                location_details_list[i] if i < len(location_details_list) else None
            )
            country = loc_detail.country if loc_detail else None
            state = loc_detail.state if loc_detail else None
            location_name = loc_detail.location_name if loc_detail else None
            market = loc_detail.market if loc_detail else None
            vendor_name = body.vendor_name
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
            # Use per-location order time when provided and scheduled; else single set_order_utc
            loc_set_order_utc = (
                per_location_order_utc[i]
                if not submit_immediately
                and per_location_order_utc is not None
                and i < len(per_location_order_utc)
                else set_order_utc
            )
            account_number = await _fetch_account_number_for_location(
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
                    status, "submission_attempts", "last_attempt_at", "failure_reason", "alert_sent_at"
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                    submitted_dt,
                    trans_no,
                    status_val,
                    submission_attempts_val,
                    last_attempt_at_val,
                    None,
                    None,
                ),
            )
            row = cur.fetchone()
            hdr_id = row[0] if row else None
            if hdr_id:
                for li in valid_lines_loc:
                    temp_vo = "Y" if getattr(li, "temp_activate_vo", False) else "N"
                    cur.execute(
                        """
                        INSERT INTO "CTH"."autoAllocationTransDtl" (
                            "autoAllocateTransID", "productNumber", "productName",
                            "vendorUnit", "orderQuantity", "vendorProductNumber", "TempActivateVO"
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            hdr_id,
                            None if not li.product_number else li.product_number,
                            li.product_name,
                            li.vendor_unit or "",
                            li.qty,
                            li.vendor_product_number or "",
                            temp_vo,
                        ),
                    )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logger.exception(
            "Failed to persist order to CTH: %s",
            e,
        )
        raise HTTPException(
            status_code=500,
            detail=(
                f"Order could not be saved to the database: {e!s}. "
                "Check backend logs. Ensure CTH.autoAllocationTransHdr exists (run backend/sql/cth_auto_allocation_tables.sql and add_auto_allocation_account_number.sql)."
            ),
        )

    total_lines = sum(len(v) for v in per_location_valid_lines)
    if submit_immediately:
        message = "Order submitted successfully." + (
            f" Order number(s): {', '.join(order_numbers)}" if order_numbers else ""
        )
    else:
        message = f"Order scheduled for {body.order_date_time} (your local time). It will be sent to the vendor at that time."
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
        return {
            "states": states,
            "markets": markets,
            "vendors": vendors,
            "locations": locations,
        }
    except Exception as e:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        raise HTTPException(
            status_code=500, detail=f"Failed to load filter options: {e!s}"
        )


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

        description = cur.description
        if description is None:
            raise HTTPException(
                status_code=500,
                detail="No column metadata returned",
            )

        colnames = [d[0] for d in description]

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
        raise HTTPException(
            status_code=500, detail=f"Failed to load transaction details: {e!s}"
        )


@router.get("/transactions")
def get_transactions(
    limit: int = Query(100, ge=1, le=500, description="Max rows to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    state: str | None = Query(None, description="Filter by state"),
    market: str | None = Query(None, description="Filter by market"),
    vendor_name: str | None = Query(
        None, alias="vendor", description="Filter by vendor name"
    ),
    location_code: str | None = Query(
        None, alias="location", description="Filter by location code"
    ),
    from_date: str | None = Query(
        None, description="Filter expected delivery from (YYYY-MM-DD)"
    ),
    to_date: str | None = Query(
        None, description="Filter expected delivery to (YYYY-MM-DD)"
    ),
    po_number: str | None = Query(
        None, alias="po", description="Filter by PO number (partial match)"
    ),
    not_submitted: bool = Query(
        False,
        description="If true, only return orders not yet submitted (status != 'SUBMITTED')",
    ),
):
    """
    List Auto Allocation transactions from PostgreSQL (CTH.autoAllocationTransHdr).
    Default: last 100 rows ordered by primary key desc. Optional filters.
    Returns one row per transaction with timestamps in ISO UTC (front end converts to local).
    """
    conn = _get_pg_connection()
    if not conn:
        logger.warning(
            "GET /transactions: no database connection (pgName/pgPassword not set?). "
            "Review page will show no transactions."
        )
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
                "accountNumber",
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
            sql += ' AND "vendorName" = %s'
        if location_code and location_code.strip():
            params.append(location_code.strip())
            sql += ' AND "locationCode" = %s'
        if from_date and from_date.strip():
            params.append(from_date.strip())
            sql += ' AND "setExpectedDeliveryDate" >= %s'
        if to_date and to_date.strip():
            params.append(to_date.strip())
            sql += ' AND "setExpectedDeliveryDate" <= %s'
        if po_number and po_number.strip():
            params.append(f"%{po_number.strip()}%")
            sql += ' AND "transactionNo" ILIKE %s'
        if not_submitted:
            sql += " AND status != 'SUBMITTED'"
        sql += ' ORDER BY (CASE WHEN status = \'SUBMITTED\' THEN 1 ELSE 0 END), "transactionNo" DESC NULLS LAST, "setOrderDateTme" DESC NULLS LAST LIMIT %s OFFSET %s'
        params.extend([limit, offset])
        cur.execute(sql, params)
        rows = cur.fetchall()

        description = cur.description
        if description is None:
            raise HTTPException(
                status_code=500,
                detail="No column metadata returned",
            )

        colnames = [d[0] for d in description]
        data = []
        for row in rows:
            rec = dict(zip(colnames, row))
            for key in (
                "setExpectedDeliveryDate",
                "setOrderDateTme",
                "submittedDateTime",
                "alert_sent_at",
            ):
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
        logger.exception("GET /transactions failed: %s", e)
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        # If table/relation doesn't exist yet, return empty so Review page still loads
        if "does not exist" in str(e).lower() or "relation" in str(e).lower():
            return {"data": []}
        raise HTTPException(
            status_code=500, detail=f"Failed to load transactions: {e!s}"
        )
