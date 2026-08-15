# Theme Design

Theme authoring reference. Setup, CLI, and markdown syntax are in `SKILL.md`.

## Setup

Project themes: `.mark2word/themes/`. Chain from `assets/base-theme.yaml` (copy or `extends`).

```yaml
---
extends: executive-resume.yaml   # frontmatter or in theme YAML
---
```

`extends` resolves: markdown directory → each `--theme-dir` → auto `.mark2word/themes` (unless `--no-auto-theme-dir`). Child deep-merges over parent; cycles rejected. Prefer layered files over one giant theme.

**Example chain:** `showcase.md` → `showcase-theme.yaml` → `showcase-base.yaml`; frontmatter can add `$pullquote: { color: "943634" }`.

## Style Priority

1. Built-in `defaults.yaml` (code fills, blockquote bar, list indents)
2. Theme `extends` chain
3. Frontmatter globals
4. Region path outer → inner (regions: theme + frontmatter only, not built-in defaults)

Within a layer: top-level props → category chain (later wins):

| Element | Chain |
|---------|--------|
| Body | top-level → `text` → `body` |
| Heading | top-level → `heading` → `h1`…`h6` |
| Fenced code | top-level → `code` → `code_block` |
| Inline code | top-level → `code` → `code_inline` |
| Blockquote | top-level → `text` → `blockquote` |
| Table cell | top-level → `table` → `th` / `td` |
| List | top-level → `list` → `ol` / `ul` |

**Regions:** top-level `$region` keys (`font`, `color`, `italic`, …) apply to body text; nested `body`, `h2`, `table`, … target elements. Nested `body` wins on conflicts for run props; use it for align/indents/spacing.

## Target Keys

| Key | Applies to |
|-----|------------|
| `body`, `text` | Paragraphs; `text` shared with lists |
| `blockquote` | `>` lines (single-cell table, optional fill/borders) |
| `code`, `code_block`, `code_inline` | Shared typography / fenced / inline |
| `image`, `hr` | Images, horizontal rules |
| `list`, `ol`, `ul` | Lists (`ol`/`ul` override shared `list`) |
| `heading`, `h1`–`h6` | Headings |
| `table`, `th`, `td` | Pipe tables |
| `$name` | `<!-- region: name -->` |

See `assets/base-theme.yaml` for a complete starter theme.

## Style Keys

Typography & layout: `font`, `size`, `color`, `bold`, `italic`, `align`, `line`, `space_before` / `space_after` / `space_between`, `indent_left` / `indent_right` / `indent_first_line` / `indent_hanging`.

Borders & fill: `border_bottom`, `border_left`, `border_right` — `{ size, color }`; `none` disables. `fill` — background; `none` disables. `padding` — `{ top, bottom, left, right }` on `th`/`td` or blockquote.

| `fill` on | Effect |
|-----------|--------|
| `th`/`td` | Cell background |
| `code_block` | Paragraph shading (one paragraph per line when multi-line) |
| `code_inline` | Run highlight on backticks |
| `blockquote` | Shaded quote cell |

**Image:** `width`, `max_width`, `align`; `alt_mode` — `doc` (accessibility metadata, default), `caption`, `both`, `none`.

**Table:** `border` on `table`; `padding` on `th`/`td`; `space_before`/`space_after` on `table`.

**Code:** typography under `code`; `fill`/`langs` under `code_block` or `code_inline`. Lang overrides: `code_block.langs.{tag}` or `code.langs.{tag}` (fence tag = key).

Lengths: `10`, `10pt`, `0.5in`.

## Page Chrome

```yaml
title: My Document          # {title}; else first h1
page:
  size: letter              # or a4
  margin: { top: 0.5in, bottom: 0.5in, left: 0.7in, right: 0.7in }
  header: "{title}"
  footer: "Draft || Page {page} of {pages}"
```

Placeholders: `{page}`, `{pages}`, `{title}`. `||` dual-aligns. Theme header/footer ≠ markdown `$footer-region` body content.

## Lists

Theme drives item styling + native Word multilevel numbering. Meta: `indent_left`, `indent_hanging`, `indent_step`, `levels` (0, 1, 2…). Per level: any style key; `format` shorthand or `num_fmt` + `template` (both required if either set). Default ordered: `1.`. Nesting: 2 spaces; body paragraph between items starts new list run.

| `format` | Examples |
|----------|----------|
| `1` / `1.` | 1, 2 / 1., 2. |
| `01` / `01.` | 01, 02 |
| `a`, `a.`, `A`, `(A)` | Letters |
| `i`, `roman`, `I`, `Roman` | Roman |
| `Section 1:` | Section 1:, … |
| `•`, `-`, `*`, `bullet` | Bullets |

```yaml
ol:  { levels: { 0: { format: "1." }, 1: { format: "a." } } }
ul:  { levels: { 0: { format: "•" }, 1: { format: "◦" } } }
list: { levels: { 2: { color: "943634" } } }
```

## Regions

```yaml
$pullquote:
  font: Georgia
  size: 13
  color: "C00000"
  italic: true
  body:
    align: center
    indent_left: 28pt
    indent_right: 28pt
```

```markdown
<!-- region: pullquote -->
Centered pull quote text.
<!-- /region -->
```

Nested regions supported.

## Element Notes

- **Blockquote:** `>` lines; table cell aligned to text column. `space_before` goes above the table, not inside the shade.
- **HR:** `---`/`***`/`___` alone on a body line; style via `hr`.
- **Tables:** header row + `\| - \|` separator required.
- **Code:** multi-line + `fill` → shaded paragraph per line.

## Workflow

1. Chain from `base-theme.yaml`; set globals and page.
2. Tune headings, lists, tables, code, images.
3. Add `$regions` only for repeated local treatments.
4. `--check-theme` on theme; `--check` on sample markdown.
5. Convert; confirm output exists, then visually inspect user-facing documents when a renderer is available.

## Pitfalls

- Unquoted hex — use `"2B579A"`.
- Flattening `extends` chains into one file.
- Blockquote styling on `body` instead of `blockquote`.
- `alt_mode: doc` expects invisible alt; use `caption`/`both` for visible text.
- Region run props on `$region` top-level or `$region.body`; align/indents under `body`.
- Missing `--theme-dir` for `extends: base-theme.yaml` — include skill `assets/` and project theme folder.
