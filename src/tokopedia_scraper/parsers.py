"""Raw response -> Product rows.

Field paths here were read off a real captured `searchProductV5` response, not
guessed. When Tokopedia changes the schema, the raw responses already in the
database can be re-parsed with an updated version of this module — no
re-scraping.

Parsing is defensive throughout: a product that fails to parse is logged and
skipped, never allowed to kill the other 23 in the page.
"""

from __future__ import annotations

import html
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Iterator
from urllib.parse import parse_qs, urlsplit, urlunsplit

from .models import Product, dig, first, note_schema_drift

log = logging.getLogger(__name__)

# Candidate locations for the product array. Ordered by preference; the first
# that yields a list wins. The extra entries are cheap insurance against
# Tokopedia renaming the wrapper (searchProductV5 -> V6) without changing the
# item shape.
SEARCH_PRODUCT_PATHS: tuple[str, ...] = (
    "data.searchProductV5.data.products",
    "data.searchProduct.data.products",
    "data.ace_search_product_v4.data.products",
)
SEARCH_HEADER_PATHS: tuple[str, ...] = (
    "data.searchProductV5.header",
    "data.searchProduct.header",
)

# Keys observed in a real searchProductV5 product. Anything outside this set is
# reported once by note_schema_drift.
KNOWN_PRODUCT_KEYS = (
    # Both spellings observed in the wild, from two captures days apart.
    "oldId",
    "oldID",
    "id",
    "ttsProductID",
    "name",
    "url",
    "applink",
    "mediaURL",
    "shop",
    "stock",
    "badge",
    "price",
    "freeShipping",
    "labelGroups",
    "labelGroupsVariant",
    "category",
    "rating",
    "wishlist",
    "ads",
    "meta",
    "__typename",
)

# labelGroups is a display-oriented grab bag. These positions carry data we
# actually want; everything else in there is styling.
SOLD_LABEL_POSITIONS = ("ri_product_credibility", "integrity")
DISCOUNT_LABEL_POSITIONS = ("ri_ribbon",)


@dataclass(slots=True)
class SearchPage:
    """Pagination facts extracted from the response header.

    `has_more` comes straight from Tokopedia and is a better stop signal than
    counting pages: it accounts for result sets shorter than the configured
    maximum.
    """

    total: int | None = None
    has_more: bool | None = None
    next_offset: int | None = None
    returned: int = 0
    extra: dict[str, str] = field(default_factory=dict)


def iter_documents(payload: Any) -> Iterator[dict[str, Any]]:
    """GraphQL batching means the top level may be a list of documents."""
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                yield item
    elif isinstance(payload, dict):
        yield payload


def clean_product_url(url: str) -> str:
    """Drop the tracking query string.

    Captured URLs carry `?extParam=ivf%3Dfalse%26keyword%3Dair+fryer&search_id=...`,
    which is per-search noise. Keeping it would make the same product look
    different across keywords and defeat URL-level deduplication.
    """
    if not url:
        return url
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def _label_value(labels: Any, positions: Iterable[str]) -> str | None:
    if not isinstance(labels, list):
        return None
    wanted = set(positions)
    for label in labels:
        if isinstance(label, dict) and label.get("position") in wanted:
            title = label.get("title")
            if isinstance(title, str) and title.strip():
                return title
    return None


def _sold_label(labels: Any) -> str | None:
    """'750+ terjual' -> passed to parse_count, which handles rb/jt and '+'."""
    value = _label_value(labels, SOLD_LABEL_POSITIONS)
    if value:
        return value
    # Fallback: any label mentioning "terjual", wherever it sits.
    if isinstance(labels, list):
        for label in labels:
            title = label.get("title") if isinstance(label, dict) else None
            if isinstance(title, str) and "terjual" in title.lower():
                return title
    return None


