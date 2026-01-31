"""Unit tests for anime_scraper.downloader with filesystem mocking."""

import pytest
import respx
import httpx
from pathlib import Path

from anime_scraper.downloader import (
    ensure_download_dir,
    download_torrent_file,
    download_group_torrents,
    create_magnet_bundle,
    create_combined_output,
    DownloadError,
    DEFAULT_DOWNLOAD_DIR,
)


class TestEnsureDownloadDir:
    """Tests for download directory creation."""

    def test_creates_directory(self, tmp_path):
        """Test creates directory if it doesn't exist."""
        download_dir = tmp_path / "new_downloads"

        result = ensure_download_dir(download_dir)

        assert result == download_dir
        assert download_dir.exists()
        assert download_dir.is_dir()

    def test_creates_nested_directories(self, tmp_path):
        """Test creates nested directory structure."""
        download_dir = tmp_path / "a" / "b" / "c"

        result = ensure_download_dir(download_dir)

        assert result.exists()
        assert result.is_dir()

    def test_existing_directory(self, temp_download_dir):
        """Test handles existing directory gracefully."""
        result = ensure_download_dir(temp_download_dir)
        assert result == temp_download_dir
        assert temp_download_dir.exists()

    def test_default_directory(self):
        """Test uses default directory when None provided."""
        result = ensure_download_dir(None)
        assert result == DEFAULT_DOWNLOAD_DIR

    def test_permission_error_raises_download_error(self, monkeypatch):
        """Test raises DownloadError on permission issues."""

        def mock_mkdir(*args, **kwargs):
            raise PermissionError("Access denied")

        monkeypatch.setattr(Path, "mkdir", mock_mkdir)

        with pytest.raises(DownloadError) as exc_info:
            ensure_download_dir(Path("/fake/path"))

        assert "Permission denied" in str(exc_info.value)

    def test_os_error_raises_download_error(self, monkeypatch):
        """Test raises DownloadError on OSError."""

        def mock_mkdir(*args, **kwargs):
            raise OSError("Disk full")

        monkeypatch.setattr(Path, "mkdir", mock_mkdir)

        with pytest.raises(DownloadError) as exc_info:
            ensure_download_dir(Path("/fake/path"))

        assert "Cannot create directory" in str(exc_info.value)


@respx.mock
class TestDownloadTorrentFile:
    """Tests for downloading individual torrent files."""

    def test_successful_download(
        self, torrent_factory, temp_download_dir, sample_torrent_file_content, mock_console
    ):
        """Test successful torrent file download."""
        torrent = torrent_factory(id="123456", name="Test Anime - 01")

        respx.get(torrent.download_url).mock(
            return_value=httpx.Response(200, content=sample_torrent_file_content)
        )

        with httpx.Client() as client:
            filepath = download_torrent_file(client, torrent, temp_download_dir)

        assert filepath is not None
        assert filepath.exists()
        assert filepath.suffix == ".torrent"
        assert filepath.read_bytes() == sample_torrent_file_content

    def test_http_error_returns_none(
        self, torrent_factory, temp_download_dir, mock_console
    ):
        """Test returns None on HTTP error."""
        torrent = torrent_factory(id="error")

        respx.get(torrent.download_url).mock(
            return_value=httpx.Response(404)
        )

        with httpx.Client() as client:
            filepath = download_torrent_file(client, torrent, temp_download_dir)

        assert filepath is None

    def test_sanitizes_filename(
        self, torrent_factory, temp_download_dir, sample_torrent_file_content, mock_console
    ):
        """Test filename sanitization for invalid characters."""
        torrent = torrent_factory(name='Test/Anime:\\<>|?*.mkv')

        respx.get(torrent.download_url).mock(
            return_value=httpx.Response(200, content=sample_torrent_file_content)
        )

        with httpx.Client() as client:
            filepath = download_torrent_file(client, torrent, temp_download_dir)

        assert filepath is not None
        assert not any(c in filepath.name for c in '<>:"/\\|?*')

    def test_network_error_returns_none(
        self, torrent_factory, temp_download_dir, mock_console
    ):
        """Test returns None on network error."""
        torrent = torrent_factory(id="network_error")

        respx.get(torrent.download_url).mock(
            side_effect=httpx.ConnectError("Connection failed")
        )

        with httpx.Client() as client:
            filepath = download_torrent_file(client, torrent, temp_download_dir)

        assert filepath is None


