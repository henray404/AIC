"""The two-stage pipeline.

Every unit of work is committed before the next one starts, so killing the
process loses at most one page or one product. Resume state lives entirely in
the database: `keyword_progress` for stage 1, `products.pdp_fetched` for
stage 2. There is no checkpoint file to get out of sync.
"""

from __future__ import annotations

import csv
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Sequence

from .config import Config
from .fetchers.base import Fetcher
from .models import Product, parse_count, parse_rating
from .parsers import parse_pdp_response, parse_search_response
from .ratelimit import CircuitOpen, FetchError
from .storage import Storage

log = logging.getLogger(__name__)

# Called as progress(done, total, label). Deliberately dumb so the caller can
# wire it to rich, tqdm, print, or nothing at all.
ProgressFn = Callable[[int, int, str], None]


@dataclass
class RunStats:
    requests: int = 0
    failures: int = 0
    pages: int = 0
    products: int = 0
    keywords_done: int = 0
    keywords_skipped: int = 0
    images: int = 0
    # Products the seller has deleted. Counted apart from `failures` because
    # they are not a problem to fix — they will never come back.
    gone: int = 0
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {k: v for k, v in self.__dict__.items() if k != "notes"}


# --------------------------------------------------------------------------
# Stage 1 — search
# --------------------------------------------------------------------------


def run_search(
    cfg: Config,
    storage: Storage,
    fetcher: Fetcher,
    keywords: Sequence[str] | None = None,
    *,
    max_pages: int | None = None,
    progress: ProgressFn | None = None,
) -> RunStats:
    """Collect product listings for each keyword.

    Resume rules:
      * a keyword already marked done is skipped without a single request;
      * an interrupted keyword restarts at last_page + 1.
    """
    stats = RunStats()
    words = list(keywords or cfg.keywords)
    page_cap = max_pages or cfg.search.max_pages_per_keyword
    target = cfg.search.target_per_keyword

    for index, keyword in enumerate(words, start=1):
        if progress:
            progress(index - 1, len(words), keyword)

        if storage.is_keyword_done(keyword):
            stats.keywords_skipped += 1
            log.info("skip %r — already complete", keyword)
            continue

        row = storage.keyword_progress(keyword)
        first_page = (row["last_page"] + 1) if row else 1
        collected = row["collected"] if row else 0

        if first_page > page_cap:
            log.info(
                "skip %r — already at page %d of a %d-page limit",
                keyword,
                first_page - 1,
                page_cap,
            )
            stats.keywords_skipped += 1
            continue

        log.info("keyword %r: pages %d..%d", keyword, first_page, page_cap)

        for page in range(first_page, page_cap + 1):
            try:
                result = fetcher.search(keyword, page)
            except CircuitOpen:
                # Deliberately not caught: the run stops rather than keep
                # hammering a server that is refusing us. Progress is saved.
                raise
            except FetchError as exc:
                stats.failures += 1
                log.error("keyword %r page %d failed: %s", keyword, page, exc)
                stats.notes.append(f"{keyword} p{page}: {exc}")
                break  # move to the next keyword rather than retry forever

            stats.requests += 1
            storage.save_raw(
                "search",
                f"{keyword}|{page}",
                result.payload,
                keyword=keyword,
                page=page,
            )

            products, page_info = parse_search_response(
                result.payload, keyword=keyword, fetcher_used=result.fetcher
            )
            storage.upsert_search_products(products)

            stats.pages += 1
            stats.products += len(products)
            collected += len(products)

            exhausted = (
                not products
                or page_info.has_more is False
                or (target and collected >= target)
            )
            storage.record_keyword_page(keyword, page, len(products), done=exhausted)

            log.info(
                "  p%-3d %3d products (total %d/%s) has_more=%s",
                page,
                len(products),
                collected,
                page_info.total,
                page_info.has_more,
            )

            if exhausted:
                stats.keywords_done += 1
                break
        else:
            # Ran out of configured pages without the site saying "no more".
            # Left un-done on purpose: raising search.max_pages_per_keyword
            # later resumes this keyword instead of skipping it.
            log.info(
                "keyword %r hit the %d-page limit; raise "
                "search.max_pages_per_keyword to continue it",
                keyword,
                page_cap,
            )

    if progress:
        progress(len(words), len(words), "done")
    return stats


