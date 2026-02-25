from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from app.core.holidays_api import get_public_holidays
from .schemas import HolidaysResponse, HolidaysMultiResponse

router = APIRouter()

# Supported country codes for public holidays (api-ninjas)
SUPPORTED_COUNTRY_CODES = {"AU", "US"}


@router.get("", response_model=HolidaysResponse)
async def get_holidays(country: str = "AU"):
    """
    Get public holidays for a given country (trial API: country only).

    Args:
        country: Country code (AU or US)

    Returns:
        List of public holidays
    """
    try:
        country_upper = country.upper()
        if country_upper not in SUPPORTED_COUNTRY_CODES:
            raise HTTPException(
                status_code=400,
                detail=f"Country must be one of: {', '.join(sorted(SUPPORTED_COUNTRY_CODES))}",
            )

        holidays = await get_public_holidays(country=country_upper)

        return {
            "source": "api-ninjas",
            "country": country_upper,
            "count": len(holidays),
            "data": holidays,
        }
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/fetch", response_model=HolidaysMultiResponse)
async def fetch_holidays(
    countries: Optional[str] = Query(
        None, description="Comma-separated country codes (AU,US). Default: AU,US"
    ),
):
    """
    Manually fetch public holidays for one or more countries (trial API: country only).
    Does not run automatically - call this endpoint when user clicks "Fetch PH data".

    Args:
        countries: Comma-separated country codes, e.g. "AU,US" (default: AU,US)

    Returns:
        Combined list of public holidays for all requested countries
    """
    try:
        if countries:
            country_list = [
                c.strip().upper() for c in countries.split(",") if c.strip()
            ]
        else:
            country_list = ["AU", "US"]

        # Validate and filter to supported only
        country_list = [c for c in country_list if c in SUPPORTED_COUNTRY_CODES]
        if not country_list:
            raise HTTPException(
                status_code=400,
                detail=f"At least one supported country required: {', '.join(sorted(SUPPORTED_COUNTRY_CODES))}",
            )

        all_holidays = []
        for country in country_list:
            holidays = await get_public_holidays(country=country)
            for h in holidays:
                h_copy = dict(h)
                h_copy["country"] = country
                all_holidays.append(h_copy)

        return {
            "source": "api-ninjas",
            "countries": country_list,
            "count": len(all_holidays),
            "data": all_holidays,
        }
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