@respx.mock
class TestDownloadGroupTorrents:
    """Tests for downloading torrent groups."""

    def test_downloads_all_torrents(
        self, torrent_group_factory, temp_download_dir, sample_torrent_file_content, mock_console
    ):
        """Test downloading all torrents in a group."""
        group = torrent_group_factory(num_torrents=3)

        for torrent in group.torrents:
            respx.get(torrent.download_url).mock(
                return_value=httpx.Response(200, content=sample_torrent_file_content)
            )

        filepaths = download_group_torrents(group, temp_download_dir)

        assert len(filepaths) == 3
        assert all(fp.exists() for fp in filepaths)

    def test_creates_group_subdirectory(
        self, torrent_group_factory, temp_download_dir, sample_torrent_file_content, mock_console
    ):
        """Test that group subdirectory is created."""
        group = torrent_group_factory(name="My Anime Group", num_torrents=1)

        respx.get(url__regex=r".*\.torrent").mock(
            return_value=httpx.Response(200, content=sample_torrent_file_content)
        )

        filepaths = download_group_torrents(group, temp_download_dir)

        # Check that files are in a subdirectory
        assert len(filepaths) == 1
        assert filepaths[0].parent.name != temp_download_dir.name

    def test_partial_download_failures(
        self, torrent_factory, metadata_factory, temp_download_dir, sample_torrent_file_content, mock_console
    ):
        """Test handling of partial download failures."""
        from anime_scraper.models import TorrentGroup

        metadata = metadata_factory()
        torrents = [
            torrent_factory(id="1", metadata=metadata),
            torrent_factory(id="2", metadata=metadata),
            torrent_factory(id="3", metadata=metadata),
        ]
        group = TorrentGroup(
            name="Test Group", description="Test", torrents=torrents
        )

        # First succeeds, second fails, third succeeds
        respx.get("https://nyaa.si/download/1.torrent").mock(
            return_value=httpx.Response(200, content=sample_torrent_file_content)
        )
        respx.get("https://nyaa.si/download/2.torrent").mock(
            return_value=httpx.Response(500)
        )
        respx.get("https://nyaa.si/download/3.torrent").mock(
            return_value=httpx.Response(200, content=sample_torrent_file_content)
        )

        filepaths = download_group_torrents(group, temp_download_dir)

        assert len(filepaths) == 2

    def test_empty_group_returns_empty_list(
        self, torrent_factory, metadata_factory, temp_download_dir, mock_console
    ):
        """Test empty group returns empty list."""
        from anime_scraper.models import TorrentGroup

        group = TorrentGroup(name="Empty", description="Empty", torrents=[])

        filepaths = download_group_torrents(group, temp_download_dir)

        assert len(filepaths) == 0


class TestCreateMagnetBundle:
    """Tests for creating magnet bundle files."""

    def test_creates_bundle_file(self, torrent_group_factory, temp_download_dir, mock_console):
        """Test creating a magnet bundle file."""
        group = torrent_group_factory(num_torrents=5)

        bundle_path = create_magnet_bundle(group, temp_download_dir)

        assert bundle_path is not None
        assert bundle_path.exists()
        assert bundle_path.suffix == ".txt"
        assert "_magnets.txt" in bundle_path.name

    def test_bundle_contains_all_magnets(
        self, torrent_factory, metadata_factory, temp_download_dir, mock_console
    ):
        """Test bundle contains all magnet links."""
        from anime_scraper.models import TorrentGroup

        metadata = metadata_factory()
        magnets = [
            "magnet:?xt=urn:btih:abc123",
            "magnet:?xt=urn:btih:def456",
            "magnet:?xt=urn:btih:ghi789",
        ]
        torrents = [
            torrent_factory(id=str(i), magnet=m, metadata=metadata)
            for i, m in enumerate(magnets)
        ]
        group = TorrentGroup(name="Test", description="Test", torrents=torrents)

        bundle_path = create_magnet_bundle(group, temp_download_dir)
        content = bundle_path.read_text()

        for magnet in magnets:
            assert magnet in content

    def test_bundle_has_headers(self, torrent_group_factory, temp_download_dir, mock_console):
        """Test bundle file has informational headers."""
        group = torrent_group_factory(name="My Anime")

        bundle_path = create_magnet_bundle(group, temp_download_dir)
        content = bundle_path.read_text()

        assert "Magnet Bundle" in content
        assert "My Anime" in content
        assert "#" in content  # Comment lines

    def test_bundle_has_instructions(
        self, torrent_group_factory, temp_download_dir, mock_console
    ):
        """Test bundle includes usage instructions."""
        group = torrent_group_factory()

        bundle_path = create_magnet_bundle(group, temp_download_dir)
        content = bundle_path.read_text()

        assert "qBittorrent" in content
        assert "Transmission" in content

    def test_no_magnets_returns_none(
        self, torrent_factory, metadata_factory, temp_download_dir, mock_console
    ):
        """Test returns None when no magnets available."""
        from anime_scraper.models import TorrentGroup

        metadata = metadata_factory()
        torrents = [
            torrent_factory(id="1", magnet="", metadata=metadata),
            torrent_factory(id="2", magnet="", metadata=metadata),
        ]
        group = TorrentGroup(name="Test", description="Test", torrents=torrents)

        bundle_path = create_magnet_bundle(group, temp_download_dir)

        assert bundle_path is None

    def test_filename_includes_timestamp(
        self, torrent_group_factory, temp_download_dir, mock_console
    ):
        """Test filename includes timestamp."""
        group = torrent_group_factory(name="Test")

        bundle_path = create_magnet_bundle(group, temp_download_dir)

        # Filename should match pattern: Test_YYYYMMDD_HHMMSS_magnets.txt
        assert "_magnets.txt" in bundle_path.name
        assert "Test" in bundle_path.name


