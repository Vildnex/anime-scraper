"""Disk-based caching for HTTP responses from nyaa.si."""

import hashlib
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Cache location following XDG conventions
CACHE_DIR = Path.home() / ".cache" / "anime-scraper"
METADATA_FILE = CACHE_DIR / "metadata.json"
CACHE_SUBDIR = CACHE_DIR / "html_cache"

# Cache expiration time
CACHE_TTL = timedelta(hours=24)


def _hash_url(url: str) -> str:
    """Generate a SHA-256 hash of a URL for use as a filename."""
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def _ensure_cache_dirs() -> None:
    """Create cache directories if they don't exist."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_SUBDIR.mkdir(parents=True, exist_ok=True)


def _read_metadata() -> dict[str, Any]:
    """Read cache metadata from disk."""
    try:
        if METADATA_FILE.exists():
            return json.loads(METADATA_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Failed to read cache metadata: {e}")
    return {}


def _write_metadata(metadata: dict[str, Any]) -> None:
    """Write cache metadata to disk atomically."""
    try:
        _ensure_cache_dirs()
        # Write to temp file first, then rename for atomicity
        temp_file = METADATA_FILE.with_suffix(".tmp")
        temp_file.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        temp_file.rename(METADATA_FILE)
    except OSError as e:
        logger.warning(f"Failed to write cache metadata: {e}")


def _clear_html_cache() -> None:
    """Remove all cached HTML files."""
    try:
        if CACHE_SUBDIR.exists():
            for cache_file in CACHE_SUBDIR.glob("*.html"):
                cache_file.unlink()
    except OSError as e:
        logger.warning(f"Failed to clear cache: {e}")


def _is_cache_expired(timestamp_str: str | None) -> bool:
    """Check if the cache timestamp indicates expiration."""
    if not timestamp_str:
        return True
    try:
        timestamp = datetime.fromisoformat(timestamp_str)
        return datetime.now() - timestamp > CACHE_TTL
    except ValueError:
        return True


class CachedHTTPClient:
    """HTTP client wrapper with transparent disk-based caching.

    The cache is invalidated when the search query changes. Only 200 OK
    responses are cached. Cache entries expire after 24 hours.

    Usage:
        with CachedHTTPClient(current_query="naruto") as client:
            response = client.get("https://nyaa.si/view/123")
    """

    def __init__(
        self,
        current_query: str | None,
        timeout: float = 30.0,
        follow_redirects: bool = True,
    ) -> None:
        """Initialize the cached HTTP client.

        Args:
            current_query: The current search query. If different from the
                cached query, the cache will be invalidated. Pass None to
                skip query-based invalidation (e.g., for metadata fetches).
            timeout: HTTP request timeout in seconds.
            follow_redirects: Whether to follow HTTP redirects.
        """
        self._timeout = timeout
        self._follow_redirects = follow_redirects
        self._client: httpx.Client | None = None
        self._current_query = current_query

        self._initialize_cache()

    def _initialize_cache(self) -> None:
        """Initialize cache, invalidating if query changed or expired."""
        _ensure_cache_dirs()

        metadata = _read_metadata()
        cached_query = metadata.get("query")
        cached_timestamp = metadata.get("timestamp")

        should_invalidate = False

        # Invalidate if query changed (only if current_query is provided)
        if self._current_query is not None and cached_query != self._current_query:
            logger.info(f"Query changed from '{cached_query}' to '{self._current_query}', clearing cache")
            should_invalidate = True

        # Invalidate if cache expired
        if _is_cache_expired(cached_timestamp):
            logger.info("Cache expired, clearing")
            should_invalidate = True

        if should_invalidate:
            _clear_html_cache()
            # Update metadata with new query and timestamp
            new_metadata = {
                "query": self._current_query,
                "timestamp": datetime.now().isoformat(),
            }
            _write_metadata(new_metadata)

    def _get_cache_path(self, url: str) -> Path:
        """Get the cache file path for a URL."""
        return CACHE_SUBDIR / f"{_hash_url(url)}.html"

    def _read_from_cache(self, url: str) -> str | None:
        """Try to read cached content for a URL."""
        cache_path = self._get_cache_path(url)
        try:
            if cache_path.exists():
                content = cache_path.read_text(encoding="utf-8")
                logger.debug(f"Cache hit for {url}")
                return content
        except OSError as e:
            logger.warning(f"Failed to read cache for {url}: {e}")
        return None

    def _write_to_cache(self, url: str, content: str) -> None:
        """Write content to cache atomically."""
        cache_path = self._get_cache_path(url)
        try:
            _ensure_cache_dirs()
            # Write atomically
            temp_path = cache_path.with_suffix(".tmp")
            temp_path.write_text(content, encoding="utf-8")
            temp_path.rename(cache_path)
            logger.debug(f"Cached {url}")
        except OSError as e:
            logger.warning(f"Failed to write cache for {url}: {e}")

    def get(self, url: str) -> httpx.Response:
        """Fetch a URL, using cache if available.

        Args:
            url: The URL to fetch.

        Returns:
            An httpx.Response object. For cached responses, a mock response
            is created with status_code=200 and the cached text.
        """
        if self._client is None:
            raise RuntimeError("Client not initialized. Use as context manager.")

        # Try cache first
        cached_content = self._read_from_cache(url)
        if cached_content is not None:
            # Create a mock response for cached content
            return _CachedResponse(cached_content)

        # Cache miss - fetch from network
        logger.debug(f"Cache miss for {url}, fetching from network")
        response = self._client.get(url)

        # Only cache successful responses
        if response.status_code == 200:
            self._write_to_cache(url, response.text)

        return response

    def __enter__(self) -> "CachedHTTPClient":
        """Enter context manager, creating the underlying HTTP client."""
        self._client = httpx.Client(
            timeout=self._timeout,
            follow_redirects=self._follow_redirects,
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context manager, closing the HTTP client."""
        if self._client is not None:
            self._client.close()
            self._client = None


class _CachedResponse:
    """Mock httpx.Response for cached content.

    Provides the minimal interface needed by the scraper/metadata modules.
    """

    def __init__(self, text: str) -> None:
        self._text = text
        self.status_code = 200

    @property
    def text(self) -> str:
        return self._text

    def raise_for_status(self) -> None:
        """No-op since cached responses are always successful."""
        pass
