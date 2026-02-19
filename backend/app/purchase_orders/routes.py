from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, HTTPException
from app.purchase_orders.schemas import (
    PurchaseOrderSubmitRequest,
    PurchaseOrderSubmitResponse,
)

router = APIRouter()

try:
    SYDNEY_TZ = ZoneInfo("Australia/Sydney")
except ZoneInfoNotFoundError:
    SYDNEY_TZ = None  # Windows: install tzdata (pip install tzdata)

# Crunchtime savePurchaseOrders endpoint will be integrated here (token/path TBD)


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

    # TODO: Call Crunchtime savePurchaseOrders when endpoint/token is available
    # response = await ct_save_purchase_orders(body)

    return PurchaseOrderSubmitResponse(
        success=True,
        message="Order accepted and scheduled for submission. Crunchtime savePurchaseOrders integration pending.",
        order_date_time=body.order_date_time,
        expected_delivery_date=body.expected_delivery_date,
        location_count=len(body.location_codes),
        line_count=len(valid_lines),
    )
