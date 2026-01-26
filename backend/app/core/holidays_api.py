import httpx
from .config import API_NINJAS_KEY

PUBLIC_HOLIDAYS_BASE_URL = "https://api.api-ninjas.com/v1"


async def get_public_holidays(country: str = "AU", year: int | None = None) -> list[dict]:
    """
    Fetch public holidays from api-ninjas.com
    
    Args:
        country: Country code (default: AU)
        year: Year to fetch holidays for (default: current year)
    
    Returns:
        List of holiday dictionaries with date, name, etc.
    """
    if not API_NINJAS_KEY:
        raise ValueError("API_NINJAS_KEY not configured")
    
    import datetime
    if year is None:
        year = datetime.datetime.now().year
    
    url = f"{PUBLIC_HOLIDAYS_BASE_URL}/publicholidays"
    headers = {
        "X-Api-Key": API_NINJAS_KEY
    }
    params = {
        "country": country,
        "year": year
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, headers=headers, params=params)
        resp.raise_for_status()
        return resp.json() if resp.content else []
