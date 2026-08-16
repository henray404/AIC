"""Pacing, backoff and the circuit breaker.

All timing is faked, so the suite stays fast and deterministic. Nothing here
sleeps for real.
"""

from __future__ import annotations

import pytest

from tokopedia_scraper.config import RateLimitConfig
from tokopedia_scraper.ratelimit import (
    RETRYABLE_STATUS,
    USER_AGENTS,
    CircuitBreaker,
    CircuitOpen,
    FetchError,
    RateLimiter,
    backoff_delay,
    execute_with_retry,
    random_user_agent,
)


@pytest.fixture
def rl_cfg() -> RateLimitConfig:
    return RateLimitConfig(
        min_delay=2.0, max_delay=5.0, max_retries=3, backoff_base=2.0, backoff_max=10.0
    )


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.slept: list[float] = []

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds

    def __call__(self) -> float:
        return self.now


# --- pacing ---------------------------------------------------------------


def test_first_request_is_not_delayed(rl_cfg):
    clock = FakeClock()
    limiter = RateLimiter(rl_cfg, sleep=clock.sleep, clock=clock)
    assert limiter.wait() == 0.0
    assert clock.slept == []


def test_delay_is_within_the_configured_window(rl_cfg):
    clock = FakeClock()
    limiter = RateLimiter(rl_cfg, sleep=clock.sleep, clock=clock)
    limiter.wait()

    for _ in range(20):
        clock.slept.clear()
        limiter.wait()
        assert clock.slept
        assert rl_cfg.min_delay <= clock.slept[0] <= rl_cfg.max_delay


def test_delay_is_randomised_not_constant(rl_cfg):
    clock = FakeClock()
    limiter = RateLimiter(rl_cfg, sleep=clock.sleep, clock=clock)
    limiter.wait()
    for _ in range(30):
        limiter.wait()
    assert len(set(clock.slept)) > 1, "a constant interval is an obvious bot tell"


def test_time_spent_in_the_request_counts_towards_the_gap(rl_cfg):
    clock = FakeClock()
    limiter = RateLimiter(rl_cfg, sleep=clock.sleep, clock=clock)
    limiter.wait()

    clock.now += 60.0  # a very slow response
    assert limiter.wait() == 0.0, "no extra sleep is owed after a slow request"


# --- backoff --------------------------------------------------------------


def test_backoff_is_capped(rl_cfg):
    for attempt in range(1, 10):
        for _ in range(20):
            assert 0.0 <= backoff_delay(attempt, rl_cfg) <= rl_cfg.backoff_max


def test_backoff_has_jitter(rl_cfg):
    values = {backoff_delay(3, rl_cfg) for _ in range(50)}
    assert len(values) > 1, "without jitter, parallel retries collide in lockstep"


# --- circuit breaker ------------------------------------------------------


def test_success_resets_the_streak():
    breaker = CircuitBreaker(threshold=3)
    breaker.record_failure("a")
    breaker.record_failure("b")
    breaker.record_success()
    assert breaker.consecutive_failures == 0

    breaker.record_failure("c")
    breaker.record_failure("d")  # only two in a row, so still closed


def test_breaker_opens_at_the_threshold():
    breaker = CircuitBreaker(threshold=3)
    breaker.record_failure("a")
    breaker.record_failure("b")

    with pytest.raises(CircuitOpen) as excinfo:
        breaker.record_failure("c")

    message = str(excinfo.value)
    assert "CAPTURE_HEADERS" in message, "the error must say how to recover"
    assert "re-run to resume" in message


# --- retry ----------------------------------------------------------------


def test_transient_failure_recovers(rl_cfg):
    calls = {"n": 0}

    def flaky() -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            raise FetchError("429 Too Many Requests", status=429)
        return "ok"

    breaker = CircuitBreaker(threshold=10)
    result = execute_with_retry(flaky, rl_cfg, breaker=breaker, sleep=lambda _: None)
    assert result == "ok"
    assert calls["n"] == 3
    assert breaker.consecutive_failures == 0


def test_permanent_failure_is_not_retried(rl_cfg):
    calls = {"n": 0}

    def not_found() -> str:
        calls["n"] += 1
        raise FetchError("404 Not Found", status=404)

    with pytest.raises(FetchError):
        execute_with_retry(not_found, rl_cfg, sleep=lambda _: None)
    assert calls["n"] == 1


def test_retries_are_exhausted_then_raised(rl_cfg):
    calls = {"n": 0}

    def always_429() -> str:
        calls["n"] += 1
        raise FetchError("429", status=429)

    with pytest.raises(FetchError):
        execute_with_retry(always_429, rl_cfg, sleep=lambda _: None)
    assert calls["n"] == rl_cfg.max_retries


def test_exhausted_retries_feed_the_breaker(rl_cfg):
    breaker = CircuitBreaker(threshold=1)

    def always_500() -> str:
        raise FetchError("500", status=500)

    with pytest.raises(CircuitOpen):
        execute_with_retry(always_500, rl_cfg, breaker=breaker, sleep=lambda _: None)


@pytest.mark.parametrize("status", sorted(RETRYABLE_STATUS))
def test_retryable_statuses(status):
    assert FetchError("x", status=status).retryable


@pytest.mark.parametrize("status", [400, 401, 404, 410, 422])
def test_non_retryable_statuses(status):
    assert not FetchError("x", status=status).retryable


def test_network_level_failure_is_retryable():
    assert FetchError("connection reset").retryable, "status=None means transient"


# --- user agents ----------------------------------------------------------


def test_user_agent_pool():
    assert random_user_agent() in USER_AGENTS
    assert len(set(USER_AGENTS)) == len(USER_AGENTS), "duplicate UA in the pool"
    assert all(ua.startswith("Mozilla/5.0") for ua in USER_AGENTS)
