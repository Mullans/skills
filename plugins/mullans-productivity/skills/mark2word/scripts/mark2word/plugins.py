"""Plugin registration for custom block parsers and emitters."""

from __future__ import annotations

from typing import Any, Callable

BlockParser = Callable[[str, int, dict[str, Any]], dict[str, Any] | None]
BlockEmitter = Callable[[Any, Any, dict[str, Any], dict[str, Any]], Any]

_block_parsers: list[BlockParser] = []
_block_emitters: dict[str, BlockEmitter] = {}


def register_block_parser(parser: BlockParser, *, prepend: bool = False) -> None:
    if prepend:
        _block_parsers.insert(0, parser)
    else:
        _block_parsers.append(parser)


def register_block_emitter(block_type: str, emitter: BlockEmitter) -> None:
    _block_emitters[block_type] = emitter


def block_parsers() -> list[BlockParser]:
    return list(_block_parsers)


def block_emitter(block_type: str) -> BlockEmitter | None:
    return _block_emitters.get(block_type)


def reset_plugins() -> None:
    """Clear registered parsers and emitters (for test isolation)."""
    _block_parsers.clear()
    _block_emitters.clear()
