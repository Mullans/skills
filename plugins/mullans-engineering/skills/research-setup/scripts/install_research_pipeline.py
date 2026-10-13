"""Install the four-skill research system without overwriting existing project files."""
import argparse
import json
from pathlib import Path


def resources(skill_root):
    """The maintenance skill owns reusable policy and implementation assets."""
    skills = Path(skill_root).resolve().parent
    required = ('research-setup', 'research-handoff', 'research-promotion',
                'maintain-research-docs')
    absent = [name for name in required if not (skills / name / 'SKILL.md').is_file()]
    if absent:
        raise ValueError('research pipeline skills missing: ' + ', '.join(absent))
    assets = skills / 'maintain-research-docs/assets/research-system'
    expected = (
        'docs/wiki.md', 'docs/research/reference-template.md',
        'docs/research/experiment-protocol.md',
        'docs/research/catalog/README.md', 'docs/research/catalog/maintenance.md',
        'docs/research/catalog/config.json', 'docs/research/catalog/subjects.json',
        'docs/research/catalog/maintenance.json',
        'scripts/workspace/research_catalog.py', 'scripts/workspace/research_docs.py',
        'scripts/workspace/research_markdown.py', 'scripts/workspace/check_doc_links.py',
    )
    result = {}
    for name in expected:
        path = assets / name
        raw = path.read_bytes()
        if len(raw) > 1024 * 1024:
            raise ValueError('oversized pipeline asset: ' + name)
        result[name] = raw
    result['docs/handoffs/README.md'] = (skills / 'research-handoff/assets/lifecycle.md').read_bytes()
    return result


def install(root, skill_root, *, dry_run=False, check=False):
    root = Path(root).resolve()
    copies = resources(skill_root)
    created, existing, missing = [], [], []
    destinations = {}
    for name in copies:
        path = root / name
        if not path.resolve().is_relative_to(root):
            raise ValueError('destination escapes project: ' + name)
        if path.exists() and not path.is_file():
            raise ValueError('pipeline destination is not a file: ' + name)
        destinations[name] = path
    for name, raw in copies.items():
        path = destinations[name]
        if path.exists():
            existing.append(name)
        elif check:
            missing.append(name)
        elif dry_run:
            created.append(name)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            try:
                with path.open('xb') as stream:
                    stream.write(raw)
            except FileExistsError:
                # A concurrent creator wins; preserve its content for adoption review.
                if not path.is_file():
                    raise ValueError('concurrent non-file destination: ' + name)
                existing.append(name)
            else:
                created.append(name)
    return {'ok': not missing, 'mode': 'check' if check else 'preview' if dry_run else 'install',
            'root': str(root), 'created': created, 'preserved_existing': existing,
            'missing': missing,
            'adoption_review_required': bool(existing)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--dry-run', action='store_true')
    modes.add_argument('--check', action='store_true')
    args = parser.parse_args(argv)
    skill_root = Path(__file__).resolve().parents[1]
    try:
        result = install(args.root, skill_root, dry_run=args.dry_run, check=args.check)
    except (OSError, ValueError) as error:
        print(json.dumps({'ok': False, 'error': str(error)}))
        return 2
    print(json.dumps(result, indent=2))
    return 0 if result['ok'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
