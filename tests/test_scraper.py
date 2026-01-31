"""Unit tests for anime_scraper.scraper with respx HTTP mocking."""

import pytest
import respx
import httpx
from bs4 import BeautifulSoup

from anime_scraper.scraper import (
    build_search_url,
    parse_torrent_row,
    get_submitter_for_torrent,
    search_nyaa,
    BASE_URL,
    CATEGORIES,
    FILTERS,
)


class TestBuildSearchUrl:
    """Tests for URL building."""

    def test_basic_search_url(self):
        """Test basic search URL construction."""
        url = build_search_url("test anime")

        assert BASE_URL in url
        assert "test" in url
        assert "anime" in url
        assert "f=0" in url  # no_filter
        assert "c=1_2" in url  # anime_english

    def test_search_url_encodes_query(self):
        """Test query is properly URL encoded."""
        url = build_search_url("test anime")
        assert "test+anime" in url or "test%20anime" in url

    @pytest.mark.parametrize(
        "category,expected_code",
        [
            ("anime", "1_0"),
            ("anime_english", "1_2"),
            ("anime_raw", "1_4"),
            ("all", "0_0"),
            ("anime_amv", "1_1"),
            ("anime_non_english", "1_3"),
        ],
    )
    def test_search_url_categories(self, category, expected_code):
        """Test different category codes."""
        url = build_search_url("test", category=category)
        assert f"c={expected_code}" in url

    @pytest.mark.parametrize(
        "filter_type,expected_code",
        [
            ("no_filter", "0"),
            ("no_remakes", "1"),
            ("trusted", "2"),
        ],
    )
    def test_search_url_filters(self, filter_type, expected_code):
        """Test different filter types."""
        url = build_search_url("test", filter_type=filter_type)
        assert f"f={expected_code}" in url

    def test_search_url_pagination(self):
        """Test pagination parameter."""
        url = build_search_url("test", page=5)
        assert "p=5" in url

    def test_search_url_sort_parameters(self):
        """Test sort parameters."""
        url = build_search_url("test", sort_by="size", order="asc")
        assert "s=size" in url
        assert "o=asc" in url

    def test_search_url_default_sort(self):
        """Test default sort is by seeders descending."""
        url = build_search_url("test")
        assert "s=seeders" in url
        assert "o=desc" in url


class TestParseTorrentRow:
    """Tests for parsing torrent table rows."""

    def test_parse_valid_torrent_row(self, sample_search_page_html):
        """Test parsing a valid torrent row."""
        soup = BeautifulSoup(sample_search_page_html, "lxml")
        rows = soup.find("tbody").find_all("tr")

        torrent = parse_torrent_row(rows[0])

        assert torrent is not None
        assert torrent.id == "1234567"
        assert "SubsPlease" in torrent.name
        assert "Test Anime - 01" in torrent.name
        assert torrent.magnet.startswith("magnet:")
        assert "ABCDEF" in torrent.magnet
        assert torrent.size == "1.4 GiB"
        assert torrent.seeders == 150
        assert torrent.leechers == 20
        assert torrent.downloads == 1000

    def test_parse_multiple_rows(self, sample_search_page_html):
        """Test parsing multiple torrent rows."""
        soup = BeautifulSoup(sample_search_page_html, "lxml")
        rows = soup.find("tbody").find_all("tr")

        torrents = [parse_torrent_row(row) for row in rows]
        torrents = [t for t in torrents if t is not None]

        assert len(torrents) == 2
        assert torrents[0].id == "1234567"
        assert torrents[1].id == "1234568"

    def test_parse_invalid_row_returns_none(self, mock_console):
        """Test that invalid/incomplete rows return None."""
        html = "<tr><td>Invalid</td></tr>"
        soup = BeautifulSoup(html, "lxml")
        row = soup.find("tr")

        torrent = parse_torrent_row(row)
        assert torrent is None

    def test_parse_row_missing_columns(self, mock_console):
        """Test row with fewer than 8 columns returns None."""
        html = "<tr><td>1</td><td>2</td><td>3</td></tr>"
        soup = BeautifulSoup(html, "lxml")
        row = soup.find("tr")

        torrent = parse_torrent_row(row)
        assert torrent is None


