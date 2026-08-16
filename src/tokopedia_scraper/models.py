"""Normalised product schema plus the defensive coercions parsers rely on.

Parsing rule for this project: a missing or malformed field becomes None and is
logged. It never raises, because one weird product must not kill a batch of 60.
Anything that *does* raise here is a bug in this module, not bad input.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Iterable

from pydantic import BaseModel, ConfigDict, Field, field_validator

log = logging.getLogger(__name__)

# Indonesian shorthand used in sold counts and prices: "10 rb" = 10 000,
# "1,2 jt" = 1 200 000.
_MAGNITUDE = {"rb": 1_000, "ribu": 1_000, "jt": 1_000_000, "juta": 1_000_000}

_NUM_RE = re.compile(r"(\d[\d.,]*)\s*(rb|ribu|jt|juta)?", re.IGNORECASE)

# Schema drift is reported once per (context, key) for the life of the process.
# Tokopedia adds fields constantly; a warning per product would be unreadable.
_drift_seen: set[tuple[str, str]] = set()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def note_schema_drift(context: str, payload: Any, known: Iterable[str]) -> list[str]:
    """Log keys present in `payload` that the parser does not know about.

    Returns the unknown keys so callers can assert on them in tests.
    """
    if not isinstance(payload, dict):
        return []
    unknown = sorted(set(payload) - set(known))
    for key in unknown:
        marker = (context, key)
        if marker not in _drift_seen:
            _drift_seen.add(marker)
            log.warning(
                "schema drift: %s has unhandled field %r (value type %s). "
                "Raw responses are stored, so this can be back-filled without "
                "re-scraping.",
                context,
                key,
                type(payload[key]).__name__,
            )
    return unknown


def _to_number(value: Any) -> float | None:
    """Best-effort number extraction from Tokopedia's very mixed formatting."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None

    text = value.replace("\xa0", " ").strip()
    if not text:
        return None

    # Price ranges ("Rp10.000 - Rp25.000") collapse to the lower bound.
    text = re.split(r"\s*[-–]\s*", text)[0]

    match = _NUM_RE.search(text)
    if not match:
        return None

    digits, suffix = match.group(1), (match.group(2) or "").lower()

    if suffix:
        # With a magnitude suffix the comma is a decimal point: "1,2rb".
        digits = digits.replace(".", "").replace(",", ".")
        try:
            return float(digits) * _MAGNITUDE[suffix]
        except ValueError:
            return None

    # Without a suffix, "." and "," are both thousands separators in the
    # Indonesian formatting Tokopedia emits ("Rp1.250.000").
    try:
        return float(digits.replace(".", "").replace(",", ""))
    except ValueError:
        return None


def parse_price(value: Any) -> int | None:
    """'Rp1.250.000' -> 1250000. Returns None rather than raising."""
    number = _to_number(value)
    if number is None:
        return None
    if number < 0:
        log.debug("negative price %r treated as missing", value)
        return None
    return int(round(number))


def parse_count(value: Any) -> int | None:
    """'10rb+' -> 10000, '1,2jt' -> 1200000, '250' -> 250."""
    number = _to_number(value)
    if number is None or number < 0:
        return None
    return int(round(number))


def parse_rating(value: Any) -> float | None:
    """Ratings arrive as 4.8, '4.8', or occasionally 48 (tenths)."""
    number = _to_number(value)
    if number is None:
        return None
    # Only whole numbers can be the tenths encoding (48 -> 4.8); a value like
    # 9.9 already carries a decimal point and is simply out of range.
    if 5 < number <= 50 and number.is_integer():
        number = number / 10.0
    if not 0 <= number <= 5:
        log.debug("rating %r outside 0..5, treated as missing", value)
        return None
    return round(number, 2)


def dig(obj: Any, path: str, default: Any = None) -> Any:
    """Walk a dotted path through nested dicts/lists: dig(d, 'data.items.0.name').

    Any missing key, wrong type or out-of-range index yields `default`.
    """
    current = obj
    for part in path.split("."):
        if isinstance(current, dict):
            if part not in current:
                return default
            current = current[part]
        elif isinstance(current, (list, tuple)):
            if not part.lstrip("-").isdigit():
                return default
            index = int(part)
            if not -len(current) <= index < len(current):
                return default
            current = current[index]
        else:
            return default
    return default if current is None else current


def first(obj: Any, *paths: str, default: Any = None) -> Any:
    """First non-None value among several candidate dotted paths.

    Tokopedia moves fields between response shapes; this lets a parser accept
    both the old and the new location without branching.
    """
    for path in paths:
        value = dig(obj, path)
        if value not in (None, ""):
            return value
    return default


