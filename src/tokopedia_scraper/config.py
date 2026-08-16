"""Config loading: config.yaml + .env, validated with Pydantic.

Secrets never live in config.yaml. Everything credential-shaped is read from the
environment via `env_secret()`, which gives a readable error instead of a
traceback when a key is missing.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Literal

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator

log = logging.getLogger(__name__)

ENV_PREFIX = "TOKOSCRAPE_"

FetcherName = Literal["graphql", "playwright", "managed", "auto"]


class MissingCredential(RuntimeError):
    """A backend was selected but its credentials are not in the environment."""


def env_secret(name: str, *, required_by: str | None = None) -> str | None:
    """Read a secret from the environment.

    `required_by` names the backend that needs it; when set, a missing or blank
    value raises MissingCredential with an actionable message rather than
    letting the request fail later with a confusing 401.
    """
    value = os.getenv(name, "").strip()
    if value:
        return value
    if required_by:
        raise MissingCredential(
            f"{required_by} needs {name}, which is unset or empty.\n"
            f"Add it to .env (see .env.example), then re-run. "
            f"No credentials are read from config.yaml by design."
        )
    return None


class SearchConfig(BaseModel):
    max_pages_per_keyword: int = 20
    # 24 is what searchProductV5 actually returns per page. A capture-derived
    # value in gql_capture.yaml overrides this; this is only the fallback.
    rows_per_page: int = 24
    target_per_keyword: int = 400


class RateLimitConfig(BaseModel):
    min_delay: float = 2.0
    max_delay: float = 5.0
    concurrency: int = 1
    max_retries: int = 5
    backoff_base: float = 2.0
    backoff_max: float = 120.0
    circuit_breaker_threshold: int = 10

    @field_validator("concurrency")
    @classmethod
    def _cap_concurrency(cls, v: int) -> int:
        if v < 1:
            raise ValueError("concurrency must be >= 1")
        if v > 3:
            raise ValueError(
                f"concurrency={v} exceeds the hard cap of 3. Tokopedia is a "
                f"live production site; parallel scraping at this level is "
                f"neither polite nor stealthy."
            )
        if v > 1:
            log.warning(
                "concurrency=%d — above the default of 1. Higher parallelism "
                "raises block risk; see README.",
                v,
            )
        return v

    @field_validator("max_delay")
    @classmethod
    def _delay_order(cls, v: float, info: Any) -> float:
        min_delay = info.data.get("min_delay")
        if min_delay is not None and v < min_delay:
            raise ValueError(f"max_delay ({v}) must be >= min_delay ({min_delay})")
        return v


class AutoConfig(BaseModel):
    fallback_after_failures: int = 5


class GraphQLConfig(BaseModel):
    capture_file: Path = Path("config/gql_capture.yaml")
    impersonate: str = "chrome"
    timeout: int = 30


class PlaywrightConfig(BaseModel):
    # Headless is refused by Tokopedia at the HTTP/2 level — measured, on every
    # page, with no other options set. See the note in config.yaml.
    headless: bool = False
    persistent_profile: bool = True
    profile_dir: Path = Path("data/browser_profile")
    block_resources: list[str] = Field(
        default_factory=lambda: ["font", "media", "stylesheet", "image"]
    )
    nav_timeout_ms: int = 30_000
    selector_timeout_ms: int = 15_000
    scroll_steps: int = 8
    scroll_pause_ms: int = 800


class ManagedConfig(BaseModel):
    provider: Literal["scrapingbee", "zenrows", "apify"] = "scrapingbee"
    render_js: bool = True
    timeout: int = 90


class ImagesConfig(BaseModel):
    enabled: bool = True
    concurrency: int = 4
    timeout: int = 30
    max_per_product: int = 8
    dir: Path = Path("data/images")


class StorageConfig(BaseModel):
    db_path: Path = Path("data/products.db")
    export_dir: Path = Path("data/exports")


class LoggingConfig(BaseModel):
    level: str = "INFO"
    file: Path = Path("logs/scraper.log")


# Path fields rewritten to absolute at load time, so callers never have to care
# what the working directory is (notebooks run from notebooks/).
_PATH_FIELDS: tuple[tuple[str, str], ...] = (
    ("graphql", "capture_file"),
    ("playwright", "profile_dir"),
    ("images", "dir"),
    ("storage", "db_path"),
    ("storage", "export_dir"),
    ("logging", "file"),
)


class Config(BaseModel):
    fetcher: FetcherName = "graphql"
    keywords: list[str] = Field(default_factory=list)
    search: SearchConfig = Field(default_factory=SearchConfig)
    rate_limit: RateLimitConfig = Field(default_factory=RateLimitConfig)
    auto: AutoConfig = Field(default_factory=AutoConfig)
    graphql: GraphQLConfig = Field(default_factory=GraphQLConfig)
    playwright: PlaywrightConfig = Field(default_factory=PlaywrightConfig)
    managed: ManagedConfig = Field(default_factory=ManagedConfig)
    images: ImagesConfig = Field(default_factory=ImagesConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    proxy_url: str | None = None

    # Directory config.yaml lives in; all relative paths resolve against it.
    root: Path = Field(default_factory=Path.cwd, exclude=True)

    @classmethod
    def load(cls, path: str | Path = "config.yaml") -> "Config":
        path = Path(path).resolve()
        if not path.is_file():
            raise FileNotFoundError(
                f"Config not found: {path}. Copy the shipped config.yaml or pass "
                f"--config <path>."
            )
        root = path.parent

        # .env sits next to config.yaml. Real env vars win over the file so that
        # CI and one-off shell overrides behave the way people expect.
        load_dotenv(root / ".env", override=False)

        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(raw, dict):
            raise ValueError(f"{path} must contain a YAML mapping at the top level")

        for applied in _apply_env_overrides(raw):
            log.info("config override from env: %s", applied)

        cfg = cls.model_validate({**raw, "root": root})

        for section, field in _PATH_FIELDS:
            node = getattr(cfg, section)
            value = getattr(node, field)
            if not value.is_absolute():
                setattr(node, field, (root / value).resolve())

        # proxy_url is optional and may legitimately only exist in .env.
        if cfg.proxy_url is None:
            cfg.proxy_url = env_secret("PROXY_URL")

        return cfg

    def ensure_dirs(self) -> None:
        """Create the directories the pipeline writes into. Safe to re-run."""
        for d in (
            self.storage.db_path.parent,
            self.storage.export_dir,
            self.images.dir,
            self.logging.file.parent,
            self.graphql.capture_file.parent,
        ):
            d.mkdir(parents=True, exist_ok=True)


def _apply_env_overrides(raw: dict[str, Any]) -> list[str]:
    """Overlay TOKOSCRAPE_<SECTION>__<KEY> env vars onto the raw config dict.

    Values stay strings; Pydantic coerces them during validation. Returns the
    names of the env vars that were applied, for logging.
    """
    applied: list[str] = []
    for env_key, value in sorted(os.environ.items()):
        if not env_key.startswith(ENV_PREFIX):
            continue
        parts = env_key[len(ENV_PREFIX) :].lower().split("__")
        node: Any = raw
        for part in parts[:-1]:
            node = node.setdefault(part, {})
            if not isinstance(node, dict):
                log.warning(
                    "ignoring %s: %r is a scalar in config.yaml, not a section",
                    env_key,
                    part,
                )
                node = None
                break
        if isinstance(node, dict):
            node[parts[-1]] = value
            applied.append(env_key)
    return applied


if __name__ == "__main__":  # pragma: no cover - manual smoke check
    import tempfile

    logging.basicConfig(level=logging.INFO)

    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "config.yaml"
        p.write_text(
            "fetcher: graphql\n"
            "keywords: [air fryer]\n"
            "rate_limit: {min_delay: 1.0, max_delay: 2.0}\n"
            "storage: {db_path: data/products.db}\n",
            encoding="utf-8",
        )

        c = Config.load(p)
        assert c.fetcher == "graphql"
        assert c.keywords == ["air fryer"]
        assert c.storage.db_path.is_absolute(), "relative paths must be resolved"
        assert c.storage.db_path.parent.parent == Path(tmp).resolve()
        assert c.search.rows_per_page == 24, "defaults must fill in"

        os.environ[f"{ENV_PREFIX}RATE_LIMIT__MIN_DELAY"] = "1.5"
        os.environ[f"{ENV_PREFIX}FETCHER"] = "playwright"
        c2 = Config.load(p)
        assert c2.rate_limit.min_delay == 1.5, "nested env override failed"
        assert c2.fetcher == "playwright", "top-level env override failed"

        # min_delay > max_delay must be rejected, not silently accepted.
        os.environ[f"{ENV_PREFIX}RATE_LIMIT__MIN_DELAY"] = "9.0"
        try:
            Config.load(p)
        except Exception as exc:
            assert "max_delay" in str(exc), exc
        else:
            raise AssertionError("min_delay > max_delay not caught")
        del os.environ[f"{ENV_PREFIX}RATE_LIMIT__MIN_DELAY"]
        del os.environ[f"{ENV_PREFIX}FETCHER"]

        try:
            Config.model_validate({"rate_limit": {"concurrency": 9}})
        except Exception as exc:
            assert "hard cap" in str(exc), exc
        else:
            raise AssertionError("concurrency cap not enforced")

        try:
            env_secret("DEFINITELY_NOT_SET_12345", required_by="ManagedFetcher")
        except MissingCredential as exc:
            assert ".env" in str(exc)
        else:
            raise AssertionError("missing credential did not raise")

    print("config.py self-check OK")
