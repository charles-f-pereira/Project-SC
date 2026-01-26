from pydantic import BaseModel
from typing import Optional


class Vendor(BaseModel):
    code: str
    name: Optional[str] = None
    activeFlag: Optional[bool] = None


class DistributionCenter(BaseModel):
    code: str
    name: Optional[str] = None
    state: Optional[str] = None
    vendorCode: Optional[str] = None


class VendorResponse(BaseModel):
    source: str
    service: str
    count: Optional[int] = None
    data: list[dict]


class HierarchyResponse(BaseModel):
    source: str
    service: str
    count: Optional[int] = None
    data: list[dict]
