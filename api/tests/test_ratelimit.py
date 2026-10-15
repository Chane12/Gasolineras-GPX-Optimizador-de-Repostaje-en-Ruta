"""Tests for per-client rate limiting (fake clock, no network)."""

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from gasolineras_api.main import create_app
from gasolineras_api.ratelimit import Budget, RateLimiter, client_ip

TRACK = {"type": "LineString", "coordinates": [[-4.70, 40.60], [-4.50, 40.70], [-4.30, 40.80]]}
GMAPS = {"origin": [-4.7, 40.6], "destination": [-4.3, 40.8], "stops": []}


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def make_request(peer: str, forwarded: str | None = None) -> Request:
    headers = [(b"x-forwarded-for", forwarded.encode())] if forwarded else []
    return Request({"type": "http", "headers": headers, "client": (peer, 1234)})


class TestRateLimiter:
    def test_allows_up_to_the_budget_then_reports_wait(self):
        clock = Clock()
        limiter = RateLimiter({"default": Budget(3, 60)}, clock=clock)

        assert [limiter.check("a", "default") for _ in range(3)] == [None, None, None]
        clock.now = 10
        assert limiter.check("a", "default") == pytest.approx(50)

    def test_window_slides(self):
        clock = Clock()
        limiter = RateLimiter({"default": Budget(2, 60)}, clock=clock)
        limiter.check("a", "default")
        clock.now = 30
        limiter.check("a", "default")

        clock.now = 61  # the first hit left the window
        assert limiter.check("a", "default") is None
        assert limiter.check("a", "default") is not None

    def test_clients_and_budgets_are_independent(self):
        limiter = RateLimiter({"default": Budget(1, 60), "external": Budget(1, 60)}, clock=Clock())
        limiter.check("a", "default")

        assert limiter.check("b", "default") is None
        assert limiter.check("a", "external") is None
        assert limiter.check("a", "default") is not None


class TestClientIp:
    def test_uses_the_socket_peer_by_default(self):
        assert client_ip(make_request("10.0.0.1", forwarded="1.2.3.4"), trusted_hops=0) == "10.0.0.1"

    def test_behind_one_proxy_takes_the_last_forwarded_address(self):
        # The client can forge the left part; the proxy appends the real address at the end.
        request = make_request("10.0.0.1", forwarded="6.6.6.6, 203.0.113.7")
        assert client_ip(request, trusted_hops=1) == "203.0.113.7"

    def test_without_forwarded_header_falls_back_to_the_peer(self):
        assert client_ip(make_request("10.0.0.1"), trusted_hops=1) == "10.0.0.1"


def client_with(budgets: dict[str, Budget]) -> TestClient:
    return TestClient(create_app(warm_up=False, rate_limiter=RateLimiter(budgets, clock=Clock())))


def test_over_budget_is_429_with_retry_after_and_spanish_message():
    client = client_with({"default": Budget(2, 60), "external": Budget(2, 60)})

    statuses = [client.post("/export/gmaps-url", json=GMAPS).status_code for _ in range(3)]

    assert statuses == [200, 200, 429]
    response = client.post("/export/gmaps-url", json=GMAPS)
    assert response.headers["retry-after"] == "60"
    assert "demasiadas peticiones" in response.json()["detail"].lower()


def test_external_endpoints_use_their_own_budget(monkeypatch):
    from gasolineras_core.optimizer import export

    monkeypatch.setattr(export, "compute_detours", lambda t, s: [None] * len(s))
    client = client_with({"default": Budget(100, 60), "external": Budget(1, 60)})
    body = {"track": TRACK, "stations": [{"lat": 40.7, "lon": -4.5}]}

    assert client.post("/detours", json=body).status_code == 200
    assert client.post("/detours", json=body).status_code == 429
    assert client.post("/export/gmaps-url", json=GMAPS).status_code == 200  # default budget untouched


def test_health_is_never_limited():
    client = client_with({"default": Budget(1, 60), "external": Budget(1, 60)})

    assert all(client.get("/health").status_code == 200 for _ in range(5))


def test_openapi_documents_429():
    paths = client_with({"default": Budget(1, 60), "external": Budget(1, 60)}).get("/openapi.json").json()["paths"]

    for path in ("/route/text", "/route/gpx", "/search", "/detours", "/export/gpx", "/export/gmaps-url"):
        assert "429" in paths[path]["post"]["responses"], path
