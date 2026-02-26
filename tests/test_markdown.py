"""Tests for the minimal Markdown renderer."""

from gh_issues.markdown import (
    STYLE_CODE, STYLE_DIM, STYLE_HEADING1, STYLE_HEADING2, STYLE_HEADING3,
    STYLE_NORMAL, STYLE_RULE,
    RenderedLine, render,
)


def _texts(lines: list[RenderedLine]) -> list[str]:
    return [l.text for l in lines]


def _styles(lines: list[RenderedLine]) -> list[str]:
    return [l.style for l in lines]


# ------------------------------------------------------------------
# Headings
# ------------------------------------------------------------------

def test_h1_style(tmp=None) -> None:
    lines = render("# Hello", width=80)
    assert lines[0].style == STYLE_HEADING1
    assert lines[0].text == "Hello"


def test_h2_style() -> None:
    lines = render("## Sub section", width=80)
    assert lines[0].style == STYLE_HEADING2


def test_h3_style() -> None:
    lines = render("### Detail", width=80)
    assert lines[0].style == STYLE_HEADING3


def test_heading_strips_hashes() -> None:
    lines = render("# Title Text", width=80)
    assert "#" not in lines[0].text


# ------------------------------------------------------------------
# Fenced code blocks
# ------------------------------------------------------------------

def test_code_block_lines_have_code_style() -> None:
    md = "```\nprint('hello')\n```"
    lines = render(md, width=80)
    assert any(l.style == STYLE_CODE for l in lines)


def test_fence_delimiters_not_emitted() -> None:
    md = "```\ncode here\n```"
    texts = _texts(render(md, width=80))
    assert not any("```" in t for t in texts)


def test_code_block_indented() -> None:
    md = "```\nfoo()\n```"
    code_lines = [l for l in render(md, width=80) if l.style == STYLE_CODE]
    assert all(l.text.startswith("  ") for l in code_lines)


# ------------------------------------------------------------------
# Inline stripping
# ------------------------------------------------------------------

def test_bold_markers_stripped() -> None:
    lines = render("**bold text**", width=80)
    assert "**" not in lines[0].text
    assert "bold text" in lines[0].text


def test_italic_markers_stripped() -> None:
    lines = render("*italic*", width=80)
    assert "*" not in lines[0].text
    assert "italic" in lines[0].text


def test_inline_code_converted() -> None:
    lines = render("Use `os.path`", width=80)
    assert "`" not in lines[0].text
    assert "os.path" in lines[0].text


def test_link_expanded() -> None:
    lines = render("[GitHub](https://github.com)", width=80)
    text = lines[0].text
    assert "GitHub" in text
    assert "https://github.com" in text


# ------------------------------------------------------------------
# Blockquotes
# ------------------------------------------------------------------

def test_blockquote_style() -> None:
    lines = render("> Some quoted text", width=80)
    assert lines[0].style == STYLE_DIM
    assert "Some quoted text" in lines[0].text


# ------------------------------------------------------------------
# Lists
# ------------------------------------------------------------------

def test_bullet_list() -> None:
    lines = render("- item one\n- item two", width=80)
    texts = _texts(lines)
    item_lines = [t for t in texts if t.strip()]
    assert any("item one" in t for t in item_lines)
    assert any("item two" in t for t in item_lines)
    assert any("•" in t for t in item_lines)


def test_numbered_list() -> None:
    lines = render("1. first\n2. second", width=80)
    texts = _texts(lines)
    assert any("first" in t for t in texts)
    assert any("second" in t for t in texts)


# ------------------------------------------------------------------
# Horizontal rule
# ------------------------------------------------------------------

def test_horizontal_rule_style() -> None:
    lines = render("---", width=80)
    assert any(l.style == STYLE_RULE for l in lines)


# ------------------------------------------------------------------
# Empty input
# ------------------------------------------------------------------

def test_empty_string_returns_empty_list() -> None:
    assert render("", width=80) == []


# ------------------------------------------------------------------
# Long line wrapping
# ------------------------------------------------------------------

def test_long_line_is_wrapped() -> None:
    long_text = "word " * 30  # 150 chars
    lines = render(long_text.strip(), width=40)
    assert all(len(l.text) <= 40 for l in lines if l.text)
    assert len(lines) > 1
