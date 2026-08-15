"""Markdown parsing: blocks, inline markup, and AST conversion."""

from __future__ import annotations

import re
from typing import Any

from mark2word.ast import Block, InlineRun
from mark2word.errors import ParseError, RegionError
from mark2word.plugins import block_parsers

RE_REGION_OPEN = re.compile(r"^<!--\s*region:\s*([A-Za-z0-9_-]+)\s*-->$")
RE_REGION_CLOSE = re.compile(r"^<!--\s*/region\s*-->$")
RE_PAGEBREAK = re.compile(r"^<!--\s*pagebreak\s*-->$", re.IGNORECASE)
RE_HR = re.compile(r"^(---|\*\*\*|___)\s*$")
RE_BLOCKQUOTE = re.compile(r"^>\s?(.*)$")
RE_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
RE_UL = re.compile(r"^[-*]\s+(.*)$")
RE_OL = re.compile(r"^(\d+)\.\s+(.*)$")
RE_IMAGE = re.compile(r"^!\[([^\]]*)\]\(([^)]+)\)\s*$")
RE_TABLE_SEP = re.compile(r"^\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?\s*$")
RE_FENCE_OPEN = re.compile(r"^```([A-Za-z0-9_+-]*)?\s*$")
RE_FENCE_CLOSE = re.compile(r"^```\s*$")
LIST_INDENT_SPACES = 2


def _list_level(raw_line: str) -> int:
    leading = raw_line[: len(raw_line) - len(raw_line.lstrip(" \t"))]
    spaces = sum(1 for ch in leading if ch == " ")
    tabs = sum(1 for ch in leading if ch == "\t")
    return (spaces + tabs * LIST_INDENT_SPACES) // LIST_INDENT_SPACES


def _split_table_row(line: str) -> list[str]:
    body = line.strip().strip("|")
    return [cell.strip() for cell in body.split("|")]


