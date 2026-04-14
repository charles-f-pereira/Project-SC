"""Crunchtime confirm receipt standard API (sync httpx)."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

import httpx

from app.core.crunchtime_api import ct_headers, service_token

logger = logging.getLogger(__name__)

GET_ALL_CONFIRM_RECEIPTS_STANDARD_PATH = (
    "/confirmreceiptstandard/v1/getAllConfirmReceiptsStandard"
)


@dataclass(frozen=True)
class ConfirmReceiptLookupResult:
    """Outcome of a single PO confirm-receipt GET."""

    http_status: int
    confirmed: bool
    confirm_receipt_utc: datetime | None
    raw_body_snippet: str


def _parse_confirm_receipt_date(value: str) -> datetime | None:
    """
    Parse CT confirmReceiptDate (naive string from API).
    Try US-style first (CT samples), then ISO, then day-first.
    Stored as UTC (CT does not document TZ; treated as UTC).
    """
    text = (value or "").strip()
    if not text:
        return None
    formats = (
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y",
    )
    for fmt in formats:
        try:
            naive = datetime.strptime(text, fmt)
            return naive.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    logger.warning("confirm_receipt_ct: unparseable confirmReceiptDate %r", text)
    return None


def _get_ci(d: dict[str, Any], *names: str) -> Any:
    """First dict value whose key matches one of names case-insensitively."""
    lower = {k.lower(): v for k, v in d.items()}
    for n in names:
        v = lower.get(n.lower())
        if v is not None:
            return v
    return None


def _coerce_to_receipt_list(payload: Any) -> list[Any] | None:
    """CT may return a bare array or wrap rows in a single-key object."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for v in payload.values():
            if isinstance(v, list) and len(v) > 0:
                return v
    return None


def _extract_first_detail(payload: Any) -> dict[str, Any] | None:
    rows = _coerce_to_receipt_list(payload)
    if not rows or len(rows) == 0:
        return None
    first = rows[0]
    if not isinstance(first, dict):
        return None
    block = _get_ci(first, "confirmReceiptStandardHeaderDetails")
    if isinstance(block, dict):
        return block
    # Some payloads may flatten header fields onto the row object
    if _get_ci(first, "confirmReceiptDate") is not None:
        return first
    return None


def fetch_confirm_receipt_for_po_sync(
    client: httpx.Client, purchase_order_number: str
) -> ConfirmReceiptLookupResult:
    """
    GET getAllConfirmReceiptsStandard for one purchaseOrderNumber (transactionNo).

    200 + non-empty array with confirmReceiptDate -> confirmed.
    200 + [] -> not confirmed.
    404 -> not confirmed.
    """
    po = (purchase_order_number or "").strip()
    if not po:
        return ConfirmReceiptLookupResult(
            http_status=0,
            confirmed=False,
            confirm_receipt_utc=None,
            raw_body_snippet="",
        )

    token = service_token("confirmreceiptstandard")
    headers = {
        **ct_headers(token_override=token),
        "accept": "application/json",
    }
    url = (
        f"{GET_ALL_CONFIRM_RECEIPTS_STANDARD_PATH}"
        f"?purchaseOrderNumber={quote(po, safe='')}"
    )
    snippet = ""
    try:
        r = client.get(url, headers=headers)
        snippet = (r.text or "")[:500]
        if r.status_code == 404:
            return ConfirmReceiptLookupResult(
                http_status=404,
                confirmed=False,
                confirm_receipt_utc=None,
                raw_body_snippet=snippet,
            )
        if r.status_code != 200:
            logger.warning(
                "confirm_receipt_ct: unexpected status=%s po=%s body=%s",
                r.status_code,
                po,
                snippet,
            )
            return ConfirmReceiptLookupResult(
                http_status=r.status_code,
                confirmed=False,
                confirm_receipt_utc=None,
                raw_body_snippet=snippet,
            )
        try:
            payload = r.json()
        except json.JSONDecodeError:
            logger.warning(
                "confirm_receipt_ct: invalid JSON po=%s body=%s", po, snippet
            )
            return ConfirmReceiptLookupResult(
                http_status=200,
                confirmed=False,
                confirm_receipt_utc=None,
                raw_body_snippet=snippet,
            )

        detail = _extract_first_detail(payload)
        if detail is None:
            logger.warning(
                "confirm_receipt_ct: 200 but no receipt header po=%s snippet=%s",
                po,
                snippet[:240],
            )
            return ConfirmReceiptLookupResult(
                http_status=200,
                confirmed=False,
                confirm_receipt_utc=None,
                raw_body_snippet=snippet,
            )

        date_raw = _get_ci(detail, "confirmReceiptDate")
        if date_raw is None:
            logger.warning(
                "confirm_receipt_ct: 200 but no confirmReceiptDate po=%s snippet=%s",
                po,
                snippet[:240],
            )
            return ConfirmReceiptLookupResult(
                http_status=200,
                confirmed=False,
                confirm_receipt_utc=None,
                raw_body_snippet=snippet,
            )
        if not isinstance(date_raw, str):
            date_raw = str(date_raw).strip()

        parsed = _parse_confirm_receipt_date(date_raw)
        if parsed is None:
            return ConfirmReceiptLookupResult(
                http_status=200,
                confirmed=False,
                confirm_receipt_utc=None,
                raw_body_snippet=snippet,
            )

        return ConfirmReceiptLookupResult(
            http_status=200,
            confirmed=True,
            confirm_receipt_utc=parsed,
            raw_body_snippet=snippet,
        )
    except httpx.RequestError as e:
        logger.warning("confirm_receipt_ct: request error po=%s: %s", po, e)
        return ConfirmReceiptLookupResult(
            http_status=0,
            confirmed=False,
            confirm_receipt_utc=None,
            raw_body_snippet=str(e),
        )
