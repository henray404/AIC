"""Politeness layer: randomised pacing, backoff with jitter, circuit breaker.

Three separate concerns, deliberately not merged:
  RateLimiter    how long to wait between *successful* requests.
  backoff_delay  how long to wait after a *failed* one.
  CircuitBreaker when to stop the run entirely instead of grinding on.
"""

from __future__ import annotations

import logging
import random
import time
from typing import Callable, Sequence, TypeVar

from .config import RateLimitConfig

log = logging.getLogger(__name__)

T = TypeVar("T")

# Modern desktop browser UAs. Rotated per request so the traffic does not look
# like one client hammering the site. Keep these plausible and current — a UA
# claiming Chrome 78 in 2026 is more suspicious than no rotation at all.
USER_AGENTS: tuple[str, ...] = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36",
)

# HTTP statuses worth retrying. 403 is included because Tokopedia returns it for
# soft bot-blocks that a backoff plus a new UA often clears.
RETRYABLE_STATUS: frozenset[int] = frozenset({403, 408, 425, 429, 500, 502, 503, 504})

# "What you asked for is gone" — which says nothing about whether we are being
# blocked. A run of deleted products must not read as a block and trip the
# circuit breaker, or a long scrape dies on other people's housekeeping.
GONE_STATUS: frozenset[int] = frozenset({404, 410})


def random_user_agent() -> str:
    return random.choice(USER_AGENTS)


class CircuitOpen(RuntimeError):
    """Too many consecutive failures — the run stops rather than keep knocking."""