def parse_search_header(payload: Any) -> SearchPage:
    page = SearchPage()
    for doc in iter_documents(payload):
        header = first(doc, *SEARCH_HEADER_PATHS)
        if not isinstance(header, dict):
            continue

        total = header.get("totalData")
        if isinstance(total, (int, float)):
            page.total = int(total)
        elif isinstance(total, str) and total.isdigit():
            page.total = int(total)

        raw_params = header.get("additionalParams")
        if isinstance(raw_params, str) and raw_params:
            params = {k: v[0] for k, v in parse_qs(raw_params).items() if v}
            page.extra = params
            if "has_more" in params:
                page.has_more = params["has_more"].lower() == "true"
            for key in ("next_offset_organic", "next_offset"):
                if params.get(key, "").isdigit():
                    page.next_offset = int(params[key])
                    break
        break
    return page


def parse_search_response(
    payload: Any,
    *,
    keyword: str | None = None,
    fetcher_used: str | None = None,
) -> tuple[list[Product], SearchPage]:
    """Parse one page of search results.

    Returns the products that parsed successfully plus the pagination facts.
    An empty product list alongside total > 0 means the schema moved — check the
    stored raw response rather than assuming the keyword has no results.
    """
    products: list[Product] = []
    seen: set[str] = set()

    for doc in iter_documents(payload):
        items = first(doc, *SEARCH_PRODUCT_PATHS)
        if not isinstance(items, list):
            continue

        for item in items:
            if not isinstance(item, dict):
                continue
            note_schema_drift("search.product", item, KNOWN_PRODUCT_KEYS)
            product = _parse_search_product(item, keyword, fetcher_used)
            if product is None:
                continue
            # A page can repeat a product across organic and ad slots.
            if product.product_id in seen:
                continue
            seen.add(product.product_id)
            products.append(product)

    page = parse_search_header(payload)
    page.returned = len(products)

    if page.total and not products:
        log.error(
            "search response reported totalData=%s but zero products parsed — "
            "the schema likely moved. Re-parse from raw_responses once "
            "SEARCH_PRODUCT_PATHS is updated; no re-scraping needed.",
            page.total,
        )
    return products, page


def _parse_search_product(
    item: dict[str, Any], keyword: str | None, fetcher_used: str | None
) -> Product | None:
    try:
        product_id = first(item, "id", "oldID", "oldId", "ttsProductID")
        url = dig(item, "url", "")
        if not product_id or not url:
            log.warning(
                "skipping product without id or url (keys: %s)", sorted(item)[:10]
            )
            return None

        breadcrumb = dig(item, "category.breadcrumb", "") or ""
        category_path = [p for p in breadcrumb.split("/") if p]
        if not category_path:
            name = dig(item, "category.name")
            category_path = [name] if name else []

        # Search only ever returns one thumbnail. image300 is the larger of the
        # two; the full gallery arrives in stage 2 and takes precedence there.
        image = first(item, "mediaURL.image300", "mediaURL.image")

        return Product(
            product_id=product_id,
            url=clean_product_url(url),
            shop_id=first(item, "shop.id", "shop.oldID", "shop.oldId"),
            shop_name=dig(item, "shop.name"),
            title=dig(item, "name"),
            # price.number is already an int in rupiah; price.text is the
            # formatted fallback, and Product coerces either.
            price=first(item, "price.number", "price.text"),
            original_price=dig(item, "price.original"),
            discount_pct=_discount_pct(item),
            rating=dig(item, "rating"),
            # searchProductV5 carries no review count. Stage 2 may supply one.
            review_count=None,
            sold_count=_sold_label(item.get("labelGroups")),
            category_path=category_path,
            image_urls=[image] if image else [],
            source_keyword=keyword,
            fetcher_used=fetcher_used,
        )
    except Exception:
        # One malformed product must never take down the rest of the page.
        log.exception("failed to parse product %r", dig(item, "id", "<no id>"))
        return None


