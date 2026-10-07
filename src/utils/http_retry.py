"""Bounded HTTP retries shared by translation and summary requests."""

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import math

import aiohttp
import requests


RETRYABLE_STATUSES = {429, 502, 503, 504}


def is_retryable(error):
    """Retry connection/time-out failures and temporary HTTP failures only."""
    if isinstance(error, aiohttp.ClientResponseError):
        return error.status in RETRYABLE_STATUSES
    if isinstance(error, requests.exceptions.HTTPError):
        return error.response is not None and error.response.status_code in RETRYABLE_STATUSES
    return True


def retry_delay(error, attempt, now=None):
    """Honor Retry-After seconds/date; otherwise use 5/10-second backoff."""
    headers = getattr(error, "headers", None)
    if isinstance(error, requests.exceptions.HTTPError) and error.response is not None:
        headers = error.response.headers
    value = (headers or {}).get("Retry-After")
    if value is None:
        value = (headers or {}).get("retry-after")
    if value is not None:
        try:
            seconds = float(value)
            if math.isfinite(seconds) and seconds >= 0:
                return seconds
        except (TypeError, ValueError):
            pass
        try:
            when = parsedate_to_datetime(value)
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            current = datetime.now(timezone.utc) if now is None else now
            return max(0.0, (when - current).total_seconds())
        except (TypeError, ValueError, OverflowError):
            pass
    return min(5.0 * 2 ** (attempt - 1), 60.0)
