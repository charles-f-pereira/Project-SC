from pydantic import BaseModel, Field
from typing import List
from datetime import datetime


class PurchaseOrderLineItem(BaseModel):
    """Single line item for a purchase order."""
    product_name: str = Field(..., description="Product display name")
    vendor_product_number: str = Field(..., description="Vendor product number (unique per location/vendor)")
    vendor_unit: str = Field(default="", description="Unit of measure for the product")
    qty: int = Field(..., ge=0, description="Quantity to order")


class PurchaseOrderSubmitRequest(BaseModel):
    """Request body for scheduling/submitting a purchase order."""
    order_date_time: str = Field(
        ...,
        description="Order date and time (ISO 8601 or YYYY-MM-DDTHH:mm) when the order is to be placed/scheduled"
    )
    expected_delivery_date: str = Field(
        ...,
        description="Expected delivery date (YYYY-MM-DD) by when products should be delivered"
    )
    location_codes: List[str] = Field(
        ...,
        min_length=1,
        description="Location codes to which the order applies"
    )
    vendor_code: str = Field(..., description="Vendor code for the order")
    line_items: List[PurchaseOrderLineItem] = Field(
        ...,
        min_length=1,
        max_length=10,
        description="Products and quantities to order (max 10 lines)"
    )


class PurchaseOrderSubmitResponse(BaseModel):
    """Response after submitting or scheduling a purchase order."""
    success: bool
    message: str
    order_date_time: str | None = None
    expected_delivery_date: str | None = None
    location_count: int = 0
    line_count: int = 0
    # When Crunchtime savePurchaseOrders is integrated, add e.g. reference_number, ct_response, etc.
