import asyncio

from fastapi import APIRouter, HTTPException, Query
from app.core.config import (
    PG_DATABASE,
    PG_HOST,
    PG_NAME,
    PG_PASSWORD,
    PG_PORT,
)
from app.core.crunchtime_api import ct_headers, service_token, get_async_client
from .catalogue_sync import run_product_catalogue_sync
from .schemas import (
    CatalogueFilterOptionsResponse,
    CatalogueProductItem,
    CatalogueResponse,
    CompanyProductsResponse,
    VendorProductPricingBatchRequest,
    VendorProductPricingResponse,
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


# Crunchtime getAllCompanyProductsEnhanced (companyproduct/v1) – kept for later phases
GET_ALL_COMPANY_PRODUCTS_ENHANCED_PATH = (
    "/companyproduct/v1/getAllCompanyProductsEnhanced"
)

# Crunchtime getAllVendorProductPricing (vendorproductpricing/v1) – Phase 1 product catalogue
GET_ALL_VENDOR_PRODUCT_PRICING_PATH = (
    "/vendorproductpricing/v1/getAllVendorProductPricing"
)


def _normalize_company_products_response(data) -> list:
    """Extract list of products from Crunchtime response (may be wrapped)."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in (
            "data",
            "companyProducts",
            "CompanyProducts",
            "products",
            "Products",
        ):
            val = data.get(key)
            if isinstance(val, list):
                return val
        return [data]
    return []


@router.get("/company-products-enhanced", response_model=CompanyProductsResponse)
async def get_company_products_enhanced(
    product_number: str | None = Query(
        None, description="Filter by product number (e.g. P-10003)"
    ),
    product_name: str | None = Query(
        None, description="Filter by product name (e.g. Meat - Chicken Maryland)"
    ),
    active_flag: bool = Query(True, description="Only active items"),
    include_details: bool = Query(
        False, description="Keep payload tidy; set false to exclude detail bloat"
    ),
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
        for key in (
            "data",
            "vendorProductPricing",
            "VendorProductPricing",
            "products",
            "Products",
        ):
            val = data.get(key)
            if isinstance(val, list):
                return val
        return [data]
    return []


@router.get("/vendor-product-pricing", response_model=VendorProductPricingResponse)
async def get_vendor_product_pricing(
    effective_date: str = Query(
        ..., description="Effective date for pricing (mm/dd/yyyy)"
    ),
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


@router.get("/catalogue/filter-options", response_model=CatalogueFilterOptionsResponse)
def get_catalogue_filter_options():
    """
    Return distinct category_name, subcategory_name, microcategory_name from CTH.CompanyProduct
    for multi-select filter dropdowns.
    """
    conn = _get_pg_connection()
    if not conn:
        return CatalogueFilterOptionsResponse()

    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT DISTINCT category_name FROM "CTH"."CompanyProduct"
            WHERE category_name IS NOT NULL AND category_name != ''
            ORDER BY category_name
            """
        )
        category_names = [r[0] for r in cur.fetchall()]

        cur.execute(
            """
            SELECT DISTINCT subcategory_name FROM "CTH"."CompanyProduct"
            WHERE subcategory_name IS NOT NULL AND subcategory_name != ''
            ORDER BY subcategory_name
            """
        )
        subcategory_names = [r[0] for r in cur.fetchall()]

        cur.execute(
            """
            SELECT DISTINCT microcategory_name FROM "CTH"."CompanyProduct"
            WHERE microcategory_name IS NOT NULL AND microcategory_name != ''
            ORDER BY microcategory_name
            """
        )
        microcategory_names = [r[0] for r in cur.fetchall()]

        cur.close()
        return CatalogueFilterOptionsResponse(
            category_names=category_names,
            subcategory_names=subcategory_names,
            microcategory_names=microcategory_names,
        )
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        try:
            conn.close()
        except Exception:
            pass


