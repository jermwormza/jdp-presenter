"""Export a Service as a plain-text outline or a full Markdown document."""
from __future__ import annotations

from app.models.service import PdfItem, ScriptureItem, Service, TextItem


def generate_outline(service: Service) -> str:
    lines = [f"SERVICE OUTLINE: {service.name}", f"Date: {service.date}", ""]
    for index, item in enumerate(service.items, start=1):
        suffix = f" ({len(item.slides)}V)" if item.type == "song" else ""
        lines.append(f"{index}. {item.title}{suffix}")
    return "\n".join(lines)


def _format_scripture_verses(item: ScriptureItem) -> str:
    """Format scripture verses with verse numbers in <sup> tags, preserving poetic structure."""
    if not item.verses:
        return ""

    lines = []

    for verse in item.verses:
        # Format verse with <sup> tag for verse number
        # Escape any markdown special chars in verse text, but preserve line breaks for poetry
        verse_text = verse.text.replace("*", r"\*").replace("_", r"\_").replace("[", r"\[").replace("]", r"\]")
        lines.append(f"<sup>{verse.verse}</sup> {verse_text}")

    return "\n".join(lines)


def generate_full_markdown(service: Service) -> str:
    lines = [f"# {service.name}", f"**Date:** {service.date}", "", "---", ""]

    for index, item in enumerate(service.items, start=1):
        lines.append(f"## {index}. {item.title}")

        if item.type == "scripture":
            # Use verses array for proper verse numbering with <sup> tags
            # Don't duplicate reference - it's already in the title
            formatted = _format_scripture_verses(item)
            if formatted:
                lines.append(formatted)
                lines.append("")
        elif item.type == "song":
            lines.append("*Song Lyrics*")
            lines.append("")
            for slide in item.slides:
                if slide.label:
                    lines.append(f"### {slide.label}")
                # Preserve line breaks in lyrics: convert \n to markdown hard line breaks (two spaces + newline)
                content = slide.content.replace("\n", "  \n")
                lines.append(content)
                lines.append("")
        elif isinstance(item, TextItem):
            lines.append("")
            lines.append(item.content)
            lines.append("")
        elif item.type == "image":
            lines.append(f"*[Image: {item.title}]*")
            lines.append("")
        elif item.type == "video":
            lines.append(f"*[Video: {item.title}]*")
        elif isinstance(item, PdfItem):
            lines.append(f"*[PDF: {item.title} - {len(item.slides)} pages]*")
            lines.append("")
        else:
            lines.append("*[Generic Item]*")
            lines.append("")

        lines.append("---")
        lines.append("")
    return "\n".join(lines)
