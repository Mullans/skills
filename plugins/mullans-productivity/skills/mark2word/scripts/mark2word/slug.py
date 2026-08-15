"""Heading slug generation for internal document links."""

from __future__ import annotations

import re

_SLUG_RE = re.compile(r"[^\w\s-]", re.UNICODE)
_SPACE_RE = re.compile(r"[\s_-]+")


def slugify(text: str) -> str:
    """GitHub-style slug from heading text."""
    cleaned = _SLUG_RE.sub("", text.strip().lower())
    return _SPACE_RE.sub("-", cleaned).strip("-")


def unique_slug(text: str, used: set[str]) -> str:
    base = slugify(text) or "section"
    if base not in used:
        used.add(base)
        return base
    n = 2
    while f"{base}-{n}" in used:
        n += 1
    slug = f"{base}-{n}"
    used.add(slug)
    return slug
