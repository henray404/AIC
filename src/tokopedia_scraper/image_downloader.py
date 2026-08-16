"""Image downloading. Optional, bounded, and never fatal.

A product whose images fail to download still keeps its text. Failures are
logged and skipped, because a dataset of 30 000 products will always contain a
few dead links, and that is not a reason to stop the run.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlsplit

import requests

from .config import Config
from .models import Product
from .ratelimit import random_user_agent

log = logging.getLogger(__name__)

# Extensions we are willing to write. Anything else is stored as .jpg, since
# Tokopedia serves JPEG under a variety of paths.
KNOWN_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

# Tokopedia's "no image" placeholder is ~4 KB. Real product photos are tens of
# KB and up, so anything this small is almost certainly that placeholder.
MIN_IMAGE_BYTES = 6_000


def image_filename(product_id: str, url: str, index: int) -> str:
    """`<product_id>_<NN>.<ext>` — the file says which product it belongs to.

    A bare content hash makes ownership invisible the moment a file leaves its
    folder, which is what happens as soon as anyone flattens the directory or
    shares a subset. The index preserves gallery order and keeps the name
    deterministic, so a re-run still recognises what is already on disk.
    """
    suffix = Path(urlsplit(url).path).suffix.lower()
    if suffix not in KNOWN_EXTENSIONS:
        suffix = ".jpg"
    return f"{product_id}_{index:02d}{suffix}"


def _download_one(
    session: requests.Session, url: str, destination: Path, timeout: int
) -> Path | None:
    if destination.exists() and destination.stat().st_size >= MIN_IMAGE_BYTES:
        return destination

    try:
        response = session.get(url, timeout=timeout, stream=True)
        if response.status_code != 200:
            log.warning("image %s -> HTTP %s", url[:80], response.status_code)
            return None

        content = response.content
        if len(content) < MIN_IMAGE_BYTES:
            log.warning(
                "image %s is only %d bytes — treated as a placeholder, not saved",
                url[:80],
                len(content),
            )
            return None

        # Write under a temporary name first: an interrupted download must not
        # leave a truncated file that the next run accepts as complete.
        temporary = destination.with_suffix(destination.suffix + ".part")
        temporary.write_bytes(content)
        temporary.replace(destination)
        return destination
    except Exception as exc:
        log.warning("image %s failed: %s: %s", url[:80], type(exc).__name__, exc)
        return None


def download_for_product(cfg: Config, product: Product) -> list[str]:
    """Download one product's images. Returns paths relative to the project root.

    Existing files are kept, so this is safe to re-run and cheap to resume.
    """
    urls = list(product.image_urls)[: cfg.images.max_per_product]
    if not urls:
        return []

    target_dir = cfg.images.dir / product.product_id
    target_dir.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers["user-agent"] = random_user_agent()
    if cfg.proxy_url:
        session.proxies = {"http": cfg.proxy_url, "https": cfg.proxy_url}

    try:
        with ThreadPoolExecutor(max_workers=max(1, cfg.images.concurrency)) as pool:
            results = list(
                pool.map(
                    lambda pair: _download_one(
                        session,
                        pair[1],
                        target_dir
                        / image_filename(product.product_id, pair[1], pair[0]),
                        cfg.images.timeout,
                    ),
                    enumerate(urls, start=1),
                )
            )
    finally:
        session.close()

    saved = [path for path in results if path is not None]
    if len(saved) < len(urls):
        log.info(
            "product %s: %d/%d images saved", product.product_id, len(saved), len(urls)
        )

    relative: list[str] = []
    for path in saved:
        try:
            relative.append(path.relative_to(cfg.root).as_posix())
        except ValueError:
            # Images configured outside the project tree: keep the absolute path.
            relative.append(path.as_posix())
    return relative


if __name__ == "__main__":  # pragma: no cover - manual smoke check
    import tempfile

    logging.basicConfig(level=logging.CRITICAL)

    # The filename must name its owner, keep gallery order, and stay stable so
    # a re-run skips what is already downloaded.
    base = "https://images.tokopedia.net/img/cache/1200/aphluv/1997/1/1/abc~.jpeg"
    assert image_filename("100359309456", base, 1) == "100359309456_01.jpeg"
    assert image_filename("100359309456", base, 12) == "100359309456_12.jpeg"
    assert image_filename("7", "https://x/y/z", 3) == "7_03.jpg", "unknown ext -> .jpg"

    # A signature on the URL must not change the name, or every run would
    # re-download the same picture under a new one.
    assert image_filename("1", base, 1) == image_filename(
        "1", base + "?x-expires=1&x-signature=z", 1
    )
    # Different products never collide, even on the same image.
    assert image_filename("1", base, 1) != image_filename("2", base, 1)
    # Sorting the names restores gallery order.
    names = [image_filename("1", base, i) for i in (3, 1, 10, 2)]
    assert sorted(names) == [image_filename("1", base, i) for i in (1, 2, 3, 10)]

    class FakeResponse:
        def __init__(self, status: int, body: bytes) -> None:
            self.status_code = status
            self.content = body

    class FakeSession:
        def __init__(self, mapping: dict[str, FakeResponse]) -> None:
            self.mapping = mapping
            self.headers: dict[str, str] = {}
            self.calls: list[str] = []

        def get(self, url: str, timeout: int = 0, stream: bool = False) -> FakeResponse:
            self.calls.append(url)
            return self.mapping.get(url, FakeResponse(404, b""))

        def close(self) -> None:
            pass

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        big = b"x" * 50_000

        session = FakeSession(
            {
                "https://img/a.jpg": FakeResponse(200, big),
                "https://img/small.jpg": FakeResponse(200, b"x" * 100),
                "https://img/gone.jpg": FakeResponse(404, b""),
            }
        )

        good = _download_one(session, "https://img/a.jpg", root / "a.jpg", 5)
        assert good is not None and good.read_bytes() == big
        assert not list(root.glob("*.part")), "temp file left behind"

        # Re-download is skipped once the file is present and big enough.
        session.calls.clear()
        again = _download_one(session, "https://img/a.jpg", root / "a.jpg", 5)
        assert again is not None and session.calls == [], "existing file refetched"

        assert _download_one(session, "https://img/small.jpg", root / "s.jpg", 5) is None
        assert not (root / "s.jpg").exists(), "placeholder image was saved"
        assert _download_one(session, "https://img/gone.jpg", root / "g.jpg", 5) is None

        # A truncated leftover must be replaced, not accepted.
        stub = root / "stub.jpg"
        stub.write_bytes(b"x" * 10)
        fixed = _download_one(session, "https://img/a.jpg", stub, 5)
        assert fixed is not None and stub.stat().st_size == len(big)

    print("image_downloader.py self-check OK")
