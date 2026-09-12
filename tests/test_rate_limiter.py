"""
Unit tests for RateLimiter.
"""
from avito_parser.rate_limiter import RateLimiter


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
