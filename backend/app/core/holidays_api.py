import httpx
from .config import API_NINJAS_KEY

PUBLIC_HOLIDAYS_BASE_URL = "https://api.api-ninjas.com/v1"


async def get_public_holidays(country: str = "AU") -> list[dict]:
    """
    Fetch public holidays from api-ninjas.com (trial API: country only, no year).
    
    Args:
        country: Country code (default: AU)
    
    Returns:
        List of holiday dictionaries with date, name, etc.
    """
    if not API_NINJAS_KEY:
        raise ValueError("API_NINJAS_KEY not configured")
    
    url = f"{PUBLIC_HOLIDAYS_BASE_URL}/publicholidays"
    headers = {
        "X-Api-Key": API_NINJAS_KEY
    }
    params = {
        "country": country
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, headers=headers, params=params)
        resp.raise_for_status()
        return resp.json() if resp.content else []
