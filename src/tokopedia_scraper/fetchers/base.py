"""The Fetcher contract and backend selection.

Every backend returns the *raw, unparsed* response. Parsing lives in
parsers.py, so switching backends never touches the pipeline, and a stored raw
response can be re-parsed later without re-scraping.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from ..config import Config
from ..ratelimit import CircuitBreaker, FetchError, RateLimiter

log = logging.getLogger(__name__)


@dataclass(slots=True)
class FetchResult:
    """One raw response, plus the provenance needed to debug it later."""

    payload: Any  # dict for JSON backends, str of HTML for browser backends
    fetcher: str
    url: str
    status: int | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def is_html(self) -> bool:
        return isinstance(self.payload, str)


class Fetcher(ABC):
    """Swappable data-acquisition backend.

    Implementations must not parse, must not touch the database, and must raise
    FetchError (never a backend-specific exception) so the retry layer can
    treat all backends alike.
    """

    name: str = "base"

    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.limiter = RateLimiter(cfg.rate_limit)
        self.breaker = CircuitBreaker(cfg.rate_limit.circuit_breaker_threshold)

    @abstractmethod
    def search(self, keyword: str, page: int) -> FetchResult:
        """Stage 1: one page of search results. `page` is 1-based."""

    @abstractmethod
    def fetch_pdp(self, product_url: str) -> FetchResult:
        """Stage 2: one product detail page."""

    def close(self) -> None:
        """Release sockets/browsers. Safe to call more than once."""

    def __enter__(self) -> "Fetcher":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()


class AutoFetcher(Fetcher):
    """GraphQL first, Playwright once GraphQL keeps failing.

    One-way: it does not switch back. Flapping between backends mid-run would
    make a failure impossible to diagnose, and if GraphQL is being blocked it
    will still be blocked five minutes later.
    """

    name = "auto"

    def __init__(self, cfg: Config) -> None:
        super().__init__(cfg)
        self._primary: Fetcher | None = _build(cfg, "graphql")
        self._fallback: Fetcher | None = None
        self._consecutive_failures = 0
        self._switched = False

    @property
    def active(self) -> Fetcher:
        if self._switched:
            if self._fallback is None:
                self._fallback = _build(self.cfg, "playwright")
            return self._fallback
        assert self._primary is not None
        return self._primary

    def _switch(self, reason: str) -> None:
        if self._switched:
            return
        log.warning(
            "auto: switching graphql -> playwright after %d consecutive "
            "failures (%s). Slower, but far harder to block.",
            self._consecutive_failures,
            reason,
        )
        self._switched = True
        if self._primary is not None:
            self._primary.close()
            self._primary = None

    def _call(self, method: str, *args: Any) -> FetchResult:
        try:
            result: FetchResult = getattr(self.active, method)(*args)
        except FetchError as exc:
            self._consecutive_failures += 1
            if self._consecutive_failures >= self.cfg.auto.fallback_after_failures:
                self._switch(str(exc))
                # Retry once on the fallback so the caller sees a result rather
                # than an error the switch has already made obsolete.
                self._consecutive_failures = 0
                return getattr(self.active, method)(*args)
            raise
        self._consecutive_failures = 0
        return result

    def search(self, keyword: str, page: int) -> FetchResult:
        return self._call("search", keyword, page)

    def fetch_pdp(self, product_url: str) -> FetchResult:
        return self._call("fetch_pdp", product_url)

    def close(self) -> None:
        for f in (self._primary, self._fallback):
            if f is not None:
                f.close()


def _build(cfg: Config, name: str) -> Fetcher:
    """Instantiate one concrete backend.

    Imports are deferred: curl_cffi and playwright are heavy and optional, and
    someone running only `export` or `stats` should not need either installed.
    """
    if name == "graphql":
        from .graphql import GraphQLFetcher

        return GraphQLFetcher(cfg)
    if name == "playwright":
        from .playwright_fetcher import PlaywrightFetcher

        return PlaywrightFetcher(cfg)
    if name == "managed":
        from .managed import ManagedFetcher

        return ManagedFetcher(cfg)
    raise ValueError(
        f"Unknown fetcher {name!r}. Valid: graphql, playwright, managed, auto."
    )


def get_fetcher(cfg: Config, override: str | None = None) -> Fetcher:
    """Build the backend named by config (or `override`, e.g. from --fetcher)."""
    name = override or cfg.fetcher
    if name == "auto":
        return AutoFetcher(cfg)
    fetcher = _build(cfg, name)
    log.info("fetcher: %s", fetcher.name)
    return fetcher


if __name__ == "__main__":  # pragma: no cover - manual smoke check
    logging.basicConfig(level=logging.CRITICAL)

    cfg = Config(fetcher="auto")
    cfg.auto.fallback_after_failures = 2

    class Stub(Fetcher):
        def __init__(self, name: str, fail: int) -> None:
            super().__init__(cfg)
            self.name = name
            self.remaining_failures = fail
            self.closed = False

        def search(self, keyword: str, page: int) -> FetchResult:
            if self.remaining_failures > 0:
                self.remaining_failures -= 1
                raise FetchError("403 blocked", status=403)
            return FetchResult(payload={"k": keyword}, fetcher=self.name, url="x")

        def fetch_pdp(self, product_url: str) -> FetchResult:
            return FetchResult(payload={}, fetcher=self.name, url=product_url)

        def close(self) -> None:
            self.closed = True

    primary, fallback = Stub("graphql", fail=99), Stub("playwright", fail=0)

    # Built by hand so the self-check never imports curl_cffi or playwright.
    auto = AutoFetcher.__new__(AutoFetcher)
    Fetcher.__init__(auto, cfg)
    auto._primary, auto._fallback = primary, fallback
    auto._consecutive_failures, auto._switched = 0, False

    try:
        auto.search("air fryer", 1)
    except FetchError:
        pass
    else:
        raise AssertionError("first failure must propagate, not switch")
    assert not auto._switched, "switched too early"

    result = auto.search("air fryer", 1)
    assert auto._switched, "never fell back after reaching the threshold"
    assert result.fetcher == "playwright", result.fetcher
    assert primary.closed, "primary must be released after switching"

    assert auto.search("kopi", 1).fetcher == "playwright", "switch must be one-way"

    try:
        _build(cfg, "nonsense")
    except ValueError as exc:
        assert "graphql" in str(exc), "error must list the valid names"
    else:
        raise AssertionError("unknown fetcher name accepted")

    print("fetchers/base.py self-check OK")
