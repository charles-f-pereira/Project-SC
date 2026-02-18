from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
import httpx
from app.core.crunchtime_api import ct_headers, service_token, BASE_URL
from .schemas import ScheduleResponse, ScheduleFilter

router = APIRouter()

# Crunchtime getAllVendorLocation endpoint path
GET_ALL_VENDOR_LOCATION_PATH = "/vendorlocation/v1/getAllVendorLocation"


def _normalize_vendor_location_response(data) -> list:
    """Extract list of vendor-location items from Crunchtime response (may be wrapped)."""
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        for key in ("data", "vendorLocations", "VendorLocations", "locations", "Locations"):
            val = data.get(key)
            if isinstance(val, list):
                items = val
                break
        else:
            items = [data]
    else:
        items = []
    return items


def _flatten_vendor_location_item(raw: dict) -> dict:
    """
    Crunchtime returns nested structure:
    - vendorLocationHeaderDetails: { vendorCode, locationCode, ... }
    - vendorLocationScheduleDetail: single object (or array) with orderDay*Flag, orderByTime*, deliverDay*
    Flatten to { locationCode, vendorCode, vendorLocationScheduleDetail: list } for frontend.
    """
    header = raw.get("vendorLocationHeaderDetails") or raw.get("VendorLocationHeaderDetails") or {}
    detail = raw.get("vendorLocationScheduleDetail") or raw.get("VendorLocationScheduleDetail")
    overrides = raw.get("scheduleOverrideRowList") or raw.get("ScheduleOverrideRowList")

    location_code = header.get("locationCode") or header.get("LocationCode") or raw.get("locationCode") or raw.get("LocationCode") or ""
    vendor_code = header.get("vendorCode") or header.get("VendorCode") or raw.get("vendorCode") or raw.get("VendorCode") or ""

    if isinstance(detail, list):
        detail_list = detail
    elif isinstance(detail, dict):
        detail_list = [detail]
    else:
        detail_list = []

    if isinstance(overrides, list):
        override_list = overrides
    elif isinstance(overrides, dict):
        override_list = [overrides]
    else:
        override_list = []

    return {
        "locationCode": location_code,
        "vendorCode": vendor_code,
        "vendorLocationScheduleDetail": detail_list,
        "scheduleOverrideRowList": override_list,
    }


# Fixed params for Crunchtime getAllVendorLocation (always sent)
CT_VENDOR_LOCATION_FIXED_PARAMS = {
    "activeFlag": "true",
    "includeDetails": "true",
    "includeNull": "false",
}


@router.get("/vendor-locations", response_model=ScheduleResponse)
async def get_vendor_locations(
    locationCode: Optional[str] = Query(None, description="Single location code (for single-location call)"),
):
    """
    Get vendor-location schedules from Crunchtime getAllVendorLocation.
    
    Single-location logic: pass exactly one locationCode. Crunchtime returns all vendors
    for that location, each with vendorLocationScheduleDetail (and scheduleOverrideRowList for overrides).
    
    Always sends: activeFlag=true, includeDetails=true, includeNull=false.
    
    Schedule detail: orderDay*Flag, orderByTime*, deliverDay* (1=Sun..7=Sat, 8=Sun next week..21=Sat week+2).
    """
    params = dict(CT_VENDOR_LOCATION_FIXED_PARAMS)
    if locationCode and locationCode.strip():
        params["locationCode"] = locationCode.strip()

    try:
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
            resp = await client.get(
                GET_ALL_VENDOR_LOCATION_PATH,
                headers=ct_headers(token_override=service_token("vendorlocation")),
                params=params,
            )
            resp.raise_for_status()
            data = resp.json()
            raw_items = _normalize_vendor_location_response(data)
            items = [_flatten_vendor_location_item(it) for it in raw_items]
            return {
                "source": "crunchtime",
                "service": "vendorlocation",
                "count": len(items),
                "data": items,
            }
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            try:
                path_alt = "/vendorlocation/v1/getAllVendorLocations"
                async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
                    resp = await client.get(
                        path_alt,
                        headers=ct_headers(token_override=service_token("vendorlocation")),
                        params=params,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    raw_items = _normalize_vendor_location_response(data)
                    items = [_flatten_vendor_location_item(it) for it in raw_items]
                    return {"source": "crunchtime", "service": "vendorlocation", "count": len(items), "data": items}
            except Exception:
                pass
            raise HTTPException(status_code=404, detail="getAllVendorLocation endpoint not found. Please confirm Crunchtime API path.")
        raise HTTPException(status_code=e.response.status_code, detail=str(e.response.text))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/vendor-locations/debug")
async def get_vendor_locations_debug(
    locationCode: Optional[str] = Query(None, description="Single location code to test"),
):
    """
    Troubleshooting: call Crunchtime getAllVendorLocation and return raw response + summary.
    Use this to see if data is returned and what structure it has.
    Example: GET /api/schedules/vendor-locations/debug?locationCode=001061
    """
    params = dict(CT_VENDOR_LOCATION_FIXED_PARAMS)
    if locationCode and locationCode.strip():
        params["locationCode"] = locationCode.strip()

    try:
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
            resp = await client.get(
                GET_ALL_VENDOR_LOCATION_PATH,
                headers=ct_headers(token_override=service_token("vendorlocation")),
                params=params,
            )
            raw = resp.json()
            items = _normalize_vendor_location_response(raw)
            first_item_keys = list(items[0].keys()) if items else []
            has_detail = False
            detail_count = 0
            if items:
                detail = items[0].get("vendorLocationScheduleDetail") or items[0].get("VendorLocationScheduleDetail")
                has_detail = detail is not None
                detail_count = len(detail) if isinstance(detail, list) else (1 if detail else 0)
            return {
                "crunchtime_status": resp.status_code,
                "params_sent": params,
                "items_count": len(items),
                "first_item_keys": first_item_keys,
                "has_vendorLocationScheduleDetail": has_detail,
                "schedule_detail_count_first_item": detail_count,
                "hint": "If items_count=0, Crunchtime returned no rows. If has_vendorLocationScheduleDetail=false or detail_count=0, schedule array is missing or empty.",
                "raw_sample": items[0] if items else None,
            }
    except httpx.HTTPStatusError as e:
        return {
            "error": "crunchtime_http_error",
            "status_code": e.response.status_code,
            "params_sent": params,
            "body": e.response.text[:1000],
        }
    except Exception as e:
        return {"error": str(e), "params_sent": params}
