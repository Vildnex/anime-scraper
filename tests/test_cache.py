"""Tests for the cache module."""

import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

import httpx
import pytest
import respx

from anime_scraper import cache
from anime_scraper.cache import (
    CachedHTTPClient,
    _hash_url,
    _is_cache_expired,
    CACHE_TTL,
)


# ============================================================================
# Unit Tests - URL Hashing
# ============================================================================


@pytest.mark.unit
class TestUrlHashing:
    """Tests for URL hashing functionality."""

    def test_hash_url_consistency(self):
        """Same URL should always produce the same hash."""
        url = "https://nyaa.si/view/123456"
        hash1 = _hash_url(url)
        hash2 = _hash_url(url)
        assert hash1 == hash2

    def test_hash_url_different_urls(self):
        """Different URLs should produce different hashes."""
        hash1 = _hash_url("https://nyaa.si/view/123")
        hash2 = _hash_url("https://nyaa.si/view/456")
        assert hash1 != hash2

    def test_hash_url_is_sha256(self):
        """Hash should be a valid SHA-256 hex string (64 characters)."""
        url_hash = _hash_url("https://example.com")
        assert len(url_hash) == 64
        assert all(c in "0123456789abcdef" for c in url_hash)


# ============================================================================
# Unit Tests - Cache Expiration
# ============================================================================


@pytest.mark.unit
class TestCacheExpiration:
    """Tests for cache expiration logic."""

    def test_expired_with_none(self):
        """None timestamp should be considered expired."""
        assert _is_cache_expired(None) is True

    def test_expired_with_invalid_string(self):
        """Invalid timestamp string should be considered expired."""
        assert _is_cache_expired("not-a-date") is True

    def test_expired_with_old_timestamp(self):
        """Timestamp older than CACHE_TTL should be expired."""
        old_time = datetime.now() - CACHE_TTL - timedelta(hours=1)
        assert _is_cache_expired(old_time.isoformat()) is True

    def test_not_expired_with_recent_timestamp(self):
        """Recent timestamp should not be expired."""
        recent_time = datetime.now() - timedelta(hours=1)
        assert _is_cache_expired(recent_time.isoformat()) is False


# ============================================================================
# Integration Tests - CachedHTTPClient
# ============================================================================


