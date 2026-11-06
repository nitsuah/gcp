"""Behavioural checks for the shared retry backoff helper."""

from gcp.retry import DEFAULT_MAX_BACKOFF, compute_backoff


def test_backoff_jitter_stays_within_one_second_of_delay():
    for _ in range(500):
        sleep_time, next_delay = compute_backoff(2.0, DEFAULT_MAX_BACKOFF)
        assert 2.0 <= sleep_time <= 3.0
        assert next_delay == 4.0


def test_backoff_is_capped_at_max_backoff():
    sleep_time, next_delay = compute_backoff(50.0, 60.0)
    assert 50.0 <= sleep_time <= 60.0
    assert next_delay == 60.0
