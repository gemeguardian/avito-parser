"""
Core HTTP client for interacting with Avito.
Orchestrates requests, PoW bypass, rate limiting, and proxy rotation.
"""
import logging
import random
import time
from typing import Callable, Dict, Generator, Iterable, List, Optional, Union
import requests
from urllib.parse import quote_plus

from .models import AvitoItem, SearchResult, SearchResultItem
from .parser import AvitoCatalogParser, AvitoItemParser
from .pow import AvitoPoWSolver
from .proxy import ProxyConfig, ProxyManager
from .rate_limiter import RateLimiter, RateLimitProfile, get_profile_config

logger = logging.getLogger(__name__)

DEFAULT_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
]

# Avito's firewall PoW token unblock lifetime (in seconds)
AVITO_UNBLOCK_TTL_SECONDS = 420.0


class AvitoParser:
    """
    High-level parser client for Avito with integrated anti-bot defenses.
    """

    def __init__(
        self,
        proxies: Optional[Union[str, List[str], ProxyManager]] = None,
        profile: Optional[Union[str, RateLimitProfile]] = None,
        min_delay: Optional[float] = None,
        max_delay: Optional[float] = None,
        timeout: float = 20.0,
        max_retries: int = 3,
        user_agent: Optional[str] = None,
        cookies: Optional[Union[str, Dict[str, str]]] = None,
    ):
        self.timeout = timeout
        self.max_retries = max_retries

        if isinstance(proxies, ProxyManager):
            self.proxy_manager = proxies
        elif proxies:
            self.proxy_manager = ProxyManager(proxies)
        else:
            self.proxy_manager = None

        # Resolve rate limiter profile
        chosen_profile = profile or RateLimitProfile.BALANCED
        self.rate_limiter = RateLimiter.from_profile(chosen_profile)

        # Allow explicit delay overrides
        if min_delay is not None:
            self.rate_limiter.min_delay = min_delay
        if max_delay is not None:
            self.rate_limiter.max_delay = max(self.rate_limiter.min_delay, max_delay)

        self.user_agent = user_agent or random.choice(DEFAULT_USER_AGENTS)

        # PoW Token TTL Tracking
        self.pow_solved_at: Optional[float] = None
        self.pow_unblock_ttl: float = AVITO_UNBLOCK_TTL_SECONDS

        # Request Metrics
        self.metrics: Dict[str, Union[int, float]] = {
            "total_requests": 0,
            "successful_requests": 0,
            "rate_limits_hit": 0,
            "pow_challenges_solved": 0,
        }

        self.session = requests.Session()
        self._setup_session()

        if cookies:
            self._apply_cookies(cookies)

    def _apply_cookies(self, cookies: Union[str, Dict[str, str]]):
        """Load session cookies from string or dict."""
        if isinstance(cookies, dict):
            self.session.cookies.update(cookies)
        elif isinstance(cookies, str):
            for part in cookies.split(";"):
                if "=" in part:
                    k, v = part.strip().split("=", 1)
                    self.session.cookies.set(k.strip(), v.strip(), domain=".avito.ru")

    def _setup_session(self):
        # Resolve platform from User-Agent to avoid WAF header mismatch
        is_mobile = "Mobile" in self.user_agent or "Android" in self.user_agent
        platform = '"Android"' if is_mobile else ('"macOS"' if "Macintosh" in self.user_agent else '"Windows"')
        sec_mobile = "?1" if is_mobile else "?0"

        self.session.headers.update({
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            "Sec-Ch-Ua": '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"',
            "Sec-Ch-Ua-Mobile": sec_mobile,
            "Sec-Ch-Ua-Platform": platform,
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
        })

    def _apply_proxy(self) -> Optional[ProxyConfig]:
        if not self.proxy_manager:
            return None
        proxy_cfg = self.proxy_manager.get_proxy()
        if proxy_cfg:
            self.session.proxies.update(proxy_cfg.to_requests())
        return proxy_cfg

    def is_pow_expired(self, buffer_seconds: float = 30.0) -> bool:
        """
        Check if the PoW session token has expired or is about to expire within buffer_seconds.
        """
        if self.pow_solved_at is None:
            return False
        elapsed = time.time() - self.pow_solved_at
        return elapsed >= (self.pow_unblock_ttl - buffer_seconds)

    def check_pow_ttl(self) -> bool:
        """
        Proactively check and refresh session if PoW token is approaching 420s expiration.
        """
        if self.is_pow_expired():
            logger.info("PoW unblock token is expiring (TTL=%ss). Re-verifying...", self.pow_unblock_ttl)
            self.session.cookies.pop("pow_solved", None)
            self.session.cookies.pop("pow_challenge", None)
            return self.warmup()
        return True

    def warmup(self, base_url: str = "https://www.avito.ru") -> bool:
        """
        Send an initial request to warm up session cookies and resolve any initial challenge.
        """
        logger.info("Warming up session against %s...", base_url)
        try:
            self._apply_proxy()
            self.metrics["total_requests"] += 1
            resp = self.session.get(base_url, timeout=self.timeout)
            if AvitoPoWSolver.is_challenge_response(resp.status_code, resp.text):
                logger.info("PoW challenge triggered during warmup. Solving...")
                solved = AvitoPoWSolver.solve(self.session, resp.text, base_url=base_url)
                if solved:
                    self.pow_solved_at = time.time()
                    self.metrics["pow_challenges_solved"] += 1
                return solved

            if resp.status_code == 200:
                self.metrics["successful_requests"] += 1
                return True
            return False
        except Exception as e:
            logger.warning("Warmup encountered an error: %s", e)
            return False

    def fetch_html(self, url: str) -> Optional[str]:
        """
        Fetch HTML for a given URL with retries, PoW solving, and rate limiting.
        """
        attempt = 0
        while attempt < self.max_retries:
            attempt += 1

            # Proactive TTL maintenance
            self.check_pow_ttl()

            self.rate_limiter.wait()
            current_proxy = self._apply_proxy()

            try:
                self.metrics["total_requests"] += 1
                logger.debug("GET %s (attempt %s/%s, proxy=%s)", url, attempt, self.max_retries, current_proxy)
                resp = self.session.get(url, timeout=self.timeout)

                # Check if PoW challenge
                if AvitoPoWSolver.is_challenge_response(resp.status_code, resp.text):
                    logger.info("Encountered firewall PoW challenge on %s. Resolving...", url)
                    solved = AvitoPoWSolver.solve(self.session, resp.text, timeout=self.timeout)
                    if solved:
                        self.pow_solved_at = time.time()
                        self.metrics["pow_challenges_solved"] += 1
                        # Retry immediately with solved cookie
                        resp = self.session.get(url, timeout=self.timeout)
                    else:
                        logger.warning("Failed to solve PoW challenge for %s", url)

                # Check for rate limit / IP block
                if resp.status_code == 429 or "Доступ ограничен: проблема с IP" in resp.text:
                    self.metrics["rate_limits_hit"] += 1
                    logger.warning("Rate limit / IP block detected on %s (HTTP %s)", url, resp.status_code)
                    self.rate_limiter.register_rate_limit()
                    if current_proxy and self.proxy_manager:
                        self.proxy_manager.mark_failure(current_proxy)
                    continue

                if resp.status_code == 200:
                    self.metrics["successful_requests"] += 1
                    self.rate_limiter.register_success()
                    if current_proxy and self.proxy_manager:
                        self.proxy_manager.mark_success(current_proxy)
                    return resp.text

                logger.warning("Non-200 response for %s: HTTP %s", url, resp.status_code)

            except requests.RequestException as e:
                logger.warning("Request failed on %s (attempt %s): %s", url, attempt, e)
                if current_proxy and self.proxy_manager:
                    self.proxy_manager.mark_failure(current_proxy)

        logger.error("Failed to retrieve %s after %s attempts.", url, self.max_retries)
        return None

    def get_item(self, url: str) -> Optional[AvitoItem]:
        """
        Parse a single Avito item by its page URL.
        """
        html = self.fetch_html(url)
        if not html:
            return None
        return AvitoItemParser.parse(html, url=url)

    def get_items(
        self,
        urls: Iterable[str],
        callback: Optional[Callable[[AvitoItem, int, int], None]] = None
    ) -> List[AvitoItem]:
        """
        Parse a sequence of Avito items with progress callback.
        """
        url_list = list(urls)
        results: List[AvitoItem] = []
        total = len(url_list)

        for i, url in enumerate(url_list, 1):
            item = self.get_item(url)
            if item:
                results.append(item)
                if callback:
                    callback(item, i, total)

        return results

    def search(
        self,
        query: str = "",
        location: str = "all",
        page: int = 1,
        price_min: Optional[int] = None,
        price_max: Optional[int] = None,
        sort: Optional[str] = None,
        category: Optional[str] = None,
    ) -> SearchResult:
        """
        Search for items across Avito with optional price and sorting filters.

        :param query: Keyword query text (e.g. 'ThinkBook')
        :param location: City or region slug ('all', 'nizhniy_novgorod', 'moskva', etc.)
        :param page: Page number (1-based)
        :param price_min: Minimum price filter (RUB)
        :param price_max: Maximum price filter (RUB)
        :param sort: Sort order: 'date' / 'new' (101), 'price_asc' (1), 'price_desc' (2)
        :param category: Optional category slug (e.g. 'noutbuki', 'telefony')
        """
        params = []
        if query:
            params.append(f"q={quote_plus(query)}")
        if page > 1:
            params.append(f"p={page}")
        if price_min is not None:
            params.append(f"pmin={price_min}")
        if price_max is not None:
            params.append(f"pmax={price_max}")
        if sort:
            sort_map = {"date": "101", "new": "101", "price_asc": "1", "price_desc": "2"}
            sort_code = sort_map.get(sort.lower(), sort)
            params.append(f"s={sort_code}")

        query_string = ("?" + "&".join(params)) if params else ""

        path_parts = [location.strip("/")]
        if category:
            path_parts.append(category.strip("/"))

        search_url = f"https://www.avito.ru/{'/'.join(path_parts)}{query_string}"
        return self.search_by_url(search_url, page=page)

    def search_by_url(self, search_url: str, page: int = 1) -> SearchResult:
        """
        Parse a search or catalog page by a direct Avito URL (with custom filters).
        """
        html = self.fetch_html(search_url)
        if not html:
            return SearchResult(url=search_url, page=page, items=[])

        res = AvitoCatalogParser.parse(html, url=search_url)
        res.page = page
        return res

    def iter_search(
        self,
        query: str = "",
        location: str = "all",
        max_pages: int = 3,
        **kwargs
    ) -> Generator[SearchResultItem, None, None]:
        """
        Generator that automatically paginates through search results up to max_pages.
        """
        for p in range(1, max_pages + 1):
            res = self.search(query=query, location=location, page=p, **kwargs)
            if not res.items:
                break
            for item in res.items:
                yield item
            # Stop if reached last page
            if res.total_count and len(res.items) * p >= res.total_count:
                break

    def get_metrics(self) -> Dict[str, Union[int, float]]:
        """Return runtime request and timing metrics."""
        return {
            **self.metrics,
            "total_waited_seconds": round(self.rate_limiter.total_waited, 2),
            "average_delay_seconds": round(self.rate_limiter.average_delay, 2),
        }

    def close(self):
        """Close HTTP session."""
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
