#!/usr/bin/env python
"""Turn a DevTools "Copy as cURL (bash)" capture into config + .env.

Why this exists: Tokopedia's GraphQL query names, payload shapes and field names
change without notice. Nothing about them is hardcoded in this project. When
something breaks you recapture in DevTools and re-run this script — no code
changes.

Usage (see docs/CAPTURE_HEADERS.md):

    python scripts/curl_to_config.py capture_page1.txt capture_page2.txt \\
        --keyword "air fryer"

    python scripts/curl_to_config.py capture_pdp.txt --stage pdp \\
        --product-url "https://www.tokopedia.com/namatoko/nama-produk"

Two captures (page 1 and page 2) let the script *derive* the paging parameter by
diffing them, rather than guessing what it is called.
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urlparse

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent

# Headers whose values are credentials. They go to .env, never to the YAML.
SECRET_HEADERS = {
    "cookie": "TOKOPEDIA_COOKIE",
    "authorization": "TOKOPEDIA_AUTHORIZATION",
    "user-agent": "TOKOPEDIA_UA",
    "x-tkpd-akamai": "TOKOPEDIA_X_TKPD_AKAMAI",
}
# Anything matching this is treated as a secret too, even if unlisted above.
SECRET_PATTERN = re.compile(r"(token|session|secret|auth|csrf|signature)", re.I)

# Headers the HTTP client must set itself. Copying them causes broken requests
# (a stale content-length) or double-decoded bodies.
DROP_HEADERS = {
    "content-length",
    "host",
    "connection",
    "accept-encoding",
    ":authority",
    ":method",
    ":path",
    ":scheme",
}


class CurlParseError(RuntimeError):
    pass


# --------------------------------------------------------------------------
# cURL parsing
# --------------------------------------------------------------------------

# Chrome emits bash ANSI-C quoting -- $'...' -- whenever the body contains an
# escape sequence, which a GraphQL query with embedded newlines always does.
# shlex does not understand it: it leaves the `$` glued to the front of the
# string, so the body stops being valid JSON and every downstream JSON parse
# silently gives up. Decode these spans before tokenising.
_ANSI_C_RE = re.compile(r"\$'((?:[^'\\]|\\.)*)'", re.DOTALL)

_SIMPLE_ESCAPES = {
    "n": "\n",
    "t": "\t",
    "r": "\r",
    "b": "\b",
    "f": "\f",
    "v": "\v",
    "a": "\a",
    "e": "\x1b",
    "\\": "\\",
    "'": "'",
    '"': '"',
    "?": "?",
}

_HEX_DIGITS = "0123456789abcdefABCDEF"


def _decode_ansi_c(text: str) -> str:
    """Decode the escape sequences inside a bash $'...' string."""
    out: list[str] = []
    i = 0
    while i < len(text):
        char = text[i]
        if char != "\\":
            out.append(char)
            i += 1
            continue

        i += 1
        if i >= len(text):
            out.append("\\")
            break

        esc = text[i]
        i += 1

        if esc in _SIMPLE_ESCAPES:
            out.append(_SIMPLE_ESCAPES[esc])
        elif esc in ("x", "u", "U"):
            width = {"x": 2, "u": 4, "U": 8}[esc]
            digits = ""
            while len(digits) < width and i < len(text) and text[i] in _HEX_DIGITS:
                digits += text[i]
                i += 1
            out.append(chr(int(digits, 16)) if digits else "\\" + esc)
        elif esc in "01234567":
            octal = esc
            while len(octal) < 3 and i < len(text) and text[i] in "01234567":
                octal += text[i]
                i += 1
            out.append(chr(int(octal, 8)))
        else:
            # Unknown escape: bash keeps both characters.
            out.append("\\" + esc)
    return "".join(out)


def _extract_ansi_c(text: str) -> tuple[str, dict[str, str]]:
    """Replace every $'...' span with a bare placeholder token.

    Returns the rewritten command plus a placeholder -> decoded value map. The
    placeholder contains no quotes or spaces, so shlex passes it through as one
    token that can be swapped back after tokenising.
    """
    replacements: dict[str, str] = {}

    def swap(match: "re.Match[str]") -> str:
        token = f"__ANSIC_{len(replacements)}__"
        replacements[token] = _decode_ansi_c(match.group(1))
        return token

    return _ANSI_C_RE.sub(swap, text), replacements


def parse_curl(text: str) -> dict[str, Any]:
    """Parse a `curl` command line into url / method / headers / body."""
    text = text.strip()
    if not text:
        raise CurlParseError("capture file is empty")

    # Chrome's cmd.exe variant uses ^ line-continuations and doubled quotes,
    # which shlex cannot handle. Detect it early with a clear message.
    if "^" in text and "\\\n" not in text and "'" not in text:
        raise CurlParseError(
            "this looks like 'Copy as cURL (cmd)'. Re-copy using "
            "'Copy as cURL (bash)' — see docs/CAPTURE_HEADERS.md step B5."
        )

    text = text.replace("\\\n", " ").replace("^\n", " ")

    text, ansi_c = _extract_ansi_c(text)
    try:
        tokens = shlex.split(text)
    except ValueError as exc:
        raise CurlParseError(f"could not tokenise the cURL command: {exc}") from exc
    tokens = [ansi_c.get(token, token) for token in tokens]

    if not tokens or not tokens[0].endswith("curl"):
        got = tokens[0] if tokens else ""
        raise CurlParseError(f"expected the file to start with 'curl', got {got!r}")

    url: str | None = None
    method: str | None = None
    headers: dict[str, str] = {}
    body: str | None = None

    i = 1
    while i < len(tokens):
        token = tokens[i]

        if token in ("-H", "--header") and i + 1 < len(tokens):
            raw = tokens[i + 1]
            name, sep, value = raw.partition(":")
            name = name.strip().lower()
            # `-H 'foo;'` is curl's syntax for "send foo with an empty value".
            # Without this branch the trailing semicolon becomes part of the
            # header name and the empty value gets filed as a required secret,
            # which makes GraphQLFetcher refuse to start over a header that
            # never carried anything.
            if not sep and name.endswith(";"):
                i += 2
                continue
            if name and name not in DROP_HEADERS:
                headers[name] = value.strip()
            i += 2
        elif token in ("-b", "--cookie") and i + 1 < len(tokens):
            headers["cookie"] = tokens[i + 1]
            i += 2
        elif token in ("-A", "--user-agent") and i + 1 < len(tokens):
            headers["user-agent"] = tokens[i + 1]
            i += 2
        elif token in ("-X", "--request") and i + 1 < len(tokens):
            method = tokens[i + 1].upper()
            i += 2
        elif token in ("-d", "--data", "--data-raw", "--data-binary", "--data-ascii"):
            if i + 1 >= len(tokens):
                raise CurlParseError(f"{token} given without a value")
            body = tokens[i + 1]
            i += 2
        elif token.startswith("-"):
            i += 1  # --compressed, -s, -L, ... nothing we need
        else:
            if url is None:
                url = token
            i += 1

    if url is None:
        raise CurlParseError("no URL found in the cURL command")

    return {
        "url": url,
        "method": method or ("POST" if body else "GET"),
        "headers": headers,
        "body": body,
    }


def split_secrets(
    headers: dict[str, str]
) -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    """-> (safe headers, {header: env var name}, {env var name: value})"""
    safe: dict[str, str] = {}
    secret_env: dict[str, str] = {}
    values: dict[str, str] = {}

    for name, value in headers.items():
        env_name = SECRET_HEADERS.get(name)
        if env_name is None and SECRET_PATTERN.search(name):
            env_name = "TOKOPEDIA_" + re.sub(
                r"[^A-Z0-9]+", "_", name.upper()
            ).strip("_")

        if env_name:
            secret_env[name] = env_name
            values[env_name] = value
        else:
            safe[name] = value

    return safe, secret_env, values


# --------------------------------------------------------------------------
# Templating
# --------------------------------------------------------------------------


def templatise_keyword(body: str, keyword: str) -> tuple[str, str]:
    """Replace the searched keyword with {{KEYWORD}}. -> (body, encoding used)"""
    variants = [
        (keyword.replace(" ", "+"), "plus"),
        (keyword.replace(" ", "%20"), "percent"),
        (keyword, "raw"),
    ]
    for needle, encoding in variants:
        if needle and needle in body:
            return body.replace(needle, "{{KEYWORD}}"), encoding
    raise CurlParseError(
        f"keyword {keyword!r} does not appear in the captured request body.\n"
        f"Pass the exact term you typed into Tokopedia via --keyword, or check "
        f"that you copied the search request and not some other GraphQL call."
    )


def _walk(value: Any, path: str = "") -> Iterator[tuple[str, Any]]:
    if isinstance(value, dict):
        for k, v in value.items():
            yield from _walk(v, f"{path}.{k}" if path else str(k))
    elif isinstance(value, list):
        for idx, v in enumerate(value):
            yield from _walk(v, f"{path}.{idx}")
    else:
        yield path, value


def _querystring_params(text: str) -> dict[str, str] | None:
    """Tokopedia nests a query string inside a JSON string field."""
    if "=" not in text:
        return None
    params: dict[str, str] = {}
    for part in text.split("&"):
        key, sep, val = part.partition("=")
        if not sep or not key:
            return None
        params[key] = val
    return params or None


def find_paging_diff(body1: str, body2: str) -> list[tuple[str, str, str]]:
    """Scalar values that differ between a page-1 and a page-2 capture."""
    diffs: list[tuple[str, str, str]] = []
    try:
        doc1, doc2 = json.loads(body1), json.loads(body2)
    except json.JSONDecodeError:
        return diffs

    flat1 = dict(_walk(doc1))
    flat2 = dict(_walk(doc2))

    for path, v1 in flat1.items():
        v2 = flat2.get(path)
        if v2 is None or v1 == v2:
            continue
        if isinstance(v1, str) and isinstance(v2, str):
            p1, p2 = _querystring_params(v1), _querystring_params(v2)
            if p1 and p2:
                for key in p1:
                    if key in p2 and p1[key] != p2[key]:
                        diffs.append((f"{path}?{key}", p1[key], p2[key]))
                continue
        diffs.append((path, str(v1), str(v2)))
    return diffs


def _replace_param(
    body: str, key: str, value: str, placeholder: str
) -> tuple[str, int]:
    """Substitute `key=value` (query string) or `"key": value` (JSON)."""
    qs = re.compile(rf"(?<![\w-]){re.escape(key)}=({re.escape(value)})(?=&|\"|$)")
    body, n = qs.subn(lambda m: m.group(0).replace(m.group(1), placeholder), body)
    if n:
        return body, n

    js = re.compile(rf'("{re.escape(key)}"\s*:\s*)"?{re.escape(value)}"?')
    body, n = js.subn(rf"\g<1>{placeholder}", body)
    return body, n


def apply_paging(
    body: str, diffs: list[tuple[str, str, str]], rows_hint: int
) -> tuple[str, dict[str, Any], list[str]]:
    """Turn the detected paging parameter into a placeholder.

    Only numeric differences are considered. A field going 1 -> 2 is a page
    number; a field going 0 -> N is a row offset.
    """
    notes: list[str] = []
    paging: dict[str, Any] = {"mode": "none"}

    numeric = [
        (path, v1, v2)
        for path, v1, v2 in diffs
        if v1.lstrip("-").isdigit() and v2.lstrip("-").isdigit()
    ]
    if not numeric:
        notes.append(
            "TODO: no numeric difference between the two captures. Paging could "
            "not be derived — edit `paging` and `body_template` by hand, or "
            "recapture page 2 (docs/CAPTURE_HEADERS.md step C)."
        )
        return body, paging, notes

    def key_of(path: str) -> str:
        return path.split("?")[-1].split(".")[-1]

    # The page counter sets the scale for everything else. Two captures are not
    # necessarily adjacent pages — scrolling can skip one — so the page size is
    # (change in row offset) / (change in page number), never the raw offset
    # delta. Getting this wrong silently doubles or halves every offset the
    # scraper ever sends.
    page_diff = next((d for d in numeric if key_of(d[0]) == "page"), None)
    page_step = 1
    if page_diff:
        page_step = int(page_diff[2]) - int(page_diff[1])
        if page_step < 1:
            notes.append(
                f"TODO: 'page' went {page_diff[1]} -> {page_diff[2]}, which is "
                f"not forward progress. Recapture two pages in order."
            )
            return body, paging, notes
        if page_step > 1:
            notes.append(
                f"note: the two captures are {page_step} pages apart "
                f"({page_diff[1]} -> {page_diff[2]}), so the page size is "
                f"derived by dividing the offset step by {page_step}."
            )
    else:
        notes.append(
            "TODO: no parameter literally named 'page' changed between the "
            "captures, so the pages are assumed to be adjacent. If they were "
            "not, paging.rows_per_page is wrong by that factor — check it "
            "against how many products one response actually returns."
        )

    # Every numeric field that moved gets templated, not just the first. A
    # payload often carries an offset, an ad offset and a page counter at once;
    # templating only one leaves the request internally inconsistent from the
    # next page onward, which the server may or may not forgive.
    found: list[dict[str, Any]] = []

    for path, v1, v2 in numeric:
        key = key_of(path)
        n1, n2 = int(v1), int(v2)
        delta = n2 - n1

        if key == "page":
            placeholder, mode, rows = "{{PAGE}}", "page", rows_hint
        elif delta > 0 and delta % page_step == 0:
            placeholder, mode, rows = "{{START}}", "start", delta // page_step
        else:
            notes.append(
                f"note: field {path!r} changed {v1} -> {v2}, which is not a "
                f"whole multiple of the page step — left as-is."
            )
            continue

        replaced, count = _replace_param(body, key, v1, placeholder)
        if not count:
            notes.append(
                f"TODO: detected paging field {path!r} but could not substitute "
                f"it into the template — edit body_template by hand."
            )
            continue

        body = replaced
        found.append({"mode": mode, "rows_per_page": rows, "param": key, "first": n1})
        notes.append(f"paging derived from capture diff: {key} {v1} -> {v2} ({mode})")

    if not found:
        return body, paging, notes

    # An explicit row offset is authoritative: it is what actually selects the
    # slice. A page counter is often decorative, but it anchors the arithmetic.
    page_entry = next((f for f in found if f["mode"] == "page"), None)
    start_entry = next((f for f in found if f["mode"] == "start"), None)
    paging = dict(start_entry or page_entry or {})

    if start_entry:
        # The offset is NOT assumed to be (page - 1) * rows: one real capture
        # had page 2 carrying offset 16 with rows 8, which that formula gets
        # wrong. Anchor on the observed (page, offset) pair and extrapolate in
        # whole steps, so the arithmetic matches whatever the site does.
        paging["anchor_start"] = start_entry["first"]
        if page_entry:
            paging["anchor_page"] = page_entry["first"]
        else:
            paging["anchor_page"] = 1
            notes.append(
                "TODO: the capture has a row offset but no page counter, so the "
                "page it came from is unknown — assuming page 1. If the capture "
                "was taken further in, set paging.anchor_page by hand."
            )
        if paging["anchor_page"] > 1:
            implied = paging["anchor_start"] - (paging["anchor_page"] - 1) * paging[
                "rows_per_page"
            ]
            notes.append(
                f"note: anchored at page {paging['anchor_page']} "
                f"(offset {paging['anchor_start']}); page 1 therefore resolves "
                f"to offset {implied}."
            )

    if len(found) > 1:
        paging["also_templated"] = [
            f["param"] for f in found if f["param"] != paging.get("param")
        ]
    paging.pop("first", None)

    rows = paging.get("rows_per_page", 0)
    if paging["mode"] == "start" and rows > 0:
        body, rows_count = _replace_param(body, "rows", str(rows), "{{ROWS}}")
        if rows_count:
            notes.append(f"rows parameter templated ({rows} per page)")

    return body, paging, notes


def templatise_pdp(body: str, product_url: str) -> tuple[str, list[str]]:
    """Replace shop/slug/url from a sample PDP capture with placeholders."""
    notes: list[str] = []
    parts = [p for p in urlparse(product_url).path.split("/") if p]
    if len(parts) < 2:
        raise CurlParseError(
            f"--product-url must look like "
            f"https://www.tokopedia.com/<shop>/<slug>, got {product_url!r}"
        )
    shop, slug = parts[0], parts[1]

    for needle, placeholder in (
        (product_url, "{{URL}}"),
        (slug, "{{SLUG}}"),
        (shop, "{{SHOP}}"),
    ):
        if needle in body:
            body = body.replace(needle, placeholder)
            notes.append(f"templated {placeholder} from {needle!r}")

    if "{{" not in body:
        notes.append(
            "TODO: neither the shop, the slug nor the URL appears in the captured "
            "PDP body. Check you copied the right request, then edit "
            "body_template by hand."
        )
    return body, notes


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------


def mask(value: str, keep: int = 6) -> str:
    return value[:keep] + "...REDACTED" if len(value) > keep else "REDACTED"


def write_env(env_path: Path, values: dict[str, str]) -> list[str]:
    """Update keys in .env, preserving every other line and all comments."""
    lines = (
        env_path.read_text(encoding="utf-8").splitlines()
        if env_path.exists()
        else ["# Written by scripts/curl_to_config.py. Gitignored. Do not commit."]
    )
    remaining = dict(values)
    out: list[str] = []

    for line in lines:
        key = line.split("=", 1)[0].strip() if "=" in line else ""
        if key in remaining:
            out.append(f"{key}={remaining.pop(key)}")
        else:
            out.append(line)

    for key, value in remaining.items():
        out.append(f"{key}={value}")

    env_path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return sorted(values)


def build_stage(
    capture: dict[str, Any],
    *,
    body_template: str,
    keyword_encoding: str | None,
    paging: dict[str, Any] | None,
    notes: list[str],
) -> tuple[dict[str, Any], dict[str, str]]:
    safe, secret_env, secret_values = split_secrets(capture["headers"])
    operation = urlparse(capture["url"]).path.rstrip("/").split("/")[-1]

    stage: dict[str, Any] = {
        "endpoint": capture["url"],
        "operation_name": operation,
        "method": capture["method"],
        "headers": safe,
        "secret_env": secret_env,
        "body_template": body_template,
    }
    if keyword_encoding:
        stage["keyword_encoding"] = keyword_encoding
    if paging:
        stage["paging"] = paging
    if notes:
        stage["notes"] = notes
    return stage, secret_values


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Convert a DevTools cURL capture into config/gql_capture.yaml + .env",
        epilog="See docs/CAPTURE_HEADERS.md for the capture procedure.",
    )
    parser.add_argument(
        "capture", type=Path, help="file containing 'Copy as cURL (bash)'"
    )
    parser.add_argument(
        "capture_page2",
        type=Path,
        nargs="?",
        help="optional second capture (page 2) used to derive the paging parameter",
    )
    parser.add_argument("--stage", choices=("search", "pdp"), default="search")
    parser.add_argument(
        "--keyword", help="the term you typed into Tokopedia (stage=search)"
    )
    parser.add_argument("--product-url", help="the product URL you opened (stage=pdp)")
    parser.add_argument("--rows", type=int, default=60, help="expected rows per page")
    parser.add_argument(
        "--out", type=Path, default=REPO_ROOT / "config" / "gql_capture.yaml"
    )
    parser.add_argument("--env", type=Path, default=REPO_ROOT / ".env")
    args = parser.parse_args(argv)

    if args.stage == "search" and not args.keyword:
        parser.error("--keyword is required for --stage search")
    if args.stage == "pdp" and not args.product_url:
        parser.error("--product-url is required for --stage pdp")

    try:
        capture = parse_curl(args.capture.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"error: {args.capture} not found", file=sys.stderr)
        return 1
    except CurlParseError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if not capture["body"]:
        print(
            "error: the captured request has no body. A GraphQL POST always has "
            "one — you probably copied a different request.",
            file=sys.stderr,
        )
        return 1

    notes: list[str] = []
    keyword_encoding: str | None = None
    paging: dict[str, Any] | None = None
    body = capture["body"]

    try:
        if args.stage == "search":
            body, keyword_encoding = templatise_keyword(body, args.keyword)
            if args.capture_page2:
                second = parse_curl(args.capture_page2.read_text(encoding="utf-8"))
                diffs = find_paging_diff(capture["body"], second["body"] or "")
                body, paging, paging_notes = apply_paging(body, diffs, args.rows)
                notes += paging_notes
            else:
                paging = {"mode": "none"}
                notes.append(
                    "TODO: only one capture given, so paging is unknown — only "
                    "page 1 can be fetched. Recapture page 2 "
                    "(docs/CAPTURE_HEADERS.md step C) and re-run."
                )
        else:
            body, pdp_notes = templatise_pdp(body, args.product_url)
            notes += pdp_notes
    except CurlParseError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    stage, secret_values = build_stage(
        capture,
        body_template=body,
        keyword_encoding=keyword_encoding,
        paging=paging,
        notes=notes,
    )

    # Merge, so capturing the PDP later does not erase the search stage.
    args.out.parent.mkdir(parents=True, exist_ok=True)
    document: dict[str, Any] = {}
    if args.out.exists():
        document = yaml.safe_load(args.out.read_text(encoding="utf-8")) or {}
    document["captured_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    document[args.stage] = stage
    args.out.write_text(
        yaml.safe_dump(document, sort_keys=False, allow_unicode=True, width=10_000),
        encoding="utf-8",
    )

    written_env = write_env(args.env, secret_values) if secret_values else []

    print(f"stage        : {args.stage}")
    print(f"endpoint     : {capture['url']}")
    print(f"operation    : {stage['operation_name']}")
    print(f"safe headers : {len(stage['headers'])} -> {args.out}")
    for name, env_name in stage["secret_env"].items():
        print(f"-> .env      : {name} -> {env_name} = {mask(secret_values[env_name])}")
    if written_env:
        print(f"env updated  : {args.env} ({', '.join(written_env)})")
    if paging:
        print(f"paging       : {paging}")
    for note in notes:
        print(f"  - {note}")

    todos = [n for n in notes if n.startswith("TODO")]
    print()
    print(f"Wrote {args.out}. Verify with notebooks/01_explore_endpoints.ipynb.")
    print("Delete the capture files now — they contain your raw cookie.")
    if todos:
        print(f"\n{len(todos)} TODO left in the config; read them above.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
