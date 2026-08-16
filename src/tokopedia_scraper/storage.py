"""SQLite storage. The database *is* the checkpoint — there is no separate
resume file, so a process killed at product 7431 loses nothing.

Three tables:
  raw_responses    every response, stored before parsing, so a parser bug or a
                   Tokopedia schema change can be fixed by re-parsing instead of
                   re-scraping.
  products         the normalised rows.
  keyword_progress per-keyword stage 1 bookkeeping.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence

from .models import Product, utcnow

log = logging.getLogger(__name__)

JSON_LIST_FIELDS = ("category_path", "image_urls", "local_image_paths")
JSON_DICT_FIELDS = ("specs",)
JSON_FIELDS = JSON_LIST_FIELDS + JSON_DICT_FIELDS

# Columns added after the first release. SQLite has no "ADD COLUMN IF NOT
# EXISTS", so they are applied by comparing against PRAGMA table_info.
MIGRATIONS: tuple[tuple[str, str], ...] = (
    ("products", "specs TEXT"),
    ("products", "pdp_error TEXT"),
)

# Columns stage 1 (search) is allowed to write. Deliberately excludes
# description / local_image_paths / pdp_fetched: re-running a search to refresh
# prices must never erase stage 2 work.
SEARCH_COLUMNS = (
    "product_id",
    "url",
    "shop_id",
    "shop_name",
    "title",
    "price",
    "original_price",
    "discount_pct",
    "currency",
    "rating",
    "review_count",
    "sold_count",
    "category_path",
    "image_urls",
    "source_keyword",
    "fetcher_used",
    "scraped_at",
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS raw_responses (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    stage       TEXT NOT NULL,
    ref         TEXT NOT NULL,
    product_id  TEXT,
    keyword     TEXT,
    page        INTEGER,
    payload     TEXT NOT NULL,
    fetched_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_raw_stage_ref ON raw_responses(stage, ref);
CREATE INDEX IF NOT EXISTS idx_raw_product   ON raw_responses(product_id);

CREATE TABLE IF NOT EXISTS products (
    product_id        TEXT PRIMARY KEY,
    url               TEXT NOT NULL,
    shop_id           TEXT,
    shop_name         TEXT,
    title             TEXT,
    price             INTEGER,
    original_price    INTEGER,
    discount_pct      REAL,
    currency          TEXT,
    rating            REAL,
    review_count      INTEGER,
    sold_count        INTEGER,
    category_path     TEXT,
    description       TEXT,
    specs             TEXT,
    image_urls        TEXT,
    local_image_paths TEXT,
    source_keyword    TEXT,
    fetcher_used      TEXT,
    scraped_at        TEXT,
    pdp_fetched       INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_products_pending ON products(pdp_fetched);
CREATE INDEX IF NOT EXISTS idx_products_keyword ON products(source_keyword);

CREATE TABLE IF NOT EXISTS keyword_progress (
    keyword    TEXT PRIMARY KEY,
    last_page  INTEGER NOT NULL DEFAULT 0,
    collected  INTEGER NOT NULL DEFAULT 0,
    done       INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);
"""


def _iso(value: datetime | str | None) -> str:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    if isinstance(value, str):
        return value
    return utcnow().isoformat()


