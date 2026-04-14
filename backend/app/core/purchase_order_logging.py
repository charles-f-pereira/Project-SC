"""Structured JSON-line logging for purchase order submit (see backend/logs/purchase_orders.log)."""

from __future__ import annotations

import json
import logging
from typing import Any

_logger = logging.getLogger("app.purchase_orders")


def po_submit_log(event: str, **fields: Any) -> None:
    payload = {"component": "purchase_orders_submit", "event": event, **fields}
    _logger.info(json.dumps(payload, default=str))
