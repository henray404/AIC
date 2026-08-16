"""Parser tests, all against recorded responses. No network.

The theme throughout: a malformed or missing field must degrade to None and be
logged, never raise. One weird product must not take down the other 59.
"""

from __future__ import annotations

import copy

import pytest

from tokopedia_scraper.models import (
    Product,
    dig,
    first,
    parse_count,
    parse_price,
    parse_rating,
)
from tokopedia_scraper.parsers import (
    IMAGE_SIZE,
    clean_product_url,
    parse_pdp_response,
    parse_search_response,
)

# --- search ---------------------------------------------------------------


def test_search_parses_recorded_response(search_payload):
    products, page = parse_search_response(
        search_payload, keyword="air fryer", fetcher_used="graphql"
    )

    assert len(products) == 2
    assert page.total == 320
    assert page.has_more is True
    assert page.next_offset == 60
    assert page.returned == 2

    product = products[0]
    assert product.product_id
    assert product.title
    assert product.price and product.price > 0
    assert product.source_keyword == "air fryer"
    assert product.fetcher_used == "graphql"
    assert product.pdp_fetched is False
    assert product.category_path
    assert product.image_urls


def test_search_strips_tracking_query(search_payload):
    products, _ = parse_search_response(search_payload)
    for product in products:
        assert "?" not in product.url
        assert "extParam" not in product.url


def test_search_dedupes_repeated_products(search_payload):
    payload = copy.deepcopy(search_payload)
    items = payload["data"]["searchProductV5"]["data"]["products"]
    items.append(copy.deepcopy(items[0]))  # ad slot repeating an organic result

    products, page = parse_search_response(payload)
    assert len(products) == 2, "the repeated product should collapse to one row"
    assert page.returned == 2


def test_search_survives_junk_entries(search_payload):
    payload = copy.deepcopy(search_payload)
    items = payload["data"]["searchProductV5"]["data"]["products"]
    payload["data"]["searchProductV5"]["data"]["products"] = [
        "not a dict",
        None,
        {},
        {"id": "no-url"},
        *items,
    ]

    products, _ = parse_search_response(payload)
    assert len(products) == 2, "junk must be skipped, real products kept"


def test_search_missing_fields_become_none():
    payload = {
        "data": {
            "searchProductV5": {
                "data": {
                    "products": [{"id": "1", "url": "https://www.tokopedia.com/a/b"}]
                }
            }
        }
    }
    products, page = parse_search_response(payload)

    assert len(products) == 1
    bare = products[0]
    assert bare.title is None
    assert bare.price is None
    assert bare.rating is None
    assert bare.sold_count is None
    assert bare.category_path == []
    assert bare.image_urls == []
    assert page.total is None and page.has_more is None


def test_search_empty_result_is_not_an_error():
    payload = {"data": {"searchProductV5": {"data": {"products": []}}}}
    products, page = parse_search_response(payload)
    assert products == []
    assert page.returned == 0


def test_search_unknown_shape_returns_nothing():
    products, page = parse_search_response({"data": {"somethingElse": {}}})
    assert products == []
    assert page.total is None


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://www.tokopedia.com/s/p?extParam=x", "https://www.tokopedia.com/s/p"),
        ("https://www.tokopedia.com/s/p", "https://www.tokopedia.com/s/p"),
        ("", ""),
    ],
)
def test_clean_product_url(url, expected):
    assert clean_product_url(url) == expected


# --- pdp ------------------------------------------------------------------


def test_pdp_parses_description(pdp_payload):
    detail = parse_pdp_response(pdp_payload, fetcher_used="graphql")

    assert detail.description and len(detail.description) > 200
    assert detail.image_urls
    assert detail.category_path
    assert not detail.is_empty
    assert not detail.description_is_image_only


def test_pdp_images_use_unexpiring_urls(pdp_payload):
    detail = parse_pdp_response(pdp_payload)

    assert detail.image_urls, "the fixture should contain media"
    for url in detail.image_urls:
        assert "x-signature" not in url, "a signed, expiring URL was kept"
        assert f"/{IMAGE_SIZE}/" in url, f"not the unsigned cache form: {url}"


