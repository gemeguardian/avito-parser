"""
Unit tests for AvitoParser client initialization, profiles, PoW TTL, and telemetry.
"""
import time
from unittest.mock import MagicMock, patch
import pytest

from avito_parser.client import AvitoParser
from avito_parser.rate_limiter import RateLimitProfile


def test_parser_profile_initialization():
    parser_default = AvitoParser()
    assert parser_default.rate_limiter.min_delay == 2.5
    assert parser_default.rate_limiter.max_delay == 4.5

    parser_stealth = AvitoParser(profile="stealth")
    assert parser_stealth.rate_limiter.min_delay == 3.5
    assert parser_stealth.rate_limiter.max_delay == 6.5

    # Override profile values with explicit params
    parser_custom = AvitoParser(profile="fast", min_delay=1.0, max_delay=3.0)
    assert parser_custom.rate_limiter.min_delay == 1.0
    assert parser_custom.rate_limiter.max_delay == 3.0


def test_pow_ttl_tracking():
    parser = AvitoParser()
    assert parser.pow_solved_at is None
    assert parser.is_pow_expired() is False

    # Simulate PoW solved
    now = time.time()
    parser.pow_solved_at = now

    # Just solved -> not expired
    assert parser.is_pow_expired() is False

    # 395 seconds later -> expired within 30s buffer (420 - 30 = 390s)
    parser.pow_solved_at = now - 395.0
    assert parser.is_pow_expired(buffer_seconds=30.0) is True


def test_parser_metrics():
    parser = AvitoParser(profile="fast")
    metrics = parser.get_metrics()
    assert metrics["total_requests"] == 0
    assert metrics["successful_requests"] == 0
    assert metrics["rate_limits_hit"] == 0
    assert metrics["pow_challenges_solved"] == 0
    assert metrics["total_waited_seconds"] == 0.0
    assert metrics["average_delay_seconds"] == 0.0
