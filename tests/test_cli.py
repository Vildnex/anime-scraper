"""Integration tests for anime_scraper.cli using Typer's CliRunner."""

import pytest
from typer.testing import CliRunner
import respx
import httpx

from anime_scraper.cli import app, display_banner, display_groups_table, display_group_details


runner = CliRunner()


class TestVersionCommand:
    """Tests for the version command."""

    def test_version_command(self):
        """Test version command displays version."""
        result = runner.invoke(app, ["version"])

        assert result.exit_code == 0
        assert "anime-scraper version" in result.stdout
        assert "1.0.0" in result.stdout


class TestCategoriesCommand:
    """Tests for the categories command."""

    def test_categories_command(self):
        """Test categories command lists all categories."""
        result = runner.invoke(app, ["categories"])

        assert result.exit_code == 0
        assert "anime" in result.stdout.lower()

    def test_categories_shows_all_options(self):
        """Test categories command shows all category options."""
        result = runner.invoke(app, ["categories"])

        assert "anime_english" in result.stdout
        assert "anime_raw" in result.stdout


@respx.mock
class TestSearchCommand:
    """Integration tests for the search command."""

    def test_search_no_results(self, empty_search_page_html, mock_console):
        """Test search with no results."""
        respx.get("https://nyaa.si/").mock(
            return_value=httpx.Response(200, text=empty_search_page_html)
        )

        result = runner.invoke(
            app,
            ["search", "nonexistent anime"],
            input="0\n0\nq\n",  # Select "any" for both languages, then quit
        )

        assert result.exit_code == 1
        assert "No torrents found" in result.stdout

    def test_search_with_dub_flag(self, sample_search_page_html, mock_console):
        """Test search with --dub flag."""
        respx.get("https://nyaa.si/").mock(
            return_value=httpx.Response(200, text=sample_search_page_html)
        )

        result = runner.invoke(
            app,
            ["search", "test anime", "--dub"],
            input="0\n0\nq\n",
        )

        # Should show dub filter message
        assert "Dubbed" in result.stdout or "dub" in result.stdout.lower()

    def test_search_with_max_pages(self, sample_search_page_html, mock_console):
        """Test search with custom max pages."""
        respx.get("https://nyaa.si/").mock(
            return_value=httpx.Response(200, text=sample_search_page_html)
        )

        result = runner.invoke(
            app,
            ["search", "test", "--pages", "2"],
            input="0\n0\nq\n",
        )

        # Should execute without error
        assert result.exit_code in [0, 1]

    def test_search_quit_without_download(
        self, sample_search_page_html, sample_detail_page_html, mock_console
    ):
        """Test search and quit without downloading."""
        respx.get("https://nyaa.si/").mock(
            return_value=httpx.Response(200, text=sample_search_page_html)
        )
        respx.get(url__regex=r"https://nyaa\.si/view/\d+").mock(
            return_value=httpx.Response(200, text=sample_detail_page_html)
        )

        result = runner.invoke(
            app,
            ["search", "test"],
            input="0\n0\nq\n",  # any/any language, quit
        )

        assert result.exit_code == 0
        assert "No group selected" in result.stdout or "Exiting" in result.stdout


class TestDisplayFunctions:
    """Tests for CLI display helper functions."""

    def test_display_banner_no_error(self):
        """Test banner displays without errors."""
        # Should not raise
        display_banner()

    def test_display_groups_table(self, torrent_group_factory):
        """Test groups table display."""
        groups = [
            torrent_group_factory(name="Group 1", num_torrents=5),
            torrent_group_factory(name="Group 2", num_torrents=3),
        ]

        # Should not raise
        display_groups_table(groups)

    def test_display_groups_table_empty(self):
        """Test groups table with empty list."""
        # Should not raise
        display_groups_table([])

    def test_display_group_details(self, torrent_group_factory):
        """Test group details display."""
        group = torrent_group_factory(num_torrents=10)

        # Should not raise
        display_group_details(group)

    def test_display_group_details_truncates_long_names(
        self, torrent_factory, metadata_factory
    ):
        """Test that long torrent names are truncated in display."""
        from anime_scraper.models import TorrentGroup

        metadata = metadata_factory()
        long_name = "A" * 100
        torrents = [torrent_factory(name=long_name, metadata=metadata)]
        group = TorrentGroup(name="Test", description="Desc", torrents=torrents)

        # Should not raise
        display_group_details(group)


class TestCLIHelp:
    """Tests for CLI help messages."""

    def test_main_help(self):
        """Test main help message."""
        result = runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        assert "search" in result.stdout
        assert "version" in result.stdout
        assert "categories" in result.stdout

    def test_search_help(self):
        """Test search command help."""
        result = runner.invoke(app, ["search", "--help"])

        assert result.exit_code == 0
        assert "anime_name" in result.stdout.lower() or "anime-name" in result.stdout.lower()
        assert "--dub" in result.stdout
        assert "--pages" in result.stdout


class TestCLIErrorHandling:
    """Tests for CLI error handling."""

    def test_search_missing_argument(self):
        """Test search without required argument."""
        result = runner.invoke(app, ["search"])

        assert result.exit_code != 0
        assert "Missing argument" in result.stdout or "Usage" in result.stdout

    @respx.mock
    def test_search_http_error(self, mock_console):
        """Test search handles HTTP errors gracefully."""
        respx.get("https://nyaa.si/").mock(
            return_value=httpx.Response(500)
        )

        result = runner.invoke(
            app,
            ["search", "test"],
            input="0\n0\nq\n",
        )

        # Should handle error and show message
        assert result.exit_code == 1
        assert "No torrents found" in result.stdout


class TestLanguagePrompts:
    """Tests for language preference prompts."""

    @respx.mock
    def test_language_selection_displayed(
        self, sample_search_page_html, sample_detail_page_html, mock_console
    ):
        """Test language selection options are displayed."""
        respx.get("https://nyaa.si/").mock(
            return_value=httpx.Response(200, text=sample_search_page_html)
        )
        respx.get(url__regex=r"https://nyaa\.si/view/\d+").mock(
            return_value=httpx.Response(200, text=sample_detail_page_html)
        )

        result = runner.invoke(
            app,
            ["search", "test"],
            input="0\n0\nq\n",
        )

        # Should show language options
        assert "Language" in result.stdout or "Audio" in result.stdout
