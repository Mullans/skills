"""Markdown to Word conversion with YAML theming."""

from mark2word.ast import Block, InlineRun
from mark2word.cli import convert_one, main, resolve_output_path, validate_document, validate_theme
from mark2word.emit import build
from mark2word.errors import (
    FrontmatterError,
    ImageError,
    Mark2WordError,
    ParseError,
    RegionError,
    ThemeError,
)
from mark2word.parser import parse_blocks, parse_inline, parse_to_ast
from mark2word.paths import ensure_input_readable, ensure_output_writable
from mark2word.plugins import register_block_emitter, register_block_parser, reset_plugins
from mark2word.theme import (
    Resolver,
    deep_merge,
    discover_theme_dirs,
    ensure_theme_chain_readable,
    load_theme,
    split_frontmatter,
)

__all__ = [
    "Block",
    "FrontmatterError",
    "ImageError",
    "InlineRun",
    "Mark2WordError",
    "ParseError",
    "RegionError",
    "Resolver",
    "ThemeError",
    "build",
    "convert_one",
    "deep_merge",
    "discover_theme_dirs",
    "ensure_input_readable",
    "ensure_output_writable",
    "ensure_theme_chain_readable",
    "load_theme",
    "main",
    "parse_blocks",
    "parse_inline",
    "parse_to_ast",
    "register_block_emitter",
    "register_block_parser",
    "reset_plugins",
    "resolve_output_path",
    "split_frontmatter",
    "validate_document",
    "validate_theme",
]

if __name__ == "__main__":
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    sys.exit(main())