class Storage:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, timeout=30)
        self.conn.row_factory = sqlite3.Row
        # WAL keeps a reader (a notebook, `stats`) from blocking the running
        # scrape; the busy timeout absorbs the brief writer overlaps.
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.executescript(SCHEMA)
        self._migrate()
        self.conn.commit()

    def _migrate(self) -> None:
        """Add columns introduced after a database was first created."""
        for table, column_def in MIGRATIONS:
            column = column_def.split()[0]
            existing = {
                row[1] for row in self.conn.execute(f"PRAGMA table_info({table})")
            }
            if column not in existing:
                log.info("migrating %s: adding column %s", table, column)
                self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {column_def}")

    # -- lifecycle ---------------------------------------------------------

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "Storage":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        try:
            yield self.conn
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    # -- raw responses -----------------------------------------------------

    def save_raw(
        self,
        stage: str,
        ref: str,
        payload: Any,
        *,
        product_id: str | None = None,
        keyword: str | None = None,
        page: int | None = None,
    ) -> None:
        """Persist a response verbatim, before any parsing touches it."""
        text = (
            payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
        )
        with self._tx() as conn:
            conn.execute(
                "INSERT INTO raw_responses "
                "(stage, ref, product_id, keyword, page, payload, fetched_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (stage, ref, product_id, keyword, page, text, utcnow().isoformat()),
            )

    def iter_raw(self, stage: str | None = None) -> Iterator[sqlite3.Row]:
        """Stream stored responses, for re-parsing without re-scraping."""
        sql = "SELECT * FROM raw_responses"
        params: tuple[Any, ...] = ()
        if stage:
            sql += " WHERE stage = ?"
            params = (stage,)
        yield from self.conn.execute(sql + " ORDER BY id", params)

    # -- products ----------------------------------------------------------

    def upsert_search_products(self, products: Iterable[Product]) -> int:
        """Insert stage 1 rows, refreshing prices on re-runs.

        Not a bare INSERT OR REPLACE: that would null out `description`,
        `local_image_paths` and `pdp_fetched` for products already enriched by
        stage 2. Only the search-derived columns are overwritten.
        """
        rows = [
            tuple(_encode(getattr(p, col), col) for col in SEARCH_COLUMNS)
            for p in products
        ]
        if not rows:
            return 0

        placeholders = ", ".join("?" * len(SEARCH_COLUMNS))
        updates = ", ".join(
            f"{col}={_conflict_expr(col)}"
            for col in SEARCH_COLUMNS
            if col != "product_id"
        )
        sql = (
            f"INSERT INTO products ({', '.join(SEARCH_COLUMNS)}) "
            f"VALUES ({placeholders}) "
            f"ON CONFLICT(product_id) DO UPDATE SET {updates}"
        )
        with self._tx() as conn:
            conn.executemany(sql, rows)
        return len(rows)

    def update_pdp(
        self,
        product_id: str,
        *,
        description: str | None,
        image_urls: Sequence[str] | None = None,
        category_path: Sequence[str] | None = None,
        fetcher_used: str | None = None,
        rating: float | None = None,
        review_count: int | None = None,
        sold_count: int | None = None,
        title: str | None = None,
        specs: dict[str, str] | None = None,
    ) -> None:
        """Write stage 2 results and flip the resume flag.

        pdp_fetched is set even when the description came back empty — the page
        was visited, and re-visiting it would just burn the same rate limit
        again. Empty descriptions are surfaced by `stats()` instead.

        The PDP is authoritative for review_count (search omits it entirely) and
        sold_count (search only gives buckets like "750+ terjual"). It is
        deliberately *not* used for price: stage 1 owns that column and
        refreshes it every run, and two writers would make it impossible to say
        when a given price was read.
        """
        sets = ["description = ?", "pdp_fetched = 1"]
        params: list[Any] = [description]
        if image_urls is not None:
            sets.append("image_urls = ?")
            params.append(json.dumps(list(image_urls), ensure_ascii=False))
        if category_path is not None:
            sets.append("category_path = ?")
            params.append(json.dumps(list(category_path), ensure_ascii=False))
        if specs is not None:
            sets.append("specs = ?")
            params.append(json.dumps(dict(specs), ensure_ascii=False))
        if fetcher_used is not None:
            sets.append("fetcher_used = ?")
            params.append(fetcher_used)
        for column, value in (
            ("rating", rating),
            ("review_count", review_count),
            ("sold_count", sold_count),
            ("title", title),
        ):
            if value is not None:
                sets.append(f"{column} = ?")
                params.append(value)
        params.append(product_id)

        with self._tx() as conn:
            conn.execute(
                f"UPDATE products SET {', '.join(sets)} WHERE product_id = ?", params
            )

    def mark_pdp_failed(self, product_id: str, error: str) -> None:
        """Record a permanent stage 2 failure so the row stops being retried.

        Products get deleted by their sellers. Without this the row keeps
        pdp_fetched = 0, so every future run queues it again — and because the
        queue is ordered by rowid, the dead ones pile up at the front and are
        the first thing every run wastes its time on.
        """
        with self._tx() as conn:
            conn.execute(
                "UPDATE products SET pdp_error = ? WHERE product_id = ?",
                (error[:500], product_id),
            )

    def pending_pdp(self, limit: int | None = None) -> list[Product]:
        """Products still awaiting stage 2. This is the whole resume mechanism."""
        sql = (
            "SELECT * FROM products WHERE pdp_fetched = 0 AND pdp_error IS NULL "
            "ORDER BY rowid"
        )
        if limit:
            sql += f" LIMIT {int(limit)}"
        return [_row_to_product(r) for r in self.conn.execute(sql)]

    def products_needing_images(
        self, limit: int | None = None, *, include_unenriched: bool = False
    ) -> list[Product]:
        """Rows that have image URLs but no local files yet.

        Enriched rows only, by default. An un-enriched row still carries just
        the low-resolution search thumbnail, whose URL is signed and expires
        within hours — and stage 2 replaces it with the full gallery anyway.
        Downloading those first spends bandwidth on files that get superseded.
        Pass include_unenriched=True to take them regardless.
        """
        sql = (
            "SELECT * FROM products "
            "WHERE image_urls IS NOT NULL AND image_urls NOT IN ('', '[]') "
            "AND (local_image_paths IS NULL OR local_image_paths IN ('', '[]')) "
        )
        if not include_unenriched:
            sql += "AND pdp_fetched = 1 "
        sql += "ORDER BY rowid"
        if limit:
            sql += f" LIMIT {int(limit)}"
        return [_row_to_product(r) for r in self.conn.execute(sql)]

    def set_local_images(self, product_id: str, paths: Sequence[str]) -> None:
        with self._tx() as conn:
            conn.execute(
                "UPDATE products SET local_image_paths = ? WHERE product_id = ?",
                (json.dumps(list(paths), ensure_ascii=False), product_id),
            )

    def iter_products(self) -> Iterator[Product]:
        yield from (
            _row_to_product(r)
            for r in self.conn.execute("SELECT * FROM products ORDER BY rowid")
        )

    def get_product(self, product_id: str) -> Product | None:
        row = self.conn.execute(
            "SELECT * FROM products WHERE product_id = ?", (product_id,)
        ).fetchone()
        return _row_to_product(row) if row else None

    # -- keyword progress --------------------------------------------------

    def keyword_progress(self, keyword: str) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT * FROM keyword_progress WHERE keyword = ?", (keyword,)
        ).fetchone()

    def is_keyword_done(self, keyword: str) -> bool:
        row = self.keyword_progress(keyword)
        return bool(row and row["done"])

    def record_keyword_page(
        self, keyword: str, page: int, new_products: int, *, done: bool = False
    ) -> None:
        """Advance a keyword's checkpoint. `collected` accumulates across runs."""
        with self._tx() as conn:
            conn.execute(
                "INSERT INTO keyword_progress "
                "(keyword, last_page, collected, done, updated_at) "
                "VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(keyword) DO UPDATE SET "
                "  last_page = MAX(last_page, excluded.last_page), "
                "  collected = collected + excluded.collected, "
                "  done      = MAX(done, excluded.done), "
                "  updated_at = excluded.updated_at",
                (keyword, page, new_products, int(done), utcnow().isoformat()),
            )

    def mark_keyword_done(self, keyword: str) -> None:
        self.record_keyword_page(keyword, 0, 0, done=True)

    # -- reporting ---------------------------------------------------------

    def stats(self) -> dict[str, Any]:
        def q(sql: str) -> int:
            return self.conn.execute(sql).fetchone()[0]

        return {
            "products": q("SELECT COUNT(*) FROM products"),
            "pdp_fetched": q("SELECT COUNT(*) FROM products WHERE pdp_fetched = 1"),
            # Only rows still worth fetching — permanently gone ones excluded,
            # so the number matches what a resume will actually attempt.
            "pending_pdp": q(
                "SELECT COUNT(*) FROM products "
                "WHERE pdp_fetched = 0 AND pdp_error IS NULL"
            ),
            "pdp_gone": q(
                "SELECT COUNT(*) FROM products WHERE pdp_error IS NOT NULL"
            ),
            "with_description": q(
                "SELECT COUNT(*) FROM products "
                "WHERE description IS NOT NULL AND TRIM(description) <> ''"
            ),
            # Products whose seller uploaded the description as images: the PDP
            # was fetched, the structured specs came back, but there is no prose.
            "specs_no_description": q(
                "SELECT COUNT(*) FROM products WHERE pdp_fetched = 1 "
                "AND specs IS NOT NULL AND specs NOT IN ('', '{}') "
                "AND (description IS NULL OR TRIM(description) = '')"
            ),
            "short_description": q(
                "SELECT COUNT(*) FROM products "
                "WHERE LENGTH(COALESCE(description,'')) BETWEEN 1 AND 49"
            ),
            "with_local_images": q(
                "SELECT COUNT(*) FROM products WHERE local_image_paths IS NOT NULL "
                "AND local_image_paths NOT IN ('', '[]')"
            ),
            "raw_responses": q("SELECT COUNT(*) FROM raw_responses"),
            "keywords_done": q("SELECT COUNT(*) FROM keyword_progress WHERE done = 1"),
            "keywords_seen": q("SELECT COUNT(*) FROM keyword_progress"),
        }


