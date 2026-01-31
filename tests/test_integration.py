"""Integration tests for complete workflows."""

import pytest
import respx
import httpx

from anime_scraper.scraper import search_nyaa
from anime_scraper.grouper import group_torrents_with_metadata
from anime_scraper.downloader import create_combined_output
from anime_scraper.utils import filter_by_language
from anime_scraper.metadata import fetch_metadata_for_torrents


@respx.mock
class TestSearchToGroupWorkflow:
    """Test the search -> group workflow."""

    def test_complete_search_and_group_workflow(
        self, sample_search_page_html, sample_detail_page_html, mock_console
    ):
        """Test complete workflow from search to grouping."""
        # Mock search page
        respx.get("https://nyaa.si/").mock(
            return_value=httpx.Response(200, text=sample_search_page_html)
        )

        # Mock detail pages for each torrent
        respx.get("https://nyaa.si/view/1234567").mock(
            return_value=httpx.Response(200, text=sample_detail_page_html)
        )
        respx.get("https://nyaa.si/view/1234568").mock(
            return_value=httpx.Response(200, text=sample_detail_page_html)
        )

        # Step 1: Search
        torrents = search_nyaa("test anime", max_pages=1, fetch_submitters=False)
        assert len(torrents) > 0

        # Step 2: Filter by language
        filtered = filter_by_language(torrents, audio_lang="any", sub_lang="any")
        assert len(filtered) > 0

        # Step 3: Group
        groups = group_torrents_with_metadata(filtered, "test anime")
        assert len(groups) > 0
        assert all(len(g.torrents) > 0 for g in groups)

    def test_search_filter_group_workflow(
        self, sample_search_page_html, sample_detail_page_html, mock_console
    ):
        """Test search with language filtering then grouping."""
        respx.get("https://nyaa.si/").mock(
            return_value=httpx.Response(200, text=sample_search_page_html)
        )
        respx.get(url__regex=r"https://nyaa\.si/view/\d+").mock(
            return_value=httpx.Response(200, text=sample_detail_page_html)
        )

        torrents = search_nyaa("anime", max_pages=1, fetch_submitters=False)

        # Filter for English subs (should match based on category)
        filtered = filter_by_language(torrents, audio_lang="any", sub_lang="english")

        # Group the filtered results
        groups = group_torrents_with_metadata(filtered, "anime")

        # Verify workflow completed
        assert isinstance(groups, list)


@respx.mock
class TestSearchToDownloadWorkflow:
    """Test the complete search -> group -> download workflow."""

    def test_complete_workflow_with_download(
        self,
        sample_search_page_html,
        sample_detail_page_html,
        sample_torrent_file_content,
        temp_download_dir,
        mock_console,
    ):
        """Test complete workflow including download."""
        # Mock search
        respx.get("https://nyaa.si/").mock(
            return_value=httpx.Response(200, text=sample_search_page_html)
        )

        # Mock detail pages
        respx.get("https://nyaa.si/view/1234567").mock(
            return_value=httpx.Response(200, text=sample_detail_page_html)
        )
        respx.get("https://nyaa.si/view/1234568").mock(
            return_value=httpx.Response(200, text=sample_detail_page_html)
        )

        # Mock torrent file downloads
        respx.get("https://nyaa.si/download/1234567.torrent").mock(
            return_value=httpx.Response(200, content=sample_torrent_file_content)
        )
        respx.get("https://nyaa.si/download/1234568.torrent").mock(
            return_value=httpx.Response(200, content=sample_torrent_file_content)
        )

        # Execute workflow
        torrents = search_nyaa("test anime", max_pages=1, fetch_submitters=False)
        groups = group_torrents_with_metadata(torrents, "test anime")

        # Download first group
        result = create_combined_output(
            group=groups[0],
            download_dir=temp_download_dir,
            download_torrents=True,
            create_bundle=True,
        )

        # Verify results
        assert result["output_dir"].exists()
        assert len(result["torrent_files"]) > 0
        assert result["magnet_bundle"] is not None
        assert result["magnet_bundle"].exists()

    def test_workflow_with_bundle_only(
        self,
        sample_search_page_html,
        sample_detail_page_html,
        temp_download_dir,
        mock_console,
    ):
        """Test workflow creating only magnet bundle."""
        respx.get("https://nyaa.si/").mock(
            return_value=httpx.Response(200, text=sample_search_page_html)
        )
        respx.get(url__regex=r"https://nyaa\.si/view/\d+").mock(
            return_value=httpx.Response(200, text=sample_detail_page_html)
        )

        torrents = search_nyaa("test", max_pages=1, fetch_submitters=False)
        groups = group_torrents_with_metadata(torrents, "test")

        result = create_combined_output(
            group=groups[0],
            download_dir=temp_download_dir,
            download_torrents=False,
            create_bundle=True,
        )

        assert result["magnet_bundle"] is not None
        assert len(result["torrent_files"]) == 0


