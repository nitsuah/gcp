"""Shared retry-with-backoff helper for Google Drive API requests."""

import logging
import random
import time
from typing import Callable

from googleapiclient.errors import HttpError

DEFAULT_MAX_BACKOFF = 60.0


def compute_backoff(delay: float, max_backoff: float) -> tuple:
    """
    Return (sleep_time, next_delay) for one exponential-backoff-with-jitter
    step, without sleeping -- shared by every retry loop in this module and
    in copy_folder.py so the jitter/doubling math has exactly one definition.
    """
    sleep_time = min(delay + random.uniform(0, 1), max_backoff)
    next_delay = min(delay * 2, max_backoff)
    return sleep_time, next_delay


def retry_log_and_sleep(
    log_level: int,
    subject: str,
    attempt: int,
    max_retries: int,
    err: Exception,
    delay: float,
    max_backoff: float,
) -> float:
    """
    Log one retry attempt and sleep for the computed backoff. Returns the
    next delay value for the caller's loop. `subject` is a short description
    of what's being retried (e.g. "Rate limited" or "Error copying foo.txt")
    -- this is the one place every retry loop in the codebase logs and
    sleeps, so that shape has exactly one definition for pylint to see.
    """
    sleep_time, next_delay = compute_backoff(delay, max_backoff)
    logging.log(
        log_level,
        "%s (attempt %d/%d, retry in %.1fs): %s",
        subject,
        attempt + 1,
        max_retries,
        sleep_time,
        err,
    )
    time.sleep(sleep_time)
    return next_delay


def call_with_rate_limit_retry(
    request_factory: Callable, max_retries: int = 3, max_backoff: float = DEFAULT_MAX_BACKOFF
):
    """
    Execute request_factory().execute(), retrying with exponential backoff on
    a 429/503 rate-limit response. Non-rate-limit HttpErrors are re-raised
    immediately; a rate limit that survives every retry is also re-raised
    (to the caller, which decides whether that's fatal for its operation).
    """
    delay = 1.0
    for attempt in range(max_retries):
        try:
            return request_factory().execute()
        except HttpError as err:
            is_rate_limit = getattr(err, "resp", None) is not None and err.resp.status in (429, 503)
            if is_rate_limit and attempt < max_retries - 1:
                delay = retry_log_and_sleep(
                    logging.WARNING, "Rate limited", attempt, max_retries, err, delay, max_backoff
                )
                continue
            raise
    return None  # unreachable: the loop always returns or raises
