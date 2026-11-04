"""
Core HTTP session management for NSE India API requests.

Adapted from the `niftyterminal` project's `core/session.py`. Handles:
- A shared, auto-refreshing httpx.AsyncClient with NSE cookie warmup
- Browser-like headers / User-Agent rotation to avoid anti-bot detection
- Rate limiting (NSE enforces ~3 req/s)
- Automatic retry + session refresh on 401 / stale cookies
- A generic raw-content fetcher with exponential backoff, used for
  downloading XBRL/XML and legacy HTML filing documents.
"""

import asyncio
import random
import time
from typing import Optional

import httpx

# ---------------------------------------------------------------------------
# User-Agent rotation pool
# ---------------------------------------------------------------------------
_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Safari/605.1.15",
]


def _random_ua() -> str:
    return random.choice(_USER_AGENTS)


HEADERS = {
    "User-Agent": _random_ua(),
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "X-Requested-With": "XMLHttpRequest",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}

# Raw-document headers (XBRL/XML + legacy HTML filings)
XBRL_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Referer": "https://www.nseindia.com/",
}

NSE_BASE_URL = "https://www.nseindia.com"
NSE_HOMEPAGE = NSE_BASE_URL
NSE_OPTION_CHAIN = f"{NSE_BASE_URL}/option-chain"

WARMUP_DELAY_MIN = 0.1
WARMUP_DELAY_MAX = 0.2


# ---------------------------------------------------------------------------
# Rate limiter (NSE enforces ~3 req/s)
# ---------------------------------------------------------------------------
class _AsyncRateLimiter:
    def __init__(self, max_rps: float = 3.0):
        self.min_interval = 1.0 / max_rps
        self._last: float = 0.0
        self._lock: Optional[asyncio.Lock] = None

    def _get_lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def wait(self):
        async with self._get_lock():
            loop = asyncio.get_event_loop()
            elapsed = loop.time() - self._last
            if elapsed < self.min_interval:
                await asyncio.sleep(self.min_interval - elapsed + random.uniform(0, 0.05))
            self._last = loop.time()


_async_limiter = _AsyncRateLimiter(max_rps=3.0)


async def _awarmup_session(session: httpx.AsyncClient, timeout: int = 10, fast: bool = False) -> bool:
    """Warm up a session by visiting the NSE homepage to acquire anti-bot cookies."""
    warmup_headers = {
        **HEADERS,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }
    try:
        response = await session.get(NSE_HOMEPAGE, headers=warmup_headers, timeout=timeout)
        response.raise_for_status()
        await asyncio.sleep(random.uniform(WARMUP_DELAY_MIN, WARMUP_DELAY_MAX) if fast else random.uniform(0.3, 0.5))
        return True
    except httpx.HTTPError:
        return False


# ---------------------------------------------------------------------------
# Shared client (singleton, refreshed every 10 minutes)
# ---------------------------------------------------------------------------
_SHARED_ASYNC_CLIENT: Optional[httpx.AsyncClient] = None
_LAST_WARMUP_TIME: float = 0
_SESSION_LOCK: Optional[asyncio.Lock] = None


def _get_session_lock() -> asyncio.Lock:
    global _SESSION_LOCK
    if _SESSION_LOCK is None:
        _SESSION_LOCK = asyncio.Lock()
    return _SESSION_LOCK


async def get_shared_client(timeout: int = 10) -> httpx.AsyncClient:
    """Get or create a shared httpx.AsyncClient with automatic warmup/refresh."""
    global _SHARED_ASYNC_CLIENT, _LAST_WARMUP_TIME

    async with _get_session_lock():
        now = time.time()
        if _SHARED_ASYNC_CLIENT is None or (now - _LAST_WARMUP_TIME) > 600:
            if _SHARED_ASYNC_CLIENT:
                try:
                    await _SHARED_ASYNC_CLIENT.aclose()
                except Exception:
                    pass

            _SHARED_ASYNC_CLIENT = httpx.AsyncClient(
                headers={**HEADERS, "User-Agent": _random_ua()},
                follow_redirects=True,
                timeout=timeout,
            )
            await _awarmup_session(_SHARED_ASYNC_CLIENT, timeout=timeout, fast=True)
            _LAST_WARMUP_TIME = now

        return _SHARED_ASYNC_CLIENT


async def refresh_shared_client(timeout: int = 10):
    """Force a session refresh (new cookies / User-Agent)."""
    global _SHARED_ASYNC_CLIENT, _LAST_WARMUP_TIME
    async with _get_session_lock():
        if _SHARED_ASYNC_CLIENT:
            try:
                await _SHARED_ASYNC_CLIENT.aclose()
            except Exception:
                pass
        _SHARED_ASYNC_CLIENT = None
        _LAST_WARMUP_TIME = 0
    return await get_shared_client(timeout)


async def aclose_shared_client():
    """Close the shared client. Call on FastAPI shutdown."""
    global _SHARED_ASYNC_CLIENT, _LAST_WARMUP_TIME
    if _SHARED_ASYNC_CLIENT:
        try:
            await _SHARED_ASYNC_CLIENT.aclose()
        except Exception:
            pass
    _SHARED_ASYNC_CLIENT = None
    _LAST_WARMUP_TIME = 0


async def afetch(url: str, timeout: int = 10, params: Optional[dict] = None, retries: int = 2) -> dict:
    """
    Asynchronously fetch JSON from an NSE API endpoint using the shared,
    cookie-warmed session. Automatically refreshes the session and retries
    on 401 / stale-cookie / network failures, and enforces rate limiting.
    """
    for attempt in range(retries + 1):
        try:
            await _async_limiter.wait()
            session = await get_shared_client(timeout)
            response = await session.get(
                url,
                params=params,
                timeout=timeout,
                headers={"Referer": NSE_OPTION_CHAIN},
            )

            if response.status_code == 401:
                if attempt < retries:
                    await refresh_shared_client(timeout)
                continue

            if response.status_code == 200:
                try:
                    return response.json()
                except ValueError:
                    pass

            if attempt < retries:
                await refresh_shared_client(timeout)
                await asyncio.sleep(random.uniform(0.3, 0.5))

        except (httpx.HTTPError, Exception):
            if attempt < retries:
                await refresh_shared_client(timeout)
                await asyncio.sleep(random.uniform(0.3, 0.5))

    return {}


async def afetch_with_backoff(url: str, timeout: int = 15, retries: int = 3) -> str:
    """
    Fetch raw text content (used for XBRL/XML and legacy HTML filing
    documents) with exponential backoff on rate-limit responses (429/503).
    """
    for attempt in range(retries):
        try:
            async with httpx.AsyncClient(headers=XBRL_HEADERS, follow_redirects=True) as client:
                resp = await client.get(url, timeout=timeout)
                if resp.status_code in (429, 503):
                    wait = (2 ** attempt) * random.uniform(1.0, 2.0)
                    await asyncio.sleep(wait)
                    continue
                if resp.status_code == 200:
                    return resp.text
        except Exception:
            if attempt < retries - 1:
                await asyncio.sleep(random.uniform(0.5, 1.0))
    return ""
