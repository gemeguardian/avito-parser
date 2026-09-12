"""
Unit tests for RateLimiter and RateLimitProfile.
"""
import pytest
from avito_parser.rate_limiter import RateLimiter, RateLimitProfile, get_profile_config


def test_rate_limiter_backoff():
    limiter = RateLimiter(min_delay=1.0, max_delay=2.0, backoff_factor=2.0, max_backoff=10.0)
    assert limiter._current_backoff == 0.0

    limiter.register_rate_limit()
    assert limiter._current_backoff == 4.0  # max_delay * 2.0

    limiter.register_rate_limit()
    assert limiter._current_backoff == 8.0

    limiter.register_rate_limit()
    assert limiter._current_backoff == 10.0  # max_backoff cap

    limiter.register_success()
    assert limiter._current_backoff == 9.0  # decay by min_delay

    limiter.reset()
    assert limiter._current_backoff == 0.0


def test_rate_limit_profiles():
    stealth = get_profile_config(RateLimitProfile.STEALTH)
    assert stealth.min_delay == 3.5
    assert stealth.max_delay == 6.5
    assert stealth.jitter == 0.5

    balanced = get_profile_config("balanced")
    assert balanced.min_delay == 2.5
    assert balanced.max_delay == 4.5

    fast = get_profile_config("fast")
    assert fast.min_delay == 0.8
    assert fast.max_delay == 1.8

    dc = get_profile_config("datacenter")
    assert dc.min_delay == 4.5
    assert dc.max_delay == 8.5

    with pytest.raises(ValueError):
        get_profile_config("unknown_profile")


def test_rate_limiter_from_profile():
    limiter = RateLimiter.from_profile("stealth")
    assert limiter.min_delay == 3.5
    assert limiter.max_delay == 6.5
    assert limiter.jitter == 0.5
    assert limiter.wait_count == 0
    assert limiter.total_waited == 0.0
    assert limiter.average_delay == 0.0


def test_rate_limiter_metrics():
    limiter = RateLimiter(min_delay=0.02, max_delay=0.03, jitter=0.0)
    w1 = limiter.wait()  # First request executes immediately
    assert w1 == 0.0
    w2 = limiter.wait()  # Second request waits min_delay
    assert w2 >= 0.015
    assert limiter.wait_count == 2
    assert limiter.total_waited == w1 + w2
    assert limiter.average_delay == (w1 + w2) / 2