def test_pdp_skips_video_entries(pdp_payload):
    payload = copy.deepcopy(pdp_payload)
    for component in payload["data"]["pdpMainInfo"]["components"]:
        if component.get("name") == "product_media":
            component["data"][0]["media"].insert(
                0,
                {
                    "type": "video",
                    "prefix": "https://images.tokopedia.net/img/cache/",
                    "suffix": "/x/poster~.jpeg",
                },
            )

    detail = parse_pdp_response(payload)
    assert not any("poster" in url for url in detail.image_urls)


def test_pdp_image_only_description_keeps_specs(pdp_image_only_payload):
    """Sellers who upload the description as pictures must stay visibly empty."""
    detail = parse_pdp_response(pdp_image_only_payload)

    assert not detail.description, "there is no prose in this response"
    assert detail.specs, "the structured spec pairs should still be captured"
    assert detail.description_is_image_only
    assert not detail.is_empty, "specs alone still count as usable data"


def test_pdp_missing_root_degrades():
    detail = parse_pdp_response({"data": {"nope": {}}}, product_id="123")
    assert detail.is_empty
    assert detail.description is None
    assert detail.image_urls == []


def test_pdp_empty_components_do_not_raise():
    payload = {"data": {"pdpMainInfo": {"data": {}, "components": []}}}
    detail = parse_pdp_response(payload, product_id="9")
    assert detail.is_empty


def test_pdp_counts_coerce_on_product(pdp_payload):
    detail = parse_pdp_response(pdp_payload)
    product = Product(
        product_id="1",
        url="https://www.tokopedia.com/a/b",
        rating=detail.rating,
        review_count=detail.review_count,
        sold_count=detail.sold_count,
        description=detail.description,
        specs=detail.specs,
    )
    if detail.review_count is not None:
        assert isinstance(product.review_count, int)
    if detail.sold_count is not None:
        assert isinstance(product.sold_count, int)


# --- coercions ------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Rp1.250.000", 1_250_000),
        ("Rp10.000 - Rp25.000", 10_000),
        (459000, 459_000),
        ("1,2jt", 1_200_000),
        (None, None),
        ("gratis ongkir", None),
        ("", None),
    ],
)
def test_parse_price(raw, expected):
    assert parse_price(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("10rb+", 10_000),
        ("1,2rb", 1_200),
        ("250", 250),
        ("terjual 5+", 5),
        (None, None),
    ],
)
def test_parse_count(raw, expected):
    assert parse_count(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [("4.8", 4.8), (48, 4.8), (5, 5.0), (9.9, None), ("abc", None), (None, None)],
)
def test_parse_rating(raw, expected):
    assert parse_rating(raw) == expected


def test_dig_never_raises():
    doc = {"a": {"b": [{"c": 1}]}}
    assert dig(doc, "a.b.0.c") == 1
    assert dig(doc, "a.b.9.c") is None
    assert dig(doc, "a.missing.deep") is None
    assert dig(doc, "a.b.notanindex") is None
    assert dig(None, "a.b") is None


def test_first_takes_the_first_present_path():
    doc = {"a": {"x": None, "y": "", "z": "value"}}
    assert first(doc, "a.x", "a.y", "a.z") == "value"
    assert first(doc, "a.x", "a.y", default="fallback") == "fallback"


def test_product_derives_discount():
    product = Product(
        product_id="1",
        url="https://www.tokopedia.com/a/b",
        price=259_000,
        original_price=899_000,
    )
    assert product.discount_pct == pytest.approx(71.19, abs=0.01)


def test_product_normalises_ids_and_lists():
    product = Product(
        product_id=123,
        url="https://www.tokopedia.com/a/b",
        image_urls=["https://x/a.jpg", "", "https://x/a.jpg", None],
        specs={"  Kondisi  ": "  Baru  ", "empty": ""},
    )
    assert product.product_id == "123"
    assert product.image_urls == ["https://x/a.jpg"]
    assert product.specs == {"Kondisi": "Baru"}
