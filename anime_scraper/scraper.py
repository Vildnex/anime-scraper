"""Nyaa.si scraper module."""

from urllib.parse import urlencode

import httpx
from bs4 import BeautifulSoup
from rich.progress import Progress, SpinnerColumn, TextColumn

from .cache import CachedHTTPClient
from .models import Torrent
from .utils import console, parse_int_safe, contains_dub_keywords, DUB_KEYWORDS

BASE_URL = "https://nyaa.si"

# Category codes for nyaa.si
CATEGORIES = {
    "all": "0_0",
    "anime": "1_0",
    "anime_amv": "1_1",
    "anime_english": "1_2",
    "anime_non_english": "1_3",
    "anime_raw": "1_4",
}

# Filter codes
FILTERS = {
    "no_filter": "0",
    "no_remakes": "1",
    "trusted": "2",
}


def build_search_url(
    query: str,
    category: str = "anime_english",
    filter_type: str = "no_filter",
    page: int = 1,
    sort_by: str = "seeders",
    order: str = "desc",
) -> str:
    """Build a search URL for nyaa.si."""
    params = {
        "f": FILTERS.get(filter_type, "0"),
        "c": CATEGORIES.get(category, "1_2"),
        "q": query,
        "s": sort_by,
        "o": order,
        "p": page,
    }
    return f"{BASE_URL}/?{urlencode(params)}"


def _extract_category(cols: list) -> str:
    """Extract category from the first column."""
    category_link = cols[0].find("a")
    return category_link.get("title", "") if category_link else ""


def _extract_name_and_id(cols: list) -> tuple[str, str] | None:
    """Extract torrent name and ID from the second column."""
    name_col = cols[1]
    name_links = name_col.find_all("a")

    for link in name_links:
        href = link.get("href", "")
        if href.startswith("/view/") and "comments" not in href:
            name = link.get_text(strip=True)
            torrent_id = href.split("/")[-1]
            return name, torrent_id
    return None


def _extract_links(cols: list) -> tuple[str, str]:
    """Extract magnet and torrent download links from the third column."""
    links_col = cols[2]

    magnet_link = links_col.find("a", href=lambda x: x and x.startswith("magnet:"))
    magnet = magnet_link.get("href", "") if magnet_link else ""

    torrent_download = links_col.find("a", href=lambda x: x and x.endswith(".torrent"))
    torrent_url = (
        f"{BASE_URL}{torrent_download.get('href', '')}" if torrent_download else ""
    )

    return magnet, torrent_url


def parse_torrent_row(row: BeautifulSoup) -> Torrent | None:
    """Parse a single torrent row from the search results table."""
    try:
        cols = row.find_all("td")
        if len(cols) < 8:
            return None

        # Extract data from columns
        category = _extract_category(cols)
        name_data = _extract_name_and_id(cols)
        if not name_data:
            return None
        name, torrent_id = name_data

        magnet, torrent_url = _extract_links(cols)

        return Torrent(
            id=torrent_id,
            name=name,
            magnet=magnet,
            torrent_url=torrent_url,
            size=cols[3].get_text(strip=True),
            date=cols[4].get_text(strip=True),
            seeders=parse_int_safe(cols[5].get_text(strip=True)),
            leechers=parse_int_safe(cols[6].get_text(strip=True)),
            downloads=parse_int_safe(cols[7].get_text(strip=True)),
            category=category,
        )
    except Exception as e:
        console.print(f"[yellow]Warning: Failed to parse row: {e}[/yellow]")
        return None


def get_submitter_for_torrent(client: httpx.Client | CachedHTTPClient, torrent_id: str) -> str:
    """Fetch the submitter name from the torrent detail page."""
    try:
        response = client.get(f"{BASE_URL}/view/{torrent_id}")
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "lxml")

        rows = soup.select(".panel-body .row")
        for row in rows:
            label = row.find(class_="col-md-1")
            if label and "Submitter:" in label.get_text():
                value = row.find(class_="col-md-5")
                if value:
                    return value.get_text(strip=True)
        return "Anonymous"
    except Exception:
        return "Anonymous"


def search_nyaa(
    query: str,
    category: str = "anime_english",
    filter_type: str = "no_filter",
    max_pages: int = 5,
    dub_only: bool = False,
    fetch_submitters: bool = True,
) -> list[Torrent]:
    """
    Search nyaa.si for torrents.

    Args:
        query: Search query (anime name)
        category: Category to search in
        filter_type: Filter type (no_filter, no_remakes, trusted)
        max_pages: Maximum number of pages to fetch
        dub_only: If True, filter for dubbed content
        fetch_submitters: If True, fetch submitter info for each torrent

    Returns:
        List of Torrent objects
    """
    torrents: list[Torrent] = []

    # Add dub keywords to search if requested
    search_query = query
    if dub_only:
        dub_terms = " OR ".join(DUB_KEYWORDS[:3])  # Use first 3 keywords for search
        search_query = f"{query} ({dub_terms})"

    with CachedHTTPClient(current_query=search_query, timeout=30.0, follow_redirects=True) as client:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Searching nyaa.si...", total=None)

            page = 1
            while page <= max_pages:
                progress.update(task, description=f"Fetching page {page}...")

                url = build_search_url(search_query, category, filter_type, page=page)

                try:
                    response = client.get(url)
                    response.raise_for_status()
                except httpx.HTTPError as e:
                    console.print(f"[red]HTTP error fetching page {page}: {e}[/red]")
                    break

                soup = BeautifulSoup(response.text, "lxml")

                table = soup.find("table", class_="torrent-list")
                if not table:
                    break

                tbody = table.find("tbody")
                if not tbody:
                    break

                rows = tbody.find_all("tr")
                if not rows:
                    break

                page_torrents = []
                for row in rows:
                    torrent = parse_torrent_row(row)
                    if torrent:
                        if dub_only and not contains_dub_keywords(torrent.name):
                            continue
                        page_torrents.append(torrent)

                if not page_torrents:
                    break

                torrents.extend(page_torrents)
                page += 1

            if fetch_submitters and torrents:
                progress.update(task, description="Fetching submitter info...")
                for i, torrent in enumerate(torrents):
                    progress.update(
                        task,
                        description=f"Fetching submitter {i + 1}/{len(torrents)}...",
                    )
                    torrent.submitter = get_submitter_for_torrent(client, torrent.id)

    console.print(f"[green]Found {len(torrents)} torrents[/green]")
    return torrents
