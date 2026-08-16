"""Storage, dedupe and resume.

The database is the only checkpoint, so these tests are really asking: can this
run be killed at any moment and restarted safely?
"""

from __future__ import annotations

import csv
import io
import json

from tokopedia_scraper.fetchers.base import Fetcher, FetchResult
from tokopedia_scraper.models import Product
from tokopedia_scraper.pipeline import (
    export_dataset,
    reparse_from_raw,
    run_enrich,
    run_search,
)
from tokopedia_scraper.ratelimit import CircuitBreaker, FetchError, RateLimiter
from tokopedia_scraper.storage import Storage


def make_product(pid: str, **kwargs) -> Product:
    return Product(
        product_id=pid,
        url=f"https://www.tokopedia.com/toko/{pid}",
        source_keyword="alpha",
        **kwargs,
    )


# --- dedupe ---------------------------------------------------------------


def test_primary_key_dedupes(storage):
    storage.upsert_search_products([make_product("1"), make_product("2")])
    storage.upsert_search_products([make_product("1"), make_product("2")])
    assert storage.stats()["products"] == 2


def test_rerun_refreshes_price(storage):
    storage.upsert_search_products([make_product("1", price=100_000)])
    storage.upsert_search_products([make_product("1", price=90_000)])
    assert storage.get_product("1").price == 90_000


def test_search_rerun_does_not_destroy_stage_two(storage):
    """The regression a plain INSERT OR REPLACE would cause."""
    storage.upsert_search_products([make_product("1", price=100_000)])
    storage.update_pdp(
        "1",
        description="Deskripsi lengkap",
        image_urls=["https://images.tokopedia.net/img/cache/1200/x/a~.jpeg"],
        specs={"Kondisi": "Baru"},
        review_count=781,
    )

    storage.upsert_search_products([make_product("1", price=88_000)])

    product = storage.get_product("1")
    assert product.price == 88_000, "price should still refresh"
    assert product.description == "Deskripsi lengkap"
    assert product.pdp_fetched is True
    assert product.review_count == 781
    assert product.specs == {"Kondisi": "Baru"}
    assert product.image_urls == [
        "https://images.tokopedia.net/img/cache/1200/x/a~.jpeg"
    ], "the PDP gallery must not be overwritten by a search thumbnail"


# --- resume ---------------------------------------------------------------


def test_pending_pdp_is_the_resume_list(storage):
    storage.upsert_search_products([make_product("1"), make_product("2")])
    assert {p.product_id for p in storage.pending_pdp()} == {"1", "2"}

    storage.update_pdp("1", description="x")
    assert [p.product_id for p in storage.pending_pdp()] == ["2"]


def test_images_wait_for_enrichment(storage):
    """Un-enriched rows hold only an expiring, low-res search thumbnail.

    Downloading those spends bandwidth on files stage 2 immediately supersedes,
    and their URLs are dead within hours anyway.
    """
    storage.upsert_search_products(
        [
            make_product(
                "1", image_urls=["https://sign.example/thumb.jpg?x-signature=z"]
            ),
            make_product(
                "2", image_urls=["https://sign.example/other.jpg?x-signature=z"]
            ),
        ]
    )
    assert storage.products_needing_images() == [], "nothing is enriched yet"

    # The escape hatch still works for anyone who wants them regardless.
    assert len(storage.products_needing_images(include_unenriched=True)) == 2

    storage.update_pdp(
        "1",
        description="x",
        image_urls=["https://images.tokopedia.net/img/cache/1200/x/a~.jpeg"],
    )
    pending = storage.products_needing_images()
    assert [p.product_id for p in pending] == ["1"]
    assert "x-signature" not in pending[0].image_urls[0]

    storage.set_local_images("1", ["data/images/1/abc.jpeg"])
    assert storage.products_needing_images() == []