# Columns that stage 2 fills in better than stage 2's search results can.
# Search returns a single low-res thumbnail and a truncated category; the PDP
# returns the full gallery and the full breadcrumb. Once a product has been
# enriched, a later search re-run must leave these alone.
#   image_urls     search returns one thumbnail, the PDP the full gallery
#   category_path  search truncates the breadcrumb
#   review_count   search does not carry it at all, so it would write NULL
#   sold_count     search buckets it ("750+ terjual"), the PDP gives the exact
#                  number (3761)
_PDP_OWNED = ("image_urls", "category_path", "review_count", "sold_count")


def _conflict_expr(column: str) -> str:
    if column in _PDP_OWNED:
        return (
            f"CASE WHEN products.pdp_fetched = 1 "
            f"THEN products.{column} ELSE excluded.{column} END"
        )
    return f"excluded.{column}"


def _encode(value: Any, column: str) -> Any:
    if column in JSON_DICT_FIELDS:
        return json.dumps(dict(value or {}), ensure_ascii=False)
    if column in JSON_LIST_FIELDS:
        return json.dumps(list(value or []), ensure_ascii=False)
    if column == "scraped_at":
        return _iso(value)
    if isinstance(value, bool):
        return int(value)
    return value


def _row_to_product(row: sqlite3.Row) -> Product:
    data = dict(row)
    for field in JSON_FIELDS:
        empty: Any = {} if field in JSON_DICT_FIELDS else []
        raw = data.get(field)
        try:
            data[field] = json.loads(raw) if raw else empty
        except json.JSONDecodeError:
            log.warning(
                "corrupt JSON in %s for product %s", field, data.get("product_id")
            )
            data[field] = empty
    data["pdp_fetched"] = bool(data.get("pdp_fetched"))
    return Product.model_validate(data)


