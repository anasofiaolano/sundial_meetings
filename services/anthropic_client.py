# utils/anthropic_client.py
#
# Shared Anthropic client utilities used across all phases.
#
#   call_with_retry(...)         — sync call with retry on 429/529/network errors
#   async_call_with_retry(...)   — async equivalent
#   extract_tool_use(response)   — pulls the tool_use block from a response
#
# Both retry functions accept the same kwargs as client.messages.create().
# Clients are singletons — one instance per process.

import asyncio
import logging
import random
import time

from anthropic import (
    Anthropic,
    AsyncAnthropic,
    APIConnectionError,
    APIStatusError,
    RateLimitError,
)

log = logging.getLogger("anthropic_client")

MAX_RETRIES = 4
BASE_DELAY  = 2.0   # seconds — doubles each attempt
MAX_DELAY   = 60.0  # cap

_client:       Anthropic      | None = None
_async_client: AsyncAnthropic | None = None


def get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic()
    return _client


def get_async_client() -> AsyncAnthropic:
    global _async_client
    if _async_client is None:
        _async_client = AsyncAnthropic()
    return _async_client


def _is_retryable(e: Exception) -> bool:
    if isinstance(e, RateLimitError):
        return True
    if isinstance(e, APIStatusError) and e.status_code in (429, 529):
        return True
    if isinstance(e, APIConnectionError):
        return True
    return False


def _backoff(attempt: int) -> float:
    """Exponential backoff with 20% jitter."""
    delay = min(BASE_DELAY * (2 ** attempt), MAX_DELAY)
    return delay + random.uniform(0, delay * 0.2)


def call_with_retry(**kwargs):
    """
    Sync wrapper around client.messages.create() with retry on transient errors.
    Usage: response = call_with_retry(model=..., max_tokens=..., messages=..., ...)
    """
    client = get_client()
    for attempt in range(MAX_RETRIES + 1):
        try:
            return client.messages.create(**kwargs)
        except Exception as e:
            if _is_retryable(e) and attempt < MAX_RETRIES:
                delay = _backoff(attempt)
                log.warning(
                    "Anthropic API error (attempt %d/%d): %s — retrying in %.1fs",
                    attempt + 1, MAX_RETRIES, e, delay,
                )
                time.sleep(delay)
            else:
                raise


async def async_call_with_retry(**kwargs):
    """
    Async wrapper around client.messages.create() with retry on transient errors.
    Usage: response = await async_call_with_retry(model=..., max_tokens=..., messages=..., ...)
    """
    client = get_async_client()
    for attempt in range(MAX_RETRIES + 1):
        try:
            return await client.messages.create(**kwargs)
        except Exception as e:
            if _is_retryable(e) and attempt < MAX_RETRIES:
                delay = _backoff(attempt)
                log.warning(
                    "Anthropic API error (attempt %d/%d): %s — retrying in %.1fs",
                    attempt + 1, MAX_RETRIES, e, delay,
                )
                await asyncio.sleep(delay)
            else:
                raise


class _RetryingStream:
    """
    Context manager that wraps client.messages.stream() with retry on
    connection-phase errors (429 / 529 / network) before any tokens arrive.
    Mid-stream errors propagate normally — a half-sent stream can't be replayed.
    """

    def __init__(self, client: Anthropic, kwargs: dict):
        self._client = client
        self._kwargs = kwargs
        self._stream = None

    def __enter__(self):
        for attempt in range(MAX_RETRIES + 1):
            try:
                self._stream = self._client.messages.stream(**self._kwargs)
                return self._stream.__enter__()
            except Exception as e:
                if _is_retryable(e) and attempt < MAX_RETRIES:
                    delay = _backoff(attempt)
                    log.warning(
                        "Anthropic stream error (attempt %d/%d): %s — retrying in %.1fs",
                        attempt + 1, MAX_RETRIES, e, delay,
                    )
                    time.sleep(delay)
                else:
                    raise

    def __exit__(self, *args):
        if self._stream:
            return self._stream.__exit__(*args)


def stream_with_retry(**kwargs) -> _RetryingStream:
    """
    Drop-in replacement for client.messages.stream() with retry on transient errors.

    Usage:
        with stream_with_retry(model=..., max_tokens=..., messages=...) as stream:
            for text in stream.text_stream:
                ...
            final = stream.get_final_message()
    """
    return _RetryingStream(get_client(), kwargs)


def extract_tool_use(response):
    """Return the first tool_use block from a response, or None."""
    return next((b for b in response.content if b.type == "tool_use"), None)
