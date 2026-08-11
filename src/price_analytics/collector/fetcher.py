from __future__ import annotations

import logging
import time
from collections.abc import Callable

import httpx

logger = logging.getLogger(__name__)


class FetchError(Exception):
    """Raised when a URL could not be fetched after exhausting retries."""


class PoliteFetcher:
    """A rate-limited HTTP client with exponential backoff on 429/5xx.

    Spaces requests at least `delay_seconds` apart and retries transient failures
    with doubling backoff (honoring a `Retry-After` header when the server sends
    one). Non-retryable errors (4xx other than 429) raise immediately.
    """

    def __init__(
        self,
        user_agent: str,
        delay_seconds: float = 1.0,
        max_retries: int = 5,
        timeout: float = 15.0,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._client = httpx.Client(
            headers={"User-Agent": user_agent}, timeout=timeout, transport=transport
        )
        self._delay = delay_seconds
        self._max_retries = max_retries
        self._sleep = sleep
        self._clock = clock
        self._last_request_at = clock() - delay_seconds

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> PoliteFetcher:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def get(self, url: str) -> httpx.Response:
        attempt = 0
        backoff = self._delay
        while True:
            attempt += 1
            self._respect_rate_limit()
            try:
                response = self._client.get(url)
            except httpx.TransportError as exc:
                if attempt > self._max_retries:
                    raise FetchError(
                        f"transport error fetching {url} after {attempt} attempts"
                    ) from exc
                logger.warning("transport error on %s (attempt %d): %s", url, attempt, exc)
                self._sleep(backoff)
                backoff *= 2
                continue

            if response.status_code == 429 or response.status_code >= 500:
                if attempt > self._max_retries:
                    raise FetchError(
                        f"giving up on {url} after {attempt} attempts, "
                        f"last status {response.status_code}"
                    )
                retry_after = response.headers.get("Retry-After")
                wait = float(retry_after) if retry_after else backoff
                logger.warning(
                    "status %d on %s (attempt %d), backing off %.1fs",
                    response.status_code,
                    url,
                    attempt,
                    wait,
                )
                self._sleep(wait)
                backoff *= 2
                continue

            response.raise_for_status()
            return response

    def _respect_rate_limit(self) -> None:
        elapsed = self._clock() - self._last_request_at
        remaining = self._delay - elapsed
        if remaining > 0:
            self._sleep(remaining)
        self._last_request_at = self._clock()
