#!/usr/bin/env python
"""Health check for a capture: one request, one parse, one report.

Does what notebooks/01_explore_endpoints.ipynb does, minus Jupyter. Use it when
the notebook kernel is being difficult, or as the fast "is my cookie still
alive?" check before starting a long run.

    python scripts/verify_capture.py
    python scripts/verify_capture.py --keyword "kaos polos pria" --page 2
    python scripts/verify_capture.py --product-url https://www.tokopedia.com/shop/slug
    python scripts/verify_capture.py --offline        # re-parse the saved response

Sends exactly one search request, plus one PDP request when --product-url is
given. Never prints cookies.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from tokopedia_scraper.config import Config, MissingCredential  # noqa: E402
from tokopedia_scraper.logging_setup import setup_logging  # noqa: E402
from tokopedia_scraper.models import Product  # noqa: E402
from tokopedia_scraper.parsers import (  # noqa: E402
    parse_pdp_response,
    parse_search_response,
)

FIELDS = (
    "title",
    "price",
    "original_price",
    "discount_pct",
    "rating",
    "sold_count",
    "shop_id",
    "shop_name",
)


def report_products(products: list[Product], sample: int = 5) -> None:
    if not products:
        print("  NO PRODUCTS PARSED")
        return

    print(f"  {'product_id':<14}{'price':<10}{'rating':<7}{'sold':<9}title")
    for p in products[:sample]:
        print(
            f"  {p.product_id:<14}{str(p.price):<10}{str(p.rating):<7}"
            f"{str(p.sold_count):<9}{(p.title or '')[:46]}"
        )

    first = products[0]
    print()
    print(f"  shop     : {first.shop_id} / {first.shop_name}")
    print(f"  category : {first.category_path}")
    print(f"  url      : {first.url}")
    print(f"  image    : {first.image_urls[:1]}")
    print()

    print(f"  missing values (out of {len(products)}):")
    for field in FIELDS:
        missing = sum(1 for p in products if getattr(p, field) is None)
        flag = "   <-- every row, check the parser" if missing == len(products) else ""
        print(f"    {field:<16}{missing}{flag}")
    print(f"    {'image_urls':<16}{sum(1 for p in products if not p.image_urls)}")
    print(f"    {'category_path':<16}{sum(1 for p in products if not p.category_path)}")

    ids = [p.product_id for p in products]
    if len(set(ids)) != len(ids):
        print(f"    duplicate ids within the page: {len(ids) - len(set(ids))}")


def run_search(cfg: Config, keyword: str, page: int, offline: bool) -> Any | None:
    """Fetch (or load) one page of search results. None on failure."""
    dump = cfg.storage.export_dir / "raw_sample_search.json"

    if offline:
        if not dump.exists():
            print(f"  {dump} not found — run once without --offline first")
            return None
        print(f"  re-parsed from {dump}")
        return json.loads(dump.read_text(encoding="utf-8"))

    from tokopedia_scraper.fetchers.graphql import CaptureIncomplete, GraphQLFetcher
    from tokopedia_scraper.ratelimit import FetchError

    fetcher = None
    try:
        fetcher = GraphQLFetcher(cfg)
        result = fetcher.search(keyword, page)
    except (CaptureIncomplete, MissingCredential) as exc:
        print(f"  CANNOT START:\n{exc}")
        return None
    except FetchError as exc:
        print(f"  REQUEST FAILED (status {exc.status}): {exc}")
        if exc.status == 403:
            print("  -> cookie expired. Recapture: docs/CAPTURE_HEADERS.md")
        return None
    finally:
        if fetcher is not None:
            fetcher.close()

    print(f"  HTTP {result.status}  meta={result.meta}")
    dump.write_text(json.dumps(result.payload, indent=2, ensure_ascii=False), "utf-8")
    print(f"  raw saved -> {dump} ({dump.stat().st_size:,} bytes)")
    return result.payload


def run_pdp(cfg: Config, product_url: str | None, offline: bool) -> Any | None:
    dump = cfg.storage.export_dir / "raw_sample_pdp.json"

    if offline:
        if not dump.exists():
            return None
        print(f"  re-parsed from {dump}")
        return json.loads(dump.read_text(encoding="utf-8"))

    from tokopedia_scraper.fetchers.graphql import CaptureIncomplete, GraphQLFetcher
    from tokopedia_scraper.ratelimit import FetchError

    fetcher = None
    try:
        fetcher = GraphQLFetcher(cfg)
        result = fetcher.fetch_pdp(product_url or "")
    except (CaptureIncomplete, MissingCredential) as exc:
        print(f"  CANNOT START:\n{exc}")
        return None
    except FetchError as exc:
        print(f"  REQUEST FAILED (status {exc.status}): {exc}")
        return None
    finally:
        if fetcher is not None:
            fetcher.close()

    print(f"  HTTP {result.status}")
    dump.write_text(json.dumps(result.payload, indent=2, ensure_ascii=False), "utf-8")
    print(f"  raw saved -> {dump}")
    return result.payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="One request, one parse, one report — verify a capture works."
    )
    parser.add_argument("--config", type=Path, default=REPO_ROOT / "config.yaml")
    parser.add_argument(
        "--keyword", default=None, help="defaults to the first configured keyword"
    )
    parser.add_argument("--page", type=int, default=1)
    parser.add_argument(
        "--product-url", default=None, help="also exercise the PDP endpoint"
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="re-parse data/exports/raw_sample_*.json instead of making requests",
    )
    args = parser.parse_args(argv)

    cfg = Config.load(args.config)
    cfg.ensure_dirs()
    setup_logging(cfg.logging.level, cfg.logging.file, force=True)

    keyword = args.keyword or (cfg.keywords[0] if cfg.keywords else "air fryer")

    print(f"=== search: {keyword!r} page {args.page} ===")
    payload = run_search(cfg, keyword, args.page, args.offline)
    if payload is None:
        return 1

    products, page = parse_search_response(
        payload, keyword=keyword, fetcher_used="graphql"
    )
    print(
        f"  parsed {len(products)} products | totalData={page.total} "
        f"| has_more={page.has_more} | next_offset={page.next_offset}"
    )
    print()
    report_products(products)

    if page.total and not products:
        print("\n  Schema moved: the response has results but none parsed.")
        print("  The raw response is saved above — fixable without re-scraping.")
        return 1

    pdp_payload = None
    if args.product_url or args.offline:
        print(f"\n=== pdp: {args.product_url or '(saved)'} ===")
        pdp_payload = run_pdp(cfg, args.product_url, args.offline)
        if pdp_payload is None and args.product_url:
            return 1

    if pdp_payload is not None:
        detail = parse_pdp_response(pdp_payload, fetcher_used="graphql")
        desc_len = len(detail.description or "")
        print(f"  title       : {(detail.title or '')[:60]}")
        print(f"  description : {desc_len} chars")
        if desc_len:
            print(f"                {(detail.description or '')[:110]!r}...")
        print(f"  images      : {len(detail.image_urls)}")
        print(f"  category    : {detail.category_path}")
        print(f"  rating      : {detail.rating}   reviews: {detail.review_count}")
        print(f"  sold        : {detail.sold_count}")
        if detail.is_empty:
            print("  PDP RETURNED NOTHING USABLE — was the right request captured?")
            return 1

    print("\nOK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
