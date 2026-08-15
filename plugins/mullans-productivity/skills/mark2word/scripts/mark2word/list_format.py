"""Parse list level format strings into Word numbering properties."""

from __future__ import annotations

import re
from typing import Any

from mark2word.errors import ThemeError

# Longest-first keyword aliases → (Word numFmt, default lvlText when keyword is used alone)
_FORMAT_KEYWORDS: list[tuple[str, str, str]] = [
    ("roman", "lowerRoman", "%1."),
    ("alph", "lowerLetter", "%1."),
    ("Roman", "upperRoman", "%1."),
    ("Alph", "upperLetter", "%1."),
    ("decimal", "decimal", "%1."),
    ("bullet", "bullet", "%1"),
    ("01.", "decimalZero", "%1."),
    ("01", "decimalZero", "%1"),
    ("1", "decimal", "%1."),
    ("i", "lowerRoman", "%1."),
    ("I", "upperRoman", "%1."),
    ("a", "lowerLetter", "%1."),
    ("A", "upperLetter", "%1."),
]

_WORD_NUM_FMTS = {
    "decimal",
    "decimalZero",
    "lowerLetter",
    "upperLetter",
    "lowerRoman",
    "upperRoman",
    "bullet",
    "none",
}

_TEMPLATE_KEYWORDS = sorted(
    (alias for alias, _, _ in _FORMAT_KEYWORDS),
    key=len,
    reverse=True,
)


def normalize_num_fmt(value: str) -> str:
    raw = str(value).strip()
    lowered = raw.lower()
    for alias, num_fmt, _ in _FORMAT_KEYWORDS:
        if lowered == alias.lower():
            return num_fmt
    if raw in _WORD_NUM_FMTS:
        return raw
    raise ThemeError(f"unknown list num_fmt: {value!r}")


def _match_keyword(text: str) -> tuple[str, str, str] | None:
    stripped = text.strip()
    for alias, num_fmt, default_lvl in _FORMAT_KEYWORDS:
        if stripped == alias or stripped.lower() == alias.lower():
            return alias, num_fmt, default_lvl
    return None


def _template_from_keyword(text: str, alias: str, num_fmt: str) -> str:
    pattern = re.compile(re.escape(alias), re.IGNORECASE)
    match = pattern.search(text)
    if match is None:
        raise ThemeError(f"could not build list template from format: {text!r}")
    return text[: match.start()] + "%1" + text[match.end() :]


def word_lvl_text(user_template: str, ilvl: int) -> str:
    """Map user ``%1`` (this level's counter) to Word's level-indexed placeholder."""
    n = ilvl + 1
    if n == 1:
        return user_template
    return re.sub(r"%1(?!\d)", f"%{n}", user_template)


def parse_format_string(text: str, *, default_num_fmt: str, default_lvl_text: str) -> tuple[str, str]:
    """Return Word ``numFmt`` and ``lvlText`` from a ``format`` shorthand or template."""
    if not str(text).strip():
        return default_num_fmt, default_lvl_text

    matched = _match_keyword(str(text))
    if matched is not None:
        _, num_fmt, lvl_text = matched
        return num_fmt, lvl_text

    raw = str(text).strip()
    for alias, num_fmt, _ in sorted(_FORMAT_KEYWORDS, key=lambda item: len(item[0]), reverse=True):
        if re.search(re.escape(alias), raw, re.IGNORECASE):
            return num_fmt, _template_from_keyword(raw, alias, num_fmt)

    if default_num_fmt == "bullet":
        return "bullet", raw

    raise ThemeError(f"unknown list format: {text!r}")


def resolve_level_numbering(
    level_cfg: dict[str, Any],
    *,
    ordered: bool,
    ilvl: int,
) -> tuple[str, str]:
    """Resolve ``numFmt`` and ``lvlText`` for one list level."""
    if ordered:
        default_num_fmt, default_lvl_text = "decimal", "%1."
    else:
        default_num_fmt, default_lvl_text = "bullet", "•"

    if "num_fmt" in level_cfg or "template" in level_cfg:
        if "num_fmt" not in level_cfg or "template" not in level_cfg:
            raise ThemeError("list level requires both num_fmt and template when either is set")
        user_text = str(level_cfg["template"])
        return normalize_num_fmt(level_cfg["num_fmt"]), user_text

    if "format" in level_cfg:
        num_fmt, user_text = parse_format_string(
            str(level_cfg["format"]),
            default_num_fmt=default_num_fmt,
            default_lvl_text=default_lvl_text,
        )
        return num_fmt, user_text

    return default_num_fmt, default_lvl_text
