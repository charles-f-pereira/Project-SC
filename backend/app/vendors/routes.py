from fastapi import APIRouter, HTTPException, Query
import httpx
from app.core.crunchtime_api import ct_headers, service_token, BASE_URL
from .schemas import VendorResponse, HierarchyResponse

router = APIRouter()


@router.get("/", response_model=VendorResponse)
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
                params=params
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                "source": "crunchtime",
                "service": "vendor",
                "count": (len(data) if isinstance(data, list) else None),
                "data": data if isinstance(data, list) else [data]
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
                        params=params
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    return {
                        "source": "crunchtime",
                        "service": "vendor",
                        "count": (len(data) if isinstance(data, list) else None),
                        "data": data if isinstance(data, list) else [data]
                    }
            except Exception:
                raise HTTPException(status_code=404, detail="Vendor endpoint not found. Please confirm endpoint path.")
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/hierarchy", response_model=HierarchyResponse)
async def get_hierarchy():
    """
    Get hierarchy data to link locations to vendor distribution centers.
    
    Note: Exact endpoint path may need to be confirmed.
    Common patterns: /hierarchy/v1/getHierarchy or /hierarchy/v1/getAllHierarchy
    
    Returns:
        Hierarchy data linking locations to vendors/DCs
    """
    # Try common endpoint patterns - may need adjustment based on actual API
    url = f"{BASE_URL}/hierarchy/v1/getHierarchy"
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                url,
                headers=ct_headers(token_override=service_token("hierarchy")),
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                "source": "crunchtime",
                "service": "hierarchy",
                "count": (len(data) if isinstance(data, list) else None),
                "data": data if isinstance(data, list) else [data]
            }
    except httpx.HTTPStatusError as e:
        # If endpoint doesn't exist, try alternative
        if e.response.status_code == 404:
            url_alt = f"{BASE_URL}/hierarchy/v1/getAllHierarchy"
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.get(
                        url_alt,
                        headers=ct_headers(token_override=service_token("hierarchy")),
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    return {
                        "source": "crunchtime",
                        "service": "hierarchy",
                        "count": (len(data) if isinstance(data, list) else None),
                        "data": data if isinstance(data, list) else [data]
                    }
            except Exception:
                raise HTTPException(status_code=404, detail="Hierarchy endpoint not found. Please confirm endpoint path.")
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