# --------------------------------------------------------------------------
# Stage 2 — product detail pages
# --------------------------------------------------------------------------


def run_enrich(
    cfg: Config,
    storage: Storage,
    fetcher: Fetcher,
    *,
    limit: int | None = None,
    progress: ProgressFn | None = None,
) -> RunStats:
    """Fetch the PDP for every product that has not had one yet.

    The pending list is the resume mechanism: it is recomputed from the
    database, so an interrupted run simply picks up the remainder.
    """
    stats = RunStats()
    pending = storage.pending_pdp(limit)
    total = len(pending)
    log.info("enrich: %d products pending", total)

    for index, product in enumerate(pending, start=1):
        if progress:
            progress(index - 1, total, product.product_id)

        try:
            result = fetcher.fetch_pdp(product.url)
        except CircuitOpen:
            raise
        except FetchError as exc:
            stats.failures += 1
            log.error("pdp %s failed: %s", product.product_id, exc)
            stats.notes.append(f"{product.product_id}: {exc}")
            if exc.is_gone:
                # The seller deleted it. Record that so the row leaves the
                # queue, instead of being the first thing every future run
                # retries — and eventually trips the circuit breaker on.
                storage.mark_pdp_failed(product.product_id, str(exc))
                stats.gone += 1
            continue
        except Exception as exc:  # noqa: BLE001 - one bad row must not end the run
            # Belt and braces. A single malformed product URL once aborted a
            # 19k-product run at row 16,036. Nothing about one row justifies
            # throwing away the hours of work still queued behind it.
            stats.failures += 1
            stats.gone += 1
            log.exception("pdp %s raised unexpectedly", product.product_id)
            stats.notes.append(f"{product.product_id}: {type(exc).__name__}: {exc}")
            storage.mark_pdp_failed(product.product_id, f"{type(exc).__name__}: {exc}")
            continue

        stats.requests += 1
        storage.save_raw(
            "pdp", product.product_id, result.payload, product_id=product.product_id
        )

        detail = parse_pdp_response(
            result.payload,
            product_id=product.product_id,
            fetcher_used=result.fetcher,
        )

        storage.update_pdp(
            product.product_id,
            description=detail.description,
            # None means "keep what stage 1 stored"; an empty list would wipe it.
            image_urls=detail.image_urls or None,
            category_path=detail.category_path or None,
            specs=detail.specs or None,
            fetcher_used=result.fetcher,
            rating=parse_rating(detail.rating),
            review_count=parse_count(detail.review_count),
            sold_count=parse_count(detail.sold_count),
            title=detail.title,
        )
        stats.products += 1

        if detail.is_empty:
            stats.notes.append(f"{product.product_id}: PDP returned nothing usable")

    if progress:
        progress(total, total, "done")
    return stats


# --------------------------------------------------------------------------
# Re-parse
# --------------------------------------------------------------------------


def reparse_from_raw(
    cfg: Config,
    storage: Storage,
    stages: Sequence[str] = ("search", "pdp"),
    *,
    progress: ProgressFn | None = None,
) -> RunStats:
    """Rebuild the products table from stored raw responses. No network at all.

    This is what makes "save the raw response first" worth the disk space: when
    a parser bug is found, or Tokopedia moves a field, the fix is a re-parse
    rather than a re-scrape.
    """
    stats = RunStats()

    for stage in stages:
        rows = list(storage.iter_raw(stage))
        log.info("reparse %s: %d stored responses", stage, len(rows))

        for index, row in enumerate(rows, start=1):
            if progress:
                progress(index - 1, len(rows), f"{stage} {row['ref']}")

            try:
                payload = json.loads(row["payload"])
            except json.JSONDecodeError:
                stats.failures += 1
                stats.notes.append(f"{stage} {row['ref']}: stored payload is not JSON")
                continue

            if stage == "search":
                products, _ = parse_search_response(
                    payload, keyword=row["keyword"], fetcher_used="reparse"
                )
                storage.upsert_search_products(products)
                stats.products += len(products)
                stats.pages += 1
            else:
                detail = parse_pdp_response(payload, product_id=row["product_id"])
                storage.update_pdp(
                    row["product_id"],
                    description=detail.description,
                    image_urls=detail.image_urls or None,
                    category_path=detail.category_path or None,
                    specs=detail.specs or None,
                    rating=parse_rating(detail.rating),
                    review_count=parse_count(detail.review_count),
                    sold_count=parse_count(detail.sold_count),
                    title=detail.title,
                )
                stats.products += 1

    if progress:
        progress(1, 1, "done")
    return stats


