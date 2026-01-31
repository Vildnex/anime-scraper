"""Torrent download and magnet bundle creation module."""

from pathlib import Path
from datetime import datetime

import httpx
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
)

from .models import Torrent, TorrentGroup
from .utils import console, sanitize_filename

DEFAULT_DOWNLOAD_DIR = Path.home() / "Downloads" / "anime-torrents"


class DownloadError(Exception):
    """Raised when download directory cannot be created or accessed."""


def ensure_download_dir(download_dir: Path | None = None) -> Path:
    """
    Ensure the download directory exists.

    Raises:
        DownloadError: If directory cannot be created (permissions, disk full, etc.)
    """
    if download_dir is None:
        download_dir = DEFAULT_DOWNLOAD_DIR

    try:
        download_dir.mkdir(parents=True, exist_ok=True)
        return download_dir
    except PermissionError:
        raise DownloadError(
            f"Permission denied: Cannot create directory '{download_dir}'. "
            "Try using --output to specify a different location."
        )
    except OSError as e:
        raise DownloadError(f"Cannot create directory '{download_dir}': {e}")


def download_torrent_file(
    client: httpx.Client, torrent: Torrent, download_dir: Path
) -> Path | None:
    """Download a single .torrent file."""
    try:
        response = client.get(torrent.download_url)
        response.raise_for_status()

        filename = sanitize_filename(torrent.name) + ".torrent"
        filepath = download_dir / filename

        filepath.write_bytes(response.content)
        return filepath

    except httpx.HTTPError as e:
        console.print(f"[red]Failed to download {torrent.name}: {e}[/red]")
        return None
    except PermissionError:
        console.print(f"[red]Permission denied writing {torrent.name}[/red]")
        return None
    except OSError as e:
        console.print(f"[red]Error saving {torrent.name}: {e}[/red]")
        return None


def download_group_torrents(
    group: TorrentGroup, download_dir: Path | None = None
) -> list[Path]:
    """
    Download all .torrent files for a group.

    Args:
        group: The TorrentGroup to download
        download_dir: Directory to save torrents (default: ~/Downloads/anime-torrents)

    Returns:
        List of paths to downloaded torrent files

    Raises:
        DownloadError: If directory cannot be created
    """
    download_dir = ensure_download_dir(download_dir)

    # Create a subfolder for this group
    group_dir = download_dir / sanitize_filename(group.name)
    try:
        group_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise DownloadError(f"Cannot create group directory '{group_dir}': {e}")

    downloaded_files: list[Path] = []

    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(
                "Downloading torrents...", total=len(group.torrents)
            )

            for torrent in group.torrents:
                progress.update(
                    task, description=f"Downloading: {torrent.name[:50]}..."
                )

                filepath = download_torrent_file(client, torrent, group_dir)
                if filepath:
                    downloaded_files.append(filepath)

                progress.advance(task)

    console.print(
        f"[green]Downloaded {len(downloaded_files)}/{len(group.torrents)} torrent files[/green]"
    )
    console.print(f"[dim]Location: {group_dir}[/dim]")

    return downloaded_files


def create_magnet_bundle(
    group: TorrentGroup, output_dir: Path | None = None
) -> Path | None:
    """
    Create a magnet bundle file containing all magnet links from the group.

    The bundle file is a simple text file with one magnet link per line.
    Most torrent clients (qBittorrent, Transmission, etc.) can import this.

    Args:
        group: The TorrentGroup to create a bundle for
        output_dir: Directory to save the bundle file

    Returns:
        Path to the created bundle file, or None if failed

    Raises:
        DownloadError: If directory cannot be created
    """
    output_dir = ensure_download_dir(output_dir)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = sanitize_filename(f"{group.name}_{timestamp}") + "_magnets.txt"
    filepath = output_dir / filename

    try:
        magnets = [t.magnet for t in group.torrents if t.magnet]

        if not magnets:
            console.print("[red]No magnet links found in this group.[/red]")
            return None

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"# Magnet Bundle: {group.name}\n")
            f.write(f"# Generated: {datetime.now().isoformat()}\n")
            f.write(f"# Total: {len(magnets)} magnets\n")
            f.write("#\n")
            f.write("# Import this file into your torrent client:\n")
            f.write("# - qBittorrent: File -> Add Torrent Links\n")
            f.write("# - Transmission: File -> Open URL\n")
            f.write("#\n\n")

            for magnet in magnets:
                f.write(f"{magnet}\n")

        console.print(f"[green]Created magnet bundle: {filepath}[/green]")
        console.print(f"[dim]Contains {len(magnets)} magnet links[/dim]")

        return filepath

    except PermissionError:
        console.print(f"[red]Permission denied writing to {filepath}[/red]")
        return None
    except OSError as e:
        console.print(f"[red]Failed to create magnet bundle: {e}[/red]")
        return None


def create_combined_output(
    group: TorrentGroup,
    download_dir: Path | None = None,
    download_torrents: bool = True,
    create_bundle: bool = True,
) -> dict:
    """
    Create both torrent downloads and magnet bundle for a group.

    Args:
        group: The TorrentGroup to process
        download_dir: Directory for output files
        download_torrents: Whether to download .torrent files
        create_bundle: Whether to create a magnet bundle file

    Returns:
        Dictionary with paths to created files

    Raises:
        DownloadError: If directory cannot be created
    """
    output_dir = ensure_download_dir(download_dir)
    result = {"torrent_files": [], "magnet_bundle": None, "output_dir": output_dir}

    if download_torrents:
        console.print("\n[bold]Downloading .torrent files...[/bold]")
        result["torrent_files"] = download_group_torrents(group, output_dir)

    if create_bundle:
        console.print("\n[bold]Creating magnet bundle...[/bold]")
        result["magnet_bundle"] = create_magnet_bundle(group, output_dir)

    return result