def _discount_pct(item: dict[str, Any]) -> float | None:
    """price.discountPercentage is unreliable.

    Observed as 0 on a product whose ribbon label said 71%. Prefer the ribbon;
    fall back to the declared field; otherwise return None and let Product
    derive it from original vs price.
    """
    ribbon = _label_value(item.get("labelGroups"), DISCOUNT_LABEL_POSITIONS)
    if ribbon:
        digits = ribbon.strip().rstrip("%").replace(",", ".")
        try:
            return float(digits)
        except ValueError:
            pass
    declared = dig(item, "price.discountPercentage")
    if isinstance(declared, (int, float)) and declared > 0:
        return float(declared)
    return None


# --------------------------------------------------------------------------
# Stage 2: product detail page (pdpMainInfo)
# --------------------------------------------------------------------------

PDP_ROOT_PATHS: tuple[str, ...] = ("data.pdpMainInfo",)

# The PDP is a list of named components rather than a fixed object, so each
# piece of data is looked up by component name.
PDP_DESCRIPTION_COMPONENT = "product_detail"
PDP_MEDIA_COMPONENT = "product_media"
PDP_CONTENT_COMPONENT = "product_content"

# Media entries ship both a signed CDN link and a `prefix`/`suffix` pair that
# composes into an unsigned cache URL. The signed one carries x-expires and dies
# within ~3 hours, which would force image downloads to happen immediately after
# every enrich. The composed one does not expire.
#
# Measured against a live product: size 500/700/900 return progressively larger
# JPEGs, 1200 and above all return the same 104 KB original, and omitting the
# size segment returns a 4 KB placeholder PNG. 1200 is therefore full resolution.
IMAGE_SIZE = "1200"

# Same field under two spellings, seen in captures taken days apart.
_MEDIA_URL_KEYS = (
    "urlMaxRes",
    "URLMaxRes",
    "urlOriginal",
    "URLOriginal",
    "urlThumbnail",
    "URLThumbnail",
)

_TAG_RE = re.compile(r"<[^>]+>")


@dataclass(slots=True)
class PdpDetail:
    """Everything stage 2 adds on top of a stage 1 row.

    Fields left as None mean "the PDP did not supply this", not "empty" — the
    caller keeps whatever search already stored.
    """

    product_id: str | None = None
    url: str | None = None
    title: str | None = None
    description: str | None = None
    specs: dict[str, str] = field(default_factory=dict)
    image_urls: list[str] = field(default_factory=list)
    category_path: list[str] = field(default_factory=list)
    price: int | None = None
    original_price: int | None = None
    discount_pct: float | None = None
    rating: float | None = None
    review_count: int | None = None
    sold_count: int | None = None
    shop_id: str | None = None
    shop_name: str | None = None

    @property
    def is_empty(self) -> bool:
        return not (self.description or self.image_urls or self.specs)

    @property
    def description_is_image_only(self) -> bool:
        """Seller wrote the description as pictures instead of text.

        Common on Tokopedia. Worth surfacing rather than papering over: for an
        auto-description dataset these rows have no target text at all.
        """
        return not self.description and bool(self.specs)


def _clean_html(text: Any) -> str | None:
    """Descriptions are mostly plain text with newlines, but not always."""
    if not isinstance(text, str):
        return None
    cleaned = html.unescape(_TAG_RE.sub("", text)).strip()
    return cleaned or None


def _media_url(entry: dict[str, Any]) -> str | None:
    """Best URL for one media entry, preferring the one that does not expire."""
    prefix = entry.get("prefix")
    suffix = entry.get("suffix")
    if isinstance(prefix, str) and isinstance(suffix, str) and prefix and suffix:
        return prefix.rstrip("/") + "/" + IMAGE_SIZE + suffix

    # No prefix/suffix pair: fall back to the signed link and accept that it
    # expires, so images must then be downloaded promptly.
    url = first(entry, *_MEDIA_URL_KEYS)
    return url if isinstance(url, str) and url else None