class FetchError(RuntimeError):
    """A request failed. `status` is set when the failure was an HTTP response."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status

    @property
    def retryable(self) -> bool:
        # Network-level failures (status is None) are retryable: connections
        # drop for reasons that have nothing to do with us.
        return self.status is None or self.status in RETRYABLE_STATUS

    @property
    def is_gone(self) -> bool:
        """The target no longer exists — our fault to record, not to panic over."""
        return self.status in GONE_STATUS


class RateLimiter:
    """Randomised delay between requests.

    A constant interval is one of the easiest bot signals to spot, so the gap is
    drawn uniformly from [min_delay, max_delay] each time. Time already spent
    inside the request counts toward the gap — pacing measures request starts,
    not idle time on top of a slow response.
    """

    def __init__(
        self,
        cfg: RateLimitConfig,
        *,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.cfg = cfg
        self._sleep = sleep
        self._clock = clock
        self._last: float | None = None

    def wait(self) -> float:
        """Block until the next request is due. Returns the seconds slept."""
        target = random.uniform(self.cfg.min_delay, self.cfg.max_delay)
        now = self._clock()
        if self._last is None:
            self._last = now
            return 0.0

        elapsed = now - self._last
        remaining = max(0.0, target - elapsed)
        if remaining:
            self._sleep(remaining)
        self._last = self._clock()
        return remaining


def backoff_delay(attempt: int, cfg: RateLimitConfig) -> float:
    """Exponential backoff with full jitter, capped at `backoff_max`.

    Full jitter (uniform over [0, computed]) rather than a fixed multiplier:
    when several workers are retrying, a deterministic backoff makes them
    collide again in lockstep.
    """
    ceiling = min(cfg.backoff_max, cfg.backoff_base ** max(1, attempt))
    return random.uniform(0.0, ceiling)


class CircuitBreaker:
    """Aborts the run after N consecutive failures.

    Consecutive, not cumulative: an occasional 429 in a long run is normal, but
    ten failures in a row means the session is dead or we are blocked, and more
    requests only make it worse.
    """

    def __init__(self, threshold: int) -> None:
        self.threshold = threshold
        self.consecutive_failures = 0
        self.total_failures = 0
        self.total_successes = 0

    def record_success(self) -> None:
        self.consecutive_failures = 0
        self.total_successes += 1

    def record_failure(self, reason: str = "") -> None:
        self.consecutive_failures += 1
        self.total_failures += 1
        if self.consecutive_failures >= self.threshold:
            raise CircuitOpen(
                f"{self.consecutive_failures} consecutive failures "
                f"(threshold {self.threshold}). Last: {reason or 'unknown'}.\n"
                f"Stopping instead of hammering the server. Likely causes: the "
                f"captured cookie expired (recapture — see docs/CAPTURE_HEADERS.md), "
                f"the IP is rate-limited (wait, or set proxy_url), or the GraphQL "
                f"schema changed. Progress is saved; re-run to resume."
            )


def execute_with_retry(
    func: Callable[[], T],
    cfg: RateLimitConfig,
    *,
    limiter: RateLimiter | None = None,
    breaker: CircuitBreaker | None = None,
    describe: str = "request",
    sleep: Callable[[float], None] = time.sleep,
    retry_on: Sequence[type[BaseException]] = (FetchError,),
) -> T:
    """Run `func`, retrying transient failures with backoff.

    Raises the last exception once retries are exhausted. CircuitOpen is never
    retried — it means stop.
    """
    last_exc: BaseException | None = None

    for attempt in range(1, cfg.max_retries + 1):
        if limiter is not None:
            limiter.wait()
        try:
            result = func()
        except CircuitOpen:
            raise
        except tuple(retry_on) as exc:
            last_exc = exc
            retryable = getattr(exc, "retryable", True)
            status = getattr(exc, "status", None)

            if not retryable:
                log.error(
                    "%s failed permanently (status %s): %s", describe, status, exc
                )
                # A deleted product is not evidence that we are blocked, so it
                # must not push the breaker toward opening. Without this, a run
                # of housekeeping deletions aborts an otherwise healthy scrape.
                if breaker is not None and not getattr(exc, "is_gone", False):
                    breaker.record_failure(f"{describe}: {exc}")
                raise

            if attempt >= cfg.max_retries:
                break

            delay = backoff_delay(attempt, cfg)
            log.warning(
                "%s failed (attempt %d/%d, status %s): %s — retrying in %.1fs",
                describe,
                attempt,
                cfg.max_retries,
                status,
                exc,
                delay,
            )
            sleep(delay)
        else:
            if breaker is not None:
                breaker.record_success()
            return result

    log.error("%s exhausted %d attempts: %s", describe, cfg.max_retries, last_exc)
    if breaker is not None:
        # May raise CircuitOpen, which is the intended louder failure.
        breaker.record_failure(f"{describe}: {last_exc}")
    assert last_exc is not None
    raise last_exc


if __name__ == "__main__":  # pragma: no cover - manual smoke check
    logging.basicConfig(level=logging.CRITICAL)

    cfg = RateLimitConfig(
        min_delay=2.0, max_delay=5.0, max_retries=3, backoff_base=2.0, backoff_max=10.0
    )

    # --- pacing: elapsed request time counts toward the gap -----------------
    slept: list[float] = []
    now = [0.0]

    def fake_sleep(seconds: float) -> None:
        slept.append(seconds)
        now[0] += seconds

    limiter = RateLimiter(cfg, sleep=fake_sleep, clock=lambda: now[0])
    assert limiter.wait() == 0.0, "first request must not be delayed"
    now[0] += 10.0  # a slow request already burned more than max_delay
    assert limiter.wait() == 0.0, "elapsed time must count toward the gap"
    slept.clear()
    limiter.wait()
    assert slept and cfg.min_delay <= slept[0] <= cfg.max_delay, slept

    # --- backoff: bounded, jittered, never constant -------------------------
    delays = [backoff_delay(a, cfg) for a in range(1, 6) for _ in range(20)]
    assert all(0.0 <= d <= cfg.backoff_max for d in delays), "backoff exceeded cap"
    assert len(set(delays)) > 1, "no jitter — retries would collide in lockstep"

    # --- circuit breaker ----------------------------------------------------
    br = CircuitBreaker(threshold=3)
    br.record_failure("a")
    br.record_failure("b")
    br.record_success()
    assert br.consecutive_failures == 0, "success must reset the streak"
    for _ in range(2):
        br.record_failure("x")
    try:
        br.record_failure("boom")
    except CircuitOpen as exc:
        assert "CAPTURE_HEADERS" in str(exc), "error must say how to recover"
    else:
        raise AssertionError("circuit breaker never opened")

    # --- retry: transient recovers, permanent does not ----------------------
    calls = {"n": 0}

    def flaky() -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            raise FetchError("429 Too Many Requests", status=429)
        return "ok"

    br2 = CircuitBreaker(threshold=10)
    assert (
        execute_with_retry(flaky, cfg, breaker=br2, sleep=lambda _: None) == "ok"
    ), "retryable failure should have recovered"
    assert calls["n"] == 3 and br2.consecutive_failures == 0

    tries = {"n": 0}

    def not_found() -> str:
        tries["n"] += 1
        raise FetchError("404 Not Found", status=404)

    try:
        execute_with_retry(not_found, cfg, sleep=lambda _: None)
    except FetchError as exc:
        assert exc.status == 404
    else:
        raise AssertionError("non-retryable status was swallowed")
    assert tries["n"] == 1, "404 must not be retried"

    attempts = {"n": 0}

    def always_429() -> str:
        attempts["n"] += 1
        raise FetchError("429", status=429)

    try:
        execute_with_retry(always_429, cfg, sleep=lambda _: None)
    except FetchError:
        pass
    else:
        raise AssertionError("exhausted retries must re-raise")
    assert (
        attempts["n"] == cfg.max_retries
    ), f"expected {cfg.max_retries} attempts, got {attempts['n']}"

    assert random_user_agent() in USER_AGENTS
    assert len(set(USER_AGENTS)) == len(USER_AGENTS), "duplicate UA in the pool"

    print("ratelimit.py self-check OK")
