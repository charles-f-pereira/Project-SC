from pydantic import BaseModel
from typing import Optional, List

# Day value mapping (Crunchtime): Sunday=1, Monday=2, ..., Saturday=7,
# Sunday following=8, Monday following=9, ..., Saturday=21


class ScheduleDetail(BaseModel):
    """
    Standard schedule detail from vendorLocationScheduleDetail.
    Fields use orderDay*Flag, orderByTime*, deliverDay* for each weekday.
    Day values: 1=Sun, 2=Mon, 3=Tue, 4=Wed, 5=Thu, 6=Fri, 7=Sat,
    8=Sun next week, ..., 21=Sat week+2.
    """

    # Allow arbitrary fields - API may use camelCase or PascalCase
    model_config = {"extra": "allow"}


class ScheduleOverride(BaseModel):
    """Schedule override from scheduleOverrideRowList - to be implemented later."""

    model_config = {"extra": "allow"}


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
    deliveryDays: Optional[List[int]] = (
        None  # 0=Monday, 6=Sunday (FilterPanel convention)
    )
    orderingDays: Optional[List[int]] = None