@pytest.mark.integration
class TestCachedHTTPClient:
    """Integration tests for the CachedHTTPClient class."""

    def test_cache_directory_creation(self, temp_cache_dir):
        """Cache directories should be created on initialization."""
        # Remove directories to test creation
        if cache.CACHE_SUBDIR.exists():
            cache.CACHE_SUBDIR.rmdir()

        with CachedHTTPClient(current_query="test") as client:
            pass

        assert cache.CACHE_DIR.exists()
        assert cache.CACHE_SUBDIR.exists()

    @respx.mock
    def test_cache_miss_fetches_from_network(self, temp_cache_dir):
        """Cache miss should fetch from network and cache the response."""
        test_url = "https://nyaa.si/view/123"
        test_html = "<html><body>Test content</body></html>"

        respx.get(test_url).mock(return_value=httpx.Response(200, text=test_html))

        with CachedHTTPClient(current_query="test") as client:
            response = client.get(test_url)
            assert response.text == test_html
            assert response.status_code == 200

        # Verify it was cached
        cache_path = cache.CACHE_SUBDIR / f"{_hash_url(test_url)}.html"
        assert cache_path.exists()
        assert cache_path.read_text() == test_html

    @respx.mock
    def test_cache_hit_no_network_request(self, temp_cache_dir):
        """Cache hit should return cached content without network request."""
        test_url = "https://nyaa.si/view/456"
        cached_html = "<html><body>Cached content</body></html>"

        # Pre-populate cache
        cache.CACHE_SUBDIR.mkdir(parents=True, exist_ok=True)
        cache_path = cache.CACHE_SUBDIR / f"{_hash_url(test_url)}.html"
        cache_path.write_text(cached_html)

        # Set up metadata to avoid cache invalidation
        metadata = {
            "query": "test",
            "timestamp": datetime.now().isoformat(),
        }
        cache.METADATA_FILE.write_text(json.dumps(metadata))

        # This route should NOT be called
        route = respx.get(test_url).mock(return_value=httpx.Response(200, text="Network content"))

        with CachedHTTPClient(current_query="test") as client:
            response = client.get(test_url)
            assert response.text == cached_html
            assert response.status_code == 200

        # Verify no network request was made
        assert not route.called

    def test_query_change_invalidates_cache(self, temp_cache_dir):
        """Changing query should clear existing cache files."""
        # Set up existing cache
        cache.CACHE_SUBDIR.mkdir(parents=True, exist_ok=True)
        old_cache_file = cache.CACHE_SUBDIR / "old_cache_file.html"
        old_cache_file.write_text("old content")

        # Set up metadata with different query
        metadata = {
            "query": "old_query",
            "timestamp": datetime.now().isoformat(),
        }
        cache.METADATA_FILE.write_text(json.dumps(metadata))

        # Initialize with new query
        with CachedHTTPClient(current_query="new_query") as client:
            pass

        # Old cache should be cleared
        assert not old_cache_file.exists()

        # Metadata should be updated
        new_metadata = json.loads(cache.METADATA_FILE.read_text())
        assert new_metadata["query"] == "new_query"

    def test_same_query_preserves_cache(self, temp_cache_dir):
        """Same query should preserve existing cache files."""
        # Set up existing cache
        cache.CACHE_SUBDIR.mkdir(parents=True, exist_ok=True)
        cache_file = cache.CACHE_SUBDIR / "preserved_cache.html"
        cache_file.write_text("preserved content")

        # Set up metadata with same query
        metadata = {
            "query": "same_query",
            "timestamp": datetime.now().isoformat(),
        }
        cache.METADATA_FILE.write_text(json.dumps(metadata))

        # Initialize with same query
        with CachedHTTPClient(current_query="same_query") as client:
            pass

        # Cache should still exist
        assert cache_file.exists()
        assert cache_file.read_text() == "preserved content"

    def test_expired_cache_invalidates(self, temp_cache_dir):
        """Expired cache should be cleared even with same query."""
        # Set up existing cache
        cache.CACHE_SUBDIR.mkdir(parents=True, exist_ok=True)
        cache_file = cache.CACHE_SUBDIR / "expired_cache.html"
        cache_file.write_text("expired content")

        # Set up metadata with old timestamp
        old_time = datetime.now() - CACHE_TTL - timedelta(hours=1)
        metadata = {
            "query": "test",
            "timestamp": old_time.isoformat(),
        }
        cache.METADATA_FILE.write_text(json.dumps(metadata))

        # Initialize - should clear expired cache
        with CachedHTTPClient(current_query="test") as client:
            pass

        # Expired cache should be cleared
        assert not cache_file.exists()

    def test_null_query_skips_query_invalidation(self, temp_cache_dir):
        """current_query=None should skip query-based invalidation."""
        # Set up existing cache
        cache.CACHE_SUBDIR.mkdir(parents=True, exist_ok=True)
        cache_file = cache.CACHE_SUBDIR / "any_cache.html"
        cache_file.write_text("any content")

        # Set up metadata with recent timestamp
        metadata = {
            "query": "some_query",
            "timestamp": datetime.now().isoformat(),
        }
        cache.METADATA_FILE.write_text(json.dumps(metadata))

        # Initialize with None query - should NOT invalidate
        with CachedHTTPClient(current_query=None) as client:
            pass

        # Cache should be preserved (query check skipped, timestamp still valid)
        assert cache_file.exists()

    @respx.mock
    def test_non_200_responses_not_cached(self, temp_cache_dir):
        """Non-200 responses should not be cached."""
        test_url = "https://nyaa.si/view/404"

        respx.get(test_url).mock(return_value=httpx.Response(404, text="Not found"))

        with CachedHTTPClient(current_query="test") as client:
            response = client.get(test_url)
            assert response.status_code == 404

        # Should not be cached
        cache_path = cache.CACHE_SUBDIR / f"{_hash_url(test_url)}.html"
        assert not cache_path.exists()

    def test_corrupt_metadata_handled_gracefully(self, temp_cache_dir):
        """Corrupt metadata.json should be handled without crashing."""
        cache.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache.METADATA_FILE.write_text("not valid json {{{")

        # Should not raise
        with CachedHTTPClient(current_query="test") as client:
            pass

        # Metadata should be recreated
        metadata = json.loads(cache.METADATA_FILE.read_text())
        assert metadata["query"] == "test"

    def test_corrupt_cache_file_handled_gracefully(self, temp_cache_dir):
        """Corrupt cache file read should fail gracefully."""
        cache.CACHE_SUBDIR.mkdir(parents=True, exist_ok=True)

        # Create a file that will fail to read (by making it a directory)
        bad_cache_path = cache.CACHE_SUBDIR / f"{_hash_url('https://example.com')}.html"
        bad_cache_path.mkdir()  # Directory, not file

        metadata = {
            "query": "test",
            "timestamp": datetime.now().isoformat(),
        }
        cache.METADATA_FILE.write_text(json.dumps(metadata))

        with CachedHTTPClient(current_query="test") as client:
            # Should return None from _read_from_cache (graceful failure)
            result = client._read_from_cache("https://example.com")
            assert result is None

    def test_context_manager_required(self, temp_cache_dir):
        """Using get() without context manager should raise error."""
        client = CachedHTTPClient(current_query="test")

        with pytest.raises(RuntimeError, match="Client not initialized"):
            client.get("https://example.com")

    @respx.mock
    def test_cached_response_interface(self, temp_cache_dir):
        """Cached response should have required interface (text, status_code, raise_for_status)."""
        test_url = "https://nyaa.si/view/789"
        test_html = "<html>content</html>"

        # Pre-populate cache
        cache.CACHE_SUBDIR.mkdir(parents=True, exist_ok=True)
        cache_path = cache.CACHE_SUBDIR / f"{_hash_url(test_url)}.html"
        cache_path.write_text(test_html)

        metadata = {
            "query": "test",
            "timestamp": datetime.now().isoformat(),
        }
        cache.METADATA_FILE.write_text(json.dumps(metadata))

        with CachedHTTPClient(current_query="test") as client:
            response = client.get(test_url)

            # Should have the interface used by scraper/metadata
            assert hasattr(response, "text")
            assert hasattr(response, "status_code")
            assert hasattr(response, "raise_for_status")

            assert response.text == test_html
            assert response.status_code == 200
            response.raise_for_status()  # Should not raise
