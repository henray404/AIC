"""Free fallback backend: a real browser.

Slower than GraphQLFetcher and far harder to block, because it *is* Chrome.

The important design choice: this does not scrape rendered HTML. It drives the
page and intercepts the GraphQL responses the page itself makes, so the payload
handed back has the same shape as GraphQLFetcher's and `parsers.py` works
unchanged. Scraping the DOM instead would mean inventing CSS selectors nobody
has verified, and would leave two parsers to keep in lockstep.
"""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import quote_plus

from ..config import Config
from ..ratelimit import FetchError, random_user_agent
from .base import Fetcher, FetchResult

log = logging.getLogger(__name__)

SEARCH_URL = "https://www.tokopedia.com/search?q={keyword}&page={page}"

# A response is the one we want if its body mentions one of these. Taken from
# the same captures that drive parsers.py, not guessed.
SEARCH_MARKERS = ("searchProductV5", "searchProduct")
PDP_MARKERS = ("pdpMainInfo",)

# Playwright resource types safe to abort. Deliberately excludes `document`,
# `script`, `xhr` and `fetch`: blocking those would stop the very GraphQL calls
# this backend exists to intercept.
BLOCKABLE = {"font", "media", "stylesheet", "image", "imageset", "other"}


class PlaywrightFetcher(Fetcher):
    name = "playwright"

    def __init__(self, cfg: Config) -> None:
        super().__init__(cfg)
        self._playwright: Any = None
        self._context: Any = None
        self._user_agent = random_user_agent()

    # -- browser lifecycle -------------------------------------------------

    def _ensure_browser(self) -> Any:
        if self._context is not None:
            return self._context

        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:  # pragma: no cover - environment issue
            raise RuntimeError(
                "playwright is not installed. Run:\n"
                "  pip install playwright\n"
                "  playwright install chromium"
            ) from exc

        if self.cfg.playwright.headless:
            log.warning(
                "playwright.headless is true. Tokopedia refuses headless "
                "Chromium at the HTTP/2 level (net::ERR_HTTP2_PROTOCOL_ERROR) "
                "on every page — measured, with no other options set. Expect "
                "every navigation to fail. Set playwright.headless: false."
            )

        pw = self._playwright = sync_playwright().start()
        opts: dict[str, Any] = {"headless": self.cfg.playwright.headless}
        if self.cfg.proxy_url:
            opts["proxy"] = {"server": self.cfg.proxy_url}

        if self.cfg.playwright.persistent_profile:
            # A persistent profile keeps cookies between runs, so the site does
            # not treat every run as a brand new visitor.
            profile = self.cfg.playwright.profile_dir
            profile.mkdir(parents=True, exist_ok=True)
            self._context = pw.chromium.launch_persistent_context(
                str(profile), user_agent=self._user_agent, **opts
            )
        else:
            browser = pw.chromium.launch(**opts)
            self._context = browser.new_context(user_agent=self._user_agent)

        self._context.set_default_timeout(self.cfg.playwright.selector_timeout_ms)
        self._install_blocking(self._context)
        return self._context

    def _install_blocking(self, context: Any) -> None:
        blocked = {r for r in self.cfg.playwright.block_resources if r in BLOCKABLE}
        if not blocked:
            return

        def route(handler: Any) -> None:
            if handler.request.resource_type in blocked:
                handler.abort()
            else:
                handler.continue_()

        context.route("**/*", route)
        log.info("playwright: blocking resource types %s", sorted(blocked))

    def close(self) -> None:
        if self._context is not None:
            try:
                self._context.close()
            finally:
                self._context = None
        if self._playwright is not None:
            try:
                self._playwright.stop()
            finally:
                self._playwright = None

    # -- interception ------------------------------------------------------

    def _collect(self, url: str, markers: tuple[str, ...], scroll: bool) -> Any:
        """Open `url` and return the first GraphQL payload matching `markers`."""
        context = self._ensure_browser()
        page = context.new_page()
        captured: list[Any] = []

        def on_response(response: Any) -> None:
            if captured or "gql.tokopedia.com" not in response.url:
                return
            try:
                body = response.text()
            except Exception:
                return
            if not any(marker in body for marker in markers):
                return
            try:
                captured.append(response.json())
            except Exception:
                log.debug("matching response was not JSON: %s", response.url)

        page.on("response", on_response)

        try:
            page.goto(url, timeout=self.cfg.playwright.nav_timeout_ms)

            if scroll:
                # Search results lazy-load. Stepwise scrolling triggers the
                # follow-up GraphQL calls; jumping straight to the bottom often
                # skips them.
                for _ in range(self.cfg.playwright.scroll_steps):
                    if captured:
                        break
                    page.mouse.wheel(0, 1400)
                    page.wait_for_timeout(self.cfg.playwright.scroll_pause_ms)

            if not captured:
                page.wait_for_timeout(self.cfg.playwright.selector_timeout_ms)
        except Exception as exc:
            raise FetchError(f"playwright navigation failed: {exc}") from exc
        finally:
            page.close()

        if not captured:
            raise FetchError(
                f"no GraphQL response matching {markers} arrived within the "
                f"timeout at {url}"
            )
        return captured[0]

    # -- Fetcher interface -------------------------------------------------

    def search(self, keyword: str, page: int) -> FetchResult:
        url = SEARCH_URL.format(keyword=quote_plus(keyword), page=page)
        self.limiter.wait()
        payload = self._collect(url, SEARCH_MARKERS, scroll=True)
        return FetchResult(
            payload=payload,
            fetcher=self.name,
            url=url,
            status=200,
            meta={"keyword": keyword, "page": page},
        )

    def fetch_pdp(self, product_url: str) -> FetchResult:
        self.limiter.wait()
        payload = self._collect(product_url, PDP_MARKERS, scroll=False)
        return FetchResult(
            payload=payload,
            fetcher=self.name,
            url=product_url,
            status=200,
            meta={"product_url": product_url},
        )


if __name__ == "__main__":  # pragma: no cover - manual smoke check
    # Offline: URL building and resource-block filtering only. Driving a real
    # browser is exercised by `python main.py search --fetcher playwright`.
    logging.basicConfig(level=logging.CRITICAL)

    cfg = Config()
    fetcher = PlaywrightFetcher(cfg)

    url = SEARCH_URL.format(keyword=quote_plus("air fryer"), page=3)
    assert url.endswith("q=air+fryer&page=3"), url
    assert quote_plus("kaos polos pria") == "kaos+polos+pria"

    cfg.playwright.block_resources = ["font", "media", "nonsense", "image"]
    blocked = {r for r in cfg.playwright.block_resources if r in BLOCKABLE}
    assert blocked == {"font", "media", "image"}, blocked
    assert "document" not in BLOCKABLE, "blocking documents would break navigation"
    assert "script" not in BLOCKABLE, "blocking scripts would stop the GraphQL calls"
    assert "xhr" not in BLOCKABLE and "fetch" not in BLOCKABLE

    # close() must be safe before anything was ever started, and idempotent.
    fetcher.close()
    fetcher.close()

    print("fetchers/playwright_fetcher.py self-check OK")
