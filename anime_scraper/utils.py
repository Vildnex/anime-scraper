"""Shared utilities for anime scraper."""

from rich.console import Console

# Shared console instance for all modules
console = Console()

# Dub detection keywords (used for search and filtering)
# Note: "dual" alone indicates dual audio (English + Japanese)
DUB_KEYWORDS = ["dub", "dubbed", "dual audio", "dual", "english dub"]

# Language keywords for filtering torrents
# Maps language name to keywords that indicate that language in torrent names
AUDIO_LANGUAGES = {
    "any": [],  # No filtering
    "english": ["english dub", "eng dub", "dubbed", "dual audio", "dual", "dub"],
    "japanese": ["japanese", "jpn", "raw"],
    "spanish": ["spanish dub", "latino", "castellano", "esp dub"],
    "portuguese": ["portuguese", "pt-br", "brazilian"],
    "french": ["french dub", "vf", "french"],
    "german": ["german dub", "german"],
    "italian": ["italian dub", "italian"],
    "chinese": ["chinese dub", "mandarin", "cantonese"],
}

SUBTITLE_LANGUAGES = {
    "any": [],  # No filtering
    "english": ["eng sub", "english sub", "engsub", "[eng]", "english"],
    "spanish": ["spanish sub", "esp sub", "spanish"],
    "portuguese": ["portuguese sub", "pt-br sub", "portuguese"],
    "french": ["french sub", "vostfr", "french"],
    "german": ["german sub", "german"],
    "italian": ["italian sub", "italian"],
    "chinese": ["chinese sub", "chi sub", "chinese"],
    "arabic": ["arabic sub", "arabic"],
    "multi": ["multi-sub", "multisub", "multi sub", "multi-subs"],
}


def parse_int_safe(text: str) -> int:
    """Parse an integer from text, returning 0 if invalid."""
    text = text.strip()
    return int(text) if text.isdigit() else 0


def contains_dub_keywords(name: str) -> bool:
    """Check if a torrent name contains dub-related keywords."""
    name_lower = name.lower()
    return any(kw in name_lower for kw in DUB_KEYWORDS)


def sanitize_filename(name: str, max_length: int = 100) -> str:
    """Sanitize a string for use as a filename."""
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        name = name.replace(char, "_")
    return name[:max_length]


def matches_language(name: str, language: str, language_dict: dict) -> bool:
    """Check if a torrent name matches the specified language keywords."""
    if language == "any":
        return True

    keywords = language_dict.get(language, [])
    if not keywords:
        return True

    name_lower = name.lower()
    return any(kw in name_lower for kw in keywords)


def filter_by_language(
    torrents: list, audio_lang: str = "any", sub_lang: str = "any"
) -> list:
    """
    Filter torrents by audio and subtitle language preferences.

    Args:
        torrents: List of Torrent objects
        audio_lang: Preferred audio language (e.g., "english", "japanese", "any")
        sub_lang: Preferred subtitle language (e.g., "english", "spanish", "any")

    Returns:
        Filtered list of torrents matching the language preferences
    """
    if audio_lang == "any" and sub_lang == "any":
        return torrents

    return [
        torrent for torrent in torrents
        if matches_language(torrent.name, audio_lang, AUDIO_LANGUAGES)
        and matches_language(torrent.name, sub_lang, SUBTITLE_LANGUAGES)
    ]
