from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
import httpx
from app.core.crunchtime_api import ct_headers, service_token, BASE_URL
from .schemas import ScheduleResponse, ScheduleFilter

router = APIRouter()


@router.get("/vendor-locations", response_model=ScheduleResponse)
async def get_vendor_locations(
    locationCode: Optional[str] = None,
    vendorCode: Optional[str] = None
):
    """
    Get vendor-location relationships with schedules.
    
    This endpoint retrieves:
    - vendorLocationScheduleDetail: Standard delivery schedules
    - scheduleOverrideRowList: Holiday/override schedules
    
    Note: Exact endpoint path may need to be confirmed.
    Common patterns: /vendorlocation/v1/getVendorLocations or /vendorlocation/v1/getAllVendorLocations
    
    Args:
        locationCode: Filter by specific location (optional)
        vendorCode: Filter by specific vendor (optional)
    
    Returns:
        Vendor-location data with schedules
    """
    # Try common endpoint patterns - may need adjustment based on actual API
    url = f"{BASE_URL}/vendorlocation/v1/getVendorLocations"
    
    params = {}
    if locationCode:
        params["locationCode"] = locationCode
    if vendorCode:
        params["vendorCode"] = vendorCode
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                url,
                headers=ct_headers(token_override=service_token("vendorlocation")),
                params=params
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                "source": "crunchtime",
                "service": "vendorlocation",
                "count": (len(data) if isinstance(data, list) else None),
                "data": data if isinstance(data, list) else [data]
            }
    except httpx.HTTPStatusError as e:
        # If endpoint doesn't exist, try alternatives
        if e.response.status_code == 404:
            alternatives = [
                f"{BASE_URL}/vendorlocation/v1/getAllVendorLocations",
                f"{BASE_URL}/vendorlocation/v1/getVendorLocationSchedules",
            ]
            for url_alt in alternatives:
                try:
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        resp = await client.get(
                            url_alt,
                            headers=ct_headers(token_override=service_token("vendorlocation")),
                            params=params
                        )
                        resp.raise_for_status()
                        data = resp.json()
                        return {
                            "source": "crunchtime",
                            "service": "vendorlocation",
                            "count": (len(data) if isinstance(data, list) else None),
                            "data": data if isinstance(data, list) else [data]
                        }
                except Exception:
                    continue
            raise HTTPException(status_code=404, detail="Vendor location endpoint not found. Please confirm endpoint path.")
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/filtered", response_model=ScheduleResponse)
async def get_filtered_schedules(filter: ScheduleFilter):
    """
    Get schedules filtered by location, vendor, state, DC, and days.
    
    This endpoint applies client-side filtering to vendor-location data.
    For production, consider implementing server-side filtering for better performance.
    
    Args:
        filter: Filter criteria
    
    Returns:
        Filtered schedule data
    """
    # First, get all vendor-location data
    # In production, this should be optimized with server-side filtering
    try:
        url = f"{BASE_URL}/vendorlocation/v1/getVendorLocations"
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                url,
                headers=ct_headers(token_override=service_token("vendorlocation")),
            )
            resp.raise_for_status()
            all_data = resp.json()
            data_list = all_data if isinstance(all_data, list) else [all_data]
            
            # Apply filters
            filtered_data = []
            for item in data_list:
                # Location filter
                if filter.locationCodes and item.get("locationCode") not in filter.locationCodes:
                    continue
                
                # Vendor filter
                if filter.vendorCodes and item.get("vendorCode") not in filter.vendorCodes:
                    continue
                
                # State filter (would need to join with location data)
                # This is a simplified version - may need enhancement
                
                # DC filter
                if filter.distributionCenters and item.get("distributionCenterCode") not in filter.distributionCenters:
                    continue
                
                # Day filters would need to check schedule details
                # This requires understanding the schedule structure
                
                filtered_data.append(item)
            
            return {
                "source": "crunchtime",
                "service": "vendorlocation",
                "count": len(filtered_data),
                "data": filtered_data
            }
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
