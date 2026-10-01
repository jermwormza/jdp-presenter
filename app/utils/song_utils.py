"""Song helpers: search normalization, smart-paste parsing, and verse-order resolution."""
from __future__ import annotations

import re

from app.models.song import Verse

_PUNCTUATION_RE = re.compile(r"[^\w\s]", re.UNICODE)
_WHITESPACE_RE = re.compile(r"\s+")


def normalize_search_text(text: str) -> str:
    """Casefold, strip punctuation, and collapse whitespace so searches ignore apostrophes
    (straight or curly), commas, and spacing differences between the query and the library."""
    return _WHITESPACE_RE.sub(" ", _PUNCTUATION_RE.sub("", text)).casefold().strip()


_HEADER_RE = re.compile(
    r"^\s*(verse\s*(?P<vnum>\d+)?|chorus|bridge|pre-?chorus|tag|ending|intro)\s*:?\s*$", re.IGNORECASE
)

# Matches an already-compact label on its own line (e.g. "v1", "c", "pc2", "tag1") — the exact
# format this module itself writes back into the lyrics textarea when editing an existing song
# (see SongEditor). Without this, re-saving an imported song (e.g. from Quelea, which uses labels
# like "c1"/"pc1") would fail to recognize its own round-tripped labels as section headers, since
# they don't match the human-readable _HEADER_RE above — silently flattening every section into
# generic auto-numbered verses and losing the original verse/chorus structure.
_COMPACT_LABEL_RE = re.compile(r"^(pc|tag|v|c|b|p|t|e|i)(\d*)$", re.IGNORECASE)

_LABELS = {
    "chorus": "c",
    "bridge": "b",
    "pre-chorus": "p",
    "prechorus": "p",
    "tag": "tag",
    "ending": "e",
    "intro": "i",
}


def _label_for_header(header: str, verse_count: int) -> str:
    header_lower = header.strip().lower()
    match = _HEADER_RE.match(header)
    if match and match.group("vnum"):
        return f"v{match.group('vnum')}"
    for key, label in _LABELS.items():
        if header_lower.startswith(key):
            return label
    if header_lower.startswith("verse"):
        return f"v{verse_count + 1}"
    return header_lower or f"v{verse_count + 1}"


def smart_paste_lyrics(text: str) -> list[Verse]:
    """Split pasted lyrics into verses using blank-line-separated paragraphs and optional headers."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]
    verses: list[Verse] = []
    auto_verse_count = 0

    for paragraph in paragraphs:
        lines = paragraph.splitlines()
        first_line = lines[0].strip()
        compact_match = _COMPACT_LABEL_RE.match(first_line)
        if compact_match and len(lines) > 1:
            label = first_line.lower()
            body = "\n".join(lines[1:]).strip()
        elif _HEADER_RE.match(first_line) and len(lines) > 1:
            label = _label_for_header(first_line, auto_verse_count)
            body = "\n".join(lines[1:]).strip()
        else:
            auto_verse_count += 1
            label = f"v{auto_verse_count}"
            body = paragraph

        if label.startswith("v"):
            auto_verse_count = max(auto_verse_count, int(label[1:]) if label[1:].isdigit() else auto_verse_count)

        verses.append(Verse(label=label, text=body))

    return verses


def resolve_verse_order(verses: list[Verse], order_tokens: list[str]) -> list[Verse]:
    """Match order tokens (e.g. Song.verse_order, or a "Verse order" field's text split on spaces)
    to actual verses. Tolerates a numberless token (e.g. "c") matching a numbered label (e.g. "c1")
    and vice versa, so slightly different labeling conventions across import sources still resolve
    to the right playback order instead of silently dropping sections.
    """
    by_label = {v.label.lower(): v for v in verses}
    by_prefix: dict[str, Verse] = {}
    for v in verses:
        prefix = v.label.lower().rstrip("0123456789")
        by_prefix.setdefault(prefix, v)

    resolved: list[Verse] = []
    for token in order_tokens:
        token = token.lower()
        verse = by_label.get(token) or by_prefix.get(token.rstrip("0123456789"))
        if verse is not None:
            resolved.append(verse)
    return resolved