def test_keyword_progress_accumulates(storage):
    storage.record_keyword_page("alpha", 1, 60)
    storage.record_keyword_page("alpha", 2, 60)

    row = storage.keyword_progress("alpha")
    assert row["last_page"] == 2
    assert row["collected"] == 120
    assert not storage.is_keyword_done("alpha")

    storage.mark_keyword_done("alpha")
    assert storage.is_keyword_done("alpha")
    assert storage.keyword_progress("alpha")["last_page"] == 2, "done must not reset"


def test_state_survives_reopening(cfg):
    with Storage(cfg.storage.db_path) as store:
        store.upsert_search_products([make_product("1"), make_product("2")])
        store.update_pdp("1", description="x")
        store.mark_keyword_done("alpha")

    with Storage(cfg.storage.db_path) as reopened:
        assert reopened.stats()["products"] == 2
        assert reopened.is_keyword_done("alpha")
        assert [p.product_id for p in reopened.pending_pdp()] == ["2"]


def test_migration_adds_specs_to_an_old_database(cfg):
    """A database created before `specs` existed must be upgraded in place."""
    with Storage(cfg.storage.db_path) as store:
        store.upsert_search_products([make_product("1")])
        store.conn.execute("ALTER TABLE products DROP COLUMN specs")
        store.conn.commit()

    with Storage(cfg.storage.db_path) as upgraded:
        columns = {
            row[1] for row in upgraded.conn.execute("PRAGMA table_info(products)")
        }
        assert "specs" in columns
        assert upgraded.stats()["products"] == 1, "existing rows must survive"


# --- pipeline resume ------------------------------------------------------


class StubFetcher(Fetcher):
    name = "stub"

    def __init__(self, cfg, payload, fail_on=None):
        self.cfg = cfg
        self.payload = payload
        self.fail_on = fail_on
        self.search_calls: list[tuple[str, int]] = []
        self.pdp_calls: list[str] = []

    def search(self, keyword: str, page: int) -> FetchResult:
        self.search_calls.append((keyword, page))
        if self.fail_on == (keyword, page):
            raise FetchError("simulated failure", status=500)

        body = json.loads(json.dumps(self.payload))
        node = body["data"]["searchProductV5"]
        for index, item in enumerate(node["data"]["products"]):
            item["id"] = f"{keyword}-{page}-{index}"
        node.setdefault("header", {})["additionalParams"] = (
            "has_more=true" if page < 3 else "has_more=false"
        )
        return FetchResult(payload=body, fetcher=self.name, url="stub")

    def fetch_pdp(self, product_url: str) -> FetchResult:
        self.pdp_calls.append(product_url)
        return FetchResult(payload=self.payload, fetcher=self.name, url=product_url)


def test_finished_keyword_costs_no_requests(cfg, storage, search_payload):
    run_search(cfg, storage, StubFetcher(cfg, search_payload), ["alpha"])
    assert storage.is_keyword_done("alpha")

    second = StubFetcher(cfg, search_payload)
    stats = run_search(cfg, storage, second, ["alpha"])
    assert second.search_calls == []
    assert stats.keywords_skipped == 1


def test_interrupted_keyword_resumes_at_the_next_page(cfg, storage, search_payload):
    broken = StubFetcher(cfg, search_payload, fail_on=("alpha", 2))
    run_search(cfg, storage, broken, ["alpha"])

    assert storage.keyword_progress("alpha")["last_page"] == 1
    assert not storage.is_keyword_done("alpha")

    healed = StubFetcher(cfg, search_payload)
    run_search(cfg, storage, healed, ["alpha"])
    assert healed.search_calls[0] == ("alpha", 2)
    assert storage.is_keyword_done("alpha")


class GoneFetcher(StubFetcher):
    """Every PDP reports that the product no longer exists."""

    def fetch_pdp(self, product_url: str) -> FetchResult:
        self.pdp_calls.append(product_url)
        raise FetchError(
            f"pdp {product_url}: GraphQL errors: [5] product: not found", status=404
        )


