from fastapi import APIRouter, HTTPException, Query
from app.core.crunchtime_api import ct_headers, service_token, get_async_client
from .schemas import CompanyProductsResponse, VendorProductPricingResponse

router = APIRouter()

# Crunchtime getAllCompanyProductsEnhanced (companyproduct/v1) – kept for later phases
GET_ALL_COMPANY_PRODUCTS_ENHANCED_PATH = "/companyproduct/v1/getAllCompanyProductsEnhanced"

# Crunchtime getAllVendorProductPricing (vendorproductpricing/v1) – Phase 1 product catalogue
GET_ALL_VENDOR_PRODUCT_PRICING_PATH = "/vendorproductpricing/v1/getAllVendorProductPricing"


def _normalize_company_products_response(data) -> list:
    """Extract list of products from Crunchtime response (may be wrapped)."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("data", "companyProducts", "CompanyProducts", "products", "Products"):
            val = data.get(key)
            if isinstance(val, list):
                return val
        return [data]
    return []


@router.get("/company-products-enhanced", response_model=CompanyProductsResponse)
async def get_company_products_enhanced(
    product_number: str | None = Query(None, description="Filter by product number (e.g. P-10003)"),
    product_name: str | None = Query(None, description="Filter by product name (e.g. Meat - Chicken Maryland)"),
    active_flag: bool = Query(True, description="Only active items"),
    include_details: bool = Query(False, description="Keep payload tidy; set false to exclude detail bloat"),
    include_null: bool = Query(False, description="Exclude NULL values"),
):
    """
    Fetch company products from Crunchtime getAllCompanyProductsEnhanced.

    Phase 1: caller must provide at least one of product_number or product_name.
    Only active items are returned (activeFlag=true). includeDetails=false and
    includeNull=false keep the payload tidy. Later: filter by category/subcategory
    /microcategory/concept.
    """
    if not product_number and not product_name:
        raise HTTPException(
            status_code=400,
            detail="Provide at least one of product_number or product_name.",
        )

    params = {
        "activeFlag": "true" if active_flag else "false",
        "includeDetails": "true" if include_details else "false",
        "includeNull": "true" if include_null else "false",
    }
    if product_number:
        params["productNumber"] = product_number.strip()
    if product_name:
        params["productName"] = product_name.strip()

    token = service_token("companyproduct")
    headers = {**ct_headers(token_override=token), "accept": "application/json"}

    async with get_async_client() as client:
        resp = await client.get(
            GET_ALL_COMPANY_PRODUCTS_ENHANCED_PATH,
            params=params,
            headers=headers,
        )
        resp.raise_for_status()
        raw = resp.json()

    items = _normalize_company_products_response(raw)
    return CompanyProductsResponse(
        source="crunchtime",
        service="getAllCompanyProductsEnhanced",
        data=items,
        count=len(items),
    )


def _normalize_vendor_pricing_response(data) -> list:
    """Crunchtime getAllVendorProductPricing returns an array; accept list or wrapped dict."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("data", "vendorProductPricing", "VendorProductPricing", "products", "Products"):
            val = data.get(key)
            if isinstance(val, list):
                return val
        return [data]
    return []


@router.get("/vendor-product-pricing", response_model=VendorProductPricingResponse)
async def get_vendor_product_pricing(
    effective_date: str = Query(..., description="Effective date for pricing (mm/dd/yyyy)"),
    market: str = Query(..., description="Market code (e.g. NSW)"),
    vendor: str = Query(..., description="Vendor name or code (e.g. Baiada)"),
    product_number: str | None = Query(None, description="Filter by product number"),
    product_name: str | None = Query(None, description="Filter by product name"),
):
    """
    Fetch vendor product pricing from Crunchtime getAllVendorProductPricing.
    Phase 1: caller must provide effective_date, market, vendor, and at least one of product_number or product_name.
    Only active products are returned (activeProductFlag=Y).
    """
    if not product_number and not product_name:
        raise HTTPException(
            status_code=400,
            detail="Provide at least one of product_number or product_name.",
        )

    params = {
        "activeProductFlag": "Y",
        "effectiveDate": effective_date.strip(),
        "market": market.strip(),
        "vendor": vendor.strip(),
    }
    if product_number:
        params["productNumber"] = product_number.strip()
    if product_name:
        params["productName"] = product_name.strip()

    token = service_token("vendorproductpricing")
    headers = {**ct_headers(token_override=token), "accept": "*/*"}

    async with get_async_client() as client:
        resp = await client.get(
            GET_ALL_VENDOR_PRODUCT_PRICING_PATH,
            params=params,
            headers=headers,
        )
        resp.raise_for_status()
        raw = resp.json()

    items = _normalize_vendor_pricing_response(raw)
    return VendorProductPricingResponse(
        source="crunchtime",
        service="getAllVendorProductPricing",
        data=items,
        count=len(items),
    )
