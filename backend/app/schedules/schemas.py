from pydantic import BaseModel
from typing import Optional, List


class ScheduleDetail(BaseModel):
    """Standard schedule detail from vendorLocationScheduleDetail"""
    pass  # Structure will depend on actual API response


class ScheduleOverride(BaseModel):
    """Schedule override from scheduleOverrideRowList"""
    pass  # Structure will depend on actual API response


class VendorLocationSchedule(BaseModel):
    locationCode: str
    vendorCode: Optional[str] = None
    distributionCenterCode: Optional[str] = None
    vendorLocationScheduleDetail: Optional[List[dict]] = None
    scheduleOverrideRowList: Optional[List[dict]] = None


class ScheduleResponse(BaseModel):
    source: str
    service: str
    count: Optional[int] = None
    data: list[dict]


class ScheduleFilter(BaseModel):
    locationCodes: Optional[List[str]] = None
    vendorCodes: Optional[List[str]] = None
    states: Optional[List[str]] = None
    distributionCenters: Optional[List[str]] = None
    deliveryDays: Optional[List[int]] = None  # 0=Monday, 6=Sunday
    orderingDays: Optional[List[int]] = None
