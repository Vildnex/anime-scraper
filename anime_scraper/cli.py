"""CLI interface for anime scraper using Typer."""

from pathlib import Path

import typer
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich import box

from . import __version__
from .scraper import search_nyaa, CATEGORIES
from .grouper import group_torrents_with_metadata
from .downloader import create_combined_output, DownloadError
from .models import TorrentGroup
from .utils import console, filter_by_language, AUDIO_LANGUAGES, SUBTITLE_LANGUAGES

app = typer.Typer(
    name="anime-scraper",
    help="Search, group, and download anime torrents from nyaa.si",
    add_completion=False,
)


def display_banner():
    """Display the application banner."""
    banner = """
    ANIME SCRAPER
    Search, Group & Download Anime from Nyaa.si
    Deterministic Grouping
    """
    console.print(Panel(banner, style="bold blue", box=box.DOUBLE))


def display_groups_table(groups: list[TorrentGroup]) -> None:
    """Display groups in a nice table format."""
    table = Table(
        title="Torrent Groups",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold magenta",
    )

    table.add_column("#", style="dim", width=4)
    table.add_column("Group Name", style="cyan", min_width=30)
    table.add_column("Season", style="white", width=8)
    table.add_column("Episodes", style="green", width=12)
    table.add_column("Quality", style="yellow", width=10)
    table.add_column("Dubbed", style="blue", width=8)
    table.add_column("Torrents", style="magenta", width=10)
    table.add_column("Total Seeders", style="green", width=12)

    for i, group in enumerate(groups, 1):
        # Get season from first torrent's metadata
        season_display = "S1"
        if group.torrents and group.torrents[0].metadata:
            season_display = group.torrents[0].metadata.season_short()

        table.add_row(
            str(i),
            group.name[:40] + "..." if len(group.name) > 40 else group.name,
            season_display,
            group.episode_range or "Various",
            group.quality or "Mixed",
            "Yes" if group.is_dubbed else "No",
            str(len(group.torrents)),
            str(group.total_seeders),
        )

    console.print(table)


def display_group_details(group: TorrentGroup) -> None:
    """Display detailed information about a group."""
    console.print(f"\n[bold cyan]Group: {group.name}[/bold cyan]")
    console.print(f"[dim]{group.description}[/dim]\n")

    table = Table(
        title="Torrents in this group",
        box=box.SIMPLE,
        show_header=True,
        header_style="bold",
    )

    table.add_column("#", style="dim", width=4)
    table.add_column("Name", style="white", min_width=50)
    table.add_column("Size", style="cyan", width=12)
    table.add_column("S", style="green", width=6)
    table.add_column("L", style="red", width=6)

    for i, torrent in enumerate(group.torrents, 1):
        name_display = (
            torrent.name[:60] + "..." if len(torrent.name) > 60 else torrent.name
        )
        table.add_row(
            str(i),
            name_display,
            torrent.size,
            str(torrent.seeders),
            str(torrent.leechers),
        )

    console.print(table)


def _parse_language_choice(choice: str, options: list[str]) -> str:
    """Parse a language choice input (number or name) against available options."""
    try:
        idx = int(choice)
        return options[idx] if 0 <= idx < len(options) else "any"
    except ValueError:
        return choice.lower() if choice.lower() in options else "any"


def _prompt_language_options(label: str, options: list[str]) -> str:
    """Display language options and prompt for selection."""
    console.print(f"\n[cyan]{label} Language Options:[/cyan]")
    for i, lang in enumerate(options):
        console.print(f"  {i}. {lang.capitalize()}")

    choice = Prompt.ask(
        f"\nSelect {label.lower()} language (number or name)",
        default="0",
    )
    return _parse_language_choice(choice, options)


def prompt_language_preference() -> tuple[str, str]:
    """
    Interactive prompt to ask user about language preferences.

    Returns:
        Tuple of (audio_language, subtitle_language)
    """
    console.print("\n[bold]Language Preferences[/bold]")
    console.print("[dim]Filter torrents by audio and subtitle language[/dim]")

    audio_lang = _prompt_language_options("Audio", list(AUDIO_LANGUAGES.keys()))
    sub_lang = _prompt_language_options("Subtitle", list(SUBTITLE_LANGUAGES.keys()))

    console.print(f"\n[green]Selected: Audio={audio_lang.capitalize()}, Subtitles={sub_lang.capitalize()}[/green]")

    return audio_lang, sub_lang


def interactive_group_selection(groups: list[TorrentGroup]) -> TorrentGroup | None:
    """Interactive prompt for selecting a group."""
    while True:
        console.print("\n[bold]Options:[/bold]")
        console.print("  [cyan]1-{n}[/cyan] - View group details and download options")
        console.print("  [cyan]q[/cyan]     - Quit without downloading")

        choice = Prompt.ask("\nSelect a group number to view details", default="q")

        if choice.lower() == "q":
            return None

        try:
            group_num = int(choice)
            if 1 <= group_num <= len(groups):
                selected_group = groups[group_num - 1]
                display_group_details(selected_group)

                if Confirm.ask("\nDownload this group?", default=True):
                    return selected_group
                else:
                    console.print("[dim]Returning to group selection...[/dim]")
            else:
                console.print(
                    f"[red]Please enter a number between 1 and {len(groups)}[/red]"
                )
        except ValueError:
            console.print("[red]Invalid input. Please enter a number or 'q'.[/red]")