# --------------------------------------------------------------------------
# Images
# --------------------------------------------------------------------------


def run_images(
    cfg: Config,
    storage: Storage,
    *,
    limit: int | None = None,
    progress: ProgressFn | None = None,
) -> RunStats:
    """Download product images for rows that have URLs but no local files."""
    from .image_downloader import download_for_product

    stats = RunStats()
    if not cfg.images.enabled:
        stats.notes.append("images.enabled is false in config — nothing to do")
        return stats

    products = storage.products_needing_images(limit)
    log.info("images: %d products with undownloaded images", len(products))

    for index, product in enumerate(products, start=1):
        if progress:
            progress(index - 1, len(products), product.product_id)

        paths = download_for_product(cfg, product)
        if paths:
            storage.set_local_images(product.product_id, paths)
            stats.images += len(paths)
            stats.products += 1
        else:
            stats.failures += 1

    if progress:
        progress(len(products), len(products), "done")
    return stats


# --------------------------------------------------------------------------
# Export
# --------------------------------------------------------------------------

EXPORT_COLUMNS = (
    "product_id",
    "shop_id",
    "shop_name",
    "url",
    "title",
    "price",
    "original_price",
    "discount_pct",
    "currency",
    "rating",
    "review_count",
    "sold_count",
    "category_path",
    "description",
    "specs",
    "image_urls",
    "local_image_paths",
    "source_keyword",
    "fetcher_used",
    "scraped_at",
    "pdp_fetched",
)

# The training-ready subset: just what a model actually consumes.
#
# product_id is the join key to data/images/<product_id>/, and url is here
# because this project's terms note promises the source is always retained.
#
# pdp_fetched earns its place by disambiguating a null description. Without it,
# "the seller wrote no description" and "stage 2 has not reached this row yet"
# look identical, and a consumer would silently train on rows that simply have
# not been collected.
SLIM_COLUMNS = (
    "product_id",
    "title",
    "price",
    "description",
    "pdp_fetched",
    "category_path",
    "image_urls",
    "local_image_paths",
    "url",
)

# Columns that hold structured values. CSV has no list or dict type, so they are
# JSON-encoded on the way out and survive a round trip.
JSON_COLUMNS = ("category_path", "image_urls", "local_image_paths", "specs")

# Below this, a description is technically present but useless as a training
# target — real rows exist with a single character in them.
MIN_TRAINABLE_CHARS = 50


def resolve_columns(
    columns: Sequence[str] | None, ready_only: bool
) -> tuple[str, ...]:
    """The columns an export actually emits.

    Shared with write_dataset_card so the card cannot document a column the
    file does not have — they used to derive this separately and drifted.
    """
    resolved = tuple(columns or EXPORT_COLUMNS)
    if ready_only:
        # Every ready row has pdp_fetched = true by definition, so the column
        # carries no information and only invites confusion.
        resolved = tuple(c for c in resolved if c != "pdp_fetched")
    return resolved



# json.dumps escapes everything below U+0020, which covers the vertical tab and
# form feed, but leaves these three literal. Python's splitlines(), JavaScript's
# older parsers and plenty of JSONL readers treat them as line breaks, so one
# record would silently arrive as two. Escaped they are still valid JSON and
# json.loads gives the original character back.
_JSON_LINE_BREAKS = {
    chr(0x85): '\\u0085',
    chr(0x2028): '\\u2028',
    chr(0x2029): '\\u2029',
}


