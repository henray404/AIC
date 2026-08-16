"""Swappable data-acquisition backends."""

from .base import AutoFetcher, Fetcher, FetchResult, get_fetcher

__all__ = ["AutoFetcher", "Fetcher", "FetchResult", "get_fetcher"]