@app.command()
def search(
    anime_name: str = typer.Argument(..., help="Name of the anime to search for"),
    dub: bool = typer.Option(
        False, "--dub", "-d", help="Filter for English dubbed content only"
    ),
    max_pages: int = typer.Option(
        5, "--pages", "-p", help="Maximum number of search result pages to fetch"
    ),
    category: str = typer.Option(
        "anime_english",
        "--category",
        "-c",
        help="Category to search in (anime, anime_english, anime_raw)",
    ),
    output_dir: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Directory to save downloaded files",
    ),
    no_submitters: bool = typer.Option(
        False,
        "--no-submitters",
        help="Skip fetching submitter info (faster but less accurate grouping)",
    ),
):
    """
    Search for anime torrents on nyaa.si.

    This command will:
    1. Search nyaa.si for the specified anime
    2. Ask for language preferences (audio/subtitle) and filter results
    3. Extract metadata from detail pages and group deterministically
    4. Present groups for interactive selection
    5. Download selected group and create a magnet bundle
    """
    display_banner()

    console.print(f"\n[bold]Searching for:[/bold] {anime_name}")
    if dub:
        console.print("[bold yellow]Filter:[/bold yellow] English Dubbed only")

    # Step 1: Search nyaa.si
    console.print("\n[bold]Step 1: Searching nyaa.si...[/bold]")
    torrents = search_nyaa(
        query=anime_name,
        category=category,
        max_pages=max_pages,
        dub_only=dub,
        fetch_submitters=not no_submitters,
    )

    if not torrents:
        console.print("[red]No torrents found. Try a different search term.[/red]")
        raise typer.Exit(1)

    # Step 2: Language preference filter
    console.print("\n[bold]Step 2: Language Preferences[/bold]")
    audio_lang, sub_lang = prompt_language_preference()

    # Apply language filter
    if audio_lang != "any" or sub_lang != "any":
        filtered_torrents = filter_by_language(torrents, audio_lang, sub_lang)
        console.print(
            f"[dim]Filtered: {len(filtered_torrents)}/{len(torrents)} torrents match your language preferences[/dim]"
        )

        if not filtered_torrents:
            console.print(
                "[yellow]No torrents match your language preferences. Using all results.[/yellow]"
            )
            filtered_torrents = torrents
    else:
        filtered_torrents = torrents

    # Step 3: Extract metadata and group deterministically
    console.print("\n[bold]Step 3: Extracting metadata and grouping...[/bold]")
    groups = group_torrents_with_metadata(filtered_torrents, anime_name)

    if not groups:
        console.print("[red]Failed to create groups.[/red]")
        raise typer.Exit(1)

    # Step 4: Display groups
    console.print("\n[bold]Step 4: Select a group to download[/bold]")
    display_groups_table(groups)

    # Step 5: Interactive selection
    selected_group = interactive_group_selection(groups)

    if not selected_group:
        console.print("[yellow]No group selected. Exiting.[/yellow]")
        raise typer.Exit(0)

    # Step 6: Download
    console.print(f"\n[bold]Step 5: Downloading group: {selected_group.name}[/bold]")

    download_torrents = Confirm.ask("Download .torrent files?", default=True)
    create_bundle = Confirm.ask("Create magnet bundle file?", default=True)

    if not download_torrents and not create_bundle:
        console.print("[yellow]Nothing to do. Exiting.[/yellow]")
        raise typer.Exit(0)

    try:
        result = create_combined_output(
            group=selected_group,
            download_dir=output_dir,
            download_torrents=download_torrents,
            create_bundle=create_bundle,
        )
    except DownloadError as e:
        console.print(f"[red]Download error: {e}[/red]")
        raise typer.Exit(1)

    # Summary
    console.print("\n" + "=" * 60)
    console.print("[bold green]Download Complete![/bold green]")
    console.print("=" * 60)

    if result["torrent_files"]:
        console.print(
            f"\n[cyan]Torrent files:[/cyan] {len(result['torrent_files'])} downloaded"
        )
    if result["magnet_bundle"]:
        console.print(f"[cyan]Magnet bundle:[/cyan] {result['magnet_bundle']}")
    console.print(f"[cyan]Output directory:[/cyan] {result['output_dir']}")

    console.print("\n[bold]Next steps:[/bold]")
    console.print("  1. Open the magnet bundle in your torrent client")
    console.print("  2. Or add individual .torrent files to your client")


@app.command()
def version():
    """Show the version number."""
    console.print(f"anime-scraper version {__version__}")


@app.command()
def categories():
    """List available categories."""
    table = Table(title="Available Categories", box=box.ROUNDED)
    table.add_column("Name", style="cyan")
    table.add_column("Code", style="dim")

    for name, code in CATEGORIES.items():
        table.add_row(name, code)

    console.print(table)


if __name__ == "__main__":
    app()
