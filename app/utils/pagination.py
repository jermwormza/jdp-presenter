"""Pagination: reflow a ServiceItem's text into pages that actually fit the output canvas.

Given the effective theme's font (and a live font_scale nudge from the Output toolbar), each
item's underlying text is word-wrapped and chunked into pages of whatever height fits inside the
canvas margins. Preview and Output call this with the same inputs so they always agree on how
many pages an item has.
"""
from __future__ import annotations

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QFont, QFontMetrics

from app.models.service import AudioItem, ImageItem, PdfItem, PptxItem, ScriptureItem, SongItem, TextItem, VideoItem
from app.models.theme import ServiceTheme, TextStyle

MARGIN = 60

_SUPERSCRIPT_DIGITS = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")


def superscript_number(number: int) -> str:
    """Render a verse number as Unicode superscript digits, e.g. 16 -> "¹⁶"."""
    return str(number).translate(_SUPERSCRIPT_DIGITS)


def format_scripture_text(item: ScriptureItem) -> str:
    """Preserve source poetry line breaks and mark transitions to or from prose."""
    chunks: list[str] = []
    previous_was_poetry: bool | None = None
    for verse in item.verses:
        text = verse.text.strip()
        is_poetry = "\n" in text
        separator = "\n\n" if previous_was_poetry is not None and is_poetry != previous_was_poetry else (
            "\n" if is_poetry else " "
        )
        if chunks:
            chunks.append(separator)
        verse_number = superscript_number(verse.verse)
        if is_poetry:
            source_lines = text.split("\n")
            poetry_indent = " " * (len(verse_number) + 1)
            text = "\n".join(
                [
                    source_lines[0],
                    *(
                        f"{poetry_indent}{line.lstrip()}" if line.strip() else ""
                        for line in source_lines[1:]
                    ),
                ]
            )
        chunks.append(f"{verse_number} {text}")
        previous_was_poetry = is_poetry
    return "".join(chunks)


def font_for_style(style: TextStyle, font_scale: float = 1.0) -> QFont:
    font = QFont(style.font_family, max(1, round(style.font_size * font_scale)))
    font.setBold(style.font_weight == "bold")
    font.setItalic(style.font_style == "italic")
    return font


def _wrap_text_to_lines(text: str, metrics: QFontMetrics, max_width: int) -> list[str]:
    lines: list[str] = []
    paragraphs = text.split("\n")
    for paragraph_index, paragraph in enumerate(paragraphs):
        leading_spaces = len(paragraph) - len(paragraph.lstrip(" "))
        first_prefix = " " * leading_spaces
        stripped = paragraph.lstrip(" ")
        verse_number = stripped.partition(" ")[0]
        next_is_poetry_line = (
            paragraph_index + 1 < len(paragraphs)
            and paragraphs[paragraph_index + 1].startswith(" ")
        )
        starts_poetry_verse = (
            next_is_poetry_line
            and verse_number
            and all(character in "⁰¹²³⁴⁵⁶⁷⁸⁹" for character in verse_number)
        )
        if starts_poetry_verse:
            continuation_prefix = " " * (len(verse_number) + 3)
        elif leading_spaces:
            continuation_prefix = first_prefix + "  "
        else:
            continuation_prefix = ""
        words = stripped.split()
        current = first_prefix
        for word in words:
            separator = "" if current.endswith(" ") or not current else " "
            candidate = f"{current}{separator}{word}"
            if current.strip() and metrics.horizontalAdvance(candidate) > max_width:
                lines.append(current.rstrip())
                current = f"{continuation_prefix}{word}"
            else:
                current = candidate
        lines.append(current.rstrip())
    return lines


def _paginate_lines(lines: list[str], max_lines_per_page: int) -> list[str]:
    max_lines_per_page = max(1, max_lines_per_page)
    pages = ["\n".join(lines[start : start + max_lines_per_page]) for start in range(0, len(lines), max_lines_per_page)]
    return pages or [""]


def _starts_verse(line: str) -> bool:
    verse_number = line.partition(" ")[0]
    return bool(verse_number) and all(
        character in "⁰¹²³⁴⁵⁶⁷⁸⁹" for character in verse_number
    )


