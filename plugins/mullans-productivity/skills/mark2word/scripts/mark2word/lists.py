"""List numbering via Word OOXML."""

from __future__ import annotations

from dataclasses import dataclass

from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph

from mark2word.theme import LevelNumbering, NumberingConfig

_ABSTRACT_CACHE_ATTR = "_mark2word_abstract_cache"
_LEVELS = 9


def _next_abstract_num_id(numbering) -> int:
    existing = [int(x) for x in numbering.xpath("./w:abstractNum/@w:abstractNumId")]
    for candidate in range(max(existing, default=-1) + 2):
        if candidate not in existing:
            return candidate
    return 0


def _build_level_xml(ilvl: int, level: LevelNumbering) -> OxmlElement:
    lvl = OxmlElement("w:lvl")
    lvl.set(qn("w:ilvl"), str(ilvl))
    start = OxmlElement("w:start")
    start.set(qn("w:val"), "1")
    num_fmt = OxmlElement("w:numFmt")
    num_fmt.set(qn("w:val"), level.num_fmt)
    lvl_text = OxmlElement("w:lvlText")
    lvl_text.set(qn("w:val"), level.lvl_text)
    lvl_jc = OxmlElement("w:lvlJc")
    lvl_jc.set(qn("w:val"), "left")
    p_pr = OxmlElement("w:pPr")
    ind = OxmlElement("w:ind")
    ind.set(qn("w:left"), str(level.left_twips))
    ind.set(qn("w:hanging"), str(level.hanging_twips))
    p_pr.append(ind)
    lvl.append(start)
    lvl.append(num_fmt)
    lvl.append(lvl_text)
    lvl.append(lvl_jc)
    lvl.append(p_pr)
    return lvl


def _build_multilevel_abstract(abstract_id: int, config: NumberingConfig) -> OxmlElement:
    abstract = OxmlElement("w:abstractNum")
    abstract.set(qn("w:abstractNumId"), str(abstract_id))
    multi = OxmlElement("w:multiLevelType")
    multi.set(qn("w:val"), "multilevel")
    abstract.append(multi)
    for ilvl in range(_LEVELS):
        abstract.append(_build_level_xml(ilvl, config.levels[ilvl]))
    return abstract


def _ensure_abstract(doc, config: NumberingConfig) -> int:
    cache = getattr(doc, _ABSTRACT_CACHE_ATTR, None)
    if cache is None:
        cache = {}
        setattr(doc, _ABSTRACT_CACHE_ATTR, cache)
    fingerprint = config.fingerprint()
    if fingerprint in cache:
        return cache[fingerprint]

    numbering = doc.part.numbering_part.numbering_definitions._numbering
    abstract_id = _next_abstract_num_id(numbering)
    abstract = _build_multilevel_abstract(abstract_id, config)
    numbering.insert(0, abstract)
    cache[fingerprint] = abstract_id
    return abstract_id


def _new_list_num_id(doc, abstract_id: int, *, start: int | None = None, level: int = 0) -> int:
    numbering = doc.part.numbering_part.numbering_definitions._numbering
    ct_num = numbering.add_num(abstract_id)
    if start is not None and start != 1:
        override = ct_num.add_lvlOverride(level)
        override.add_startOverride(start)
    return ct_num.numId


def _same_list_run(prev: Paragraph | None, *, ordered: bool, run_num_id: int | None) -> bool:
    if prev is None or run_num_id is None:
        return False
    expected_style = "List Number" if ordered else "List Bullet"
    return prev.style.name == expected_style


def apply_list_numbering(
    paragraph: Paragraph,
    doc,
    *,
    ordered: bool,
    start: int | None,
    level: int,
    prev: Paragraph | None,
    run_num_id: int | None,
    numbering_config: NumberingConfig,
) -> int:
    """Apply list numbering and return the numId for the current list run."""
    abstract_id = _ensure_abstract(doc, numbering_config)

    if _same_list_run(prev, ordered=ordered, run_num_id=run_num_id):
        num_id = run_num_id
    else:
        list_start = start if ordered else None
        num_id = _new_list_num_id(doc, abstract_id, start=list_start, level=level)

    p_pr = paragraph._p.get_or_add_pPr()
    num_pr = p_pr.get_or_add_numPr()
    num_pr.get_or_add_numId().val = num_id
    num_pr.get_or_add_ilvl().val = level
    return num_id