def _pdp_components(root: dict[str, Any]) -> dict[str, list[Any]]:
    """name -> data list. Duplicate names keep the first non-empty payload."""
    out: dict[str, list[Any]] = {}
    components = root.get("components")
    if not isinstance(components, list):
        return out
    for component in components:
        if not isinstance(component, dict):
            continue
        name = component.get("name")
        data = component.get("data")
        if not isinstance(name, str) or not isinstance(data, list):
            continue
        if data and not out.get(name):
            out[name] = data
    return out


def parse_pdp_response(
    payload: Any, *, product_id: str | None = None, fetcher_used: str | None = None
) -> PdpDetail:
    """Parse a product detail page.

    Paths were read off a real captured `pdpMainInfo` response. Anything the
    response omits comes back as None so the caller can leave the stage 1 value
    in place.
    """
    detail = PdpDetail(product_id=product_id)

    root: dict[str, Any] | None = None
    for doc in iter_documents(payload):
        candidate = first(doc, *PDP_ROOT_PATHS)
        if isinstance(candidate, dict):
            root = candidate
            break

    if root is None:
        log.error(
            "no %s in PDP response for %s — schema moved, or the wrong request "
            "was captured. The raw response is stored; re-parse after updating "
            "PDP_ROOT_PATHS.",
            PDP_ROOT_PATHS[0],
            product_id or "<unknown>",
        )
        return detail

    basic = dig(root, "data.basicInfo", {}) or {}
    components = _pdp_components(root)

    detail.product_id = str(basic.get("productID") or product_id or "") or None
    detail.url = clean_product_url(dig(basic, "url", "") or "")
    detail.shop_id = str(basic.get("shopID")) if basic.get("shopID") else None
    detail.shop_name = basic.get("shopName")

    # Stage 1 has no review count at all, and only a bucketed sold count
    # ("750+ terjual"). The PDP carries exact numbers, so prefer them.
    detail.rating = dig(basic, "stats.rating")
    detail.review_count = dig(basic, "stats.countReview")
    detail.sold_count = first(basic, "txStats.countSold", "txStats.itemSoldFmt")

    detail.category_path = [
        entry["name"]
        for entry in (dig(basic, "category.detail", []) or [])
        if isinstance(entry, dict) and entry.get("name")
    ] or ([dig(basic, "category.name")] if dig(basic, "category.name") else [])

    # -- description ------------------------------------------------------
    description_data = components.get(PDP_DESCRIPTION_COMPONENT) or []
    if description_data and isinstance(description_data[0], dict):
        node = description_data[0]
        detail.description = _clean_html(
            first(node, "productDetailDescription.content", "description")
        )
        # The same component carries structured title/subtitle pairs. They are
        # the only usable text when the prose description is empty, which
        # happens whenever the seller uploaded it as images instead.
        for entry in node.get("content") or []:
            if not isinstance(entry, dict):
                continue
            key = _clean_html(entry.get("title"))
            value = _clean_html(entry.get("subtitle"))
            if key and value:
                detail.specs[key] = value

    # -- title and price --------------------------------------------------
    content_data = components.get(PDP_CONTENT_COMPONENT) or []
    if content_data and isinstance(content_data[0], dict):
        node = content_data[0]
        detail.title = first(node, "name", "parentName")
        detail.price = first(node, "price.value", "price.priceFmt")
        detail.original_price = dig(node, "price.slashPriceFmt")
        pct = dig(node, "price.discPercentage")
        if isinstance(pct, str) and pct.strip().rstrip("%").isdigit():
            detail.discount_pct = float(pct.strip().rstrip("%"))
    if not detail.title:
        detail.title = basic.get("name")

    # -- images -----------------------------------------------------------
    media_data = components.get(PDP_MEDIA_COMPONENT) or []
    urls: list[str] = []
    if media_data and isinstance(media_data[0], dict):
        for entry in media_data[0].get("media") or []:
            if not isinstance(entry, dict):
                continue
            # Video entries carry a poster frame that duplicates the first
            # still, so skip them rather than storing the same image twice.
            if entry.get("type") != "image":
                continue
            url = _media_url(entry)
            if url and url not in urls:
                urls.append(url)
    if not urls and basic.get("defaultMediaURL"):
        urls = [basic["defaultMediaURL"]]
    detail.image_urls = urls

    # NOTE: the product_detail_media_N components hold marketing infographics
    # (1080x1502 sales pitches), not photographs of the product. Deliberately
    # excluded — they would poison an image dataset.

    if detail.is_empty:
        log.warning(
            "PDP for %s yielded neither description nor images; components "
            "present: %s",
            product_id or detail.product_id or "<unknown>",
            sorted(components)[:12],
        )
    return detail