def _is_table_row(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("|") and "|" in stripped[1:]


def parse_blocks(md: str) -> list[dict[str, Any]]:
    return [block.to_dict() for block in parse_to_ast(md)]


def _try_custom_parser(lines: list[str], idx: int, region_stack: list[str]) -> tuple[Block | None, int]:
    stripped = lines[idx].strip()
    line_no = idx + 1
    ctx: dict[str, Any] = {"lines": lines, "region_stack": region_stack}
    for parser in block_parsers():
        custom = parser(stripped, line_no, ctx)
        if custom is not None:
            next_idx = int(ctx.get("next_idx", idx + 1))
            if next_idx <= idx:
                next_idx = idx + 1
            return Block.from_dict(custom), next_idx
    return None, idx


def parse_to_ast(md: str) -> list[Block]:
    blocks: list[Block] = []
    region_stack: list[str] = []
    lines = md.splitlines()
    idx = 0
    while idx < len(lines):
        raw = lines[idx]
        line_no = idx + 1
        stripped = raw.strip()
        if not stripped:
            idx += 1
            continue

        custom, next_idx = _try_custom_parser(lines, idx, region_stack)
        if custom is not None:
            blocks.append(custom)
            idx = next_idx
            continue

        mo = RE_REGION_OPEN.match(stripped)
        if mo:
            region_stack.append(mo.group(1))
            idx += 1
            continue
        if RE_REGION_CLOSE.match(stripped):
            if not region_stack:
                raise RegionError("region close without a matching open", line_no)
            region_stack.pop()
            idx += 1
            continue

        if RE_PAGEBREAK.match(stripped):
            blocks.append(Block(type="pagebreak", region=list(region_stack), line_no=line_no))
            idx += 1
            continue

        if RE_HR.match(stripped):
            blocks.append(Block(type="hr", region=list(region_stack), line_no=line_no))
            idx += 1
            continue

        bq = RE_BLOCKQUOTE.match(stripped)
        if bq:
            quote_lines = [bq.group(1)]
            idx += 1
            while idx < len(lines):
                nxt = lines[idx].strip()
                if not nxt:
                    if idx + 1 < len(lines) and RE_BLOCKQUOTE.match(lines[idx + 1].strip()):
                        idx += 1
                        continue
                    break
                nxt_bq = RE_BLOCKQUOTE.match(nxt)
                if not nxt_bq:
                    break
                quote_lines.append(nxt_bq.group(1))
                idx += 1
            blocks.append(Block(
                type="blockquote",
                text="\n".join(quote_lines),
                region=list(region_stack),
                line_no=line_no,
            ))
            continue

        if RE_FENCE_OPEN.match(stripped):
            lang = RE_FENCE_OPEN.match(stripped).group(1) or ""
            idx += 1
            code_lines: list[str] = []
            while idx < len(lines):
                if RE_FENCE_CLOSE.match(lines[idx].strip()):
                    idx += 1
                    break
                code_lines.append(lines[idx].rstrip())
                idx += 1
            else:
                raise ParseError("unclosed fenced code block", line_no)
            blocks.append(Block(
                type="code",
                text="\n".join(code_lines),
                code_lang=lang,
                region=list(region_stack),
                line_no=line_no,
            ))
            continue

        if _is_table_row(stripped) and idx + 1 < len(lines) and RE_TABLE_SEP.match(lines[idx + 1].strip()):
            row = _split_table_row(stripped)
            col_count = len(row)
            idx += 2
            rows = [row]
            while idx < len(lines) and _is_table_row(lines[idx]):
                next_row = _split_table_row(lines[idx])
                if len(next_row) != col_count:
                    raise ParseError(
                        f"table row has {len(next_row)} columns, expected {col_count}",
                        idx + 1,
                    )
                rows.append(next_row)
                idx += 1
            blocks.append(Block(
                type="table",
                rows=rows,
                region=list(region_stack),
                line_no=line_no,
            ))
            continue

        region = list(region_stack)
        level = _list_level(raw)

        mh = RE_HEADING.match(stripped)
        if mh:
            blocks.append(Block(
                type=f"h{len(mh.group(1))}",
                text=mh.group(2).strip(),
                region=region,
                line_no=line_no,
            ))
            idx += 1
            continue

        img = RE_IMAGE.match(stripped)
        if img:
            blocks.append(Block(
                type="image",
                image_alt=img.group(1),
                image_path=img.group(2).strip(),
                region=region,
                line_no=line_no,
            ))
            idx += 1
            continue

        mu = RE_UL.match(stripped)
        if mu:
            blocks.append(Block(
                type="list",
                ordered=False,
                text=mu.group(1).strip(),
                region=region,
                list_level=level,
                line_no=line_no,
            ))
            idx += 1
            continue

        mol = RE_OL.match(stripped)
        if mol:
            blocks.append(Block(
                type="list",
                ordered=True,
                text=mol.group(2).strip(),
                list_number=int(mol.group(1)),
                region=region,
                list_level=level,
                line_no=line_no,
            ))
            idx += 1
            continue

        blocks.append(Block(type="body", text=stripped, region=region, line_no=line_no))
        idx += 1

    if region_stack:
        open_regions = " > ".join(region_stack)
        raise RegionError(f"unclosed region: {open_regions}")
    return blocks


def _toggle_emphasis(stars: int, bold: bool, italic: bool) -> tuple[bool, bool]:
    if stars == 3:
        return not bold, not italic
    if stars == 2:
        return not bold, italic
    return bold, not italic


def parse_inline(text: str) -> list[InlineRun]:
    runs: list[InlineRun] = []
    buf: list[str] = []
    bold = italic = False
    i, n = 0, len(text)

    def flush():
        if buf:
            runs.append(InlineRun("".join(buf), bold, italic, False))
            buf.clear()

    while i < n:
        c = text[i]
        if c == "\\" and i + 1 < n:
            buf.append(text[i + 1])
            i += 2
            continue
        if c == "`":
            end = text.find("`", i + 1)
            if end == -1:
                buf.append(c)
                i += 1
                continue
            flush()
            runs.append(InlineRun(text[i + 1:end], code=True))
            i = end + 1
            continue
        if c == "[":
            close = text.find("]", i + 1)
            if close != -1 and close + 1 < n and text[close + 1] == "(":
                end = text.find(")", close + 2)
                if end != -1:
                    flush()
                    label = text[i + 1:close]
                    url = text[close + 2:end]
                    for sub in parse_inline(label):
                        runs.append(InlineRun(
                            sub.text, sub.bold, sub.italic, sub.code, url=url
                        ))
                    i = end + 1
                    continue
        if c in "*_":
            run = len(text[i:]) - len(text[i:].lstrip(c))
            stars = min(run, 3)
            flush()
            bold, italic = _toggle_emphasis(stars, bold, italic)
            i += stars
            continue
        buf.append(c)
        i += 1
    flush()
    return runs


def split_dual_align(text: str) -> tuple[str, str] | None:
    """Split on || for dual alignment, ignoring backticks and escaped bars."""
    in_code = False
    i = 0
    n = len(text)
    while i < n:
        if text[i] == "\\" and i + 1 < n:
            i += 2
            continue
        if text[i] == "`":
            in_code = not in_code
            i += 1
            continue
        if not in_code and text[i : i + 2] == "||":
            left = text[:i].rstrip()
            right = text[i + 2 :].lstrip()
            if left and right:
                return left, right
            i += 2
            continue
        i += 1
    return None
