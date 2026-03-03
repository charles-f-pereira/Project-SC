import logging
from fastapi import APIRouter, HTTPException
import httpx
import json
import os
from app.core.crunchtime_api import ct_headers, service_token, BASE_URL
from .schemas import VendorResponse, HierarchyResponse

logger = logging.getLogger(__name__)


def _extract_vendor_list(raw):
    """Extract list of items from Crunchtime vendor response (list or dict with list value)."""
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        for key in (
            "vendorDetailDetails",
            "VendorDetailDetails",
            "vendorDetails",
            "VendorDetails",
            "data",
            "Data",
            "vendors",
            "Vendors",
            "getAllVendorsResponse",
            "GetAllVendorsResponse",
        ):
            val = raw.get(key)
            if isinstance(val, list):
                return val
        for val in raw.values():
            if isinstance(val, list) and len(val) > 0 and isinstance(val[0], dict):
                return val
    return []


def _normalize_vendor(v: dict) -> dict:
    """Ensure top-level code/supplyCode/vendorCode so frontend can display (prod may use different shape)."""
    if not isinstance(v, dict):
        return v
    out = dict(v)
    code = (
        out.get("supplyCode")
        or out.get("SupplyCode")
        or out.get("vendorCode")
        or out.get("VendorCode")
        or out.get("code")
        or out.get("Code")
    )
    if code is None:
        for k, vv in out.items():
            if vv is not None and vv != "" and isinstance(vv, (str, int)):
                if "code" in k.lower() or (
                    k.lower() in ("id", "supply") and len(str(vv)) < 30
                ):
                    code = str(vv)
                    break
    if code is not None:
        out["supplyCode"] = out["vendorCode"] = out["code"] = str(code)
    return out


router = APIRouter()

# Debug: log path to confirm handler is hit (workspace .cursor/debug.log)
_DEBUG_LOG = os.path.normpath(
    os.path.join(
        os.path.dirname(__file__), "..", "..", "..", "..", ".cursor", "debug.log"
    )
)


@router.get("", response_model=VendorResponse)
async def get_all_vendors(activeFlag: bool | None = None):
    """
    Get all vendors from Crunchtime.

    Note: Exact endpoint path may need to be confirmed.
    Common patterns: /vendor/v1/getAllVendors or /vendor/v1/getVendors

    Args:
        activeFlag: Filter by active status (optional)

    Returns:
        List of vendors with metadata
    """
    # Try common endpoint patterns - may need adjustment based on actual API
    url = f"{BASE_URL}/vendor/v1/getAllVendors"

    params = {}
    if activeFlag is not None:
        params["activeFlag"] = str(activeFlag).lower()

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                url,
                headers=ct_headers(token_override=service_token("vendor")),
                params=params,
            )
            resp.raise_for_status()
            raw = resp.json()
            data = _extract_vendor_list(raw)
            data = [
                _normalize_vendor(item) if isinstance(item, dict) else item
                for item in data
            ]
            if isinstance(raw, dict) and not data:
                logger.warning(
                    "vendors: Crunchtime returned a dict with no recognized list; keys=%s",
                    list(raw.keys()),
                )
            else:
                logger.info("vendors: returning count=%s", len(data))
            return {
                "source": "crunchtime",
                "service": "vendor",
                "count": len(data),
                "data": data,
            }
    except httpx.HTTPStatusError as e:
        # If endpoint doesn't exist, try alternative
        if e.response.status_code == 404:
            url_alt = f"{BASE_URL}/vendor/v1/getVendors"
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.get(
                        url_alt,
                        headers=ct_headers(token_override=service_token("vendor")),
                        params=params,
                    )
                    resp.raise_for_status()
                    raw = resp.json()
                    data = _extract_vendor_list(raw)
                    data = [
                        _normalize_vendor(item) if isinstance(item, dict) else item
                        for item in data
                    ]
                    return {
                        "source": "crunchtime",
                        "service": "vendor",
                        "count": len(data),
                        "data": data,
                    }
            except Exception:
                raise HTTPException(
                    status_code=404,
                    detail="Vendor endpoint not found. Please confirm endpoint path.",
                )
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/count")
async def get_vendors_count(activeFlag: bool | None = None):
    """Return only the count of vendors (for debugging when full response is too large)."""
    url = f"{BASE_URL}/vendor/v1/getAllVendors"
    params = {}
    if activeFlag is not None:
        params["activeFlag"] = str(activeFlag).lower()
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                url,
                headers=ct_headers(token_override=service_token("vendor")),
                params=params,
            )
            resp.raise_for_status()
            data = _extract_vendor_list(resp.json())
            return {"count": len(data)}
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(
                    f"{BASE_URL}/vendor/v1/getVendors",
                    headers=ct_headers(token_override=service_token("vendor")),
                    params=params,
                )
                resp.raise_for_status()
                data = _extract_vendor_list(resp.json())
                return {"count": len(data)}
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sample")
async def get_vendors_sample(activeFlag: bool | None = True):
    """Return first raw + normalized vendor (for debugging prod response shape)."""
    url = f"{BASE_URL}/vendor/v1/getAllVendors"
    params = {}
    if activeFlag is not None:
        params["activeFlag"] = str(activeFlag).lower()
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                url,
                headers=ct_headers(token_override=service_token("vendor")),
                params=params,
            )
            resp.raise_for_status()
            raw = resp.json()
            data = _extract_vendor_list(raw)
            first = data[0] if data and isinstance(data[0], dict) else None
            return {
                "count": len(data),
                "raw": first,
                "normalized": _normalize_vendor(first) if first else None,
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/hierarchy/health")
async def hierarchy_health():
    """Confirm hierarchy router is reachable; returns 200."""
    return {"ok": True, "route": "hierarchy"}


@router.get("/hierarchy/debug")
async def get_hierarchy_debug(
    hierarchyType: str | None = None, levelNumber: int | None = 3
):
    """
    Call Crunchtime hierarchy API and return the raw response and status.
    Use this to verify whether Distribution Centers (hierarchy) data is being returned.
    Example: GET /api/vendors/hierarchy/debug?hierarchyType=3-AU%20Supply%20Chain%20-%20PFD&levelNumber=3
    """
    url = f"{BASE_URL}/hierarchy/v2/getHierarchyDetails"
    headers = ct_headers(token_override=service_token("hierarchy"))
    params = {}
    if hierarchyType:
        params["hierarchyType"] = hierarchyType
    if levelNumber is not None:
        params["levelNumber"] = levelNumber

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                url, headers=headers, params=params if params else None
            )
            try:
                raw_body = resp.json()
            except Exception:
                raw_body = resp.text
            return {
                "crunchtime_status_code": resp.status_code,
                "crunchtime_url": str(resp.url),
                "params_sent": params,
                "raw_response": raw_body,
                "response_type": "dict"
                if isinstance(raw_body, dict)
                else "list"
                if isinstance(raw_body, list)
                else "str",
                "hint": "If status_code is 200, check raw_response for 'locations' or a list of items with parentLogicalName/locationCode.",
            }
    except httpx.HTTPStatusError as e:
        return {
            "crunchtime_status_code": e.response.status_code,
            "crunchtime_url": str(e.request.url),
            "params_sent": params,
            "error": e.response.text,
            "hint": "4xx from Crunchtime may mean wrong hierarchyType, wrong endpoint, or auth.",
        }
    except Exception as e:
        return {
            "params_sent": params,
            "error": str(e),
            "hint": "Check network, BASE_URL, and CRUNCHTIME_HIERARCHY_TOKEN_TEST.",
        }