def _jsonl_line(row: dict[str, object]) -> str:
    """One JSONL record that is guaranteed to occupy exactly one line."""
    line = json.dumps(row, ensure_ascii=False)
    for char, escape in _JSON_LINE_BREAKS.items():
        if char in line:
            line = line.replace(char, escape)
    return line


def _one_line(text: str) -> str:
    """Squash `text` onto one physical line, without gluing words together.

    str.split() with no argument, not a CR/LF regex: sellers paste from Word and
    Notepad, so the text arrives carrying vertical tabs, form feeds, U+0085 and
    U+2028. Python's splitlines() breaks on all of those, and a regex that knows
    only CR and LF leaves records still spanning two lines — the exact thing
    this function exists to prevent. Splitting on whitespace matches splitlines
    by construction.
    """
    return " ".join(text.split())


def _row(product: Product, columns: Sequence[str]) -> dict[str, object]:
    data = product.model_dump()
    data["scraped_at"] = product.scraped_at.isoformat()
    return {key: data.get(key) for key in columns}


def export_dataset(
    cfg: Config,
    storage: Storage,
    formats: Sequence[str] = ("jsonl", "csv"),
    *,
    columns: Sequence[str] | None = None,
    stem: str = "products",
    ready_only: bool = False,
    csv_single_line: bool = False,
) -> list[Path]:
    """Write the normalised table to data/exports/ in the requested formats.

    `columns` selects which fields to emit (defaults to all of them) and `stem`
    names the output files, so a slim training export can sit beside the full
    one instead of overwriting it.

    `ready_only` keeps just the rows a model can actually train on: stage 2 done
    and a non-empty description. Handing someone a file that is 80% nulls
    because a scrape is still running invites them to draw the wrong conclusion
    about the data.

    `csv_single_line` collapses newlines inside text fields so one record is one
    physical line. Quoted newlines are valid CSV and every real parser handles
    them, but they make the file look corrupt to anything that splits on lines,
    which is most quick tooling. It loses paragraph breaks, so it is off by
    default and the JSONL export always keeps the original text.
    """
    columns = resolve_columns(columns, ready_only)

    cfg.storage.export_dir.mkdir(parents=True, exist_ok=True)

    products = list(storage.iter_products())
    if ready_only:
        products = [
            p
            for p in products
            if p.pdp_fetched
            and p.description
            and len(p.description) >= MIN_TRAINABLE_CHARS
        ]
    rows = [_row(p, columns) for p in products]
    written: list[Path] = []

    if not rows:
        log.warning("nothing to export — the products table is empty")
        return written

    if "jsonl" in formats:
        path = cfg.storage.export_dir / f"{stem}.jsonl"
        with path.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(_jsonl_line(row) + "\n")
        written.append(path)

    if "csv" in formats:
        path = cfg.storage.export_dir / f"{stem}.csv"
        # utf-8-sig, not utf-8: without the BOM Excel decodes the file as the
        # system codepage and every accented character and emoji in the
        # descriptions turns to mojibake. pandas strips the BOM on its own.
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(columns))
            writer.writeheader()
            for row in rows:
                flat = dict(row)
                for column in JSON_COLUMNS:
                    if column not in flat:
                        continue
                    value = flat.get(column)
                    flat[column] = json.dumps(
                        value if value else ({} if column == "specs" else []),
                        ensure_ascii=False,
                    )
                if csv_single_line:
                    flat = {
                        k: _one_line(v) if isinstance(v, str) else v
                        for k, v in flat.items()
                    }
                writer.writerow(flat)
        written.append(path)

    if "parquet" in formats:
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
        except ImportError:
            log.warning("parquet requested but pyarrow is not installed — skipped")
        else:
            table = pa.Table.from_pylist(rows)
            path = cfg.storage.export_dir / f"{stem}.parquet"
            pq.write_table(table, path)
            written.append(path)

    for path in written:
        log.info(
            "exported %d rows -> %s (%d bytes)", len(rows), path, path.stat().st_size
        )
    return written


