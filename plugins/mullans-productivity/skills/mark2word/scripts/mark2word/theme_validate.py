"""Theme file validation for --check-theme."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from mark2word.errors import ThemeError
from mark2word.list_format import normalize_num_fmt, parse_format_string
from mark2word.theme import PAGE_SIZES, PROP_KEYS, _load_theme_file, discover_theme_dirs


def validate_theme_file(
    theme_path: Path,
    *,
    theme_dirs: list[Path] | None = None,
) -> dict[str, Any]:
    """Load and validate a theme YAML file (including extends chain)."""
    theme_path = theme_path.resolve()
    if not theme_path.is_file():
        raise ThemeError(f"theme file not found: {theme_path}")

    md_stub = theme_path.parent / ".mark2word-theme-check.md"
    dirs = list(theme_dirs or [])
    for discovered in discover_theme_dirs(md_stub):
        if discovered not in dirs:
            dirs.append(discovered)

    data = yaml.safe_load(theme_path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ThemeError(f"theme file must be a YAML mapping: {theme_path}")

    parent_ext = data.get("extends")
    merged = dict(data)
    if parent_ext is not None:
        parent = _load_theme_file(parent_ext, md_stub, dirs)
        from mark2word.theme import deep_merge

        merged = deep_merge(parent, {k: v for k, v in data.items() if k != "extends"})

    _validate_merged_theme(merged, theme_path)
    return merged


def _validate_merged_theme(theme: dict[str, Any], source: Path) -> None:
    page = theme.get("page")
    if isinstance(page, dict):
        size = str(page.get("size", "letter")).lower()
        if size not in PAGE_SIZES:
            raise ThemeError(f"unknown page size: {page.get('size')!r} in {source}")

    for key, value in theme.items():
        if key.startswith("$") or key in {"extends", "page", "title", "languages"}:
            if key == "page":
                _validate_page_chrome(value)
            continue
        if key in {"list", "ol", "ul"} and isinstance(value, dict):
            _validate_list_block(value, source)
        elif isinstance(value, dict):
            _validate_style_dict(value, source, context=key)

    for block_key in ("code", "code_block"):
        block = theme.get(block_key)
        if isinstance(block, dict):
            langs = block.get("langs")
            if isinstance(langs, dict):
                for lang, cfg in langs.items():
                    if isinstance(cfg, dict):
                        _validate_style_dict(
                            cfg, source, context=f"{block_key}.langs.{lang}",
                        )


def _validate_page_chrome(page: Any) -> None:
    if not isinstance(page, dict):
        return
    for slot in ("header", "footer"):
        cfg = page.get(slot)
        if cfg is None:
            continue
        if isinstance(cfg, str):
            continue
        if isinstance(cfg, dict):
            continue
        raise ThemeError(f"page.{slot} must be a string or mapping")


def _validate_list_block(block: dict[str, Any], source: Path) -> None:
    levels = block.get("levels")
    if not isinstance(levels, dict):
        return
    for level, cfg in levels.items():
        if not isinstance(cfg, dict):
            continue
        ordered = True
        try:
            if "format" in cfg:
                parse_format_string(str(cfg["format"]), default_num_fmt="decimal", default_lvl_text="%1.")
            if "num_fmt" in cfg:
                normalize_num_fmt(str(cfg["num_fmt"]))
            if "num_fmt" in cfg or "template" in cfg:
                if "num_fmt" not in cfg or "template" not in cfg:
                    raise ThemeError(
                        f"list level {level} requires both num_fmt and template in {source}"
                    )
        except ThemeError:
            raise
        _validate_style_dict(cfg, source, context=f"list.levels.{level}")


def _validate_style_dict(style: dict[str, Any], source: Path, *, context: str) -> None:
    for prop, value in style.items():
        if prop in {"levels", "langs", "border", "padding", "margin"}:
            continue
        if prop in {"format", "num_fmt", "template", "indent_step"}:
            continue
        if prop not in PROP_KEYS and prop not in {"width", "max_width", "alt_mode"}:
            raise ThemeError(f"unknown style key {prop!r} in {context} ({source})")
        if prop == "align" and value not in {"left", "center", "right", "justify"}:
            raise ThemeError(f"invalid align {value!r} in {context} ({source})")
        if prop == "alt_mode" and value not in {"caption", "doc", "both", "none"}:
            raise ThemeError(f"invalid alt_mode {value!r} in {context} ({source})")
