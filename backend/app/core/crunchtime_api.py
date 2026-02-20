from __future__ import annotations

import httpx

from .config import (
    AUTH_TOKEN,
    BASE_URL,
    COMPANY_PRODUCT_ENHANCED_TOKEN,
    HIERARCHY_TOKEN,
    PASSWORD,
    PURCHASE_ORDERS_TOKEN,
    SITE_NAME,
    USER_ID,
    VENDOR_LOCATION_TOKEN,
    VENDOR_PRODUCT_PRICING_TOKEN,
    VENDOR_TOKEN,
)


def _require(value: str | None, name: str) -> str:
    if value is None or value == "":
        raise RuntimeError(f"Missing required configuration value: {name}")
    return value


def service_token(service_key: str | None) -> str:
    """
    Resolve a CrunchTime token for a specific service using explicit env vars
    when available, otherwise fall back to the global AUTH_TOKEN.
    """
    auth = _require(AUTH_TOKEN, "AUTH_TOKEN")

    if service_key:
        key = service_key.lower()
        explicit_map: dict[str, str] = {
            "hierarchy": _require(HIERARCHY_TOKEN, "HIERARCHY_TOKEN")
            if HIERARCHY_TOKEN
            else auth,
            "vendor": _require(VENDOR_TOKEN, "VENDOR_TOKEN") if VENDOR_TOKEN else auth,
            "vendorlocation": _require(VENDOR_LOCATION_TOKEN, "VENDOR_LOCATION_TOKEN")
            if VENDOR_LOCATION_TOKEN
            else auth,
            "location": auth,
            "companyproduct": _require(
                COMPANY_PRODUCT_ENHANCED_TOKEN, "COMPANY_PRODUCT_ENHANCED_TOKEN"
            )
            if COMPANY_PRODUCT_ENHANCED_TOKEN
            else auth,
            "vendorproductpricing": _require(
                VENDOR_PRODUCT_PRICING_TOKEN, "VENDOR_PRODUCT_PRICING_TOKEN"
            )
            if VENDOR_PRODUCT_PRICING_TOKEN
            else auth,
            "purchaseorder": _require(PURCHASE_ORDERS_TOKEN, "PURCHASE_ORDERS_TOKEN")
            if PURCHASE_ORDERS_TOKEN
            else auth,
            "purchaseorders": _require(PURCHASE_ORDERS_TOKEN, "PURCHASE_ORDERS_TOKEN")
            if PURCHASE_ORDERS_TOKEN
            else auth,
        }
        return explicit_map.get(key, auth)

    return auth


def ct_headers(token_override: str | None = None) -> dict[str, str]:
    """CrunchTime requires these four fields on every request."""
    return {
        "authenticationtoken": token_override or _require(AUTH_TOKEN, "AUTH_TOKEN"),
        "sitename": _require(SITE_NAME, "SITE_NAME"),
        "userid": _require(USER_ID, "USER_ID"),
        "password": _require(PASSWORD, "PASSWORD"),
    }


def ct_headers_with_credentials(
    user_id: str,
    password: str,
    token_override: str | None = None,
) -> dict[str, str]:
    """Build CrunchTime headers using supplied credentials instead of server defaults."""
    return {
        "authenticationtoken": token_override or _require(AUTH_TOKEN, "AUTH_TOKEN"),
        "sitename": _require(SITE_NAME, "SITE_NAME"),
        "userid": user_id,
        "password": password,
    }


def get_async_client(timeout_seconds: float = 30.0) -> httpx.AsyncClient:
    """Create an AsyncClient preconfigured with the CrunchTime base URL."""
    return httpx.AsyncClient(
        base_url=_require(BASE_URL, "BASE_URL"), timeout=timeout_seconds
    )
