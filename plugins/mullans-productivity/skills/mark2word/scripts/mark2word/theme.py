"""Theme loading, cascade resolution, and unit helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from docx.shared import Inches, Pt, RGBColor

from mark2word.errors import FrontmatterError, ThemeError
from mark2word.list_format import resolve_level_numbering, word_lvl_text


def _load_defaults() -> dict[str, Any]:
    path = Path(__file__).with_name("defaults.yaml")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ThemeError(f"defaults file must be a YAML mapping: {path}")
    return data


DEFAULTS: dict[str, Any] = _load_defaults()

PROP_KEYS = {
    "font", "size", "color", "bold", "italic", "align", "line",
    "space_before", "space_between", "space_after",
    "indent_left", "indent_right", "indent_hanging", "indent_first_line",
    "border_bottom", "border_left", "border_right",
    "fill", "width", "max_width", "alt_mode", "padding",
}


def fill_enabled(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str) and value.strip().lower() in {"none", "false", ""}:
        return False
    return True


def border_enabled(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str) and value.strip().lower() in {"none", "false", ""}:
        return False
    return isinstance(value, dict)


def length_to_twips(value) -> int:
    if value is None:
        return 0
    return int(round(pt_value(value) * 20))


def border_width_twips(spec: dict[str, Any]) -> int:
    """Visual width of a cell border for layout (pt → twips)."""
    return length_to_twips(spec.get("size", "0.5pt"))

IMAGE_ALT_MODES = {"caption", "doc", "both", "none"}

HEADINGS = {f"h{i}" for i in range(1, 7)}
TEXT_ELEMENTS = {
    "body", "list", "ol", "ul", "code", "code_block", "code_inline",
    "blockquote", "image", "hr",
}
CODE_ELEMENTS = {"code_block", "code_inline"}
TABLE_ELEMENTS = {"table", "th", "td"}
LIST_KINDS = {"list", "ol", "ul"}
LIST_FORMAT_KEYS = {"format", "num_fmt", "template"}
LIST_META_KEYS = {"indent_step", "levels"}

PAGE_SIZES = {
    "letter": (Inches(8.5), Inches(11)),
    "a4": (Inches(8.27), Inches(11.69)),
}

FRONTMATTER_RE = re.compile(
    r"^\ufeff?---[ \t]*\r?\n(.*?)^---[ \t]*\r?\n?(.*)$",
    re.DOTALL | re.MULTILINE,
)


@dataclass(frozen=True)
class LevelNumbering:
    num_fmt: str
    lvl_text: str
    left_twips: int
    hanging_twips: int


@dataclass(frozen=True)
class NumberingConfig:
    ordered: bool
    levels: tuple[LevelNumbering, ...]

    def fingerprint(self) -> tuple[Any, ...]:
        return (
            self.ordered,
            tuple(
                (level.num_fmt, level.lvl_text, level.left_twips, level.hanging_twips)
                for level in self.levels
            ),
        )


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def to_length(v):
    if isinstance(v, (int, float)):
        return Pt(v)
    s = str(v).strip().lower()
    if s.endswith("pt"):
        return Pt(float(s[:-2]))
    if s.endswith("in"):
        return Inches(float(s[:-2]))
    return Pt(float(s))


def hex_color(v):
    return RGBColor.from_string(str(v).lstrip("#"))


def pt_value(v):
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().lower()
    if s.endswith("pt"):
        return float(s[:-2])
    if s.endswith("in"):
        return float(s[:-2]) * 72.0
    return float(s)


def split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    try:
        parsed = yaml.safe_load(m.group(1))
    except yaml.YAMLError as exc:
        raise FrontmatterError(f"invalid YAML in frontmatter: {exc}") from exc
    body = m.group(2)
    if parsed is None:
        return {}, body
    if not isinstance(parsed, dict):
        raise FrontmatterError(
            f"frontmatter must be a YAML mapping, got {type(parsed).__name__}"
        )
    return parsed, body


def discover_theme_dirs(md_path: Path) -> list[Path]:
    dirs: list[Path] = []
    seen: set[Path] = set()
    for parent in [md_path.parent, *md_path.parent.parents]:
        candidate = (parent / ".mark2word" / "themes").resolve()
        if candidate.is_dir() and candidate not in seen:
            seen.add(candidate)
            dirs.append(candidate)
    return dirs


def _theme_candidates(ext: Path, md_path: Path, theme_dirs=None):
    if ext.is_absolute():
        yield ext
        return
    yield md_path.parent / ext
    for theme_dir in theme_dirs or []:
        yield Path(theme_dir).expanduser() / ext


def _load_theme_file(
    ext: str | Path,
    md_path: Path,
    theme_dirs=None,
    seen: set[Path] | None = None,
) -> dict[str, Any]:
    seen = seen or set()
    checked = [path.resolve() for path in _theme_candidates(Path(ext), md_path, theme_dirs)]
    ext_path = next((path for path in checked if path.exists()), None)
    if ext_path is None:
        searched = ", ".join(str(path) for path in checked)
        raise ThemeError(f"extends references missing theme: {ext}; searched: {searched}")
    if ext_path in seen:
        raise ThemeError(f"theme inheritance cycle detected at: {ext_path}")
    seen.add(ext_path)
    data = yaml.safe_load(ext_path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ThemeError(f"theme file must be a YAML mapping: {ext_path}")
    parent_ext = data.pop("extends", None)
    if parent_ext is not None:
        parent = _load_theme_file(parent_ext, md_path, theme_dirs, seen)
        data = deep_merge(parent, data)
    return data


def load_theme(
    front: dict[str, Any],
    md_path: Path,
    theme_dirs=None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    external: dict[str, Any] = {}
    front = dict(front)
    ext = front.pop("extends", None)
    if ext is not None:
        external = _load_theme_file(ext, md_path, theme_dirs)
    return external, front


def ensure_theme_chain_readable(
    front: dict[str, Any],
    md_path: Path,
    theme_dirs=None,
) -> None:
    """Verify frontmatter ``extends`` theme files exist and are readable."""
    from mark2word.paths import ensure_input_readable

    ext = front.get("extends")
    if ext is None:
        return
    _ensure_theme_chain_readable(ext, md_path, theme_dirs, set(), ensure_input_readable)


def _ensure_theme_chain_readable(
    ext: str | Path,
    md_path: Path,
    theme_dirs,
    seen: set[Path],
    check_readable,
) -> None:
    checked = [path.resolve() for path in _theme_candidates(Path(ext), md_path, theme_dirs)]
    ext_path = next((path for path in checked if path.exists()), None)
    if ext_path is None:
        searched = ", ".join(str(path) for path in checked)
        raise ThemeError(
            f"Error: cannot read theme file {ext}: file not found; searched: {searched}"
        )
    if ext_path in seen:
        raise ThemeError(f"theme inheritance cycle detected at: {ext_path}")
    seen.add(ext_path)
    check_readable(ext_path, kind="theme")
    data = yaml.safe_load(ext_path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ThemeError(f"theme file must be a YAML mapping: {ext_path}")
    parent_ext = data.get("extends")
    if parent_ext is not None:
        _ensure_theme_chain_readable(parent_ext, md_path, theme_dirs, seen, check_readable)


def _bare(layer: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in layer.items() if k in PROP_KEYS}


def _key_order(element: str) -> list[str]:
    if element in HEADINGS:
        return ["heading", element]
    if element == "ol" or element == "ul":
        return ["list", element]
    if element == "code_block":
        return ["code", "code_block"]
    if element == "code_inline":
        return ["code", "code_inline"]
    if element in TEXT_ELEMENTS:
        return ["text", element]
    if element == "image":
        return ["image"]
    if element == "blockquote":
        return ["text", "blockquote"]
    if element == "hr":
        return ["hr"]
    if element in TABLE_ELEMENTS:
        if element == "table":
            return ["table"]
        return ["table", element]
    return [element]


def _layer_contribution(layer: dict[str, Any], element: str) -> dict[str, Any]:
    out = dict(_bare(layer))
    for key in _key_order(element):
        sub = layer.get(key)
        if isinstance(sub, dict):
            out.update({k: v for k, v in sub.items() if k in PROP_KEYS})
    return out


class Resolver:
    def __init__(self, external: dict[str, Any], glob: dict[str, Any]):
        self.global_layers = [DEFAULTS, external, glob]
        self.region_sources = [external, glob]
        self._cache: dict[tuple[str, tuple[str, ...]], dict[str, Any]] = {}

    @staticmethod
    def _descend(layer: dict[str, Any], path: list[str]) -> dict[str, Any] | None:
        node: Any = layer
        for name in path:
            if not isinstance(node, dict):
                return None
            node = node.get("$" + name)
        return node if isinstance(node, dict) else None

    def resolve(self, element: str, region_path: tuple[str, ...] | None = None) -> dict[str, Any]:
        key = (element, region_path or ())
        if key not in self._cache:
            self._cache[key] = self._resolve_uncached(element, region_path)
        return dict(self._cache[key])

    def _resolve_uncached(
        self, element: str, region_path: tuple[str, ...] | None = None
    ) -> dict[str, Any]:
        style: dict[str, Any] = {}
        for layer in self.global_layers:
            style.update(_layer_contribution(layer, element))
        for depth in range(1, len(region_path or ()) + 1):
            prefix = region_path[:depth]
            for src in self.region_sources:
                block = self._descend(src, list(prefix))
                if block is not None:
                    style.update(_layer_contribution(block, element))
        return style

    def _list_block_from_layers(
        self,
        region_path: tuple[str, ...] | None,
        *,
        ordered: bool,
    ) -> dict[str, Any]:
        """Merge raw list/ol|ul theme blocks (including nesting meta keys)."""
        block: dict[str, Any] = {}
        keys = ["list", "ol" if ordered else "ul"]
        for layer in self.global_layers:
            for key in keys:
                sub = layer.get(key)
                if isinstance(sub, dict):
                    block = deep_merge(block, sub)
        for depth in range(1, len(region_path or ()) + 1):
            prefix = region_path[:depth]
            for src in self.region_sources:
                node = self._descend(src, list(prefix))
                if isinstance(node, dict):
                    for key in keys:
                        sub = node.get(key)
                        if isinstance(sub, dict):
                            block = deep_merge(block, sub)
        return block

    @staticmethod
    def _level_override(block: dict[str, Any], ilvl: int) -> dict[str, Any]:
        levels = block.get("levels") or {}
        level_ov = levels.get(ilvl) or levels.get(str(ilvl))
        return dict(level_ov) if isinstance(level_ov, dict) else {}

    def _level_indents_twips(self, block: dict[str, Any], ilvl: int) -> tuple[int, int]:
        level_ov = self._level_override(block, ilvl)
        base = pt_value(block.get("indent_left", 18))
        step_raw = block.get("indent_step")
        if step_raw is None:
            step_raw = block.get("indent_hanging") or block.get("indent_left") or 18
        step = pt_value(step_raw)
        hanging_pt = pt_value(
            level_ov.get("indent_hanging", block.get("indent_hanging", block.get("indent_left", 18)))
        )
        if "indent_left" in level_ov:
            left_pt = pt_value(level_ov["indent_left"])
        else:
            left_pt = base + ilvl * step
        return int(left_pt * 20), int(hanging_pt * 20)

    def resolve_numbering_config(
        self,
        region_path: tuple[str, ...] | None,
        *,
        ordered: bool,
    ) -> NumberingConfig:
        block = self._list_block_from_layers(region_path, ordered=ordered)
        levels: list[LevelNumbering] = []
        for ilvl in range(9):
            level_cfg = self._level_override(block, ilvl)
            num_fmt, lvl_text = resolve_level_numbering(level_cfg, ordered=ordered, ilvl=ilvl)
            lvl_text = word_lvl_text(lvl_text, ilvl)
            left_twips, hanging_twips = self._level_indents_twips(block, ilvl)
            levels.append(
                LevelNumbering(
                    num_fmt=num_fmt,
                    lvl_text=lvl_text,
                    left_twips=left_twips,
                    hanging_twips=hanging_twips,
                )
            )
        return NumberingConfig(ordered=ordered, levels=tuple(levels))

    def resolve_list_style(
        self,
        list_level: int,
        region_path: tuple[str, ...] | None = None,
        *,
        ordered: bool,
    ) -> dict[str, Any]:
        """Resolve list paragraph/run styling (not numbering indents)."""
        kind = "ol" if ordered else "ul"
        style = dict(self.resolve(kind, region_path))
        level_ov = self._level_override(
            self._list_block_from_layers(region_path, ordered=ordered),
            list_level,
        )
        if level_ov:
            style.update({k: v for k, v in level_ov.items() if k in PROP_KEYS})
        for key in ("indent_left", "indent_first_line", "indent_hanging"):
            style.pop(key, None)
        return style

    def resolve_code_block_style(
        self,
        code_lang: str = "",
        region_path: tuple[str, ...] | None = None,
    ) -> dict[str, Any]:
        style = dict(self.resolve("code_block", region_path))
        if not code_lang:
            return style
        for layer in self.global_layers:
            code_block = layer.get("code_block") or layer.get("code")
            if not isinstance(code_block, dict):
                continue
            langs = code_block.get("langs")
            if isinstance(langs, dict) and code_lang in langs:
                sub = langs[code_lang]
                if isinstance(sub, dict):
                    style.update({k: v for k, v in sub.items() if k in PROP_KEYS})
        for depth in range(1, len(region_path or ()) + 1):
            prefix = region_path[:depth]
            for src in self.region_sources:
                node = self._descend(src, list(prefix))
                if not isinstance(node, dict):
                    continue
                code_block = node.get("code_block") or node.get("code")
                if not isinstance(code_block, dict):
                    continue
                langs = code_block.get("langs")
                if isinstance(langs, dict) and code_lang in langs:
                    sub = langs[code_lang]
                    if isinstance(sub, dict):
                        style.update({k: v for k, v in sub.items() if k in PROP_KEYS})
        return style

    def resolve_code_inline_style(
        self,
        region_path: tuple[str, ...] | None = None,
    ) -> dict[str, Any]:
        return dict(self.resolve("code_inline", region_path))

    def resolve_code_style(
        self,
        code_lang: str = "",
        region_path: tuple[str, ...] | None = None,
    ) -> dict[str, Any]:
        """Backward-compatible alias for fenced code block styling."""
        return self.resolve_code_block_style(code_lang, region_path)
