import logging
from fastapi import APIRouter, HTTPException
import httpx
from app.core.crunchtime_api import ct_headers, service_token, BASE_URL
from .schemas import LocationResponse

logger = logging.getLogger(__name__)

router = APIRouter()


def _extract_list(raw):
    """Extract list of items from Crunchtime response (list or dict with list value)."""
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        # Try known keys (camelCase and PascalCase)
        for key in (
            "locationDetailDetails",
            "LocationDetailDetails",
            "locationDetails",
            "LocationDetails",
            "data",
            "Data",
            "locations",
            "Locations",
            "getAllLocationsResponse",
            "GetAllLocationsResponse",
        ):
            val = raw.get(key)
            if isinstance(val, list):
                return val
        # Fallback: first dict value that is a non-empty list of dicts
        for val in raw.values():
            if isinstance(val, list) and len(val) > 0 and isinstance(val[0], dict):
                return val
    return []


def _get_nested(obj: dict, *keys: str):
    """Return first non-None value for given keys (checks both camelCase and PascalCase)."""
    for k in keys:
        v = obj.get(k) or obj.get(k[0].upper() + k[1:]) if k else None
        if v is not None and v != "":
            return v
    return None


def _normalize_location(loc: dict) -> dict:
    """Ensure top-level locationCode, country, state, market so frontend can display (prod may use different shape)."""
    if not isinstance(loc, dict):
        return loc
    out = dict(loc)
    # Code: try known keys then any key containing 'code' or 'id'
    code = _get_nested(
        out, "locationCode", "LocationCode", "code", "Code"
    ) or _get_nested(out, "locationId", "LocationId", "id", "Id")
    if code is None:
        for k, v in out.items():
            if v is not None and v != "" and isinstance(v, (str, int)):
                if "code" in k.lower() or (k.lower() == "id" and len(str(v)) < 20):
                    code = str(v)
                    break
    if code is not None:
        out["locationCode"] = out["code"] = str(code)
    # Nested: locationDetailDetails, locationNameAddressDetails
    for key in (
        "locationDetailDetails",
        "LocationDetailDetails",
        "locationDetails",
        "LocationDetails",
    ):
        details = out.get(key)
        if isinstance(details, list) and details and isinstance(details[0], dict):
            d0 = details[0]
            if out.get("market") is None:
                out["market"] = _get_nested(d0, "market", "Market") or out.get("market")
            if out.get("state") is None:
                out["state"] = _get_nested(
                    d0, "stateProvince", "state", "State", "stateCode", "StateCode"
                ) or out.get("state")
            break
    for key in ("locationNameAddressDetails", "LocationNameAddressDetails"):
        name_addr = out.get(key)
        if isinstance(name_addr, list) and name_addr and isinstance(name_addr[0], dict):
            n0 = name_addr[0]
            if out.get("country") is None:
                out["country"] = _get_nested(n0, "country", "Country") or out.get(
                    "country"
                )
            if out.get("state") is None:
                out["state"] = _get_nested(
                    n0, "stateProvince", "state", "State"
                ) or out.get("state")
            break
    # Fallback: copy any top-level key that looks like country/state/market
    if out.get("country") is None:
        for k, v in out.items():
            if v and isinstance(v, str) and "country" in k.lower():
                out["country"] = v
                break
    if out.get("state") is None:
        for k, v in out.items():
            if v and isinstance(v, str) and "state" in k.lower():
                out["state"] = v
                break
    if out.get("market") is None:
        for k, v in out.items():
            if v and isinstance(v, str) and "market" in k.lower():
                out["market"] = v
                break
    return out


@router.get("", response_model=LocationResponse)
async def get_all_locations(activeFlag: bool | None = None):
    """
    Get all locations from Crunchtime.

    Args:
        activeFlag: Filter by active status (optional)

    Returns:
        List of locations with metadata
    """
    url = f"{BASE_URL}/location/v1/getAllLocations"

    # Build query parameters for CrunchTime API
    params = {}
    if activeFlag is not None:
        params["activeFlag"] = str(activeFlag).lower()

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                url,
                headers=ct_headers(token_override=service_token("location")),
                params=params,
            )
            resp.raise_for_status()
            raw = resp.json()
            data = _extract_list(raw)
            # Normalize each item so frontend always gets locationCode/code and optional country/state/market
            data = [
                _normalize_location(item) if isinstance(item, dict) else item
                for item in data
            ]
            if isinstance(raw, dict) and not data:
                logger.warning(
                    "locations: Crunchtime returned a dict with no recognized list; keys=%s",
                    list(raw.keys()),
                )
            else:
                logger.info("locations: returning count=%s", len(data))
            return {
                "source": "crunchtime",
                "service": "location",
                "count": len(data),
                "data": data,
                "filter": {"activeFlag": activeFlag}
                if activeFlag is not None
                else None,
            }
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/count")
async def get_locations_count(activeFlag: bool | None = None):
    """Return only the count of locations (for debugging when full response is too large)."""
    url = f"{BASE_URL}/location/v1/getAllLocations"
    params = {}
    if activeFlag is not None:
        params["activeFlag"] = str(activeFlag).lower()
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                url,
                headers=ct_headers(token_override=service_token("location")),
                params=params,
            )
            resp.raise_for_status()
            data = _extract_list(resp.json())
            return {"count": len(data)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sample")
async def get_locations_sample(activeFlag: bool | None = True):
    """Return first raw + normalized location (for debugging prod response shape)."""
    url = f"{BASE_URL}/location/v1/getAllLocations"
    params = {}
    if activeFlag is not None:
        params["activeFlag"] = str(activeFlag).lower()
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                url,
                headers=ct_headers(token_override=service_token("location")),
                params=params,
            )
            resp.raise_for_status()
            raw = resp.json()
            data = _extract_list(raw)
            first = data[0] if data and isinstance(data[0], dict) else None
            return {
                "count": len(data),
                "raw": first,
                "normalized": _normalize_location(first) if first else None,
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
