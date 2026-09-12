"""
avito-parser: Fast, robust scraper for Avito with automated PoW solving and proxy rotation.
"""
from .client import AvitoParser
from .models import AvitoItem, ItemParam, SearchResult, SearchResultItem, SellerInfo
from .parser import AvitoCatalogParser, AvitoItemParser
from .pow import AvitoPoWSolver
from .proxy import ProxyConfig, ProxyManager
from .rate_limiter import RateLimiter, RateLimitProfile, get_profile_config
from .exporter import ItemExporter

__version__ = "1.1.0"
__all__ = [
    "AvitoParser",
    "AvitoItem",
    "ItemParam",
    "SearchResult",
    "SearchResultItem",
    "SellerInfo",
    "AvitoItemParser",
    "AvitoCatalogParser",
    "AvitoPoWSolver",
    "ProxyConfig",
    "ProxyManager",
    "RateLimiter",
    "RateLimitProfile",
    "get_profile_config",
    "ItemExporter",
]
