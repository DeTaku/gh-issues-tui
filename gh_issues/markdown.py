"""Minimal Markdown renderer for terminal display.

Handles the subset of Markdown common in GitHub issue bodies and comments:
  - ATX headings (# / ## / ###)
  - Bullet lists (-, *, +)
  - Numbered lists
  - Bold (**text** or __text__)
  - Italic (*text* or _text_)
  - Inline code (`code`)
  - Fenced code blocks (``` or ~~~)
  - Links: [text](url) → "text  <url>"
  - Blockquotes (> ...)
  - Horizontal rules (--- / ***)
  - Bare URLs are left as-is

Output is a list of RenderedLine named tuples, each containing a plain
string and a style tag understood by the UI layer.  No curses imports here
so this module is independently testable.

Public surface:
    render(text, width) -> list[RenderedLine]
"""

import re
import textwrap
from typing import NamedTuple

# Style tags interpreted by the UI layer.
STYLE_NORMAL = "normal"
STYLE_HEADING1 = "heading1"
STYLE_HEADING2 = "heading2"
STYLE_HEADING3 = "heading3"
STYLE_CODE = "code"
STYLE_DIM = "dim"
STYLE_RULE = "rule"


class RenderedLine(NamedTuple):
    text: str
    style: str = STYLE_NORMAL


def render(text: str, width: int) -> list[RenderedLine]:
    """Render markdown text into a list of terminal-ready lines."""
    if not text:
        return []
    lines = _split_into_blocks(text)
    result: list[RenderedLine] = []
    for line in lines:
        result.extend(_render_line(line, width))
    return result


# ------------------------------------------------------------------
# Block parsing
# ------------------------------------------------------------------

def _split_into_blocks(text: str) -> list[str]:
    """Normalise line endings and return raw lines."""
    return text.replace("\r\n", "\n").replace("\r", "\n").split("\n")


def _render_line(raw: str, width: int) -> list[RenderedLine]:
    """Convert one raw markdown line into one or more RenderedLines."""
    # Fenced code block start/end is handled in render() via state;
    # here we just deal with single-line content that arrives pre-classified.
    # (Code block state is threaded through render() below.)
    # This function is called for non-code-block lines.

    stripped = raw.rstrip()

    # Empty line
    if not stripped:
        return [RenderedLine("", STYLE_NORMAL)]

    # ATX headings
    heading_match = re.match(r"^(#{1,6})\s+(.*)", stripped)
    if heading_match:
        level = len(heading_match.group(1))
        content = _strip_inline(heading_match.group(2))
        style = (
            STYLE_HEADING1 if level == 1
            else STYLE_HEADING2 if level == 2
            else STYLE_HEADING3
        )
        return [RenderedLine(content, style)]

    # Horizontal rule
    if re.match(r"^(\*{3,}|-{3,}|_{3,})\s*$", stripped):
        return [RenderedLine("─" * min(width, 60), STYLE_RULE)]

    # Blockquote
    if stripped.startswith("> "):
        content = _strip_inline(stripped[2:])
        return _wrap("│ " + content, width, STYLE_DIM)

    # Bullet list
    bullet = re.match(r"^(\s*)([-*+])\s+(.*)", stripped)
    if bullet:
        indent = len(bullet.group(1))
        content = _strip_inline(bullet.group(3))
        prefix = "  " * (indent // 2) + "• "
        return _wrap(prefix + content, width, STYLE_NORMAL)

    # Numbered list
    numbered = re.match(r"^(\s*)(\d+)\.\s+(.*)", stripped)
    if numbered:
        indent = len(numbered.group(1))
        num = numbered.group(2)
        content = _strip_inline(numbered.group(3))
        prefix = "  " * (indent // 2) + f"{num}. "
        return _wrap(prefix + content, width, STYLE_NORMAL)

    # Default paragraph text
    return _wrap(_strip_inline(stripped), width, STYLE_NORMAL)


def _strip_inline(text: str) -> str:
    """Remove inline markdown markers, expanding links."""
    # Links: [text](url) → text <url>
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 <\2>", text)
    # Bold with **
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    # Bold with __
    text = re.sub(r"__(.+?)__", r"\1", text)
    # Italic with *
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    # Italic with _
    text = re.sub(r"_([^_]+)_", r"\1", text)
    # Inline code
    text = re.sub(r"`([^`]+)`", r"[\1]", text)
    # Strikethrough
    text = re.sub(r"~~(.+?)~~", r"\1", text)
    return text


def _wrap(text: str, width: int, style: str) -> list[RenderedLine]:
    """Word-wrap text to width, returning one RenderedLine per line."""
    if width < 10:
        return [RenderedLine(text, style)]
    wrapped = textwrap.wrap(text, width=width, break_long_words=True)
    if not wrapped:
        return [RenderedLine("", style)]
    return [RenderedLine(line, style) for line in wrapped]


# ------------------------------------------------------------------
# Override render() with stateful fenced-code-block handling
# ------------------------------------------------------------------

def render(text: str, width: int) -> list[RenderedLine]:  # noqa: F811
    """Render markdown text into a list of terminal-ready lines."""
    if not text:
        return []

    raw_lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    result: list[RenderedLine] = []
    in_code_block = False
    fence_pattern = re.compile(r"^(```|~~~)")

    for raw in raw_lines:
        if fence_pattern.match(raw.rstrip()):
            in_code_block = not in_code_block
            # Don't emit the fence line itself.
            continue

        if in_code_block:
            # Preserve code lines verbatim, indent by 2 spaces.
            result.append(RenderedLine("  " + raw.rstrip(), STYLE_CODE))
        else:
            result.extend(_render_line(raw, width))

    return result
