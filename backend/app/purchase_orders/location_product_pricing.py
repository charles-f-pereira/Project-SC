"""
Crunchtime saveLocationProductPricing: activate (reOrderVoFlag Y) or deactivate (N) VO ordering
for a location/product(s). Used before savePurchaseOrders for TempActivateVO products, then
deactivate after PO success.
"""

import logging
from typing import List, Tuple

import httpx

from app.core.config import BASE_URL
from app.core.crunchtime_api import ct_headers, service_token

logger = logging.getLogger("app.purchase_orders.location_product_pricing")

SAVE_LOCATION_PRODUCT_PRICING_PATH = "/locationproductpricing/v1/saveLocationProductPricing"


def _build_payload(location_code: str, product_numbers: List[str], re_order_vo_flag: str) -> dict:
    """Build request body for saveLocationProductPricing."""
    units = [
        {
            "locationCode": location_code,
            "productNumber": pn,
            "reOrderVoFlag": re_order_vo_flag,
        }
        for pn in product_numbers
        if (pn or "").strip()
    ]
    return {
        "locationCode": location_code,
        "locationProductPricingDetails": [
            {"locationProductPricingUnitsDetails": units}
        ],
    }


def save_location_product_pricing_sync(
    location_code: str,
    product_numbers: List[str],
    re_order_vo_flag: str,
) -> Tuple[bool, int, str]:
    """
    Call Crunchtime saveLocationProductPricing (sync). Used by scheduler and by routes via asyncio.to_thread.
    Returns (success, status_code, message).
    """
    location_code = (location_code or "").strip()
    if not location_code or not product_numbers:
        return True, 200, "No products to update"
    product_numbers = [str(p).strip() for p in product_numbers if (p or "").strip()]
    if not product_numbers:
        return True, 200, "No products to update"
    flag = "Y" if (re_order_vo_flag or "").strip().upper() == "Y" else "N"
    payload = _build_payload(location_code, product_numbers, flag)
    token = service_token("locationproductpricing")
    headers = {
        **ct_headers(token_override=token),
        "accept": "application/json",
        "content-type": "application/json",
    }
    logger.info(
        "saveLocationProductPricing: location=%s products=%s reOrderVoFlag=%s",
        location_code,
        product_numbers,
        flag,
    )
    try:
        with httpx.Client(base_url=BASE_URL, timeout=30.0) as client:
            r = client.post(
                SAVE_LOCATION_PRODUCT_PRICING_PATH,
                json=payload,
                headers=headers,
            )
        if r.status_code == 200:
            logger.info(
                "saveLocationProductPricing: success location=%s reOrderVoFlag=%s",
                location_code,
                flag,
            )
            return True, r.status_code, r.text or ""
        logger.warning(
            "saveLocationProductPricing: failed location=%s status=%s body=%s",
            location_code,
            r.status_code,
            (r.text or "")[:500],
        )
        return False, r.status_code, r.text or ""
    except Exception as e:
        logger.exception(
            "saveLocationProductPricing: error location=%s reOrderVoFlag=%s: %s",
            location_code,
            flag,
            e,
        )
        return False, 0, str(e)
