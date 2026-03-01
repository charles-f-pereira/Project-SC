from pydantic import BaseModel, Field
from typing import Any, List

# Crunchtime response structure may vary; we pass through the API response.
# Phase 1: no strict schema; later we can define CompanyProductEnhanced if needed.


class CatalogueFilterOptionsResponse(BaseModel):
    """Distinct category, subcategory, microcategory for filter dropdowns (from CTH.CompanyProduct)."""

    category_names: List[str] = Field(default_factory=list)
    subcategory_names: List[str] = Field(default_factory=list)
    microcategory_names: List[str] = Field(default_factory=list)


class CatalogueProductItem(BaseModel):
    """Single product from CTH.CompanyProduct for catalogue filter results."""

    id: int
    number: str
    name: str | None = None
    category_name: str | None = None
    subcategory_name: str | None = None
    microcategory_name: str | None = None


class CatalogueResponse(BaseModel):
    """Products from PostgreSQL (CTH.CompanyProduct) matching filters."""

    data: List[CatalogueProductItem] = Field(default_factory=list)
    count: int = 0


class VendorProductPricingBatchRequest(BaseModel):
    """Request body for batch vendor product pricing (one CT call per product, max 10)."""

    effective_date: str = Field(..., description="Effective date mm/dd/yyyy")
    market: str = Field(..., description="Market code")
    vendor: str = Field(..., description="Vendor name or code")
    product_numbers: List[str] = Field(
        ...,
        min_length=1,
        max_length=10,
        description="Company product numbers (1–10); one getAllVendorProductPricing call per product",
    )


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
