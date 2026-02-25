"""
Product catalogue sync: fetch from Crunchtime getCompanyProductsEnhancedByPage
(pageSize=100) and upsert into CTH.CompanyProduct, Concept, Department,
UserDefinedCategories, and junction tables.
Runs synchronously (sync httpx + psycopg2); call from FastAPI via asyncio.to_thread.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from app.core.config import (
    BASE_URL,
    PG_DATABASE,
    PG_HOST,
    PG_NAME,
    PG_PASSWORD,
    PG_PORT,
)
from app.core.crunchtime_api import ct_headers, service_token

logger = logging.getLogger(__name__)

GET_COMPANY_PRODUCTS_ENHANCED_BY_PAGE_PATH = (
    "/companyproduct/v1/getCompanyProductsEnhancedByPage"
)
PAGE_SIZE = 100


def _get_connection():
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


def _extract_product_list(data: Any, _depth: int = 0) -> list[dict]:
    """Extract list of product header details from ByPage response. Handles nested wrappers."""
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return []
    # Known keys that contain the product array (try exact match first).
    # Crunchtime ByPage returns companyProductEnhancedDetails.
    list_keys = (
        "companyProductEnhancedDetails",
        "companyProductEnhancedHeaderDetails",
        "companyProducts",
        "CompanyProducts",
        "data",
        "products",
        "Products",
        "items",
        "pageContent",
        "content",
        "result",
    )
    for key in list_keys:
        val = data.get(key)
        if isinstance(val, list):
            return val
    # Nested wrapper: e.g. { "getCompanyProductsEnhancedByPageResult": { "companyProductEnhancedHeaderDetails": [...] } }
    if _depth < 3:
        for key, val in data.items():
            if isinstance(val, dict):
                out = _extract_product_list(val, _depth + 1)
                if out:
                    return out
    return []


def _get_str(item: dict, *keys: str, default: str | None = None) -> str | None:
    for k in keys:
        v = item.get(k)
        if v is not None and str(v).strip() != "":
            return str(v).strip()
    return default


def _get_int(item: dict, *keys: str) -> int | None:
    for k in keys:
        v = item.get(k)
        if v is None:
            continue
        try:
            return int(v)
        except (TypeError, ValueError):
            continue
    return None


def _get_ts(item: dict, *keys: str) -> datetime | None:
    for k in keys:
        v = item.get(k)
        if v is None:
            continue
        if isinstance(v, datetime):
            return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
        if isinstance(v, (int, float)):
            try:
                return datetime.fromtimestamp(v, tz=timezone.utc)
            except (ValueError, OSError):
                continue
        s = str(v).strip()
        if not s:
            continue
        try:
            parsed = datetime.fromisoformat(s.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        except ValueError:
            pass
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                parsed = datetime.strptime(s[:19], fmt)
                return parsed.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
    return None


def _get_list(item: dict, *keys: str) -> list[dict]:
    for k in keys:
        val = item.get(k)
        if isinstance(val, list):
            return val
    return []


def _norm_flag(v: str | None) -> str | None:
    if not v or not str(v).strip():
        return None
    s = str(v).strip()
    if len(s) == 1:
        return s.upper()
    return "Y" if s.lower() in ("true", "y", "yes", "1") else "N"


def _upsert_product(cur, row: dict, now_utc: datetime) -> int | None:
    """Upsert one CompanyProduct; return id."""
    number = _get_str(
        row, "number", "productNumber", "Number", "productNo", "product_no"
    )
    if not number:
        return None
    name = _get_str(row, "name", "productName", "Name")
    display_name = _get_str(row, "displayName", "display_name")
    description = _get_str(row, "description", "Description")
    active_flag = _norm_flag(_get_str(row, "activeFlag", "active_flag"))
    product_id = _get_str(row, "productId", "product_id")
    category_name = _get_str(row, "categoryName", "category_name")
    category_code = _get_str(row, "categoryCode", "category_code")
    subcategory_name = _get_str(row, "subcategoryName", "subcategory_name")
    subcategory_code = _get_str(row, "subcategoryCode", "subcategory_code")
    microcategory_name = _get_str(row, "microcategoryName", "microcategory_name")
    microcategory_code = _get_str(row, "microcategoryCode", "microcategory_code")
    bid_sheet = _get_str(row, "bidSheet", "bid_sheet")
    comment = _get_str(row, "comment", "Comment")
    internal_comment = _get_str(row, "internalComment", "internal_comment")
    product_type = _get_str(row, "productType", "product_type")
    product_group = _get_str(row, "productGroup", "product_group")
    product_line = _get_str(row, "productLine", "product_line")
    primary_shipping_type = _get_str(
        row, "primaryShippingType", "primary_shipping_type"
    )
    secondary_shipping_type = _get_str(
        row, "secondaryShippingType", "secondary_shipping_type"
    )
    inventory_unit = _get_str(
        row, "inventoryUnitPackageType", "inventory_unit_package_type"
    )
    preferred_vendor_unit = _get_str(
        row, "preferredVendorUnitPackageType", "preferred_vendor_unit_package_type"
    )
    unit_of_measure = _get_str(row, "unitOfMeasure", "unit_of_measure")
    default_uom = _get_str(row, "defaultUnitOfMeasure", "default_unit_of_measure")
    pack_size = _get_str(row, "packSize", "pack_size")
    case_size = _get_str(row, "caseSize", "case_size")
    order_multiple = _get_str(row, "orderMultiple", "order_multiple")
    upc = _get_str(row, "universalProductCode", "universal_product_code")
    gl_number = _get_int(row, "glNumber", "gl_number")
    gl_description = _get_str(row, "glDescription", "gl_description")
    cost_center = _get_str(row, "costCenter", "cost_center")
    inventory_type = _get_str(row, "inventoryType", "inventory_type")
    brand = _get_str(row, "brand", "Brand")
    supplier_code = _get_str(row, "supplierCode", "supplier_code")
    taxable_flag = _norm_flag(_get_str(row, "taxableFlag", "taxable_flag"))
    orderable_flag = _norm_flag(_get_str(row, "orderableFlag", "orderable_flag"))
    sort_order = _get_int(row, "sortOrder", "sort_order")
    image_url = _get_str(row, "imageUrl", "image_url")
    status = _get_str(row, "status", "Status")
    created_date = _get_ts(row, "createdDate", "created_date")
    last_modified_date = _get_ts(row, "lastModifiedDate", "last_modified_date")
    raw_json = json.dumps(row) if row else None

    cur.execute(
        """
        INSERT INTO "CTH"."CompanyProduct" (
            number, name, display_name, description, active_flag, product_id,
            category_name, category_code, subcategory_name, subcategory_code,
            microcategory_name, microcategory_code, bid_sheet, comment, internal_comment,
            product_type, product_group, product_line, primary_shipping_type, secondary_shipping_type,
            inventory_unit_package_type, preferred_vendor_unit_package_type,
            unit_of_measure, default_unit_of_measure, pack_size, case_size, order_multiple,
            universal_product_code, gl_number, gl_description, cost_center, inventory_type,
            brand, supplier_code, taxable_flag, orderable_flag, sort_order, image_url, status,
            created_date, last_modified_date, raw_json, updated_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s
        )
        ON CONFLICT (number) DO UPDATE SET
            name = EXCLUDED.name,
            display_name = EXCLUDED.display_name,
            description = EXCLUDED.description,
            active_flag = EXCLUDED.active_flag,
            product_id = EXCLUDED.product_id,
            category_name = EXCLUDED.category_name,
            category_code = EXCLUDED.category_code,
            subcategory_name = EXCLUDED.subcategory_name,
            subcategory_code = EXCLUDED.subcategory_code,
            microcategory_name = EXCLUDED.microcategory_name,
            microcategory_code = EXCLUDED.microcategory_code,
            bid_sheet = EXCLUDED.bid_sheet,
            comment = EXCLUDED.comment,
            internal_comment = EXCLUDED.internal_comment,
            product_type = EXCLUDED.product_type,
            product_group = EXCLUDED.product_group,
            product_line = EXCLUDED.product_line,
            primary_shipping_type = EXCLUDED.primary_shipping_type,
            secondary_shipping_type = EXCLUDED.secondary_shipping_type,
            inventory_unit_package_type = EXCLUDED.inventory_unit_package_type,
            preferred_vendor_unit_package_type = EXCLUDED.preferred_vendor_unit_package_type,
            unit_of_measure = EXCLUDED.unit_of_measure,
            default_unit_of_measure = EXCLUDED.default_unit_of_measure,
            pack_size = EXCLUDED.pack_size,
            case_size = EXCLUDED.case_size,
            order_multiple = EXCLUDED.order_multiple,
            universal_product_code = EXCLUDED.universal_product_code,
            gl_number = EXCLUDED.gl_number,
            gl_description = EXCLUDED.gl_description,
            cost_center = EXCLUDED.cost_center,
            inventory_type = EXCLUDED.inventory_type,
            brand = EXCLUDED.brand,
            supplier_code = EXCLUDED.supplier_code,
            taxable_flag = EXCLUDED.taxable_flag,
            orderable_flag = EXCLUDED.orderable_flag,
            sort_order = EXCLUDED.sort_order,
            image_url = EXCLUDED.image_url,
            status = EXCLUDED.status,
            created_date = EXCLUDED.created_date,
            last_modified_date = EXCLUDED.last_modified_date,
            raw_json = EXCLUDED.raw_json,
            updated_at = EXCLUDED.updated_at
        RETURNING id
        """,
        (
            number,
            name,
            display_name,
            description,
            active_flag,
            product_id,
            category_name,
            category_code,
            subcategory_name,
            subcategory_code,
            microcategory_name,
            microcategory_code,
            bid_sheet,
            comment,
            internal_comment,
            product_type,
            product_group,
            product_line,
            primary_shipping_type,
            secondary_shipping_type,
            inventory_unit,
            preferred_vendor_unit,
            unit_of_measure,
            default_uom,
            pack_size,
            case_size,
            order_multiple,
            upc,
            gl_number,
            gl_description,
            cost_center,
            inventory_type,
            brand,
            supplier_code,
            taxable_flag,
            orderable_flag,
            sort_order,
            image_url,
            status,
            created_date,
            last_modified_date,
            raw_json,
            now_utc,
        ),
    )
    row = cur.fetchone()
    return row[0] if row else None


def _upsert_concept(cur, code: str, active_flag: str | None) -> None:
    if not code:
        return
    cur.execute(
        """
        INSERT INTO "CTH"."Concept" (code, active_flag)
        VALUES (%s, %s)
        ON CONFLICT (code) DO UPDATE SET active_flag = EXCLUDED.active_flag
        """,
        (code, active_flag),
    )


def _upsert_department(cur, code: str, active_flag: str | None) -> None:
    if not code:
        return
    cur.execute(
        """
        INSERT INTO "CTH"."Department" (code, active_flag)
        VALUES (%s, %s)
        ON CONFLICT (code) DO UPDATE SET active_flag = EXCLUDED.active_flag
        """,
        (code, active_flag),
    )


def _upsert_udc(cur, code: str, active_flag: str | None) -> None:
    if not code:
        return
    cur.execute(
        """
        INSERT INTO "CTH"."UserDefinedCategories" (code, active_flag)
        VALUES (%s, %s)
        ON CONFLICT (code) DO UPDATE SET active_flag = EXCLUDED.active_flag
        """,
        (code, active_flag),
    )


def _replace_junction_links(
    cur,
    company_product_id: int,
    concepts: list[dict],
    departments: list[dict],
    udcs: list[dict],
) -> None:
    cur.execute(
        'DELETE FROM "CTH"."CompanyProductConcept" WHERE company_product_id = %s',
        (company_product_id,),
    )
    cur.execute(
        'DELETE FROM "CTH"."CompanyProductDepartment" WHERE company_product_id = %s',
        (company_product_id,),
    )
    cur.execute(
        'DELETE FROM "CTH"."CompanyProductUserDefinedCategory" WHERE company_product_id = %s',
        (company_product_id,),
    )

    def _code_from_item(item: Any, *keys: str) -> str | None:
        if item is None:
            return None
        if isinstance(item, str) and item.strip():
            return item.strip()
        if isinstance(item, dict):
            return _get_str(item, *keys)
        return None

    for c in concepts:
        code = _code_from_item(c, "code", "Code", "conceptCode", "concept_code")
        if code:
            _upsert_concept(
                cur,
                code,
                _get_str(c, "activeFlag", "active_flag")
                if isinstance(c, dict)
                else None,
            )
            cur.execute(
                """
                INSERT INTO "CTH"."CompanyProductConcept" (company_product_id, concept_code)
                VALUES (%s, %s)
                ON CONFLICT (company_product_id, concept_code) DO NOTHING
                """,
                (company_product_id, code),
            )
    for d in departments:
        code = _code_from_item(d, "code", "Code", "departmentCode", "department_code")
        if code:
            _upsert_department(
                cur,
                code,
                _get_str(d, "activeFlag", "active_flag")
                if isinstance(d, dict)
                else None,
            )
            cur.execute(
                """
                INSERT INTO "CTH"."CompanyProductDepartment" (company_product_id, department_code)
                VALUES (%s, %s)
                ON CONFLICT (company_product_id, department_code) DO NOTHING
                """,
                (company_product_id, code),
            )
    for u in udcs:
        code = _code_from_item(u, "code", "Code", "userDefinedCategoryCode", "udc_code")
        if code:
            _upsert_udc(
                cur,
                code,
                _get_str(u, "activeFlag", "active_flag")
                if isinstance(u, dict)
                else None,
            )
            cur.execute(
                """
                INSERT INTO "CTH"."CompanyProductUserDefinedCategory" (company_product_id, udc_code)
                VALUES (%s, %s)
                ON CONFLICT (company_product_id, udc_code) DO NOTHING
                """,
                (company_product_id, code),
            )


def run_product_catalogue_sync(
    minutes_since_update: int | None = None,
) -> dict[str, Any]:
    """
    Fetch all pages from getCompanyProductsEnhancedByPage (pageSize=100),
    upsert into CTH tables. Optionally pass minutes_since_update for delta sync.
    Returns dict with ok, message, products_processed, pages, error.
    """
    token = service_token("companyproduct")
    headers = {**ct_headers(token_override=token), "accept": "application/json"}
    conn = _get_connection()
    if not conn:
        return {
            "ok": False,
            "message": "Database not configured (pgName/pgPassword not set)",
            "products_processed": 0,
            "pages": 0,
            "error": "no_db",
        }

    now_utc = datetime.now(timezone.utc)
    products_processed = 0
    page = 1
    total_pages = 0
    first_page_keys: list[str] = []  # for debugging when 0 products

    try:
        with httpx.Client(base_url=BASE_URL, timeout=120.0) as client:
            while True:
                params: dict[str, Any] = {
                    "pageSize": PAGE_SIZE,
                    "pageNumber": page,
                }
                if minutes_since_update is not None:
                    params["minutesSinceUpdate"] = minutes_since_update

                resp = client.get(
                    GET_COMPANY_PRODUCTS_ENHANCED_BY_PAGE_PATH,
                    params=params,
                    headers=headers,
                )
                resp.raise_for_status()
                raw = resp.json()
                items = _extract_product_list(raw)
                total_pages = page

                if not items:
                    if page == 1 and isinstance(raw, dict):
                        first_page_keys = list(raw.keys())
                        logger.warning(
                            "Product catalogue sync: first page returned no product list. "
                            "Top-level response keys: %s",
                            first_page_keys,
                        )
                    break

                cur = conn.cursor()
                try:
                    for item in items:
                        row = item
                        # Unwrap if API returns e.g. [ {"companyProductEnhancedHeaderDetails": {...}} ]
                        if isinstance(row, dict) and not _get_str(
                            row, "number", "productNumber", "Number"
                        ):
                            for wrap_key in (
                                "companyProductEnhancedHeaderDetails",
                                "header",
                                "product",
                                "data",
                            ):
                                if isinstance(row.get(wrap_key), dict):
                                    row = row[wrap_key]
                                    break
                        product_id = _upsert_product(cur, row, now_utc)
                        if product_id is None:
                            continue
                        products_processed += 1
                        # Use original item for link lists so we don't lose them after unwrap
                        concepts = _get_list(
                            item,
                            "companyProductEnhancedConceptDetails",
                            "conceptDetailList",
                            "conceptDetails",
                            "concepts",
                            "ConceptDetails",
                        )
                        departments = _get_list(
                            item,
                            "companyProductEnhancedDepartmentDetails",
                            "departmentDetailList",
                            "departmentDetails",
                            "departments",
                            "DepartmentDetails",
                        )
                        udcs = _get_list(
                            item,
                            "companyProductEnhancedUserDefinedCategoryDetails",
                            "userDefinedCategoryDetailList",
                            "userDefinedCategoryDetails",
                            "userDefinedCategories",
                            "UserDefinedCategoryDetails",
                        )
                        _replace_junction_links(
                            cur, product_id, concepts, departments, udcs
                        )
                    conn.commit()
                finally:
                    cur.close()

                if len(items) < PAGE_SIZE:
                    break
                page += 1

    except httpx.HTTPStatusError as e:
        logger.exception("Product catalogue sync HTTP error")
        if conn:
            conn.rollback()
        return {
            "ok": False,
            "message": f"Crunchtime API error: {e.response.status_code}",
            "products_processed": products_processed,
            "pages": total_pages,
            "error": "http",
        }
    except Exception as e:
        logger.exception("Product catalogue sync failed")
        if conn:
            conn.rollback()
        return {
            "ok": False,
            "message": str(e),
            "products_processed": products_processed,
            "pages": total_pages,
            "error": "sync",
        }
    finally:
        if conn:
            conn.close()

    message = f"Synced {products_processed} products from {total_pages} page(s)"
    if products_processed == 0 and first_page_keys:
        message += f". Response keys: {first_page_keys}"
    return {
        "ok": True,
        "message": message,
        "products_processed": products_processed,
        "pages": total_pages,
    }
