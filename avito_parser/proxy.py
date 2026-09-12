"""
Proxy management and rotation module for avito-parser.
Supports HTTP/HTTPS, SOCKS4, SOCKS5, authentication, and failure tracking.
"""
import itertools
import logging
import random
import re
from typing import Dict, List, Optional, Union

logger = logging.getLogger(__name__)


class ProxyConfig:
    """
    Standardized proxy representation with formatting helpers.
    """

    def __init__(self, raw: str):
        self.raw = raw.strip()
        self.url = self._normalize(self.raw)
        self.fail_count = 0
        self.is_active = True

    @staticmethod
    def _normalize(proxy_str: str) -> str:
        # Check standard URI scheme
        if "://" in proxy_str:
            scheme, rest = proxy_str.split("://", 1)
            # convert socks5 to socks5h for remote DNS resolution
            if scheme.lower() == "socks5":
                scheme = "socks5h"
            return f"{scheme}://{rest}"

        # Handle host:port:user:pass
        parts = proxy_str.split(":")
        if len(parts) == 4:
            host, port, user, password = parts
            return f"socks5h://{user}:{password}@{host}:{port}"
        elif len(parts) == 2:
            host, port = parts
            return f"http://{host}:{port}"
        
        return proxy_str

    def to_requests(self) -> Dict[str, str]:
        """Convert to requests proxy dictionary."""
        return {
            "http": self.url,
            "https": self.url,
        }

    def __repr__(self) -> str:
        # Mask password in logs
        masked = re.sub(r':([^@]+)@', ':****@', self.url)
        return f"<ProxyConfig {masked}>"


class ProxyManager:
    """
    Manages a pool of proxies with rotation and fault tolerance.
    """

    def __init__(
        self,
        proxies: Optional[Union[str, List[str]]] = None,
        max_fails: int = 3,
        randomize: bool = False
    ):
        self.max_fails = max_fails
        self.randomize = randomize
        self.pool: List[ProxyConfig] = []

        if proxies:
            if isinstance(proxies, str):
                proxies = [proxies]
            for p in proxies:
                p_clean = p.strip()
                if p_clean and not p_clean.startswith("#"):
                    self.pool.append(ProxyConfig(p_clean))

        self._cycle = itertools.cycle(self.pool) if self.pool else None

    @classmethod
    def from_file(cls, filepath: str, **kwargs) -> "ProxyManager":
        """Load proxies from a line-separated text file."""
        with open(filepath, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        return cls(lines, **kwargs)

    def get_proxy(self) -> Optional[ProxyConfig]:
        """Get the next active proxy from the pool."""
        active = [p for p in self.pool if p.is_active]
        if not active:
            return None

        if self.randomize:
            return random.choice(active)

        for _ in range(len(self.pool)):
            p = next(self._cycle)
            if p.is_active:
                return p

        return None

    def mark_success(self, proxy: ProxyConfig):
        """Reset failure counter on success."""
        proxy.fail_count = 0

    def mark_failure(self, proxy: ProxyConfig):
        """Register a failure and disable if threshold exceeded."""
        proxy.fail_count += 1
        if proxy.fail_count >= self.max_fails:
            proxy.is_active = False
            logger.warning("Proxy %s exceeded max failures (%s). Deactivated.", proxy, self.max_fails)
        else:
            logger.info("Proxy %s recorded failure %s/%s", proxy, proxy.fail_count, self.max_fails)

    def reset_all(self):
        """Re-enable all proxies in the pool."""
        for p in self.pool:
            p.fail_count = 0
            p.is_active = True

    def __len__(self) -> int:
        return len(self.pool)