@respx.mock
class TestCreateCombinedOutput:
    """Integration tests for combined download operations."""

    def test_creates_both_torrents_and_bundle(
        self, torrent_group_factory, temp_download_dir, sample_torrent_file_content, mock_console
    ):
        """Test creating both torrent files and magnet bundle."""
        group = torrent_group_factory(num_torrents=2)

        for torrent in group.torrents:
            respx.get(torrent.download_url).mock(
                return_value=httpx.Response(200, content=sample_torrent_file_content)
            )

        result = create_combined_output(
            group,
            temp_download_dir,
            download_torrents=True,
            create_bundle=True,
        )

        assert len(result["torrent_files"]) == 2
        assert result["magnet_bundle"] is not None
        assert result["output_dir"] == temp_download_dir

    def test_torrents_only(
        self, torrent_group_factory, temp_download_dir, sample_torrent_file_content, mock_console
    ):
        """Test creating only torrent files."""
        group = torrent_group_factory(num_torrents=1)

        respx.get(group.torrents[0].download_url).mock(
            return_value=httpx.Response(200, content=sample_torrent_file_content)
        )

        result = create_combined_output(
            group,
            temp_download_dir,
            download_torrents=True,
            create_bundle=False,
        )

        assert len(result["torrent_files"]) == 1
        assert result["magnet_bundle"] is None

    def test_bundle_only(self, torrent_group_factory, temp_download_dir, mock_console):
        """Test creating only magnet bundle."""
        group = torrent_group_factory()

        result = create_combined_output(
            group,
            temp_download_dir,
            download_torrents=False,
            create_bundle=True,
        )

        assert len(result["torrent_files"]) == 0
        assert result["magnet_bundle"] is not None

    def test_neither_option(self, torrent_group_factory, temp_download_dir, mock_console):
        """Test with both options disabled."""
        group = torrent_group_factory()

        result = create_combined_output(
            group,
            temp_download_dir,
            download_torrents=False,
            create_bundle=False,
        )

        assert len(result["torrent_files"]) == 0
        assert result["magnet_bundle"] is None

    def test_default_download_dir_when_none(
        self, torrent_group_factory, mock_console
    ):
        """Test uses default directory when None provided."""
        group = torrent_group_factory()

        result = create_combined_output(
            group,
            download_dir=None,
            download_torrents=False,
            create_bundle=False,
        )

        assert result["output_dir"] == DEFAULT_DOWNLOAD_DIR


class TestDownloadError:
    """Tests for DownloadError exception."""

    def test_download_error_is_exception(self):
        """Test DownloadError is an Exception."""
        assert issubclass(DownloadError, Exception)

    def test_download_error_message(self):
        """Test DownloadError can carry a message."""
        error = DownloadError("Test error message")
        assert str(error) == "Test error message"
