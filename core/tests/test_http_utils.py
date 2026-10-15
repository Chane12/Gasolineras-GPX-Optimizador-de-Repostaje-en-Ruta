"""Tests for the rate limiter and TTL cache (pure logic, fake clock)."""

import pytest

from gasolineras_core.http_utils import RateLimitBusyError, RateLimiter, TTLCache


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0
        self.slept: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)


class TestRateLimiter:
    def test_first_call_does_not_wait(self):
        clock = FakeClock()
        limiter = RateLimiter(1.0, 10.0, clock=clock, sleep=clock.sleep)
        limiter.wait()
        assert clock.slept == []

    def test_back_to_back_calls_are_spaced_by_min_interval(self):
        clock = FakeClock()
        limiter = RateLimiter(1.0, 10.0, clock=clock, sleep=clock.sleep)
        limiter.wait()
        limiter.wait()  # same instant: reserves the slot 1 s later
        limiter.wait()  # and the next one 2 s later
        assert clock.slept == [pytest.approx(1.0), pytest.approx(2.0)]

    def test_no_wait_once_the_interval_has_passed(self):
        clock = FakeClock()
        limiter = RateLimiter(1.0, 10.0, clock=clock, sleep=clock.sleep)
        limiter.wait()
        clock.now += 1.5
        limiter.wait()
        assert clock.slept == []

    def test_raises_busy_instead_of_queueing_too_long(self):
        clock = FakeClock()
        limiter = RateLimiter(1.0, 2.0, clock=clock, sleep=clock.sleep)
        for _ in range(3):  # slots at +0, +1, +2
            limiter.wait()
        with pytest.raises(RateLimitBusyError):
            limiter.wait()  # would need to wait 3 s > 2 s


class TestTTLCache:
    def test_returns_stored_value_until_it_expires(self):
        clock = FakeClock()
        cache: TTLCache[str] = TTLCache(max_items=10, ttl_s=60, clock=clock)
        cache.set("a", "value")
        clock.now += 59
        assert cache.get("a") == "value"
        clock.now += 2
        assert cache.get("a") is None
        assert len(cache) == 0

    def test_evicts_least_recently_used_when_full(self):
        cache: TTLCache[int] = TTLCache(max_items=2, ttl_s=60)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.get("a")  # "b" is now the least recently used
        cache.set("c", 3)
        assert cache.get("a") == 1
        assert cache.get("b") is None
        assert cache.get("c") == 3