def test_gone_products_leave_the_queue(cfg, storage, search_payload):
    """A deleted product must not be retried on every future run.

    Rows keep pdp_fetched = 0 when stage 2 fails, and the queue is ordered by
    rowid, so dead products accumulate at the front. Left unhandled they are the
    first thing each run spends requests on, and enough in a row reads as a
    block and trips the circuit breaker.
    """
    run_search(cfg, storage, StubFetcher(cfg, search_payload), ["alpha"])
    before = storage.stats()["pending_pdp"]
    assert before > 2

    def marked() -> set[str]:
        return {
            row[0]
            for row in storage.conn.execute(
                "SELECT product_id FROM products WHERE pdp_error IS NOT NULL"
            )
        }

    stats = run_enrich(cfg, storage, GoneFetcher(cfg, search_payload), limit=2)
    first_round = marked()

    assert stats.gone == 2
    assert stats.failures == 2
    assert len(first_round) == 2
    assert storage.stats()["pdp_gone"] == 2
    assert storage.stats()["pending_pdp"] == before - 2

    # The whole point: a second run must move on to different products.
    # Compared by product_id, not URL — the fixture reuses URLs across ids.
    run_enrich(cfg, storage, GoneFetcher(cfg, search_payload), limit=2)
    second_round = marked() - first_round

    assert len(second_round) == 2, "the second run did not advance past the dead rows"
    assert not (second_round & first_round)


def test_gone_products_do_not_trip_the_circuit_breaker(cfg, storage, search_payload):
    """Deleted products say nothing about whether we are being blocked."""
    run_search(cfg, storage, StubFetcher(cfg, search_payload), ["alpha"])

    gone = GoneFetcher(cfg, search_payload)
    gone.breaker = CircuitBreaker(threshold=2)
    gone.limiter = RateLimiter(cfg.rate_limit, sleep=lambda _: None)

    # No CircuitOpen, despite far more consecutive failures than the threshold.
    stats = run_enrich(cfg, storage, gone)
    assert stats.gone == stats.failures > 2
    assert storage.stats()["pending_pdp"] == 0


def test_one_bad_row_does_not_end_the_run(cfg, storage, search_payload, pdp_payload):
    """A single unexpected exception must not discard the rest of the queue."""

    class OneExploder(StubFetcher):
        def fetch_pdp(self, product_url: str) -> FetchResult:
            self.pdp_calls.append(product_url)
            if len(self.pdp_calls) == 1:
                raise ValueError("something nobody anticipated")
            return FetchResult(payload=self.payload, fetcher=self.name, url=product_url)

    run_search(cfg, storage, StubFetcher(cfg, search_payload), ["alpha"])
    pending = storage.stats()["pending_pdp"]
    assert pending > 1

    fetcher = OneExploder(cfg, pdp_payload)
    stats = run_enrich(cfg, storage, fetcher)

    assert len(fetcher.pdp_calls) == pending, "the run stopped at the bad row"
    assert stats.failures == 1
    assert stats.products == pending - 1
    assert storage.stats()["pending_pdp"] == 0


def test_enrich_only_touches_pending(cfg, storage, search_payload, pdp_payload):
    run_search(cfg, storage, StubFetcher(cfg, search_payload), ["alpha"])

    enricher = StubFetcher(cfg, pdp_payload)
    run_enrich(cfg, storage, enricher, limit=1)
    assert len(enricher.pdp_calls) == 1

    remaining = storage.stats()["pending_pdp"]
    again = StubFetcher(cfg, pdp_payload)
    run_enrich(cfg, storage, again)
    assert len(again.pdp_calls) == remaining, "already-enriched rows were refetched"


# --- reparse and export ---------------------------------------------------


def test_reparse_rebuilds_without_network(cfg, storage, search_payload, pdp_payload):
    run_search(cfg, storage, StubFetcher(cfg, search_payload), ["alpha"])
    run_enrich(cfg, storage, StubFetcher(cfg, pdp_payload), limit=2)

    before = storage.stats()["products"]
    stats = reparse_from_raw(cfg, storage)

    assert stats.failures == 0
    assert storage.stats()["products"] == before, "reparse must not duplicate rows"
    assert stats.products > 0


