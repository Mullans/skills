"""Bounded Markdown primitives shared by documentation maintenance tools.

This is structural interpretation, not a claim-support validator or renderer.
"""
from dataclasses import dataclass
import re
from urllib.parse import unquote

CEILING = 1024**2
HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$", re.MULTILINE)
UNIT = re.compile(r"^(Finding|Contract|Negative result) ([A-Z][A-Z0-9-]+):\s*(.+)$")
INLINE = re.compile(r"!?\[([^\]\n]*)\]\(\s*(<[^>\n]+>|[^\s\n)]+)(?:\s+[\"'][^\n]*?[\"'])?\s*\)")
DEFINITION = re.compile(r"^ {0,3}\[([^\]\n]+)\]:\s*(<[^>\n]+>|\S+)", re.MULTILINE)
REFERENCE = re.compile(r"!?\[([^\]\n]+)\](?:\[([^\]\n]*)\])?")


def label(value):
    return " ".join(value.split()).casefold()


def masked(text, inline_code=True):
    """Replace fences/comments/inline code with spaces, keeping source offsets."""
    out, fence = [], None
    for line in text.splitlines(keepends=True):
        match = re.match(r"^\s*(`{3,}|~{3,})", line)
        if match:
            mark = match[1]
            if fence is None:
                fence = (mark[0], len(mark))
            elif mark[0] == fence[0] and len(mark) >= fence[1]:
                fence = None
            out.append(re.sub(r"[^\r\n]", " ", line))
        elif fence:
            out.append(re.sub(r"[^\r\n]", " ", line))
        else:
            out.append(line)
    result = "".join(out)
    blank = lambda m: re.sub(r"[^\r\n]", " ", m[0])
    result = re.sub(r"<!--.*?-->", blank, result, flags=re.S)
    return re.sub(r"(`+)([^\n]*?)\1", blank, result) if inline_code else result


@dataclass(frozen=True)
class Citation:
    target: str
    start: int
    end: int
    target_start: int
    target_end: int
    kind: str
    definition: bool = False


def citations(text):
    view = masked(text)
    definitions = {label(m[1]): m for m in DEFINITION.finditer(view)}
    result, occupied = [], []
    for m in INLINE.finditer(view):
        result.append(Citation(m[2].strip('<>'), m.start(), m.end(), m.start(2), m.end(2), 'inline'))
        occupied.append((m.start(), m.end()))
    for m in definitions.values():
        result.append(Citation(m[2].strip('<>'), m.start(), m.end(), m.start(2), m.end(2), 'reference', True))
        occupied.append((m.start(), m.end()))
    for m in REFERENCE.finditer(view):
        if any(a <= m.start() < b for a, b in occupied):
            continue
        key = label(m[2] if m[2] else m[1])
        definition = definitions.get(key)
        if definition:
            result.append(Citation(definition[2].strip('<>'), m.start(), m.end(),
                                   definition.start(2), definition.end(2), 'reference'))
    return sorted(result, key=lambda c: (c.start, c.definition))


def unresolved_references(text):
    view = masked(text)
    defs = {label(m[1]) for m in DEFINITION.finditer(view)}
    result = [m[0] for m in re.finditer(r"\[([^\]\n]+)\]\[([^\]\n]*)\]", view)
              if label(m[2] or m[1]) not in defs]
    return result


def expand_references(text, document):
    """Give the legacy finding-field parser resolved inline review citations."""
    defs = {label(m[1]): m[2] for m in DEFINITION.finditer(masked(document))}
    def replace(m):
        destination = defs.get(label(m[2] or m[1]))
        return f'[{m[1]}]({destination})' if destination else m[0]
    text = re.sub(r"\[([^\]\n]+)\]\[([^\]\n]*)\]", replace, text)
    return re.sub(r"(?<!!)\[([^\]\n]+)\](?![\[(])",
                  lambda m: f'[{m[1]}]({defs[label(m[1])]})' if label(m[1]) in defs else m[0], text)


def slug(title):
    title = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", title)
    return re.sub(r"[^\w\- ]", "", title.casefold()).replace(" ", "-")


def anchors(text):
    counts, result = {}, set()
    for m in HEADING.finditer(masked(text, False)):
        name = slug(m[2]); number = counts.get(name, 0); counts[name] = number + 1
        result.add(name if not number else f'{name}-{number}')
    result.update(re.findall(r'<a\s+(?:id|name)=["\']([^"\']+)', masked(text, False)))
    return result


def local_target(root, source, target):
    target = unquote(target.strip('<>'))
    if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", target) or target.startswith('//'):
        return None
    relative, _, anchor = target.partition('#')
    path = (source.parent / relative).resolve() if relative else source.resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f'citation escapes workspace: {target}')
    return path, anchor


def units(text):
    headings = list(HEADING.finditer(masked(text, False)))
    result = []
    for index, h in enumerate(headings):
        match = UNIT.fullmatch(h[2])
        if not match:
            continue
        end = next((later.start() for later in headings[index+1:] if len(later[1]) <= len(h[1])), len(text))
        result.append({'id': match[2], 'kind': match[1], 'title': match[3], 'start': h.start(),
                       'end': end, 'line': text[:h.start()].count('\n')+1, 'text': text[h.start():end]})
    return result


def projection(text, include_code=False):
    """Conservative visible-text tokens; URLs and formatting are not growth."""
    text = re.sub(r'<!--.*?-->', '', text, flags=re.S)
    lines, fence, review, technical = [], None, False, []
    def protect(value):
        technical.append(value)
        return f'\ue000{len(technical)-1}\ue001'
    for line in text.splitlines():
        match = re.match(r'^\s*(`{3,}|~{3,})', line)
        if match:
            mark = match[1]
            if fence is None: fence = (mark[0], len(mark))
            elif fence[0] == mark[0] and len(mark) >= fence[1]: fence = None
            continue
        if fence:
            if include_code: lines.append(protect(line))
            continue
        if re.match(r'^\*\*(Review basis|Standing):\*\*', line):
            review = True; continue
        if re.match(r'^\*\*[A-Za-z ]+:\*\*|^#{1,6}\s', line): review = False
        if review or DEFINITION.match(line): continue
        if re.fullmatch(r'\s*\|?\s*[:\-]+(?:\s*\|\s*[:\-]+)+\s*\|?\s*', line): continue
        lines.append(line)
    result = '\n'.join(lines)
    result = re.sub(r'(`+)([^\n]*?)\1', lambda m: protect(m[2]), result)
    result = INLINE.sub(lambda m: m[1] if not m[1].isdigit() else '', result)
    defs = {label(m[1]) for m in DEFINITION.finditer(masked(text))}
    result = REFERENCE.sub(lambda m: (m[1] if not m[1].isdigit() else '')
                           if label(m[2] or m[1]) in defs else m[0], result)
    result = re.sub(r'^\s*#{1,6}\s+', '', result, flags=re.M)
    result = re.sub(r'\*\*(.+?)\*\*|__(.+?)__', lambda m: m[1] or m[2], result)
    result = re.sub(r'^\s*(?:[-*+]\s+|>\s*)', '', result, flags=re.M)
    result = result.replace('|', ' ')
    result = re.sub(r'\ue000(\d+)\ue001', lambda m: technical[int(m[1])], result)
    return ' '.join(result.split())
