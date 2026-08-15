"""Document header/footer from theme page settings."""

from __future__ import annotations

import re
from typing import Any

from mark2word.oxml_helpers import (
    add_dual_align_tab,
    add_field,
    add_run_text,
    clear_style_tab_stops,
    paragraph_element,
    prepare_dual_align_paragraph,
)
from mark2word.parser import split_dual_align

# Word's default Header/Footer styles add center/right tabs that stack with paragraph tabs.
_WORD_CHROME_TAB_STOPS = (4680, 9360)

_PLACEHOLDER = re.compile(r"\{page\}|\{pages\}|\{title\}")


def configure_page_chrome(
    doc,
    page: dict[str, Any],
    *,
    doc_title: str,
    content_width_twips: int,
) -> None:
    header = page.get("header")
    footer = page.get("footer")
    if not header and not footer:
        return
    clear_style_tab_stops(doc, "Header", "Footer")
    sec = doc.sections[0]
    meta = {"title": doc_title}
    if header:
        _apply_chrome_slot(sec.header, header, meta, content_width_twips)
    if footer:
        _apply_chrome_slot(sec.footer, footer, meta, content_width_twips)


def _apply_chrome_slot(container, cfg, meta: dict[str, str], content_width_twips: int) -> None:
    text = cfg if isinstance(cfg, str) else str(cfg.get("text", ""))
    if not text.strip():
        return
    p = container.paragraphs[0] if container.paragraphs else container.add_paragraph()
    p.text = ""
    parts = split_dual_align(text)
    if parts:
        left, right = parts
        prepare_dual_align_paragraph(
            p, content_width_twips, suppress_positions=_WORD_CHROME_TAB_STOPS,
        )
        _render_chrome_segment(p, left, meta)
        add_dual_align_tab(p)
        _render_chrome_segment(p, right, meta)
    else:
        _render_chrome_segment(p, text, meta)


def _render_chrome_segment(paragraph, text: str, meta: dict[str, str]) -> None:
    pos = 0
    p_el = paragraph_element(paragraph)
    for match in _PLACEHOLDER.finditer(text):
        if match.start() > pos:
            add_run_text(p_el, text[pos:match.start()])
        token = match.group(0)
        if token == "{page}":
            add_field(paragraph, "PAGE")
        elif token == "{pages}":
            add_field(paragraph, "NUMPAGES")
        elif token == "{title}":
            add_run_text(p_el, meta.get("title", ""))
        pos = match.end()
    if pos < len(text):
        add_run_text(p_el, text[pos:])
