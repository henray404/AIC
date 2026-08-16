"""Logging: rich-formatted stdout plus a rotating plain-text file."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler

FILE_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

console = Console(stderr=True)

_configured = False


def setup_logging(
    level: str = "INFO",
    log_file: Path | str | None = "logs/scraper.log",
    *,
    force: bool = False,
) -> logging.Logger:
    """Configure root logging. Idempotent — safe to call from every notebook cell.

    The file handler always records DEBUG regardless of `level`, so a run that
    looked fine on screen can still be autopsied afterwards.
    """
    global _configured
    root = logging.getLogger()

    if _configured and not force:
        return root

    for handler in root.handlers[:]:
        root.removeHandler(handler)
        handler.close()

    root.setLevel(logging.DEBUG)

    stdout_handler = RichHandler(
        console=console,
        rich_tracebacks=True,
        show_path=False,
        markup=False,
    )
    stdout_handler.setLevel(getattr(logging, level.upper(), logging.INFO))
    stdout_handler.setFormatter(logging.Formatter("%(message)s", datefmt="[%X]"))
    root.addHandler(stdout_handler)

    if log_file:
        path = Path(log_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            path, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(FILE_FORMAT, datefmt=DATE_FORMAT))
        root.addHandler(file_handler)

    # These libraries log every connection at DEBUG; the file handler would
    # drown in it.
    for noisy in ("urllib3", "asyncio", "matplotlib", "PIL"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _configured = True
    return root


if __name__ == "__main__":  # pragma: no cover - manual smoke check
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "logs" / "scraper.log"
        setup_logging("WARNING", target, force=True)

        log = logging.getLogger("tokopedia_scraper.selfcheck")
        log.debug("debug line, below the stdout threshold")
        log.warning("warning line")

        for h in logging.getLogger().handlers:
            h.flush()

        text = target.read_text(encoding="utf-8")

        # Windows refuses to delete a file with an open handle, so release the
        # log before the TemporaryDirectory tries to clean up.
        for h in logging.getLogger().handlers[:]:
            logging.getLogger().removeHandler(h)
            h.close()

        assert "debug line" in text, "file handler must capture DEBUG regardless"
        assert "WARNING" in text and "tokopedia_scraper.selfcheck" in text
        assert text.startswith("20"), f"timestamp missing: {text[:40]!r}"

    print("logging_setup.py self-check OK")