@router.get("/catalogue", response_model=CatalogueResponse)
def get_catalogue_products(
    product_number: str | None = Query(
        None, description="Filter by product number (wildcard)"
    ),
    product_name: str | None = Query(
        None, description="Filter by product name (wildcard)"
    ),
    category_name: list[str] | None = Query(
        None, description="Filter by category name(s); multiple allowed"
    ),
    subcategory_name: list[str] | None = Query(
        None, description="Filter by subcategory name(s); multiple allowed"
    ),
    microcategory_name: list[str] | None = Query(
        None, description="Filter by microcategory name(s); multiple allowed"
    ),
    limit: int = Query(2000, ge=1, le=10000, description="Max rows to return"),
):
    """
    Search CTH.CompanyProduct with wildcards for product number/name and multi-select for
    category, subcategory, microcategory. No limit on displayed results (up to limit param).
    """
    conn = _get_pg_connection()
    if not conn:
        return CatalogueResponse()

    try:
        cur = conn.cursor()
        conditions = ["1=1"]
        params = []

        if product_number and product_number.strip():
            conditions.append("number ILIKE %s")
            params.append(
                "%"
                + product_number.strip().replace("%", "\\%").replace("_", "\\_")
                + "%"
            )
        if product_name and product_name.strip():
            conditions.append("(name ILIKE %s OR COALESCE(display_name, '') ILIKE %s)")
            pn = (
                "%" + product_name.strip().replace("%", "\\%").replace("_", "\\_") + "%"
            )
            params.extend([pn, pn])

        def _ensure_list(val):
            if val is None:
                return []
            return list(val) if isinstance(val, (list, tuple)) else [val]

        cat_names = _ensure_list(category_name)
        sub_names = _ensure_list(subcategory_name)
        micro_names = _ensure_list(microcategory_name)
        if cat_names:
            placeholders = ",".join(["%s"] * len(cat_names))
            conditions.append(f"category_name IN ({placeholders})")
            params.extend(cat_names)
        if sub_names:
            placeholders = ",".join(["%s"] * len(sub_names))
            conditions.append(f"subcategory_name IN ({placeholders})")
            params.extend(sub_names)
        if micro_names:
            placeholders = ",".join(["%s"] * len(micro_names))
            conditions.append(f"microcategory_name IN ({placeholders})")
            params.extend(micro_names)

        sql = f"""
            SELECT id, number, name, category_name, subcategory_name, microcategory_name
            FROM "CTH"."CompanyProduct"
            WHERE {" AND ".join(conditions)}
            ORDER BY number
            LIMIT %s
        """
        params.append(limit)
        cur.execute(sql, params)
        rows = cur.fetchall()
        cur.close()

        data = [
            CatalogueProductItem(
                id=r[0],
                number=r[1] or "",
                name=r[2],
                category_name=r[3],
                subcategory_name=r[4],
                microcategory_name=r[5],
            )
            for r in rows
        ]
        return CatalogueResponse(data=data, count=len(data))
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        try:
            conn.close()
        except Exception:
            pass


@router.post(
    "/vendor-product-pricing-batch", response_model=VendorProductPricingResponse
)
async def get_vendor_product_pricing_batch(body: VendorProductPricingBatchRequest):
    """
    For each product number (max 10), call Crunchtime getAllVendorProductPricing once.
    Combine all results into a single list (Market, Product Number, Product Name, Vendor Product Number, vendor unit).
    """
    if not body.product_numbers:
        raise HTTPException(
            status_code=400,
            detail="product_numbers must contain at least one product number.",
        )

    token = service_token("vendorproductpricing")
    headers = {**ct_headers(token_override=token), "accept": "*/*"}
    combined = []

    async with get_async_client() as client:
        for product_number in body.product_numbers:
            pn = (product_number or "").strip()
            if not pn:
                continue
            params = {
                "activeProductFlag": "Y",
                "effectiveDate": body.effective_date.strip(),
                "market": body.market.strip(),
                "vendor": body.vendor.strip(),
                "productNumber": pn,
            }
            try:
                resp = await client.get(
                    GET_ALL_VENDOR_PRODUCT_PRICING_PATH,
                    params=params,
                    headers=headers,
                )
                resp.raise_for_status()
                raw = resp.json()
                items = _normalize_vendor_pricing_response(raw)
                combined.extend(items)
            except Exception:
                # Log but continue with other products
                combined.extend([])

    return VendorProductPricingResponse(
        source="crunchtime",
        service="getAllVendorProductPricing",
        data=combined,
        count=len(combined),
    )


@router.post("/fetch-meta-data")
async def fetch_meta_data(minutes_since_update: int | None = Query(None)):
    """
    Manually trigger the product catalogue sync: fetch from Crunchtime
    getCompanyProductsEnhancedByPage (pageSize=100) and upsert into CTH tables.
    Optional minutes_since_update for delta sync.
    """
    result = await asyncio.to_thread(
        run_product_catalogue_sync, minutes_since_update=minutes_since_update
    )
    if not result.get("ok"):
        raise HTTPException(
            status_code=502 if result.get("error") == "http" else 500,
            detail=result.get("message", "Sync failed"),
        )
    return result