FIELD_NOTES: tuple[tuple[str, str], ...] = (
    ("product_id", "Kunci utama. Sama dengan nama folder di images/."),
    ("title", "Judul dari penjual, apa adanya."),
    ("price", "Rupiah, integer. Harga saat diambil — bisa promo."),
    ("original_price", "Harga coret. Kosong kalau tidak sedang diskon."),
    ("discount_pct", "Diturunkan dari harga coret, atau dari label ribbon."),
    ("rating", "0-5. Kosong kalau produk belum punya ulasan."),
    ("review_count", "Hanya ada dari halaman detail produk."),
    ("sold_count", "Angka pasti dari halaman detail; dari pencarian hanya ember."),
    ("category_path", "Breadcrumb, dari umum ke spesifik."),
    ("description", "PROSA SAJA. Kosong kalau penjual menulisnya sebagai gambar."),
    ("specs", "Pasangan spesifikasi terstruktur. Terisi walau description kosong."),
    ("image_urls", "URL CDN tanpa tanda tangan — tidak kedaluwarsa."),
    ("local_image_paths", "Relatif terhadap root project, kosong kalau belum diunduh."),
    ("source_keyword", "Kata kunci pencarian yang memunculkan produk ini."),
    ("url", "Halaman sumber di Tokopedia. Dipertahankan agar tiap baris terlacak."),
    ("scraped_at", "ISO-8601 UTC."),
    ("pdp_fetched", "false = halaman detail belum dikunjungi, BUKAN berarti kosong."),
)


