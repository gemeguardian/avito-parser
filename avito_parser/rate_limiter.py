"""
Adaptive rate limiting and delay controller with profiles, jitter, and exponential backoff.
"""
from dataclasses import dataclass
from enum import Enum
import logging
import random
import time
from typing import Dict, Optional, Union

logger = logging.getLogger(__name__)


class RateLimitProfile(str, Enum):
    """
    Standardized rate-limiting profiles tuned for Avito anti-bot firewall thresholds.
    """
    STEALTH = "stealth"
    BALANCED = "balanced"
    FAST_ROTATING = "fast_rotating"
    DATACENTER = "datacenter"
    MOBILE_SINGLE = "mobile_single"


@dataclass
class ProfileConfig:
    min_delay: float
    max_delay: float
    jitter: float
    backoff_factor: float
    max_backoff: float
    description: str


PROFILES: Dict[RateLimitProfile, ProfileConfig] = {
    RateLimitProfile.STEALTH: ProfileConfig(
        min_delay=3.5,
        max_delay=6.5,
        jitter=0.5,
        backoff_factor=2.0,
        max_backoff=60.0,
        description="Safe mode for single residential or mobile IP. Emulates natural human browsing."
    ),
    RateLimitProfile.BALANCED: ProfileConfig(
        min_delay=2.5,
        max_delay=4.5,
        jitter=0.3,
        backoff_factor=1.8,
        max_backoff=45.0,
        description="Default profile. Optimal balance between scraping speed and avoiding 429/PoW."
    ),
    RateLimitProfile.FAST_ROTATING: ProfileConfig(
        min_delay=0.8,
        max_delay=1.8,
        jitter=0.2,
        backoff_factor=1.5,
        max_backoff=30.0,
        description="High-speed profile intended exclusively with large rotating residential proxy pools."
    ),
    RateLimitProfile.DATACENTER: ProfileConfig(
        min_delay=4.5,
        max_delay=8.5,
        jitter=0.7,
        backoff_factor=2.2,
        max_backoff=90.0,
        description="Conservative profile for datacenter proxy subnets that face strict Avito scrutiny."
    ),
    RateLimitProfile.MOBILE_SINGLE: ProfileConfig(
        min_delay=35.0,
        max_delay=60.0,
        jitter=5.0,
        backoff_factor=2.0,
        max_backoff=300.0,
        description="Ultra-conservative profile for direct unproxied requests from a single mobile IP."
    ),
}


def get_profile_config(profile: Union[str, RateLimitProfile]) -> ProfileConfig:
    """Resolve a profile name or enum to a ProfileConfig."""
    if isinstance(profile, str):
        profile_key = profile.lower().strip()
        # support alias "fast" for "fast_rotating"
        if profile_key == "fast":
            profile_key = "fast_rotating"
        try:
            profile_enum = RateLimitProfile(profile_key)
        except ValueError:
            valid = [p.value for p in RateLimitProfile] + ["fast"]
            raise ValueError(f"Unknown profile '{profile}'. Choose from: {valid}")
    else:
        profile_enum = profile

    return PROFILES[profile_enum]


class RateLimiter:
    """
    Controls timing between outgoing requests to avoid triggering anti-bot rate limits.
    """

    def __init__(
        self,
        min_delay: float = 2.5,
        max_delay: float = 4.5,
        jitter: float = 0.3,
        backoff_factor: float = 1.8,
        max_backoff: float = 45.0,
    ):
        self.min_delay = min_delay
        self.max_delay = max(min_delay, max_delay)
        self.jitter = max(0.0, jitter)
        self.backoff_factor = backoff_factor
        self.max_backoff = max_backoff
        self._current_backoff = 0.0
        self._last_request_time: Optional[float] = None

        # Telemetry
        self.total_waited: float = 0.0
        self.wait_count: int = 0

    @classmethod
    def from_profile(cls, profile: Union[str, RateLimitProfile]) -> "RateLimiter":
        """Instantiate RateLimiter configured according to a preset profile."""
        cfg = get_profile_config(profile)
        return cls(
            min_delay=cfg.min_delay,
            max_delay=cfg.max_delay,
            jitter=cfg.jitter,
            backoff_factor=cfg.backoff_factor,
            max_backoff=cfg.max_backoff,
        )

    def wait(self) -> float:
        """
        Sleep for the required delay plus any active backoff and random jitter.
        Returns the actual time waited in seconds.
        """
        now = time.time()
        base_delay = random.uniform(self.min_delay, self.max_delay)

        # Add Gaussian jitter
        if self.jitter > 0:
            jitter_offset = random.gauss(0, self.jitter)
            base_delay = max(0.1, base_delay + jitter_offset)

        total_delay = base_delay + self._current_backoff
        actual_waited = 0.0

        if self._last_request_time is not None:
            elapsed = now - self._last_request_time
            remaining = total_delay - elapsed
            if remaining > 0:
                logger.debug("RateLimiter: waiting %.2f sec (base=%.2f, backoff=%.2f)", remaining, base_delay, self._current_backoff)
                time.sleep(remaining)
                actual_waited = remaining
        else:
            if self._current_backoff > 0:
                time.sleep(self._current_backoff)
                actual_waited = self._current_backoff

        self.total_waited += actual_waited
        self.wait_count += 1
        self._last_request_time = time.time()
        return actual_waited

    def register_success(self):
        """On successful response, gradually decay backoff."""
        if self._current_backoff > 0:
            self._current_backoff = max(0.0, self._current_backoff - self.min_delay)
            logger.debug("RateLimiter: decaying backoff to %.2f sec", self._current_backoff)

    def register_rate_limit(self):
        """On HTTP 429 or firewall block, increase backoff exponentially."""
        if self._current_backoff == 0.0:
            self._current_backoff = self.max_delay * self.backoff_factor
        else:
            self._current_backoff = min(self.max_backoff, self._current_backoff * self.backoff_factor)
        logger.warning("RateLimiter: rate limit detected. Increased backoff to %.2f sec", self._current_backoff)

    def reset(self):
        """Reset rate limiter state."""
        self._current_backoff = 0.0
        self._last_request_time = None

    @property
    def average_delay(self) -> float:
        """Calculate average wait delay in seconds."""
        if self.wait_count == 0:
            return 0.0
        return self.total_waited / self.wait_count