def _paginate_scripture_lines(lines: list[str], max_lines_per_page: int) -> list[str]:
    max_lines_per_page = max(1, max_lines_per_page)
    units: list[tuple[list[str], bool]] = []
    line_index = 0
    while line_index < len(lines):
        starts_poetry_verse = (
            _starts_verse(lines[line_index])
            and line_index + 1 < len(lines)
            and lines[line_index + 1].startswith(" ")
        )
        if not starts_poetry_verse:
            units.append(([lines[line_index]], False))
            line_index += 1
            continue

        verse_lines = [lines[line_index]]
        line_index += 1
        while line_index < len(lines) and not _starts_verse(lines[line_index]):
            verse_lines.append(lines[line_index])
            line_index += 1
        units.append((verse_lines, True))

    pages: list[str] = []
    current_page: list[str] = []
    for unit_lines, keep_together in units:
        if (
            keep_together
            and len(unit_lines) <= max_lines_per_page
            and current_page
            and len(current_page) + len(unit_lines) > max_lines_per_page
        ):
            pages.append("\n".join(current_page))
            current_page = []
        for line in unit_lines:
            if len(current_page) == max_lines_per_page:
                pages.append("\n".join(current_page))
                current_page = []
            current_page.append(line)
    if current_page:
        pages.append("\n".join(current_page))
    return pages or [""]


def _text_pages(
    text: str,
    style: TextStyle,
    canvas_size: QSize,
    font_scale: float,
    *,
    keep_poetry_verses_together: bool = False,
) -> list[str]:
    metrics = QFontMetrics(font_for_style(style, font_scale))
    max_width = max(1, canvas_size.width() - 2 * MARGIN)
    max_height = max(1, canvas_size.height() - 2 * MARGIN)
    line_height = metrics.lineSpacing() or 1
    max_lines = max(1, max_height // line_height)
    lines = _wrap_text_to_lines(text, metrics, max_width)
    if keep_poetry_verses_together:
        return _paginate_scripture_lines(lines, max_lines)
    return _paginate_lines(lines, max_lines)


def autofit_font_size(
    text: str,
    style: TextStyle,
    canvas_size: QSize,
    font_scale: float = 1.0,
    min_size: int = 12,
    max_size: int = 300,
) -> int:
    """Largest font size (capped by font_scale) whose text still fits the canvas without clipping.

    Uses QFontMetrics.boundingRect with the exact same TextWordWrap flag drawText will use, so the
    fitted size can never cause Qt to clip a line at paint time (which would look like "lost"
    lines/line-breaks if a naive word-wrap estimate diverged from Qt's own text layout).
    """
    max_width = max(1, canvas_size.width() - 2 * MARGIN)
    max_height = max(1, canvas_size.height() - 2 * MARGIN)
    cap = max(min_size, round(max_size * font_scale))

    best = min_size
    lo, hi = min_size, cap
    while lo <= hi:
        mid = (lo + hi) // 2
        font = QFont(style.font_family, mid)
        font.setBold(style.font_weight == "bold")
        font.setItalic(style.font_style == "italic")
        metrics = QFontMetrics(font)
        # Tall probe rect: boundingRect wraps freely without clipping so we get the true required height.
        probe_rect = QRect(0, 0, max_width, 10_000_000)
        required_height = metrics.boundingRect(probe_rect, Qt.TextFlag.TextWordWrap, text).height()
        if required_height <= max_height:
            best = mid
            lo = mid + 1
        else:
            hi = mid - 1
    return best


def paginate_item(item, theme: ServiceTheme, canvas_size: QSize, font_scale: float = 1.0) -> list[str]:
    if isinstance(item, ScriptureItem):
        # Verses always flow continuously (joined by a single space) between each other — poetic
        # structure is never forced globally. Instead, each verse's OWN embedded line breaks (real
        # "\n" characters already present in the source text for poetic passages like Psalms, and
        # absent for prose) are preserved as-is, so poetic vs continuous style is entirely
        # data-driven per verse rather than a blanket theme setting.
        text = format_scripture_text(item)
        return _text_pages(
            text,
            theme.scripture.verse_text,
            canvas_size,
            font_scale,
            keep_poetry_verses_together=True,
        )
    if isinstance(item, SongItem):
        # Exactly one page per authored verse/chorus slide — never merged, never split.
        return [slide.content for slide in item.slides] or [""]
    if isinstance(item, TextItem):
        return _text_pages(item.content, theme.scripture.verse_text, canvas_size, font_scale)
    if isinstance(item, (ImageItem, VideoItem, AudioItem, PdfItem, PptxItem)):
        return [""]
    return [""]
