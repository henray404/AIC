"""Paid backend: a third-party scraping API stands in for our own networking.

For when a deadline is closer than the block rate is tolerable.

HONESTY NOTE — read this before spending money
----------------------------------------------
The provider request shapes below are written from general familiarity with
these services, NOT from their current documentation. Every provider-specific
parameter is marked `TODO verify`. Nothing here has been run against a live
account, and a wrong parameter usually surfaces as a confusing 4xx rather than
an obvious error.

Before a paid run, check the provider docs for: the endpoint path, how a POST
body is forwarded to the target, and how request headers are passed through.
Then test exactly one request:

    python main.py enrich --fetcher managed --limit 1

The credential handling, provider selection, error messages and the reuse of
the captured GraphQL request *are* finished and tested. Only the per-provider
wire format needs confirming.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from ..config import Config, env_secret
from ..ratelimit import FetchError, execute_with_retry
from .base import Fetcher, FetchResult
from .graphql import (
    CaptureIncomplete,
    _encode_keyword,
    _load_capture,
    _render,
    _split_product_url,
)

log = logging.getLogger(__name__)

# provider -> env var holding its credential.
PROVIDER_KEYS = {
    "scrapingbee": "SCRAPINGBEE_API_KEY",
    "zenrows": "ZENROWS_API_KEY",
    "apify": "APIFY_API_TOKEN",
}


class ManagedFetcher(Fetcher):
    """Sends the captured GraphQL request through a paid scraping API.

    Reuses the same capture file as GraphQLFetcher, so switching backends never
    means recapturing anything.
    """

    name = "managed"

    def __init__(self, cfg: Config) -> None:
        super().__init__(cfg)
        provider = cfg.managed.provider
        if provider not in PROVIDER_KEYS:
            raise ValueError(
                f"Unknown managed provider {provider!r}. "
                f"Valid: {', '.join(sorted(PROVIDER_KEYS))}."
            )
        self.provider = provider
        self.name = f"managed:{provider}"

        # Fail at construction, not on the first request: a run that dies 200
        # products in because of a missing key is worse than one that never
        # starts.
        self.api_key = env_secret(
            PROVIDER_KEYS[provider], required_by=f"ManagedFetcher ({provider})"
        )
        self.capture = _load_capture(cfg.graphql.capture_file)
        self._session: Any = None

        if provider != "scrapingbee":
            log.warning(
                "provider %r is a stub — read the TODOs in fetchers/managed.py "
                "before relying on it",
                provider,
            )

    @property
    def session(self) -> Any:
        if self._session is None:
            import requests

            self._session = requests.Session()
        return self._session

    def close(self) -> None:
        if self._session is not None:
            self._session.close()
            self._session = None

    # -- request building --------------------------------------------------

    def _stage(self, name: str) -> dict[str, Any]:
        stage = self.capture.get(name)
        if not isinstance(stage, dict) or not stage.get("body_template"):
            raise CaptureIncomplete(
                f"config/gql_capture.yaml has no usable '{name}' stage. "
                f"ManagedFetcher replays the same capture GraphQLFetcher uses — "
                f"see docs/CAPTURE_HEADERS.md."
            )
        return stage

    def _target_headers(self, stage: dict[str, Any]) -> dict[str, str]:
        headers = {str(k): str(v) for k, v in (stage.get("headers") or {}).items()}
        for header_name, env_name in (stage.get("secret_env") or {}).items():
            value = env_secret(env_name)
            if value:
                headers[header_name] = value
        headers.setdefault("content-type", "application/json")
        return headers

    def _build_request(
        self, stage: dict[str, Any], body: str
    ) -> tuple[str, dict[str, Any], dict[str, str], str]:
        """-> (provider url, query params, headers, body to send)."""
        target_url = stage["endpoint"]
        target_headers = self._target_headers(stage)

        if self.provider == "scrapingbee":
            # TODO verify against https://www.scrapingbee.com/documentation/
            #   - the endpoint path
            #   - the parameter that forwards our POST body to the target
            #   - the convention for passing target headers through
            #     (commonly a prefix on each header name)
            params = {
                "api_key": self.api_key,
                "url": target_url,
                "render_js": "false",  # the target is a JSON API, not a page
                "forward_headers": "true",
            }
            headers = {f"Spb-{k}": v for k, v in target_headers.items()}
            return "https://app.scrapingbee.com/api/v1/", params, headers, body

        if self.provider == "zenrows":
            # TODO stub — verify against https://docs.zenrows.com/ before use.
            # Believed to be a request to https://api.zenrows.com/v1/ carrying
            # `apikey` and `url`, but the POST-forwarding convention is
            # unconfirmed and guessing it would just burn credits.
            raise NotImplementedError(
                "The zenrows adapter is a stub. Fill in _build_request() from "
                "https://docs.zenrows.com/ and delete this raise, or set "
                "managed.provider: scrapingbee."
            )

        # apify
        # TODO stub — Apify uses a different model entirely: you start an actor
        # run and then poll its dataset, rather than making one synchronous
        # request. That does not fit this interface without a polling wrapper.
        raise NotImplementedError(
            "The apify adapter is a stub. Apify runs actors asynchronously and "
            "needs a run-then-poll wrapper, which this synchronous Fetcher "
            "interface does not provide. Use managed.provider: scrapingbee, or "
            "implement the wrapper."
        )

    def _post(self, stage: dict[str, Any], body: str, describe: str) -> FetchResult:
        url, params, headers, payload_body = self._build_request(stage, body)

        try:
            response = self.session.post(
                url,
                params=params,
                headers=headers,
                data=payload_body.encode("utf-8"),
                timeout=self.cfg.managed.timeout,
            )
        except Exception as exc:
            raise FetchError(f"{describe}: {type(exc).__name__}: {exc}") from exc

        if response.status_code != 200:
            # Providers put the real reason in the body; without it, a 4xx here
            # is indistinguishable from a 4xx at Tokopedia.
            raise FetchError(
                f"{describe}: {self.provider} returned HTTP "
                f"{response.status_code}: {response.text[:200]}",
                status=response.status_code,
            )

        try:
            return FetchResult(
                payload=response.json(),
                fetcher=self.name,
                url=stage["endpoint"],
                status=response.status_code,
            )
        except json.JSONDecodeError as exc:
            raise FetchError(
                f"{describe}: {self.provider} did not return JSON "
                f"({response.text[:200]!r}). Check the provider parameters — "
                f"see the TODOs in fetchers/managed.py."
            ) from exc

    # -- Fetcher interface -------------------------------------------------

    def search(self, keyword: str, page: int) -> FetchResult:
        stage = self._stage("search")
        paging = stage.get("paging") or {}
        rows = int(paging.get("rows_per_page") or self.cfg.search.rows_per_page)
        anchor_page = int(paging.get("anchor_page") or 1)
        anchor_start = int(paging.get("anchor_start") or 0)

        body = _render(
            stage["body_template"],
            KEYWORD=_encode_keyword(keyword, stage.get("keyword_encoding", "plus")),
            PAGE=str(page),
            START=str(anchor_start + (page - anchor_page) * rows),
            ROWS=str(rows),
        )

        describe = f"search {keyword!r} p{page}"
        result = execute_with_retry(
            lambda: self._post(stage, body, describe),
            self.cfg.rate_limit,
            limiter=self.limiter,
            breaker=self.breaker,
            describe=describe,
        )
        result.meta = {"keyword": keyword, "page": page, "rows": rows}
        return result

    def fetch_pdp(self, product_url: str) -> FetchResult:
        stage = self._stage("pdp")
        shop, slug = _split_product_url(product_url)
        body = _render(stage["body_template"], URL=product_url, SHOP=shop, SLUG=slug)

        describe = f"pdp {slug}"
        result = execute_with_retry(
            lambda: self._post(stage, body, describe),
            self.cfg.rate_limit,
            limiter=self.limiter,
            breaker=self.breaker,
            describe=describe,
        )
        result.meta = {"product_url": product_url}
        return result


if __name__ == "__main__":  # pragma: no cover - manual smoke check
    import os

    from ..config import MissingCredential

    logging.basicConfig(level=logging.CRITICAL)

    # An unknown provider must be rejected by config validation.
    try:
        Config(managed={"provider": "nonsense"})
    except Exception as exc:
        assert "provider" in str(exc)
    else:
        raise AssertionError("unknown provider accepted by config")

    cfg = Config()
    saved = {var: os.environ.pop(var, None) for var in PROVIDER_KEYS.values()}

    # A missing key must fail loudly at construction, not mid-run.
    try:
        ManagedFetcher(cfg)
    except MissingCredential as exc:
        assert "SCRAPINGBEE_API_KEY" in str(exc)
        assert ".env" in str(exc), "the error must say where to put the key"
    else:
        raise AssertionError("missing API key did not raise")

    # With a key present, construction proceeds to the capture file, which is
    # the next thing that can legitimately be missing.
    os.environ["SCRAPINGBEE_API_KEY"] = "synthetic-key-not-real"
    try:
        fetcher = ManagedFetcher(cfg)
    except CaptureIncomplete as exc:
        assert "CAPTURE_HEADERS" in str(exc)
    else:
        assert fetcher.name == "managed:scrapingbee"
        assert fetcher.api_key == "synthetic-key-not-real"
        # The two stubs must refuse clearly rather than send a guessed request.
        for stub in ("zenrows", "apify"):
            fetcher.provider = stub
            try:
                fetcher._build_request({"endpoint": "https://x", "headers": {}}, "{}")
            except NotImplementedError as exc:
                assert "stub" in str(exc)
            else:
                raise AssertionError(f"{stub} stub silently built a request")
        fetcher.close()

    assert set(PROVIDER_KEYS) == {"scrapingbee", "zenrows", "apify"}

    for var, value in saved.items():
        if value is not None:
            os.environ[var] = value
        else:
            os.environ.pop(var, None)

    print("fetchers/managed.py self-check OK")
