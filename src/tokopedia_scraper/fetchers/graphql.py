"""Free default backend: Tokopedia's internal GraphQL API via curl_cffi.

curl_cffi rather than requests because Tokopedia fingerprints the TLS
handshake. A perfectly-formed request from python-requests still gets a 403,
because the JA3 signature says "not a browser" before a single header is read.
`impersonate="chrome"` replays Chrome's handshake.

Nothing about Tokopedia's schema is hardcoded. The endpoint, operation name,
headers and request body all come from config/gql_capture.yaml, which
scripts/curl_to_config.py generates from a DevTools capture. When Tokopedia
changes its schema you recapture; this file does not change.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any
from urllib.parse import quote, quote_plus, urlparse

import yaml

from ..config import Config, env_secret
from ..ratelimit import FetchError, execute_with_retry, random_user_agent
from .base import Fetcher, FetchResult

log = logging.getLogger(__name__)


class CaptureIncomplete(RuntimeError):
    """The capture file is missing or lacks what this request needs.

    Deliberately not a FetchError: retrying cannot fix it, and the circuit
    breaker should not disguise it as a network problem. The fix is always to
    recapture — see docs/CAPTURE_HEADERS.md.
    """


class GraphQLFetcher(Fetcher):
    name = "graphql"

    def __init__(self, cfg: Config) -> None:
        super().__init__(cfg)
        self.capture = _load_capture(cfg.graphql.capture_file)
        self._session: Any = None

        ua = env_secret("TOKOPEDIA_UA")
        if ua:
            # One UA for the whole run. The captured cookie was issued to this
            # UA and the TLS fingerprint is fixed by `impersonate`; rotating the
            # UA on top of that is a *mismatch*, which is more detectable than
            # no rotation at all. Playwright and Managed rotate freely.
            self._user_agent = ua
        else:
            self._user_agent = random_user_agent()
            log.warning(
                "no TOKOPEDIA_UA captured — falling back to a rotated UA. "
                "Re-run scripts/curl_to_config.py so the UA matches the cookie."
            )

    # -- session -----------------------------------------------------------

    @property
    def session(self) -> Any:
        if self._session is None:
            try:
                from curl_cffi import requests as cffi_requests
            except ImportError as exc:  # pragma: no cover - environment issue
                raise RuntimeError(
                    "curl_cffi is not installed, and GraphQLFetcher cannot work "
                    "without it (plain requests gets 403 on TLS fingerprint "
                    "alone). Run: pip install curl_cffi"
                ) from exc

            self._session = cffi_requests.Session(
                impersonate=self.cfg.graphql.impersonate,
                proxies=(
                    {"http": self.cfg.proxy_url, "https": self.cfg.proxy_url}
                    if self.cfg.proxy_url
                    else None
                ),
            )
        return self._session

    def close(self) -> None:
        if self._session is not None:
            self._session.close()
            self._session = None

    # -- request building --------------------------------------------------

    def _stage(self, name: str) -> dict[str, Any]:
        stage = self.capture.get(name)
        if not isinstance(stage, dict) or not stage.get("body_template"):
            step = "step B" if name == "search" else "step D"
            raise CaptureIncomplete(
                f"config/gql_capture.yaml has no usable '{name}' stage.\n"
                f"Capture it: see docs/CAPTURE_HEADERS.md ({step}), then run "
                f"scripts/curl_to_config.py."
            )
        return stage

    def _headers(self, stage: dict[str, Any]) -> dict[str, str]:
        headers = {str(k): str(v) for k, v in (stage.get("headers") or {}).items()}

        for header_name, env_name in (stage.get("secret_env") or {}).items():
            if header_name == "user-agent":
                headers["user-agent"] = self._user_agent
                continue
            # required_by: the capture recorded this header, so the request the
            # site accepted included it. A missing value gets an actionable
            # error instead of a mystifying 403 later.
            value = env_secret(env_name, required_by=f"GraphQLFetcher ({header_name})")
            if value:
                headers[header_name] = value

        headers.setdefault("user-agent", self._user_agent)
        headers.setdefault("content-type", "application/json")
        return headers

    def _post(self, stage: dict[str, Any], body: str, describe: str) -> FetchResult:
        endpoint = stage["endpoint"]
        try:
            response = self.session.post(
                endpoint,
                data=body.encode("utf-8"),
                headers=self._headers(stage),
                timeout=self.cfg.graphql.timeout,
            )
        except Exception as exc:  # curl_cffi raises its own exception tree
            # status=None marks it retryable: connections drop for reasons that
            # have nothing to do with us.
            raise FetchError(f"{describe}: {type(exc).__name__}: {exc}") from exc

        if response.status_code != 200:
            raise FetchError(
                f"{describe}: HTTP {response.status_code}", status=response.status_code
            )

        try:
            payload = response.json()
        except Exception as exc:
            snippet = response.text[:200].replace("\n", " ")
            raise FetchError(f"{describe}: response was not JSON ({snippet!r})") from exc

        _raise_on_graphql_errors(payload, describe)

        return FetchResult(
            payload=payload,
            fetcher=self.name,
            url=endpoint,
            status=response.status_code,
        )

    # -- Fetcher interface -------------------------------------------------

    def search(self, keyword: str, page: int) -> FetchResult:
        stage = self._stage("search")
        paging = stage.get("paging") or {}
        mode = paging.get("mode", "none")

        if page > 1 and mode == "none":
            raise CaptureIncomplete(
                f"asked for page {page}, but the capture has no paging parameter "
                f"(paging.mode = none). Capture page 2 as well — "
                f"docs/CAPTURE_HEADERS.md step C — and re-run "
                f"scripts/curl_to_config.py."
            )

        rows = int(paging.get("rows_per_page") or self.cfg.search.rows_per_page)

        # The offset is anchored on the (page, offset) pair actually observed
        # during capture rather than assumed to be (page - 1) * rows — a real
        # capture had page 2 carrying offset 16 with rows 8, which that formula
        # gets wrong. Extrapolating in whole steps from a measured point matches
        # whatever the site does without needing to know why it does it.
        anchor_page = int(paging.get("anchor_page") or 1)
        anchor_start = int(paging.get("anchor_start") or 0)
        start = anchor_start + (page - anchor_page) * rows

        if start < 0:
            raise CaptureIncomplete(
                f"page {page} extrapolates to a negative offset ({start}). The "
                f"capture was taken on page {anchor_page}; recapture from page 1 "
                f"(docs/CAPTURE_HEADERS.md step C), or start the run at page "
                f"{anchor_page}."
            )
        if page < anchor_page:
            log.warning(
                "page %d is below the captured anchor page %d — the offset is "
                "extrapolated and may not line up with what the site expects.",
                page,
                anchor_page,
            )

        body = _render(
            stage["body_template"],
            KEYWORD=_encode_keyword(keyword, stage.get("keyword_encoding", "plus")),
            PAGE=str(page),
            START=str(start),
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
        result.meta = {"product_url": product_url, "shop": shop, "slug": slug}
        return result


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


def _load_capture(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise CaptureIncomplete(
            f"{path} not found. GraphQLFetcher has no hardcoded query names or "
            f"payloads by design — it needs a DevTools capture.\n"
            f"Follow docs/CAPTURE_HEADERS.md, then run:\n"
            f'  python scripts/curl_to_config.py capture_page1.txt '
            f'capture_page2.txt --keyword "air fryer"\n'
            f"Or switch backends: fetcher: playwright in config.yaml."
        )
    document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(document, dict):
        raise CaptureIncomplete(f"{path} is not a YAML mapping — regenerate it.")

    for stage_name in ("search", "pdp"):
        for note in (document.get(stage_name) or {}).get("notes", []):
            if str(note).startswith("TODO"):
                log.warning("capture %s: %s", stage_name, note)
    return document


def _encode_keyword(keyword: str, encoding: str) -> str:
    if encoding == "plus":
        return quote_plus(keyword)
    if encoding == "percent":
        return quote(keyword)
    # raw: the keyword sits directly inside a JSON string, so it still has to
    # survive JSON escaping.
    return json.dumps(keyword)[1:-1]


def _render(template: str, **values: str) -> str:
    body = template
    for key, value in values.items():
        body = body.replace("{{" + key + "}}", value)
    leftover = [
        placeholder
        for placeholder in ("KEYWORD", "PAGE", "START", "ROWS", "SHOP", "SLUG", "URL")
        if "{{" + placeholder + "}}" in body
    ]
    if leftover:
        log.debug("body_template still contains placeholders: %s", leftover)
    return body


def _split_product_url(product_url: str) -> tuple[str, str]:
    parts = [p for p in urlparse(product_url).path.split("/") if p]
    if len(parts) < 2:
        # A per-product data problem, not a capture problem — so FetchError,
        # not CaptureIncomplete. status=404 marks it permanent, so the row gets
        # recorded and skipped rather than aborting the run. One malformed URL
        # out of 19k once killed a scrape at row 16,036.
        raise FetchError(
            f"unusable product URL {product_url!r} — expected "
            f"https://www.tokopedia.com/<shop>/<slug>",
            status=404,
        )
    return parts[0], parts[1]


# GraphQL errors that will never succeed on a retry. A product the seller has
# deleted is gone: asking five times with backoff wastes a minute per row, and
# across runs it wastes that minute again every single time.
_PERMANENT_GQL_ERRORS = ("not found", "not exist", "unavailable")


def _raise_on_graphql_errors(payload: Any, describe: str) -> None:
    """GraphQL reports failures with HTTP 200 and an `errors` array."""
    documents = payload if isinstance(payload, list) else [payload]
    for doc in documents:
        if isinstance(doc, dict) and doc.get("errors"):
            messages = "; ".join(
                str(e.get("message", e))[:200] if isinstance(e, dict) else str(e)[:200]
                for e in doc["errors"]
            )
            lowered = messages.lower()
            permanent = any(marker in lowered for marker in _PERMANENT_GQL_ERRORS)
            # 404 sits outside RETRYABLE_STATUS, so the retry layer gives up at
            # once instead of burning five attempts on a product that is gone.
            raise FetchError(
                f"{describe}: GraphQL errors: {messages}",
                status=404 if permanent else None,
            )


if __name__ == "__main__":  # pragma: no cover - manual smoke check
    # Offline: exercises templating and error handling. No network, no curl_cffi.
    logging.basicConfig(level=logging.CRITICAL)

    template = (
        '[{"operationName":"Q","variables":{"params":'
        '"q={{KEYWORD}}&start={{START}}&rows={{ROWS}}","adParams":"page={{PAGE}}"}}]'
    )
    rendered = _render(template, KEYWORD="air+fryer", START="60", ROWS="60", PAGE="2")
    assert "{{" not in rendered, rendered
    assert "start=60" in rendered and "page=2" in rendered
    json.loads(rendered)  # must still be valid JSON after substitution

    assert _encode_keyword("air fryer", "plus") == "air+fryer"
    assert _encode_keyword("air fryer", "percent") == "air%20fryer"
    assert _encode_keyword('kaos "polos"', "raw") == 'kaos \\"polos\\"'
    # A quote in the keyword must not break the surrounding JSON document.
    json.loads('{"q":"' + _encode_keyword('kaos "polos"', "raw") + '"}')

    assert _split_product_url("https://www.tokopedia.com/tokoa/air-fryer-5l") == (
        "tokoa",
        "air-fryer-5l",
    )
    # A malformed URL must be a per-product failure, not a fatal one, and must
    # be permanent so the row is recorded and never retried.
    try:
        _split_product_url("https://www.tokopedia.com/shoponly/")
    except FetchError as exc:
        assert exc.status == 404 and exc.is_gone
        assert not exc.retryable
    else:
        raise AssertionError("malformed product URL accepted")

    # GraphQL failures arrive as HTTP 200 with an errors array.
    try:
        _raise_on_graphql_errors([{"errors": [{"message": "field not found"}]}], "t")
    except FetchError as exc:
        assert "field not found" in str(exc)
    else:
        raise AssertionError("GraphQL errors array was ignored")
    _raise_on_graphql_errors({"data": {"ok": True}}, "t")  # must not raise

    try:
        _load_capture(Path("does/not/exist.yaml"))
    except CaptureIncomplete as exc:
        assert "CAPTURE_HEADERS" in str(exc), "error must point at the recovery doc"
    else:
        raise AssertionError("missing capture file accepted")

    print("fetchers/graphql.py self-check OK")
