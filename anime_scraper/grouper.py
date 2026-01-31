"""Deterministic torrent grouping module."""

from collections import defaultdict

from .models import Torrent, TorrentGroup, TorrentMetadata
from .metadata import fetch_metadata_for_torrents
from .utils import console, contains_dub_keywords


def group_torrents_deterministic(
    torrents: list[Torrent], anime_name: str
) -> list[TorrentGroup]:
    """
    Group torrents deterministically based on extracted metadata.

    Groups are formed by exact match on:
    - Release group (submitter)
    - Anime name
    - Season
    - Audio language (DUB)
    - Subtitle language (SUB)
    - Quality

    Args:
        torrents: List of torrents with metadata already extracted
        anime_name: Name of the anime being searched (for fallback)

    Returns:
        List of TorrentGroup objects, sorted by total seeders
    """
    if not torrents:
        return []

    # Ensure all torrents have metadata
    for torrent in torrents:
        if torrent.metadata is None:
            torrent.metadata = TorrentMetadata(anime_name=anime_name)

    # Group by the deterministic key
    groups_dict: dict[str, list[Torrent]] = defaultdict(list)
    for torrent in torrents:
        key = torrent.metadata.group_key()
        groups_dict[key].append(torrent)

    # Convert to TorrentGroup objects
    groups = []
    for key, torrent_list in groups_dict.items():
        # Use the first torrent's metadata as representative
        metadata = torrent_list[0].metadata

        # Determine episode range
        episodes = []
        for t in torrent_list:
            if t.metadata and t.metadata.episode:
                # Extract episode number
                ep_str = t.metadata.episode.replace("Episode ", "")
                try:
                    episodes.append(int(ep_str))
                except ValueError:
                    pass

        if episodes:
            episodes.sort()
            if len(episodes) == 1:
                episode_range = f"Episode {episodes[0]}"
            else:
                episode_range = f"Episodes {min(episodes)}-{max(episodes)}"
        else:
            episode_range = "Various"

        # Check if any are dubbed
        is_dubbed = metadata.audio_language.lower() == "english" or any(
            contains_dub_keywords(t.name) for t in torrent_list
        )

        group = TorrentGroup(
            name=metadata.group_name(),
            description=f"Release group: {metadata.release_group}, "
                        f"Quality: {metadata.quality}, "
                        f"Audio: {metadata.audio_language}, "
                        f"Subs: {metadata.subtitle_language}",
            torrents=torrent_list,
            episode_range=episode_range,
            quality=metadata.quality,
            is_dubbed=is_dubbed,
        )
        groups.append(group)

    # Sort groups by total seeders (descending)
    groups.sort(key=lambda g: g.total_seeders, reverse=True)

    console.print(f"[green]Created {len(groups)} groups (deterministic)[/green]")
    return groups


def group_torrents_with_metadata(
    torrents: list[Torrent], anime_name: str
) -> list[TorrentGroup]:
    """
    Main entry point for grouping torrents.

    This function:
    1. Fetches detail pages for all torrents
    2. Extracts metadata from each page
    3. Groups torrents deterministically by exact metadata match

    Args:
        torrents: List of torrents to group
        anime_name: Name of the anime being searched

    Returns:
        List of TorrentGroup objects
    """
    if not torrents:
        return []

    console.print("\n[bold]Fetching torrent details for metadata extraction...[/bold]")

    # Fetch metadata from detail pages
    torrents = fetch_metadata_for_torrents(torrents)

    console.print("\n[bold]Grouping torrents by metadata...[/bold]")

    # Group deterministically
    return group_torrents_deterministic(torrents, anime_name)
