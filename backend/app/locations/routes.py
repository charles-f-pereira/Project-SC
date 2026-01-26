from fastapi import APIRouter, HTTPException, Query
import httpx
from app.core.crunchtime_api import ct_headers, service_token, BASE_URL
from .schemas import LocationResponse

router = APIRouter()


@router.get("/", response_model=LocationResponse)
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
                params=params
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                "source": "crunchtime",
                "service": "location",
                "count": (len(data) if isinstance(data, list) else None),
                "data": data,
                "filter": {"activeFlag": activeFlag} if activeFlag is not None else None
            }
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