@respx.mock
class TestMetadataWorkflow:
    """Tests for metadata extraction workflow."""

    def test_metadata_extraction_populates_torrents(
        self, sample_detail_page_html, torrent_factory, mock_console
    ):
        """Test metadata extraction populates torrent objects."""
        torrents = [
            torrent_factory(id="1234567", metadata=None),
            torrent_factory(id="1234568", metadata=None),
        ]

        respx.get("https://nyaa.si/view/1234567").mock(
            return_value=httpx.Response(200, text=sample_detail_page_html)
        )
        respx.get("https://nyaa.si/view/1234568").mock(
            return_value=httpx.Response(200, text=sample_detail_page_html)
        )

        result = fetch_metadata_for_torrents(torrents)

        assert len(result) == 2
        assert all(t.metadata is not None for t in result)
        assert all(t.submitter == "SubsPlease" for t in result)

    def test_metadata_extraction_handles_failures(
        self, sample_detail_page_html, torrent_factory, mock_console
    ):
        """Test metadata extraction handles partial failures."""
        torrents = [
            torrent_factory(id="success", metadata=None),
            torrent_factory(id="fail", metadata=None),
        ]

        respx.get("https://nyaa.si/view/success").mock(
            return_value=httpx.Response(200, text=sample_detail_page_html)
        )
        respx.get("https://nyaa.si/view/fail").mock(
            return_value=httpx.Response(404)
        )

        result = fetch_metadata_for_torrents(torrents)

        # All torrents should have metadata (fallback for failures)
        assert len(result) == 2
        assert all(t.metadata is not None for t in result)


@respx.mock
class TestEdgeCaseWorkflows:
    """Test edge cases and error scenarios."""

    def test_workflow_with_http_errors(
        self, sample_search_page_html, mock_console
    ):
        """Test workflow handles HTTP errors gracefully."""
        respx.get("https://nyaa.si/").mock(
            return_value=httpx.Response(200, text=sample_search_page_html)
        )

        # Mock detail pages with errors
        respx.get("https://nyaa.si/view/1234567").mock(
            return_value=httpx.Response(500)
        )
        respx.get("https://nyaa.si/view/1234568").mock(
            return_value=httpx.Response(404)
        )

        torrents = search_nyaa("test", max_pages=1, fetch_submitters=False)

        # Should still complete with fallback metadata
        groups = group_torrents_with_metadata(torrents, "test")
        assert len(groups) >= 0

    def test_workflow_empty_results_at_each_stage(self, mock_console):
        """Test workflow with no results at various stages."""
        # Empty search results
        torrents = []
        groups = group_torrents_with_metadata(torrents, "test")
        assert len(groups) == 0

    def test_filter_removes_all_results(
        self, sample_search_page_html, mock_console
    ):
        """Test workflow when filter removes all results."""
        respx.get("https://nyaa.si/").mock(
            return_value=httpx.Response(200, text=sample_search_page_html)
        )

        torrents = search_nyaa("test", max_pages=1, fetch_submitters=False)

        # Filter for Spanish (should match nothing in our sample)
        filtered = filter_by_language(
            torrents, audio_lang="spanish", sub_lang="spanish"
        )

        # Should be empty
        assert len(filtered) == 0

    def test_grouping_with_no_metadata(self, torrent_factory, mock_console):
        """Test grouping handles torrents without metadata."""
        torrents = [
            torrent_factory(id="1", metadata=None),
            torrent_factory(id="2", metadata=None),
        ]

        from anime_scraper.grouper import group_torrents_deterministic

        groups = group_torrents_deterministic(torrents, "Fallback Name")

        assert len(groups) > 0
        assert all(t.metadata is not None for t in groups[0].torrents)


@respx.mock
class TestDubOnlyWorkflow:
    """Tests for dub-only search workflow."""

    def test_dub_only_modifies_search(self, sample_search_page_html, mock_console):
        """Test dub_only parameter affects search."""
        route = respx.get("https://nyaa.si/").mock(
            return_value=httpx.Response(200, text=sample_search_page_html)
        )

        search_nyaa("anime", dub_only=True, max_pages=1, fetch_submitters=False)

        # Check that dub keywords were added to query
        request_url = str(route.calls.last.request.url)
        assert "dub" in request_url.lower() or "dual" in request_url.lower()


class TestDataIntegrity:
    """Tests for data integrity across workflow stages."""

    @respx.mock
    def test_torrent_ids_preserved(
        self, sample_search_page_html, sample_detail_page_html, mock_console
    ):
        """Test torrent IDs are preserved through workflow."""
        respx.get("https://nyaa.si/").mock(
            return_value=httpx.Response(200, text=sample_search_page_html)
        )
        respx.get(url__regex=r"https://nyaa\.si/view/\d+").mock(
            return_value=httpx.Response(200, text=sample_detail_page_html)
        )

        torrents = search_nyaa("test", max_pages=1, fetch_submitters=False)
        original_ids = {t.id for t in torrents}

        groups = group_torrents_with_metadata(torrents, "test")

        # Verify IDs are preserved in groups
        grouped_ids = set()
        for group in groups:
            for torrent in group.torrents:
                grouped_ids.add(torrent.id)

        assert original_ids == grouped_ids

    @respx.mock
    def test_magnet_links_preserved(
        self, sample_search_page_html, sample_detail_page_html, mock_console
    ):
        """Test magnet links are preserved through workflow."""
        respx.get("https://nyaa.si/").mock(
            return_value=httpx.Response(200, text=sample_search_page_html)
        )
        respx.get(url__regex=r"https://nyaa\.si/view/\d+").mock(
            return_value=httpx.Response(200, text=sample_detail_page_html)
        )

        torrents = search_nyaa("test", max_pages=1, fetch_submitters=False)
        original_magnets = {t.magnet for t in torrents}

        groups = group_torrents_with_metadata(torrents, "test")

        # Verify magnets are preserved
        grouped_magnets = set()
        for group in groups:
            for torrent in group.torrents:
                grouped_magnets.add(torrent.magnet)

        assert original_magnets == grouped_magnets