@router.get("/hierarchy", response_model=HierarchyResponse)
async def get_hierarchy(hierarchyType: str | None = None, levelNumber: int | None = 3):
    # Debug: confirm this handler is hit (if 404 persists, this log will be missing)
    try:
        with open(_DEBUG_LOG, "a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {"message": "get_hierarchy_called", "hierarchyType": hierarchyType}
                )
                + "\n"
            )
    except Exception:
        pass
    """
    Get hierarchy data to link locations to vendor distribution centers.
    
    Uses the endpoint: /hierarchy/v2/getHierarchyDetails with levelNumber=3
    so the response is an array of level-3 items with parentLogicalName (DC name)
    and locationCode for linking to locations.
    
    Args:
        hierarchyType: Hierarchy type (e.g., "3-AU Supply Chain - PFD")
        levelNumber: Level to return; default 3 for DC/location rows.
    
    Returns:
        Hierarchy data linking locations to vendors/DCs
    """
    url = f"{BASE_URL}/hierarchy/v2/getHierarchyDetails"
    headers = ct_headers(token_override=service_token("hierarchy"))
    empty_ok = {"source": "crunchtime", "service": "hierarchy", "count": 0, "data": []}

    # Build params: hierarchyType required for DC/location data; levelNumber=3 for level-3 rows
    params = {}
    if hierarchyType:
        params["hierarchyType"] = hierarchyType
    if levelNumber is not None:
        params["levelNumber"] = levelNumber

    async def _get(params_to_use):
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, headers=headers, params=params_to_use)
            resp.raise_for_status()
            data = resp.json()
            # Crunchtime returns { locationCode, hierarchyType, locations: [...] }; extract locations array
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict) and "locations" in data:
                raw = data["locations"]
                items = raw if isinstance(raw, list) else [raw]
            else:
                items = [data] if isinstance(data, dict) else [data]
            # If levelNumber=3 was requested, filter to level-3 rows in case API returns all levels
            if levelNumber == 3 and items:
                items = [
                    i
                    for i in items
                    if i.get("levelNumber") == 3 or i.get("levelNumber") == "3"
                ]
            return {
                "source": "crunchtime",
                "service": "hierarchy",
                "count": len(items),
                "data": items,
            }

    try:
        return await _get(params)
    except httpx.HTTPStatusError as e:
        # Crunchtime may 404 for unknown hierarchyType or if levelNumber is not supported; never return 404 to client
        if e.response.status_code == 404 and params.get("levelNumber") is not None:
            try:
                params_no_level = {
                    k: v for k, v in params.items() if k != "levelNumber"
                }
                return await _get(params_no_level)
            except Exception:
                return empty_ok
        # Always return 200 with empty data for any 4xx from Crunchtime so the app keeps loading
        return empty_ok
    except Exception:
        # Any other error (network, parse, etc.): return 200 with empty data so the app keeps loading
        return empty_ok
