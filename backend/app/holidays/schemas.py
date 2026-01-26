from pydantic import BaseModel
from typing import Optional
from datetime import date


class PublicHoliday(BaseModel):
    date: str
    name: str
    country: str


class HolidaysResponse(BaseModel):
    source: str
    country: str
    year: int
    count: int
    data: list[dict]
