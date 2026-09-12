"""
Unit tests for ProxyConfig and ProxyManager.
"""
from avito_parser.proxy import ProxyConfig, ProxyManager


def test_proxy_normalization():
    p1 = ProxyConfig("socks5://1.2.3.4:1080")
    assert p1.url == "socks5h://1.2.3.4:1080"

    p2 = ProxyConfig("1.2.3.4:8080:user:pass")
    assert p2.url == "socks5h://user:pass@1.2.3.4:8080"

    p3 = ProxyConfig("1.2.3.4:3128")
    assert p3.url == "http://1.2.3.4:3128"


def test_proxy_manager_rotation():
    proxies = ["http://1.1.1.1:8080", "http://2.2.2.2:8080", "http://3.3.3.3:8080"]
    pm = ProxyManager(proxies, max_fails=2)
    assert len(pm) == 3

    seen = [pm.get_proxy().url for _ in range(3)]
    assert "http://1.1.1.1:8080" in seen
    assert "http://2.2.2.2:8080" in seen
    assert "http://3.3.3.3:8080" in seen


def test_proxy_manager_failover():
    proxies = ["http://1.1.1.1:8080", "http://2.2.2.2:8080"]
    pm = ProxyManager(proxies, max_fails=2)

    p1 = pm.get_proxy()
    pm.mark_failure(p1)
    assert p1.is_active is True
    pm.mark_failure(p1)
    assert p1.is_active is False

    # Now only p2 should be returned
    p2 = pm.get_proxy()
    assert p2.url == "http://2.2.2.2:8080"
