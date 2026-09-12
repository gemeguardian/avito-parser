"""
Adaptive rate limiting and delay controller with jitter and exponential backoff.
"""
import logging
import random
import time
from typing import Optional

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Controls timing between outgoing requests to avoid triggering anti-bot rate limits.
    """

    def __init__(
        self,
        min_delay: float = 2.0,
        max_delay: float = 4.0,
        backoff_factor: float = 1.5,
        max_backoff: float = 45.0,
    ):
        self.min_delay = min_delay
        self.max_delay = max(min_delay, max_delay)
        self.backoff_factor = backoff_factor
        self.max_backoff = max_backoff
        self._current_backoff = 0.0
        self._last_request_time: Optional[float] = None

    def wait(self):
        """
        Sleep for the required delay plus any active backoff.
        """
        now = time.time()
        base_delay = random.uniform(self.min_delay, self.max_delay)
        total_delay = base_delay + self._current_backoff

        if self._last_request_time is not None:
            elapsed = now - self._last_request_time
            remaining = total_delay - elapsed
            if remaining > 0:
                logger.debug("RateLimiter: waiting %.2f sec (base=%.2f, backoff=%.2f)", remaining, base_delay, self._current_backoff)
                time.sleep(remaining)
        else:
            if self._current_backoff > 0:
                time.sleep(self._current_backoff)

        self._last_request_time = time.time()

    def register_success(self):
        """
        On successful response, gradually decay backoff.
        """
        if self._current_backoff > 0:
            self._current_backoff = max(0.0, self._current_backoff - self.min_delay)
            logger.debug("RateLimiter: decaying backoff to %.2f sec", self._current_backoff)

    def register_rate_limit(self):
        """
        On HTTP 429 or firewall block, increase backoff exponentially.
        """
        if self._current_backoff == 0.0:
            self._current_backoff = self.max_delay * self.backoff_factor
        else:
            self._current_backoff = min(self.max_backoff, self._current_backoff * self.backoff_factor)
        logger.warning("RateLimiter: rate limit detected. Increased backoff to %.2f sec", self._current_backoff)

    def reset(self):
        """Reset rate limiter state."""
        self._current_backoff = 0.0
        self._last_request_time = None