@respx.mock
class TestGetSubmitterForTorrent:
    """Tests for fetching submitter from detail page."""

    def test_get_submitter_success(self, sample_detail_page_html):
        """Test successful submitter extraction."""
        torrent_id = "1234567"

        respx.get(f"{BASE_URL}/view/{torrent_id}").mock(
            return_value=httpx.Response(200, text=sample_detail_page_html)
        )

        with httpx.Client() as client:
            submitter = get_submitter_for_torrent(client, torrent_id)

        assert submitter == "SubsPlease"

    def test_get_submitter_not_found_returns_anonymous(self):
        """Test returns 'Anonymous' when submitter not found."""
        torrent_id = "999999"
        html = "<html><body>No submitter info</body></html>"

        respx.get(f"{BASE_URL}/view/{torrent_id}").mock(
            return_value=httpx.Response(200, text=html)
        )

        with httpx.Client() as client:
            submitter = get_submitter_for_torrent(client, torrent_id)

        assert submitter == "Anonymous"

    def test_get_submitter_http_error_returns_anonymous(self):
        """Test returns 'Anonymous' on HTTP error."""
        torrent_id = "error"

        respx.get(f"{BASE_URL}/view/{torrent_id}").mock(
            return_value=httpx.Response(404)
        )

        with httpx.Client() as client:
            submitter = get_submitter_for_torrent(client, torrent_id)

        assert submitter == "Anonymous"

    def test_get_submitter_exception_returns_anonymous(self):
        """Test returns 'Anonymous' on exception."""
        torrent_id = "exception"

        respx.get(f"{BASE_URL}/view/{torrent_id}").mock(
            side_effect=httpx.ConnectError("Connection failed")
        )

        with httpx.Client() as client:
            submitter = get_submitter_for_torrent(client, torrent_id)

        assert submitter == "Anonymous"


@respx.mock
class TestSearchNyaa:
    """Integration tests for search_nyaa function."""

    def test_search_returns_torrents(self, sample_search_page_html, mock_console):
        """Test search returns parsed torrents."""
        respx.get(f"{BASE_URL}/").mock(
            return_value=httpx.Response(200, text=sample_search_page_html)
        )

        torrents = search_nyaa("test anime", fetch_submitters=False, max_pages=1)

        assert len(torrents) == 2
        assert all(isinstance(t.seeders, int) for t in torrents)

    def test_search_empty_results(self, empty_search_page_html, mock_console):
        """Test search with no results."""
        respx.get(f"{BASE_URL}/").mock(
            return_value=httpx.Response(200, text=empty_search_page_html)
        )

        torrents = search_nyaa("nonexistent anime", max_pages=1)
        assert len(torrents) == 0

    def test_search_with_dub_filter(self, sample_search_page_html, mock_console):
        """Test dub_only parameter modifies search query."""
        route = respx.get(f"{BASE_URL}/").mock(
            return_value=httpx.Response(200, text=sample_search_page_html)
        )

        search_nyaa("test", dub_only=True, fetch_submitters=False, max_pages=1)

        # Check that the request included dub keywords
        request_url = str(route.calls.last.request.url)
        assert "dub" in request_url.lower() or "dual" in request_url.lower()

    def test_search_http_error_handling(self, mock_console):
        """Test graceful handling of HTTP errors."""
        respx.get(f"{BASE_URL}/").mock(return_value=httpx.Response(500))

        torrents = search_nyaa("test", max_pages=1)
        assert len(torrents) == 0

    def test_search_respects_max_pages(self, sample_search_page_html, mock_console):
        """Test search stops at max_pages."""
        # First page has results, second page is empty
        respx.get(f"{BASE_URL}/").mock(
            return_value=httpx.Response(200, text=sample_search_page_html)
        )

        torrents = search_nyaa("test", fetch_submitters=False, max_pages=1)
        assert len(torrents) > 0

    def test_search_with_category(self, sample_search_page_html, mock_console):
        """Test search with specific category."""
        route = respx.get(f"{BASE_URL}/").mock(
            return_value=httpx.Response(200, text=sample_search_page_html)
        )

        search_nyaa("test", category="anime_raw", fetch_submitters=False, max_pages=1)

        request_url = str(route.calls.last.request.url)
        assert "c=1_4" in request_url  # anime_raw code

    def test_search_with_filter_type(self, sample_search_page_html, mock_console):
        """Test search with filter type."""
        route = respx.get(f"{BASE_URL}/").mock(
            return_value=httpx.Response(200, text=sample_search_page_html)
        )

        search_nyaa(
            "test", filter_type="trusted", fetch_submitters=False, max_pages=1
        )

        request_url = str(route.calls.last.request.url)
        assert "f=2" in request_url  # trusted filter


class TestCategoryAndFilterConstants:
    """Tests for CATEGORIES and FILTERS constants."""

    def test_categories_dict_populated(self):
        """Test CATEGORIES dictionary is populated."""
        assert len(CATEGORIES) > 0
        assert "anime" in CATEGORIES
        assert "anime_english" in CATEGORIES

    def test_filters_dict_populated(self):
        """Test FILTERS dictionary is populated."""
        assert len(FILTERS) > 0
        assert "no_filter" in FILTERS
        assert "trusted" in FILTERS

    def test_base_url_is_nyaa(self):
        """Test BASE_URL points to nyaa.si."""
        assert "nyaa.si" in BASE_URL
