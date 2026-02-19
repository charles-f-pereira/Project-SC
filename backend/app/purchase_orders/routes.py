import asyncio
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
from fastapi import APIRouter, HTTPException

from app.core.config import BASE_URL, PG_DATABASE, PG_HOST, PG_NAME, PG_PASSWORD, PG_PORT
from app.core.crunchtime_api import ct_headers, get_async_client, service_token
from app.purchase_orders.schemas import (
    PurchaseOrderSubmitRequest,
    PurchaseOrderSubmitResponse,
)

router = APIRouter()

SAVE_PURCHASE_ORDERS_PATH = "/purchaseorder/v1/savePurchaseOrders"

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
    # Order date/time must be current or future
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

    # Expected delivery date must be today or future (Sydney date)
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
    today_sydney = now_sydney.date()
    if delivery_date < today_sydney:
        raise HTTPException(
            status_code=400,
            detail="Expected delivery date must be today or in the future.",
        )

    # Validate that at least one line has qty > 0
    valid_lines = [li for li in body.line_items if li.qty > 0]
    if not valid_lines:
        raise HTTPException(
            status_code=400,
            detail="At least one line item must have quantity greater than 0.",
        )

    ct_expected_date = _expected_delivery_date_to_ct_format(body.expected_delivery_date)
    detail_rows = [
        {
            "orderQuantity": li.qty,
            "vendorProductNumber": li.vendor_product_number,
            "vendorUnit": li.vendor_unit or "",
        }
        for li in valid_lines
    ]

    # Crunchtime allows max 1 purchase order per savePurchaseOrders call; one payload per location.
    payloads = []
    for loc_code in body.location_codes:
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

    token = service_token("purchaseorder")
    headers = {
        **ct_headers(token_override=token),
        "accept": "application/json",
        "content-type": "application/json",
    }

    # One call per location, concurrently
    order_numbers = []
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

    now_utc = datetime.now(timezone.utc)
    order_dt_sydney = _parse_order_datetime_sydney(body.order_date_time)
    set_order_utc = order_dt_sydney.astimezone(timezone.utc) if order_dt_sydney else now_utc
    expected_dow = _day_of_week_abbrev(body.expected_delivery_date)

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
            for i, loc_code in enumerate(body.location_codes):
                trans_no = order_numbers[i] if i < len(order_numbers) else (order_numbers[0] if order_numbers else None)
                loc_detail = location_details_list[i] if i < len(location_details_list) else None
                country = loc_detail.country if loc_detail else None
                state = loc_detail.state if loc_detail else None
                location_name = loc_detail.location_name if loc_detail else None
                market = loc_detail.market if loc_detail else None
                vendor_name = body.vendor_name
                cur.execute(
                    """
                    INSERT INTO "CTH"."autoAllocationTransHdr" (
                        country, state, "locationCode", "locationName", market,
                        "vendorCode", "vendorName", "distributionCenter",
                        "createDateTime", "setOrderDateTme", "setExpectedDeliveryDate",
                        "setExpectedDeliveryDOW", "submittedDateTime", "transactionNo"
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING "autoAllocateTransID"
                    """,
                    (
                        country, state, loc_code, location_name, market,
                        body.vendor_code, vendor_name, None,
                        now_utc, set_order_utc, body.expected_delivery_date,
                        expected_dow, now_utc, trans_no,
                    ),
                )
                row = cur.fetchone()
                hdr_id = row[0] if row else None
                if hdr_id:
                    for li in valid_lines:
                        cur.execute(
                            """
                            INSERT INTO "CTH"."autoAllocationTransDtl" (
                                "autoAllocateTransID", "productNumber", "productName",
                                "vendorUnit", "orderQuantity"
                            ) VALUES (%s, %s, %s, %s, %s)
                            """,
                            (hdr_id, None if not li.product_number else li.product_number, li.product_name, li.vendor_unit or "", li.qty),
                        )
            conn.commit()
            cur.close()
            conn.close()
        except Exception as db_err:
            # Log but do not fail the request; Crunchtime already succeeded
            pass

    return PurchaseOrderSubmitResponse(
        success=True,
        message="Order submitted successfully." + (f" Order number(s): {', '.join(order_numbers)}" if order_numbers else ""),
        order_date_time=body.order_date_time,
        expected_delivery_date=body.expected_delivery_date,
        location_count=len(body.location_codes),
        line_count=len(valid_lines),
    )
