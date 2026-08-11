import httpx
import pytest

from price_analytics.collector.fetcher import FetchError, PoliteFetcher


def _fetcher(handler, **kwargs) -> tuple[PoliteFetcher, list[float]]:
    sleeps: list[float] = []
    fetcher = PoliteFetcher(
        user_agent="test-agent",
        delay_seconds=0.0,
        transport=httpx.MockTransport(handler),
        sleep=sleeps.append,
        clock=lambda: 0.0,
        **kwargs,
    )
    return fetcher, sleeps


def test_get_returns_response_on_success():
    def handler(request):
        return httpx.Response(200, text="ok")

    fetcher, sleeps = _fetcher(handler)

    response = fetcher.get("https://example.test/a")

    assert response.status_code == 200
    assert response.text == "ok"
    assert sleeps == []


def test_retries_on_429_then_succeeds():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(429)
        return httpx.Response(200, text="ok")

    fetcher, sleeps = _fetcher(handler, max_retries=5)

    response = fetcher.get("https://example.test/a")

    assert response.status_code == 200
    assert calls["n"] == 3
    assert len(sleeps) == 2


def test_retry_after_header_is_honored():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, headers={"Retry-After": "3"})
        return httpx.Response(200, text="ok")

    fetcher, sleeps = _fetcher(handler)

    fetcher.get("https://example.test/a")

    assert sleeps[0] == 3.0


def test_gives_up_after_max_retries():
    def handler(request):
        return httpx.Response(503)

    fetcher, sleeps = _fetcher(handler, max_retries=2)

    with pytest.raises(FetchError):
        fetcher.get("https://example.test/a")

    assert len(sleeps) == 2


def test_raises_on_404_without_retrying():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(404)

    fetcher, sleeps = _fetcher(handler, max_retries=5)

    with pytest.raises(httpx.HTTPStatusError):
        fetcher.get("https://example.test/a")

    assert calls["n"] == 1
    assert sleeps == []
