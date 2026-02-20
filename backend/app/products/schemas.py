from pydantic import BaseModel
from typing import Any, List

# Crunchtime response structure may vary; we pass through the API response.
# Phase 1: no strict schema; later we can define CompanyProductEnhanced if needed.


class CompanyProductsResponse(BaseModel):
    """Response from GET company products enhanced (Crunchtime passthrough)."""

    source: str = "crunchtime"
    service: str = "getAllCompanyProductsEnhanced"
    data: List[Any] = []
    count: int = 0


class VendorProductPricingResponse(BaseModel):
    """Response from GET vendor product pricing (Crunchtime passthrough)."""

    source: str = "crunchtime"
    service: str = "getAllVendorProductPricing"
    data: List[Any] = []
    count: int = 0