def test_export_round_trips(cfg, storage, search_payload, pdp_payload):
    run_search(cfg, storage, StubFetcher(cfg, search_payload), ["alpha"])
    run_enrich(cfg, storage, StubFetcher(cfg, pdp_payload), limit=1)

    paths = export_dataset(cfg, storage, ("jsonl", "csv"))
    assert len(paths) == 2

    lines = (cfg.storage.export_dir / "products.jsonl").read_text("utf-8").splitlines()
    assert len(lines) == storage.stats()["products"]

    row = json.loads(lines[0])
    assert isinstance(row["category_path"], list)
    assert isinstance(row["specs"], dict)
    assert isinstance(row["image_urls"], list)

    with (cfg.storage.export_dir / "products.csv").open(encoding="utf-8") as handle:
        csv_rows = list(csv.DictReader(handle))
    assert len(csv_rows) == len(lines)
    # Lists and dicts must survive the CSV trip as JSON, not as repr().
    assert isinstance(json.loads(csv_rows[0]["image_urls"]), list)
    assert isinstance(json.loads(csv_rows[0]["specs"]), dict)


def test_csv_single_line_keeps_one_record_per_line(
    cfg, storage, search_payload, pdp_payload
):
    run_search(cfg, storage, StubFetcher(cfg, search_payload), ["alpha"])
    run_enrich(cfg, storage, StubFetcher(cfg, pdp_payload), limit=1)
    # Every separator str.splitlines() breaks on, not just \n — sellers paste
    # from Word and these really do turn up in the descriptions.
    messy = "baris satu\r\n\x0bdua\x0ctiga\x85empat lima enam, ada koma"
    storage.conn.execute("UPDATE products SET description = ?", (messy,))
    storage.conn.commit()

    # JSONL has the same trap: json.dumps leaves U+0085/2028/2029 literal, so a
    # reader using splitlines() would see one record as two.
    export_dataset(cfg, storage, ("jsonl",), stem="flat")
    jsonl = (cfg.storage.export_dir / "flat.jsonl").read_text("utf-8")
    assert len(jsonl.splitlines()) == storage.stats()["products"]
    assert json.loads(jsonl.splitlines()[0])["description"] == messy, (
        "escaping must be reversible — json.loads gives the original text back"
    )

    export_dataset(cfg, storage, ("csv",), csv_single_line=True, stem="flat")
    text = (cfg.storage.export_dir / "flat.csv").read_text("utf-8-sig")

    # One physical line per record plus the header, and the comma inside the
    # description must not have split a field.
    assert len(text.splitlines()) == storage.stats()["products"] + 1

    rows = list(csv.DictReader(io.StringIO(text)))
    assert rows[0]["description"] == "baris satu dua tiga empat lima enam, ada koma"

    # Default stays lossless: the separators are still there.
    export_dataset(cfg, storage, ("csv",), stem="raw")
    # newline="" or Python rewrites the \r\n inside the field before the CSV
    # parser sees it, and the round trip looks lossy when it is not.
    with (cfg.storage.export_dir / "raw.csv").open(
        encoding="utf-8-sig", newline=""
    ) as handle:
        raw = list(csv.DictReader(handle))
    assert raw[0]["description"] == messy


def test_export_of_empty_database_is_not_an_error(cfg, storage):
    assert export_dataset(cfg, storage, ("jsonl",)) == []


# --- raw responses --------------------------------------------------------


def test_raw_is_saved_before_parsing(cfg, storage, search_payload):
    run_search(cfg, storage, StubFetcher(cfg, search_payload), ["alpha"])
    raw = list(storage.iter_raw("search"))

    assert raw, "raw responses must be stored"
    assert raw[0]["keyword"] == "alpha"
    assert raw[0]["page"] == 1
    assert json.loads(raw[0]["payload"])["data"]["searchProductV5"]


def test_corrupt_json_column_does_not_crash_reads(storage):
    storage.upsert_search_products([make_product("1")])
    storage.conn.execute("UPDATE products SET image_urls = 'not json'")
    storage.conn.commit()

    product = storage.get_product("1")
    assert product.image_urls == [], "corrupt JSON should degrade to empty"
