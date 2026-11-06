"""Behavioural checks for the shared retry backoff helper."""

from gcp.retry import DEFAULT_MAX_BACKOFF, compute_backoff


def test_backoff_jitter_stays_within_one_second_of_delay():
    """Jitter adds between 0 and 1 second and the next delay doubles."""
    for _ in range(500):
        sleep_time, next_delay = compute_backoff(2.0, DEFAULT_MAX_BACKOFF)
        assert 2.0 <= sleep_time <= 3.0
        assert next_delay == 4.0


def test_backoff_next_delay_is_capped_at_max_backoff():
    """Doubling stops at the configured maximum."""
    sleep_time, next_delay = compute_backoff(50.0, 60.0)
    assert 50.0 <= sleep_time <= 51.0
    assert next_delay == 60.0


def test_backoff_sleep_is_capped_at_max_backoff():
    """Jitter never pushes the sleep past the configured maximum."""
    for _ in range(100):
        sleep_time, next_delay = compute_backoff(60.0, 60.0)
        assert sleep_time == 60.0
        assert next_delay == 60.0
