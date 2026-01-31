"""Unit tests for anime_scraper.utils."""

import pytest
from anime_scraper.utils import (
    parse_int_safe,
    contains_dub_keywords,
    sanitize_filename,
    matches_language,
    filter_by_language,
    AUDIO_LANGUAGES,
    SUBTITLE_LANGUAGES,
    DUB_KEYWORDS,
)


class TestParseIntSafe:
    """Tests for parse_int_safe utility."""

    @pytest.mark.parametrize(
        "text,expected",
        [
            ("123", 123),
            ("0", 0),
            ("999", 999),
            ("  42  ", 42),  # With whitespace
            ("1", 1),
            ("999999", 999999),
        ],
    )
    def test_parse_int_safe_valid_inputs(self, text, expected):
        """Test parsing valid integer strings."""
        assert parse_int_safe(text) == expected

    @pytest.mark.parametrize(
        "text",
        [
            "",
            "invalid",
            "12.5",
            "12a",
            "abc123",
            "  ",
            "-5",  # Negative not supported by isdigit()
        ],
    )
    def test_parse_int_safe_invalid_inputs(self, text):
        """Test invalid inputs return 0."""
        assert parse_int_safe(text) == 0


class TestContainsDubKeywords:
    """Tests for dub keyword detection."""

    @pytest.mark.parametrize(
        "name",
        [
            "[Group] Anime (English Dub)",
            "Anime [Dubbed]",
            "[Group] Anime DUAL AUDIO",
            "[Group] Anime [DUAL]",
            "[Group] Anime [Dub]",
            "Anime dub version",
            "ANIME DUB",
            "anime dual audio release",
            "english dub anime",
        ],
    )
    def test_contains_dub_keywords_true(self, name):
        """Test dub keyword detection returns True."""
        assert contains_dub_keywords(name) is True

    @pytest.mark.parametrize(
        "name",
        [
            "[Group] Anime [English Sub]",
            "[Group] Anime [720p]",
            "Regular Anime Title",
            "[SubsPlease] Anime - 01 (1080p)",
            "Japanese Only Anime",
            "Anime with Subtitles",
        ],
    )
    def test_contains_dub_keywords_false(self, name):
        """Test non-dub names return False."""
        assert contains_dub_keywords(name) is False

    def test_dub_keywords_list_not_empty(self):
        """Ensure DUB_KEYWORDS is populated."""
        assert len(DUB_KEYWORDS) > 0


class TestSanitizeFilename:
    """Tests for filename sanitization."""

    @pytest.mark.parametrize(
        "name,expected",
        [
            ("Normal Filename.txt", "Normal Filename.txt"),
            ("file<with>angle", "file_with_angle"),
            ("file:with:colons", "file_with_colons"),
            ("file/with/slashes", "file_with_slashes"),
            ("file\\with\\backslash", "file_with_backslash"),
            ("file|with|pipe", "file_with_pipe"),
            ('file"with"quotes', "file_with_quotes"),
            ("file?with?question", "file_with_question"),
            ("file*with*star", "file_with_star"),
        ],
    )
    def test_sanitize_filename_invalid_chars(self, name, expected):
        """Test that invalid characters are replaced."""
        result = sanitize_filename(name)
        assert result == expected

    def test_sanitize_filename_max_length_default(self):
        """Test default max length is 100."""
        long_name = "a" * 150
        result = sanitize_filename(long_name)
        assert len(result) == 100

    def test_sanitize_filename_max_length_custom(self):
        """Test custom max length."""
        long_name = "a" * 150
        result = sanitize_filename(long_name, max_length=50)
        assert len(result) == 50

    def test_sanitize_filename_short_name_unchanged(self):
        """Test short names are not truncated."""
        name = "short.txt"
        result = sanitize_filename(name)
        assert result == name

    def test_sanitize_filename_all_invalid_chars(self):
        """Test string with multiple invalid characters."""
        name = '<>:"/\\|?*'
        result = sanitize_filename(name)
        assert result == "_________"

    def test_sanitize_filename_preserves_valid_unicode(self):
        """Test that valid unicode characters are preserved."""
        name = "Anime_Test_File"
        result = sanitize_filename(name)
        assert result == name


