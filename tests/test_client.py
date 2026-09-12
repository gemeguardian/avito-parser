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


def test_parser_cookies_support():
    parser_dict = AvitoParser(cookies={"test_cookie": "123", "session": "abc"})
    assert parser_dict.session.cookies.get("test_cookie") == "123"
    assert parser_dict.session.cookies.get("session") == "abc"

    parser_str = AvitoParser(cookies="foo=bar; baz=qux")
    assert parser_str.session.cookies.get("foo") == "bar"
    assert parser_str.session.cookies.get("baz") == "qux"



def test_search_url_building():
    parser = AvitoParser()

    with patch.object(parser, "search_by_url") as mock_search_by_url:
        mock_search_by_url.return_value = MagicMock()

        # Simple query
        parser.search(query="ThinkBook", location="moskva")
        mock_search_by_url.assert_called_with("https://www.avito.ru/moskva?q=ThinkBook", page=1)

        # Query with filters
        parser.search(
            query="RTX 4060",
            location="nizhniy_novgorod",
            category="noutbuki",
            price_min=50000,
            price_max=90000,
            sort="price_asc",
            page=2,
        )
        called_url = mock_search_by_url.call_args[0][0]
        assert "nizhniy_novgorod/noutbuki" in called_url
        assert "q=RTX+4060" in called_url
        assert "p=2" in called_url
        assert "pmin=50000" in called_url
        assert "pmax=90000" in called_url
        assert "s=1" in called_url