class Product(BaseModel):
    """One row of the `products` table."""

    # Unknown keys are dropped rather than rejected; note_schema_drift() is what
    # makes them visible.
    model_config = ConfigDict(extra="ignore")

    product_id: str
    url: str

    shop_id: str | None = None
    shop_name: str | None = None

    title: str | None = None
    price: int | None = None
    original_price: int | None = None
    discount_pct: float | None = None
    currency: str = "IDR"

    rating: float | None = None
    review_count: int | None = None
    sold_count: int | None = None

    category_path: list[str] = Field(default_factory=list)

    # Prose only. Many sellers upload their description as images instead of
    # text, and for an auto-description dataset those products must stay
    # visibly empty rather than be padded with something that is not prose.
    description: str | None = None

    # Structured attribute pairs from the PDP ("Kondisi": "Baru", ...). Present
    # even when `description` is empty, so a product whose description is an
    # image still carries usable facts.
    specs: dict[str, str] = Field(default_factory=dict)

    image_urls: list[str] = Field(default_factory=list)
    local_image_paths: list[str] = Field(default_factory=list)

    source_keyword: str | None = None
    fetcher_used: str | None = None
    scraped_at: datetime = Field(default_factory=utcnow)

    # Stage 2 marker: False until the PDP has been fetched and parsed.
    pdp_fetched: bool = False

    @field_validator("product_id", "shop_id", mode="before")
    @classmethod
    def _ids_as_str(cls, v: Any) -> Any:
        # IDs arrive as int in some responses and str in others; the primary key
        # must be one type or dedupe silently breaks.
        return str(v) if isinstance(v, (int, float)) else v

    # Coercion lives on the model, not in the parser, so that *every* caller
    # (parsers, notebooks, re-parse-from-raw scripts) gets the same defensive
    # behaviour: a malformed value becomes None instead of raising.
    @field_validator("price", "original_price", mode="before")
    @classmethod
    def _coerce_price(cls, v: Any) -> Any:
        return v if v is None or isinstance(v, int) else parse_price(v)

    @field_validator("review_count", "sold_count", mode="before")
    @classmethod
    def _coerce_count(cls, v: Any) -> Any:
        return v if v is None or isinstance(v, int) else parse_count(v)

    @field_validator("rating", mode="before")
    @classmethod
    def _coerce_rating(cls, v: Any) -> Any:
        return None if v is None else parse_rating(v)

    @field_validator("discount_pct", mode="before")
    @classmethod
    def _coerce_pct(cls, v: Any) -> Any:
        return v if v is None or isinstance(v, float) else _to_number(v)

    @field_validator("title", "shop_name", "description", mode="before")
    @classmethod
    def _clean_text(cls, v: Any) -> Any:
        if isinstance(v, str):
            v = v.strip()
            return v or None
        return v

    @field_validator("image_urls", "local_image_paths", "category_path", mode="before")
    @classmethod
    def _clean_list(cls, v: Any) -> Any:
        if v is None:
            return []
        if isinstance(v, str):
            v = [v]
        if not isinstance(v, (list, tuple)):
            return []
        seen: set[str] = set()
        out: list[str] = []
        for item in v:
            if not isinstance(item, str):
                continue
            item = item.strip()
            if item and item not in seen:
                seen.add(item)
                out.append(item)
        return out

    @field_validator("specs", mode="before")
    @classmethod
    def _clean_specs(cls, v: Any) -> Any:
        if not isinstance(v, dict):
            return {}
        out: dict[str, str] = {}
        for key, value in v.items():
            key = str(key).strip()
            value = "" if value is None else str(value).strip()
            if key and value:
                out[key] = value
        return out

    @field_validator("scraped_at", mode="before")
    @classmethod
    def _aware_utc(cls, v: Any) -> Any:
        if isinstance(v, datetime) and v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v

    def model_post_init(self, _ctx: Any) -> None:
        # Derive the discount when the site gave us both prices but no percentage.
        if (
            self.discount_pct is None
            and self.price is not None
            and self.original_price
            and self.original_price > self.price
        ):
            drop = (self.original_price - self.price) / self.original_price
            object.__setattr__(self, "discount_pct", round(drop * 100, 2))


if __name__ == "__main__":  # pragma: no cover - manual smoke check
    logging.basicConfig(level=logging.WARNING)

    assert parse_price("Rp1.250.000") == 1_250_000
    assert parse_price("Rp10.000 - Rp25.000") == 10_000, "range must take lower bound"
    assert parse_price(459000) == 459_000
    assert parse_price("1,2jt") == 1_200_000
    assert parse_price(None) is None and parse_price("gratis ongkir") is None

    assert parse_count("10rb+") == 10_000
    assert parse_count("1,2rb") == 1_200
    assert parse_count("250") == 250
    assert parse_count("terjual 5+") == 5

    assert parse_rating("4.8") == 4.8
    assert parse_rating(48) == 4.8, "tenths encoding must be rescaled"
    assert parse_rating(9.9) is None

    doc = {"data": {"items": [{"name": "A"}, {"name": "B"}]}}
    assert dig(doc, "data.items.1.name") == "B"
    assert dig(doc, "data.items.9.name") is None, "out-of-range must not raise"
    assert dig(doc, "data.missing.deep") is None
    assert first(doc, "data.nope", "data.items.0.name") == "A"

    # A near-empty payload must still produce a row.
    sparse = Product(product_id=123, url="https://www.tokopedia.com/x/y")
    assert sparse.product_id == "123", "int id must normalise to str"
    assert sparse.title is None and sparse.image_urls == []
    assert sparse.pdp_fetched is False
    assert sparse.scraped_at.tzinfo is not None

    full = Product(
        product_id="1",
        url="https://www.tokopedia.com/toko-contoh/air-fryer",
        title="  Air Fryer 5L  ",
        price="Rp459.000",
        original_price="Rp699.000",
        image_urls=[
            "https://images.tokopedia.net/a.jpg",
            "",
            "https://images.tokopedia.net/a.jpg",
        ],
    )
    assert full.title == "Air Fryer 5L", "whitespace must be stripped"
    assert full.price == 459_000 and full.original_price == 699_000
    assert full.discount_pct == 34.33, f"derived discount wrong: {full.discount_pct}"
    assert full.image_urls == ["https://images.tokopedia.net/a.jpg"], "must dedupe"

    unknown = note_schema_drift("search.item", {"name": "x", "newField": 1}, ["name"])
    assert unknown == ["newField"]
    assert note_schema_drift("search.item", {"name": "x", "newField": 1}, ["name"]) == [
        "newField"
    ], "drift detection must stay pure even when logging is suppressed"

    print("models.py self-check OK")