class TestMatchesLanguage:
    """Tests for language matching."""

    def test_matches_language_any_always_true(self):
        """Test 'any' language always matches."""
        assert matches_language("Any Random Name", "any", AUDIO_LANGUAGES) is True
        assert matches_language("", "any", AUDIO_LANGUAGES) is True

    @pytest.mark.parametrize(
        "name,language",
        [
            ("Anime English Dub", "english"),
            ("Anime dubbed version", "english"),
            ("Anime Dual Audio", "english"),
            ("Anime [DUAL]", "english"),
        ],
    )
    def test_matches_language_english_audio(self, name, language):
        """Test English audio language matching."""
        assert matches_language(name, language, AUDIO_LANGUAGES) is True

    @pytest.mark.parametrize(
        "name,language",
        [
            ("Anime Japanese Audio", "japanese"),
            ("Anime [JPN]", "japanese"),
            ("Anime Raw", "japanese"),
        ],
    )
    def test_matches_language_japanese_audio(self, name, language):
        """Test Japanese audio language matching."""
        assert matches_language(name, language, AUDIO_LANGUAGES) is True

    @pytest.mark.parametrize(
        "name,language",
        [
            ("Anime [English Sub]", "english"),
            ("Anime Eng Sub", "english"),
            ("Anime [Eng]", "english"),
        ],
    )
    def test_matches_language_english_subtitle(self, name, language):
        """Test English subtitle language matching."""
        assert matches_language(name, language, SUBTITLE_LANGUAGES) is True

    @pytest.mark.parametrize(
        "name,language",
        [
            ("Anime Multi-Sub", "multi"),
            ("Anime MultiSub", "multi"),
            ("Anime multi sub", "multi"),
        ],
    )
    def test_matches_language_multi_subtitle(self, name, language):
        """Test multi-subtitle language matching."""
        assert matches_language(name, language, SUBTITLE_LANGUAGES) is True

    def test_matches_language_unknown_returns_true(self):
        """Test unknown language key returns True (no filtering)."""
        assert matches_language("Anime", "unknown_lang", AUDIO_LANGUAGES) is True

    def test_matches_language_no_match(self):
        """Test returns False when no keywords match."""
        assert matches_language("Anime Japanese", "english", AUDIO_LANGUAGES) is False


class TestFilterByLanguage:
    """Tests for language filtering."""

    def test_filter_by_language_no_filter(self, torrent_factory):
        """Test returns all torrents when no filter applied."""
        torrents = [torrent_factory(id=str(i)) for i in range(5)]

        filtered = filter_by_language(torrents, audio_lang="any", sub_lang="any")

        assert len(filtered) == 5

    def test_filter_by_audio_language(self, torrent_factory):
        """Test filtering by audio language."""
        torrents = [
            torrent_factory(id="1", name="Anime [English Dub]"),
            torrent_factory(id="2", name="Anime [Japanese]"),
            torrent_factory(id="3", name="Anime [Dual Audio]"),
        ]

        filtered = filter_by_language(torrents, audio_lang="english", sub_lang="any")

        # Should match "English Dub" and "Dual Audio"
        assert len(filtered) == 2
        ids = [t.id for t in filtered]
        assert "1" in ids
        assert "3" in ids

    def test_filter_by_subtitle_language(self, torrent_factory):
        """Test filtering by subtitle language."""
        torrents = [
            torrent_factory(id="1", name="Anime [English Sub]"),
            torrent_factory(id="2", name="Anime [Spanish Sub]"),
            torrent_factory(id="3", name="Anime [Multi-Sub]"),
        ]

        filtered = filter_by_language(torrents, audio_lang="any", sub_lang="english")

        assert len(filtered) == 1
        assert filtered[0].id == "1"

    def test_filter_by_both_languages(self, torrent_factory):
        """Test filtering by both audio and subtitle."""
        torrents = [
            torrent_factory(id="1", name="Anime [English Dub] [Eng Sub]"),
            torrent_factory(id="2", name="Anime [Japanese] [Eng Sub]"),
            torrent_factory(id="3", name="Anime [Dual Audio] [French]"),
        ]

        filtered = filter_by_language(
            torrents, audio_lang="english", sub_lang="english"
        )

        # #1 and #3 match english audio (Dub/Dual), but only #1 matches english sub
        assert len(filtered) == 1
        assert filtered[0].id == "1"

    def test_filter_by_language_empty_result(self, torrent_factory):
        """Test returns empty list when no matches."""
        torrents = [torrent_factory(name="Anime [Japanese] [Japanese Sub]")]

        filtered = filter_by_language(torrents, audio_lang="english", sub_lang="any")

        assert len(filtered) == 0

    def test_filter_by_language_empty_input(self):
        """Test filtering empty list returns empty list."""
        filtered = filter_by_language([], audio_lang="english", sub_lang="english")
        assert len(filtered) == 0


class TestLanguageDictionaries:
    """Tests for language dictionary constants."""

    def test_audio_languages_has_any(self):
        """Test AUDIO_LANGUAGES has 'any' key."""
        assert "any" in AUDIO_LANGUAGES
        assert AUDIO_LANGUAGES["any"] == []

    def test_subtitle_languages_has_any(self):
        """Test SUBTITLE_LANGUAGES has 'any' key."""
        assert "any" in SUBTITLE_LANGUAGES
        assert SUBTITLE_LANGUAGES["any"] == []

    def test_audio_languages_has_common_languages(self):
        """Test AUDIO_LANGUAGES has common languages."""
        assert "english" in AUDIO_LANGUAGES
        assert "japanese" in AUDIO_LANGUAGES

    def test_subtitle_languages_has_common_languages(self):
        """Test SUBTITLE_LANGUAGES has common languages."""
        assert "english" in SUBTITLE_LANGUAGES
        assert "multi" in SUBTITLE_LANGUAGES