if __name__ == "__main__":  # pragma: no cover - manual smoke check
    logging.basicConfig(level=logging.CRITICAL)

    # Shape copied from a real searchProductV5 response; values are synthetic.
    def make_item(pid: str, **over: Any) -> dict[str, Any]:
        item: dict[str, Any] = {
            "oldId": int(pid),
            "id": pid,
            "ttsProductID": "1735377132712199238",
            "name": "Air Fryer 5L Contoh",
            "url": (
                "https://www.tokopedia.com/toko-contoh/air-fryer-5l-contoh"
                "?extParam=ivf%3Dfalse%26keyword%3Dair+fryer%26src%3Dsearch"
            ),
            "applink": "tokopedia://product/" + pid,
            "mediaURL": {
                "image": "https://images.tokopedia.net/img/a-250.jpg",
                "image300": "https://images.tokopedia.net/img/a-300.jpg",
                "videoCustom": "",
            },
            "shop": {"oldId": 123, "id": "0000123", "name": "Toko Contoh", "city": ""},
            "price": {
                "text": "Rp259.000",
                "number": 259000,
                "range": "",
                "original": "Rp899.000",
                "discountPercentage": 0,
            },
            "labelGroups": [
                {
                    "id": 301,
                    "position": "ri_product_credibility",
                    "title": "750+ terjual",
                },
                {"id": 503, "position": "ri_ribbon", "title": "71%"},
                {"id": 1801, "position": "final_price", "title": "Rp259.000"},
            ],
            "category": {
                "id": "60",
                "name": "Elektronik",
                "breadcrumb": "elektronik/elektronik-dapur/air-fryer",
            },
            "rating": "4.7",
            "__typename": "searchProductV5Product",
        }
        item.update(over)
        return item

    payload = [
        {
            "data": {
                "searchProductV5": {
                    "header": {
                        "totalData": 320,
                        "additionalParams": (
                            "next_offset_organic=24&next_offset_organic_ad=24"
                            "&search_id=SYNTHETIC&has_more=true"
                        ),
                    },
                    "data": {
                        "products": [
                            make_item("0000000001"),
                            make_item("0000000002", rating="4.8"),
                            make_item("0000000001"),  # repeated slot
                        ]
                    },
                }
            }
        }
    ]

    products, page = parse_search_response(
        payload, keyword="air fryer", fetcher_used="graphql"
    )

    assert len(products) == 2, f"dedupe within a page failed: {len(products)}"
    p = products[0]
    assert p.product_id == "0000000001"
    assert p.title == "Air Fryer 5L Contoh"
    assert p.price == 259_000 and p.original_price == 899_000
    assert p.discount_pct == 71.0, f"ribbon discount not used: {p.discount_pct}"
    assert p.rating == 4.7
    assert p.sold_count == 750, f"sold label not parsed: {p.sold_count}"
    assert p.review_count is None, "searchProductV5 has no review count"
    assert p.shop_id == "0000123" and p.shop_name == "Toko Contoh"
    assert p.category_path == ["elektronik", "elektronik-dapur", "air-fryer"]
    assert p.image_urls == ["https://images.tokopedia.net/img/a-300.jpg"]
    assert p.source_keyword == "air fryer" and p.fetcher_used == "graphql"
    assert p.pdp_fetched is False
    assert "?" not in p.url, f"tracking query not stripped: {p.url}"
    assert p.url.endswith("/air-fryer-5l-contoh")

    assert page.total == 320
    assert page.has_more is True
    assert page.next_offset == 24
    assert page.returned == 2

    # Missing fields must degrade to None, not raise.
    sparse = [
        {
            "data": {
                "searchProductV5": {
                    "data": {
                        "products": [
                            {"id": "9", "url": "https://www.tokopedia.com/a/b"}
                        ]
                    }
                }
            }
        }
    ]
    got, page2 = parse_search_response(sparse)
    assert len(got) == 1, "a bare product must still parse"
    assert got[0].title is None and got[0].price is None
    assert got[0].sold_count is None and got[0].category_path == []
    assert page2.total is None and page2.has_more is None

    # Junk in the array must be skipped, not fatal.
    junk = [
        {
            "data": {
                "searchProductV5": {
                    "data": {
                        "products": [
                            "not a dict",
                            {},
                            {"id": "x"},
                            make_item("0000000003"),
                        ]
                    }
                }
            }
        }
    ]
    got3, _ = parse_search_response(junk)
    assert [g.product_id for g in got3] == ["0000000003"], [
        g.product_id for g in got3
    ]

    # A ribbon-free product falls back to the derived discount.
    no_ribbon = make_item("0000000004", labelGroups=[])
    derived, _ = parse_search_response(
        [{"data": {"searchProductV5": {"data": {"products": [no_ribbon]}}}}]
    )
    assert derived[0].discount_pct == 71.19, derived[0].discount_pct

    # -- PDP ---------------------------------------------------------------
    # Shape copied from a real pdpMainInfo response; values are synthetic.
    pdp_payload = [
        {
            "data": {
                "pdpMainInfo": {
                    "data": {
                        "basicInfo": {
                            "productID": "0000000001",
                            "shopID": "0000123",
                            "shopName": "Toko Contoh",
                            "url": (
                                "https://www.tokopedia.com/toko-contoh/air-fryer"
                                "?extParam=whid%3D442392%26src%3Dpdp"
                            ),
                            "defaultMediaURL": "https://images.tokopedia.net/img/def.jpg",
                            "stats": {"rating": 4.8, "countReview": "781"},
                            "txStats": {"countSold": "3761", "itemSoldFmt": "3 rb+"},
                            "category": {
                                "id": "5472",
                                "name": "Air Fryer",
                                "detail": [
                                    {"id": "60", "name": "Elektronik"},
                                    {"id": "3882", "name": "Elektronik Dapur"},
                                    {"id": "5472", "name": "Air Fryer"},
                                ],
                            },
                        }
                    },
                    "components": [
                        {"name": "ticker_info", "type": "ticker_info", "data": []},
                        {
                            "name": "product_media",
                            "type": "product_media",
                            "data": [
                                {
                                    "media": [
                                        {
                                            "type": "video",
                                            "URLMaxRes": "https://images.tokopedia.net/img/poster.jpg",
                                        },
                                        {
                                            # Upper-case spelling, no prefix pair.
                                            "type": "image",
                                            "URLOriginal": "https://images.tokopedia.net/img/a-700.jpg",
                                            "URLMaxRes": "https://images.tokopedia.net/img/a-1600.jpg",
                                        },
                                        {
                                            # Lower-case spelling, no prefix pair.
                                            "type": "image",
                                            "urlOriginal": "https://images.tokopedia.net/img/b-700.jpg",
                                        },
                                        {
                                            # prefix/suffix present: the signed
                                            # link must be ignored in its favour.
                                            "type": "image",
                                            "urlMaxRes": (
                                                "https://p16-images-sign-sg.tokopedia-static.net/x"
                                                "?x-expires=1785834283&x-signature=REDACTED"
                                            ),
                                            "prefix": "https://images.tokopedia.net/img/cache/",
                                            "suffix": "/aphluv/1997/1/1/deadbeef~.jpeg",
                                        },
                                        {
                                            "type": "image",
                                            "URLMaxRes": "https://images.tokopedia.net/img/a-1600.jpg",
                                        },
                                    ]
                                }
                            ],
                        },
                        {
                            "name": "product_content",
                            "type": "product_content",
                            "data": [
                                {
                                    "name": "Air Fryer 3.5L Contoh",
                                    "price": {
                                        "value": 329800,
                                        "priceFmt": "Rp329.800",
                                        "slashPriceFmt": "Rp499.800",
                                        "discPercentage": "34%",
                                    },
                                }
                            ],
                        },
                        {
                            "name": "product_detail",
                            "type": "product_detail",
                            "data": [
                                {
                                    "title": "Detail produk",
                                    "productDetailDescription": {
                                        "title": "Deskripsi",
                                        "content": (
                                            "Masak lebih sehat &amp; praktis.\n"
                                            "<b>Spesifikasi</b>\nDaya : 650 Watt\n"
                                        ),
                                    },
                                }
                            ],
                        },
                        {
                            "name": "product_detail_media_1",
                            "type": "product_detail_media",
                            "data": [
                                {
                                    "contentMedia": [
                                        {
                                            "url": "https://images.tokopedia.net/img/infographic.jpg",
                                            "type": "image",
                                        }
                                    ]
                                }
                            ],
                        },
                    ],
                }
            }
        }
    ]

    d = parse_pdp_response(pdp_payload, product_id="0000000001")
    assert d.description is not None
    assert "Masak lebih sehat & praktis." in d.description, "entities not unescaped"
    assert "<b>" not in d.description, "HTML tags not stripped"
    assert "650 Watt" in d.description
    assert d.title == "Air Fryer 3.5L Contoh"
    assert d.price == 329_800 and d.original_price == "Rp499.800"
    assert d.discount_pct == 34.0
    assert d.rating == 4.8
    assert d.review_count == "781", "PDP supplies the review count search lacks"
    assert d.sold_count == "3761", "exact sold count preferred over '3 rb+'"
    assert d.shop_id == "0000123" and d.shop_name == "Toko Contoh"
    assert d.category_path == ["Elektronik", "Elektronik Dapur", "Air Fryer"]
    assert "?" not in (d.url or ""), f"tracking query kept: {d.url}"
    assert d.image_urls == [
        "https://images.tokopedia.net/img/a-1600.jpg",
        "https://images.tokopedia.net/img/b-700.jpg",
        f"https://images.tokopedia.net/img/cache/{IMAGE_SIZE}/aphluv/1997/1/1/deadbeef~.jpeg",
    ], d.image_urls
    assert not any(
        "x-signature" in u for u in d.image_urls
    ), "an expiring signed URL was kept even though prefix/suffix was available"
    assert (
        "https://images.tokopedia.net/img/infographic.jpg" not in d.image_urls
    ), "marketing infographic must not enter the image dataset"
    assert not d.is_empty

    # The coercions only bite once these land on a Product.
    enriched = Product(
        product_id=d.product_id or "0000000001",
        url=d.url or "https://www.tokopedia.com/a/b",
        review_count=d.review_count,
        sold_count=d.sold_count,
        rating=d.rating,
        description=d.description,
    )
    assert enriched.review_count == 781 and enriched.sold_count == 3761

    # A response missing pdpMainInfo must degrade, not raise.
    empty = parse_pdp_response([{"data": {"somethingElse": {}}}], product_id="9")
    assert empty.is_empty and empty.description is None

    # Components present but all empty: still no crash.
    bare = parse_pdp_response(
        [{"data": {"pdpMainInfo": {"data": {}, "components": []}}}], product_id="9"
    )
    assert bare.is_empty and bare.image_urls == []

    print("parsers.py self-check OK")