if __name__ == "__main__":  # pragma: no cover - manual smoke check
    import tempfile

    logging.basicConfig(level=logging.WARNING)

    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "products.db"

        def make(pid: str, **kw: Any) -> Product:
            return Product(
                product_id=pid,
                url=f"https://www.tokopedia.com/toko/{pid}",
                source_keyword="air fryer",
                **kw,
            )

        with Storage(db) as st:
            st.upsert_search_products(
                [make("1", price=100_000), make("2", price=200_000)]
            )
            # Same ids again: the primary key must dedupe, not duplicate.
            st.upsert_search_products(
                [make("1", price=90_000), make("2", price=200_000)]
            )
            assert st.stats()["products"] == 2, "primary key failed to dedupe"
            assert st.get_product("1").price == 90_000, "re-run must refresh price"

            st.update_pdp(
                "1",
                description="Deskripsi lengkap produk",
                image_urls=["https://images.tokopedia.net/a.jpg"],
                rating=4.8,
                review_count=781,
                sold_count=3761,
            )
            assert st.stats()["pdp_fetched"] == 1
            enriched = st.get_product("1")
            assert enriched.review_count == 781, "PDP-only field not written"
            assert enriched.sold_count == 3761 and enriched.rating == 4.8
            # price stays owned by stage 1 — still the 90_000 written above.
            assert enriched.price == 90_000, enriched.price

            # The critical regression: a stage 1 re-run must not wipe stage 2.
            st.upsert_search_products([make("1", price=88_000)])
            p1 = st.get_product("1")
            assert p1.description == "Deskripsi lengkap produk", "stage 2 data destroyed"
            assert p1.pdp_fetched is True, "pdp_fetched reset by search re-run"
            assert p1.price == 88_000
            assert p1.image_urls == [
                "https://images.tokopedia.net/a.jpg"
            ], "search re-run overwrote the PDP image gallery"

            pending = st.pending_pdp()
            assert [p.product_id for p in pending] == ["2"], "resume list wrong"

            st.save_raw(
                "search",
                "air fryer|1",
                {"data": {"items": []}},
                keyword="air fryer",
                page=1,
            )
            st.save_raw("pdp", "1", '{"raw": "text"}', product_id="1")
            assert st.stats()["raw_responses"] == 2
            assert len(list(st.iter_raw("pdp"))) == 1

            st.record_keyword_page("air fryer", 1, 60)
            st.record_keyword_page("air fryer", 2, 60)
            row = st.keyword_progress("air fryer")
            assert row["last_page"] == 2 and row["collected"] == 120
            assert not st.is_keyword_done("air fryer")
            st.mark_keyword_done("air fryer")
            assert st.is_keyword_done("air fryer")
            assert (
                st.keyword_progress("air fryer")["last_page"] == 2
            ), "done must not reset page"

            assert st.products_needing_images()[0].product_id == "1"
            st.set_local_images("1", ["data/images/1/abc.jpg"])
            assert st.get_product("1").local_image_paths == ["data/images/1/abc.jpg"]
            assert st.products_needing_images() == []

        # Reopening must see everything: the DB is the only checkpoint.
        with Storage(db) as st2:
            assert st2.stats()["products"] == 2
            assert st2.is_keyword_done("air fryer")
            assert [p.product_id for p in st2.pending_pdp()] == ["2"]

    print("storage.py self-check OK")
