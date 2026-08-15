---
name: mark2word
description: Use when converting styled Markdown, YAML-frontmatter documents, or .md files into Microsoft Word .docx with mark2word, including selecting or creating project-local themes.
---

# Mark2Word

## Overview

Mark2Word converts styled Markdown into a Word `.docx`. Styling lives in YAML frontmatter, external theme files, and named regions — the Markdown body stays readable in any viewer.

### Supported content

- Headings (`#` … `######`) with Word bookmarks for internal links
- Body paragraphs (one line = one paragraph)
- Bulleted (`-` / `*`) and ordered (`1.`) lists with **nested levels** (2 spaces per indent)
- Blockquotes (`> quoted text`, multi-line)
- Inline **bold**, *italic*, `code`, and [hyperlinks](url) (emphasis inside links works)
- Internal links: `[text](#heading-slug)`
- Dual-aligned lines: `Left || Right` (ignored inside backticks)
- Fenced code blocks (`` ```lang `` … `` ``` ``)
- Pipe tables with separator row
- Images: `![alt](path.png)` (paths relative to the markdown file)
- Horizontal rules: `---`, `***`, or `___` on their own line (body only; frontmatter stripped first)
- Named regions: `<!-- region: name -->` … `<!-- /region -->` (nested supported)
- Page breaks: `<!-- pagebreak -->` (HTML comment, invisible in MD viewers)

### Supported styling

- Global typography, spacing, alignment, borders (`border_bottom`, `border_left`, `border_right`), `indent_left` / `indent_right`
- Element targets: `body`, `text`, `blockquote`, `code`, `code_block`, `code_inline`, `image`, `hr`, `heading`, `h1`–`h6`, `list`, `ol`, `ul`, `table`, `th`, `td`
- **Built-in defaults** (`defaults.yaml`) merged under every theme — code fills, blockquote bar styling, list indents
- **Background fills** — table cells, fenced code (paragraph shading), inline code (run highlight), blockquotes (cell); set `fill: none` to disable
- Per-level list numbering and colors via `list` / `ol` / `ul` → `levels` (including zero-padded `01.`)
- Code per-language overrides: `code_block.langs.{lang}` or `code.langs.{lang}` matched to fence language tags
- Image sizing and alt: `width`, `max_width`, `align`, `alt_mode` (`doc` writes Word accessibility metadata; `caption`/`both` add visible text)
- Table `border`, cell `padding`, `space_before` / `space_after`
- Region blocks (`$name`) with top-level props plus nested element overrides (`body`, `h2`, `table`, …)
- Page size (`letter`, `a4`), margins, **header/footer** with `{page}`, `{pages}`, `{title}` and `||` dual-align
- **Chained themes** via `extends` in frontmatter *and* in theme YAML files

Word-only features (frontmatter, HTML comments) do not appear in normal Markdown preview.

## Resources

- `scripts/mark2word.py` — bundled converter (`python-docx`, `PyYAML`)
- `scripts/requirements.txt` — runtime dependency ranges for the bundled converter
- `assets/base-theme.yaml` — starter theme; pass as `--theme-dir` when documents use `extends: base-theme.yaml` (built-in defaults apply even without this file)
- `references/theme-design.md` — theme authoring reference (read when creating, editing, or substantially customizing themes)

## Convert A Document

Prefer the user's project environment when one exists.

The bundled converter requires Python 3.10 or newer, `python-docx`, and `PyYAML`. If the project environment does not already provide them, install the pinned-compatible ranges into that environment:

```bash
python -m pip install -r /path/to/mark2word/scripts/requirements.txt
```

**Bundled skill script** (absolute paths):

```bash
python /path/to/mark2word/scripts/mark2word.py \
  --theme-dir /path/to/mark2word/assets \
  /path/to/project/document.md \
  -o /path/to/project/document.docx
```

Omit output path to write `<basename>.docx` beside the input.

**Batch:** repeat `-i`; `-o` must be a directory:

```bash
uv run mark2word -i a.md -i b.md -o ./out/
```

**Validate document** (frontmatter, theme chain, markdown parse):

```bash
uv run mark2word --check document.md
```

**Validate theme YAML** (extends chain, page size, list formats, keys):

```bash
uv run mark2word --check-theme .mark2word/themes/my-theme.yaml --theme-dir .mark2word/themes
```

## CLI Options

| Flag | Purpose |
|------|---------|
| `-i` / `--input` | Markdown input (repeat for batch) |
| `-o` / `--output` | Output `.docx` file or directory |
| `--theme-dir` | Folder for relative `extends` paths (repeatable; first match wins) |
| `--no-auto-theme-dir` | Skip auto-discovery of `.mark2word/themes` near the input |
| `--check` | Validate document without writing `.docx` |
| `--check-theme` | Validate theme YAML (including `extends` chain) |
| `--verbose` | Warn on ordered-list number mismatches |
| `-V` / `--version` | Print version |

Exit codes: `0` success, `1` error, `2` usage error.

Inputs, theme chains, and output paths are checked **before** conversion.

## Theme Resolution

```yaml
---
extends: base-theme.yaml
title: My Report
font: Calibri
$header: { align: center }
---
```

**Search order** for relative `extends`:

1. Markdown file's directory
2. Each `--theme-dir`, in order

**Auto-discovery:** `.mark2word/themes` near the input and in parent dirs (unless `--no-auto-theme-dir`).

**Chained inheritance** in theme files:

```text
showcase.md  →  extends: showcase-theme.yaml
showcase-theme.yaml  →  extends: showcase-base.yaml
```

**Style priority:** built-in defaults → theme chain → frontmatter globals → region path (outer → inner). Within each layer: top-level props, then category chains (`code` → `code_block`, `heading` → `h2`, `text` → `body`). Region top-level `font`/`size`/`color` apply to body text inside that region. Details: `references/theme-design.md`.

## Project Local Themes

```text
/path/to/project/.mark2word/themes/my-theme.yaml
```

```yaml
---
extends: my-theme.yaml
---
```

Copy or chain from `assets/base-theme.yaml`. Include `--theme-dir` for skill `assets/` when the chain references `base-theme.yaml`.

## Quick Markdown Reference

```markdown
---
extends: my-theme.yaml
title: My Doc
page:
  footer: "Confidential || Page {page} of {pages}"
---

<!-- region: header -->
# Title
Subtitle || contact@example.com
<!-- /region -->

## Section

See [Overview](#section) for details.

Body with **bold**, *italic*, `code`, and [link](https://example.com).

> Blockquote line one
> line two

Left side || Right side

- Bullet
  - Nested
1. Ordered
   1. Nested
2. Continues

| Col A | Col B |
| - | - |
| one | two |

![Diagram](images/diagram.png)

---

```python
print("hello")
```

<!-- pagebreak -->

## Next Section
```

**Lists:** a body paragraph between items starts a new list run (ordered numbering restarts). `--verbose` warns when markdown numbers skip (e.g. `1.` then `3.`).

**Internal links:** slug from heading text (`## My Section` → `#my-section`).

## Verification

1. Confirm `.docx` exists and is non-empty.
2. Re-run with `--check` or `--check-theme` if validation is needed.
3. For a user-facing deliverable, visually inspect the rendered document when a Word or DOCX renderer is available. If it is not available, verify the document structure programmatically and state that visual QA was not performed.

**Common fixes**

- Missing theme — add `--theme-dir` for skill `assets/` and project theme folder.
- Missing images — paths relative to the markdown file, or absolute.
- Unknown `#anchor` — slug must match an existing heading.