def write_dataset_card(
    cfg: Config,
    storage: Storage,
    path: Path | None = None,
    columns: Sequence[str] | None = None,
) -> Path:
    """Write DATASET.md: what this is, where it came from, what to watch out for.

    Numbers are read from the database at write time. A dataset handed to
    someone else without this is a pile of JSON they have to reverse-engineer.
    """
    from datetime import datetime, timezone

    stats = storage.stats()
    conn = storage.conn
    q = lambda sql: conn.execute(sql).fetchone()  # noqa: E731

    lengths = [
        r[0]
        for r in conn.execute(
            "SELECT LENGTH(description) FROM products "
            "WHERE description IS NOT NULL AND TRIM(description) <> '' "
            "ORDER BY LENGTH(description)"
        )
    ]
    median = lengths[len(lengths) // 2] if lengths else 0
    shops = q("SELECT COUNT(DISTINCT shop_id) FROM products")[0]
    keywords = q("SELECT COUNT(DISTINCT source_keyword) FROM products")[0]
    first, last = q("SELECT MIN(scraped_at), MAX(scraped_at) FROM products")
    priced = q("SELECT COUNT(*) FROM products WHERE price > 0")[0]

    path = path or cfg.storage.export_dir / "DATASET.md"
    # Document only the fields actually exported. Listing columns that are not
    # in the file sends the reader hunting for something that is not there.
    wanted = set(columns) if columns else {name for name, _ in FIELD_NOTES}
    fields = "\n".join(
        f"| `{name}` | {note} |" for name, note in FIELD_NOTES if name in wanted
    )

    # Without pdp_fetched the reader cannot tell "not visited" from "seller
    # wrote none" — but a ready-only export has no unvisited rows to confuse
    # them with, so the ambiguity that note exists to warn about is gone.
    empty_desc_note = (
        """1. **`description` kosong punya dua arti.** Cek `pdp_fetched`. `false` berarti
   belum diambil; `true` dengan description kosong berarti penjualnya memang
   menulis deskripsi sebagai gambar. Filter latih yang benar:
   `pdp_fetched == true and description`."""
        if "pdp_fetched" in wanted
        else """1. **`description` kosong berarti penjualnya menulis deskripsi sebagai gambar.**
   Setiap baris di file ini halaman detailnya sudah diambil, jadi kosong bukan
   berarti belum terkumpul. Buang baris itu untuk melatih model teks."""
    )

    path.write_text(
        f"""# Dataset produk Tokopedia

Dikumpulkan untuk riset non-komersial: melatih model auto-description dan
rekomendasi harga untuk penjual UMKM.

Dibuat {datetime.now(timezone.utc).strftime('%d %B %Y %H:%M UTC')}.

## Isi

| | |
|---|---|
| Produk | {stats['products']:,} |
| Sudah diambil halaman detailnya | {stats['pdp_fetched']:,} |
| Punya deskripsi teks | {stats['with_description']:,} |
| Deskripsi berupa gambar (specs saja) | {stats['specs_no_description']:,} |
| Punya harga | {priced:,} |
| Gambar terunduh | {stats['with_local_images']:,} produk |
| Toko berbeda | {shops:,} |
| Kata kunci | {keywords} |
| Median panjang deskripsi | {median:,} karakter |
| Tanggal pengambilan daftar produk | {(first or '')[:10]} s.d. {(last or '')[:10]} |

## Field

| Field | Catatan |
|---|---|
{fields}

## Yang harus diperhatikan sebelum melatih model

{empty_desc_note}

2. **Ada harga yang tidak masuk akal.** Ditemukan kaos seharga Rp1,99 miliar —
   penjual iseng atau salah ketik nol. Response aslinya memang berisi angka itu.
   Saring per kategori sebelum melatih model harga.

3. **Ada judul duplikat.** Produk yang di-listing ulang dengan `product_id`
   berbeda. Pisahkan train/test berdasarkan judul atau toko, bukan acak, kalau
   tidak contoh yang sama bocor ke kedua sisi.

4. **`price` adalah potret saat diambil.** Banyak yang sedang promo. Bandingkan
   dengan `original_price` kalau butuh harga normal.

5. **CSV dan JSONL tidak identik isinya.** Kalau kedua-duanya ada, `.jsonl`
   menyimpan deskripsi persis seperti yang ditulis penjual — lengkap dengan
   ganti baris antar paragraf. `.csv` yang diekspor dengan `--csv-single-line`
   meratakan ganti baris itu jadi spasi supaya satu produk = satu baris berkas,
   karena ganti baris di dalam tanda kutip (walau sah menurut standar CSV)
   bikin berkasnya terbaca rusak oleh tool yang membaca per baris. Untuk
   melatih model teks, pakai `.jsonl`.

## Asal dan batasan pemakaian

Diambil dari halaman publik Tokopedia. Kolom `url` menyimpan sumber tiap baris.

Deskripsi dan gambar adalah karya berhak cipta penjual masing-masing. Dataset
ini untuk riset non-komersial dan **tidak untuk diredistribusikan publik**.
Ketentuan layanan Tokopedia secara umum melarang pengumpulan data otomatis.
""",
        encoding="utf-8",
    )
    log.info("dataset card -> %s", path)
    return path


if __name__ == "__main__":  # pragma: no cover - manual smoke check
    import tempfile

    from .fetchers.base import FetchResult

    logging.basicConfig(level=logging.CRITICAL)

    def make_payload(keyword: str, page: int, count: int, has_more: bool) -> dict:
        return {
            "data": {
                "searchProductV5": {
                    "header": {
                        "totalData": 500,
                        "additionalParams": (
                            f"has_more={'true' if has_more else 'false'}"
                        ),
                    },
                    "data": {
                        "products": [
                            {
                                # Keyword in the id: two keywords returning the
                                # same product_id would (correctly) dedupe, which
                                # would make this fixture test the wrong thing.
                                "id": f"{keyword}-{page}-{i}",
                                "name": f"{keyword} {page}-{i}",
                                "url": f"https://www.tokopedia.com/t/{keyword}-{page}-{i}",
                                "price": {"number": 10_000 + i},
                            }
                            for i in range(count)
                        ]
                    },
                }
            }
        }

    class FakeFetcher(Fetcher):
        name = "fake"

        def __init__(self, cfg: Config, fail_on: tuple[str, int] | None = None) -> None:
            self.cfg = cfg
            self.fail_on = fail_on
            self.search_calls: list[tuple[str, int]] = []
            self.pdp_calls: list[str] = []

        def search(self, keyword: str, page: int) -> FetchResult:
            self.search_calls.append((keyword, page))
            if self.fail_on == (keyword, page):
                raise FetchError("boom", status=500)
            return FetchResult(
                payload=make_payload(keyword, page, 2, page < 3),
                fetcher=self.name,
                url="x",
            )

        def fetch_pdp(self, product_url: str) -> FetchResult:
            self.pdp_calls.append(product_url)
            return FetchResult(
                payload={
                    "data": {
                        "pdpMainInfo": {
                            "data": {
                                "basicInfo": {
                                    "stats": {"rating": 4.5, "countReview": "12"},
                                    "txStats": {"countSold": "34"},
                                }
                            },
                            "components": [
                                {
                                    "name": "product_detail",
                                    "data": [
                                        {
                                            "productDetailDescription": {
                                                "content": "Deskripsi panjang produk"
                                            }
                                        }
                                    ],
                                }
                            ],
                        }
                    }
                },
                fetcher=self.name,
                url=product_url,
            )

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        cfg = Config(keywords=["alpha", "beta"])
        cfg.storage.db_path = root / "products.db"
        cfg.storage.export_dir = root / "exports"
        cfg.search.max_pages_per_keyword = 5
        cfg.search.target_per_keyword = 0  # let has_more decide

        # --- stage 1, clean run ------------------------------------------
        with Storage(cfg.storage.db_path) as store:
            fetcher = FakeFetcher(cfg)
            stats = run_search(cfg, store, fetcher)
            assert stats.pages == 6, stats.pages  # 3 pages x 2 keywords
            assert stats.products == 12, stats.products
            assert store.stats()["products"] == 12
            assert store.is_keyword_done("alpha") and store.is_keyword_done("beta")

            # --- resume: a completed keyword costs zero requests ----------
            again = FakeFetcher(cfg)
            stats2 = run_search(cfg, store, again)
            assert again.search_calls == [], "finished keywords must not be refetched"
            assert stats2.keywords_skipped == 2

        # --- stage 1 interrupted mid-keyword -----------------------------
        cfg.storage.db_path = root / "resume.db"
        with Storage(cfg.storage.db_path) as store:
            broken = FakeFetcher(cfg, fail_on=("alpha", 2))
            run_search(cfg, store, broken, keywords=["alpha"])
            assert store.keyword_progress("alpha")["last_page"] == 1
            assert not store.is_keyword_done("alpha")

            healed = FakeFetcher(cfg)
            run_search(cfg, store, healed, keywords=["alpha"])
            assert healed.search_calls[0] == ("alpha", 2), healed.search_calls[:1]
            assert store.is_keyword_done("alpha")

            # --- stage 2 --------------------------------------------------
            pdp_fetcher = FakeFetcher(cfg)
            estats = run_enrich(cfg, store, pdp_fetcher)
            assert estats.products == store.stats()["pdp_fetched"]
            assert store.stats()["pending_pdp"] == 0
            enriched = next(iter(store.iter_products()))
            assert enriched.description == "Deskripsi panjang produk"
            assert enriched.review_count == 12 and enriched.sold_count == 34

            # enrich again: nothing pending, so nothing fetched
            second = FakeFetcher(cfg)
            run_enrich(cfg, store, second)
            assert second.pdp_calls == [], "enriched products must not be refetched"

            # --- export ---------------------------------------------------
            paths = export_dataset(cfg, store, ("jsonl", "csv"))
            assert len(paths) == 2
            jsonl = cfg.storage.export_dir / "products.jsonl"
            lines = jsonl.read_text("utf-8").strip().split("\n")
            assert len(lines) == store.stats()["products"]
            first_row = json.loads(lines[0])
            assert first_row["product_id"] and first_row["description"]
            assert isinstance(first_row["category_path"], list)

            with (cfg.storage.export_dir / "products.csv").open(encoding="utf-8") as fh:
                csv_rows = list(csv.DictReader(fh))
            assert len(csv_rows) == len(lines)
            assert json.loads(csv_rows[0]["image_urls"]) == []

    print("pipeline.py self-check OK")
