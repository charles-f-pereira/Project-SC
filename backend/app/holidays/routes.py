from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from app.core.holidays_api import get_public_holidays
from .schemas import HolidaysResponse

router = APIRouter()


@router.get("/", response_model=HolidaysResponse)
async def get_holidays(country: str = "AU", year: Optional[int] = None):
    """
    Get public holidays for a given country and year.
    
    Args:
        country: Country code (default: AU)
        year: Year to fetch holidays for (default: current year)
    
    Returns:
        List of public holidays
    """
    try:
        import datetime
        if year is None:
            year = datetime.datetime.now().year
        
        holidays = await get_public_holidays(country=country, year=year)
        
        return {
            "source": "api-ninjas",
            "country": country,
            "year": year,
            "count": len(holidays),
            "data": holidays
        }
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
