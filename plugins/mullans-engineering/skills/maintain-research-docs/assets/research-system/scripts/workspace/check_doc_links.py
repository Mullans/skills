"""Check local Markdown links in maintained navigation (no network access)."""
import argparse
from pathlib import Path

try:
    import research_markdown as md
except ModuleNotFoundError:
    from scripts.workspace import research_markdown as md


def check(files, root):
    missing, checked, cache = [], 0, {}
    for path in sorted(files):
        if path.stat().st_size > md.CEILING: raise ValueError(f'Oversized document: {path.name}')
        text = path.read_text(encoding='utf-8-sig')
        for unresolved in md.unresolved_references(text):
            missing.append((path.relative_to(root), unresolved + ' (undefined citation)'))
        for citation in md.citations(text):
            if citation.definition: continue
            result = md.local_target(root, path, citation.target)
            if result is None: continue
            checked += 1
            target, anchor = result
            if not target.exists(): missing.append((path.relative_to(root), citation.target))
            elif anchor and target.suffix == '.md':
                if target not in cache:
                    if target.stat().st_size > md.CEILING: raise ValueError('Oversized heading target')
                    cache[target] = md.anchors(target.read_text(encoding='utf-8-sig'))
                if anchor not in cache[target]: missing.append((path.relative_to(root), citation.target + ' (missing heading)'))
    return checked, missing


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('paths', nargs='*', help='Repository-relative Markdown files/directories')
    args = parser.parse_args()
    root = args.root.resolve()
    selected = args.paths or ['docs', 'experiments']
    files = set()
    for value in selected:
        path = (root/value).resolve()
        if not path.is_relative_to(root) or not path.exists():
            parser.error(f'Missing or out-of-workspace document path: {value}')
        files.update(path.rglob('*.md') if path.is_dir() else [path])
    checked, missing = check(files, root)
    print(f'Checked {checked} local links in {len(files)} documents; missing: {len(missing)}')
    for path, target in missing[:20]: print(f'{path}: {target}')
    if len(missing)>20: print(f'{len(missing)-20} additional missing links; narrow the requested paths.')
    return bool(missing)


if __name__ == '__main__': raise SystemExit(main())
