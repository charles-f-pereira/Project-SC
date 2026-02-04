from pydantic import BaseModel
from typing import Optional, List
from datetime import date


class PublicHoliday(BaseModel):
    date: str
    name: str
    country: str


class HolidaysResponse(BaseModel):
    source: str
    country: str
    count: int
    data: list[dict]


class HolidaysMultiResponse(BaseModel):
    source: str
    countries: List[str]
    count: int
    data: list[dict]
