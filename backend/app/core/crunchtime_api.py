from __future__ import annotations

import os
import httpx
from .config import (
    BASE_URL, AUTH_TOKEN, SITE_NAME, USER_ID, PASSWORD,
    HIERARCHY_TOKEN, VENDOR_TOKEN, VENDOR_LOCATION_TOKEN
)


def service_token(service_key: str | None) -> str:
    """
    Resolve a CrunchTime token for a specific service using explicit env vars
    when available, otherwise fall back to the global AUTH_TOKEN.
    """
    if service_key:
        key = service_key.lower()
        explicit_map = {
            "hierarchy": HIERARCHY_TOKEN or AUTH_TOKEN,
            "vendor": VENDOR_TOKEN or AUTH_TOKEN,
            "vendorlocation": VENDOR_LOCATION_TOKEN or AUTH_TOKEN,
            "location": AUTH_TOKEN,
        }
        return explicit_map.get(key, AUTH_TOKEN)
    return AUTH_TOKEN


def ct_headers(token_override: str | None = None) -> dict:
    """CrunchTime requires these four fields on every request."""
    return {
        "authenticationtoken": token_override or AUTH_TOKEN,
        "sitename": SITE_NAME,
        "userid": USER_ID,
        "password": PASSWORD,
    }


def ct_headers_with_credentials(
    user_id: str,
    password: str,
    token_override: str | None = None,
) -> dict:
    """Build CrunchTime headers using supplied credentials instead of server defaults."""
    return {
        "authenticationtoken": token_override or AUTH_TOKEN,
        "sitename": SITE_NAME,
        "userid": user_id,
        "password": password,
    }


def get_async_client(timeout_seconds: float = 30.0) -> httpx.AsyncClient:
    """Create an AsyncClient preconfigured with the CrunchTime base URL."""
    return httpx.AsyncClient(base_url=BASE_URL, timeout=timeout_seconds)
