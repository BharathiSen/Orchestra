"""Structured observability logger (stdout JSON-ish lines)."""

from __future__ import annotations

import json
import logging
from typing import Any

_logger = logging.getLogger("orchestra.observability")
if not _logger.handlers:
    handler = logging.StreamHandler()
    # Emit the JSON payload verbatim so log shippers can parse it as-is.
    handler.setFormatter(logging.Formatter("%(message)s"))
    _logger.addHandler(handler)
    _logger.setLevel(logging.INFO)
    # Without this, records reach both this handler and the root handler
    # configured in main.py, printing every event twice.
    _logger.propagate = False


def log_event(event: str, **fields: Any) -> None:
    payload = {"event": event, **fields}
    try:
        _logger.info(json.dumps(payload, default=str))
    except Exception:  # noqa: BLE001
        _logger.info("%s %s", event, fields)
