from pydantic import BaseModel
from typing import Optional


class Location(BaseModel):
    code: str
    name: Optional[str] = None
    state: Optional[str] = None
    activeFlag: Optional[bool] = None


class LocationResponse(BaseModel):
    source: str
    service: str
    count: Optional[int] = None
    data: list[dict]
    filter: Optional[dict] = None
