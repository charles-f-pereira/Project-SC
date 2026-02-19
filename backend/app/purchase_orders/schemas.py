from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class LocationDetail(BaseModel):
    """Per-location data for recording in the transaction (not sent to Crunchtime)."""
    location_code: str = Field(..., description="Location code")
    location_name: Optional[str] = Field(None, description="Location display name")
    country: Optional[str] = Field(None, description="Country for this location")
    state: Optional[str] = Field(None, description="State for this location")
    market: Optional[str] = Field(None, description="Market for this location")


class PurchaseOrderLineItem(BaseModel):
    """Single line item for a purchase order."""
    product_name: str = Field(..., description="Product display name")
    product_number: Optional[str] = Field(None, description="Company product number (e.g. P-10003)")
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
    location_details: Optional[List[LocationDetail]] = Field(
        None,
        description="Per-location Country, State, LocationName, Market for recording (same order as location_codes)"
    )
    vendor_code: str = Field(..., description="Vendor code for the order")
    vendor_name: Optional[str] = Field(None, description="Vendor display name for recording")
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
