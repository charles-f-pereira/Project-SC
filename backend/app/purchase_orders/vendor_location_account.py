"""CrunchTime getAllVendorLocation helper for account number (shared by purchase order routes)."""

from __future__ import annotations

from app.core.crunchtime_api import ct_headers, get_async_client, service_token

GET_ALL_VENDOR_LOCATION_PATH = "/vendorlocation/v1/getAllVendorLocation"
CT_VENDOR_LOCATION_FIXED_PARAMS = {
    "activeFlag": "true",
    "includeDetails": "true",
    "includeNull": "false",
}


def _normalize_vendor_location_response(data) -> list:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in (
            "data",
            "vendorLocations",
            "VendorLocations",
            "locations",
            "Locations",
        ):
            val = data.get(key)
            if isinstance(val, list):
                return val
        return [data]
    return []


async def fetch_account_number_for_location(
    location_code: str, vendor_code: str
) -> str | None:
    if not (location_code and location_code.strip()) or not (
        vendor_code and vendor_code.strip()
    ):
        return None
    params = dict(CT_VENDOR_LOCATION_FIXED_PARAMS)
    params["locationCode"] = location_code.strip()
    headers = {
        **ct_headers(token_override=service_token("vendorlocation")),
        "accept": "application/json",
    }
    try:
        async with get_async_client() as client:
            resp = await client.get(
                GET_ALL_VENDOR_LOCATION_PATH,
                params=params,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        return None
    items = _normalize_vendor_location_response(data)
    want = (vendor_code or "").strip()
    for raw in items:
        if not isinstance(raw, dict):
            continue
        header = (
            raw.get("vendorLocationHeaderDetails")
            or raw.get("VendorLocationHeaderDetails")
            or {}
        )
        vc = (
            header.get("vendorCode")
            or header.get("VendorCode")
            or raw.get("vendorCode")
            or raw.get("VendorCode")
            or ""
        )
        if (vc or "").strip() != want:
            continue
        trans = (
            raw.get("vendorLocationTransmissionDetail")
            or raw.get("VendorLocationTransmissionDetail")
            or {}
        )
        acc = trans.get("accountNumber") or trans.get("AccountNumber")
        if acc is not None and str(acc).strip():
            return str(acc).strip()
        return None
    return None
