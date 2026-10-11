"""Batch organizational review of committed research references; no game I/O."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from uuid import uuid4

try:
    import research_markdown as md
except ModuleNotFoundError:
    from scripts.workspace import research_markdown as md

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = 'docs/research/catalog/maintenance.json'
MEASUREMENT = 1
ROLES = {'subject', 'index', 'gateway', 'template', 'workflow'}
DEFAULTS = {'word_threshold': 2000, 'unit_threshold': 12, 'change_percent': 20}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def inside(root, path):
    value = Path(path)
    resolved = (root/value).resolve()
    if value.is_absolute() or not resolved.is_relative_to(root.resolve()):
        raise ValueError(f'path escapes workspace: {path}')
    return resolved


def read(path):
    before = path.stat()
    if before.st_size > md.CEILING: raise ValueError(f'oversized document: {path}')
    with path.open('rb') as stream:
        raw = stream.read(md.CEILING+1)
        opened = os.fstat(stream.fileno())
    after = path.stat()
    stamp = lambda s: (s.st_size, s.st_mtime_ns, s.st_ino)
    if len(raw) > md.CEILING or stamp(before) != stamp(opened) or stamp(before) != stamp(after):
        raise ValueError(f'document changed during read: {path}')
    return raw


def git(root, *args, accepted=(0,), index=None, input=None):
    env = os.environ.copy()
    # A caller's temporary-index setting must not affect committed-state checks.
    env.pop('GIT_INDEX_FILE', None)
    if index is not None: env['GIT_INDEX_FILE'] = str(index)
    p = subprocess.run(['git', '-c', f'safe.directory={root.as_posix()}',
                        '--no-pager', *args], cwd=root, env=env, input=input, capture_output=True)
    if p.returncode not in accepted:
        detail = (p.stderr or p.stdout).decode(errors='replace').strip()[:1500]
        raise ValueError(f'Git {args[0]} failed: {detail}')
    return p.stdout


def git_blob(root, revision, path):
    inside(root, path)
    size = int(git(root, 'cat-file', '-s', f'{revision}:{path}').strip())
    if size > md.CEILING: raise ValueError(f'oversized Git document: {path}')
    raw = git(root, 'show', f'{revision}:{path}')
    if len(raw) > md.CEILING: raise ValueError(f'oversized Git output: {path}')
    return raw


def metrics(text):
    found = md.units(text)
    return {'words': len(md.projection(text).split()),
            'comparison_words': len(md.projection(text, True).split()),
            'unit_count': len(found), 'unit_ids': [u['id'] for u in found]}


def changed(root, before, after):
    old, new = md.projection(before, True), md.projection(after, True)
    # Git performs the comparison; projection files are disposable and not tracked.
    with tempfile.TemporaryDirectory(prefix='research-doc-diff-') as directory:
        a, b = Path(directory)/'before.txt', Path(directory)/'after.txt'
        a.write_text(old+'\n', encoding='utf-8'); b.write_text(new+'\n', encoding='utf-8')
        output = git(root, 'diff', '--no-index', '--no-ext-diff', '--no-textconv',
                     '--word-diff=porcelain', '--word-diff-regex=[^[:space:]]+',
                     '--', str(a), str(b), accepted=(0, 1)).decode('utf-8')
    added = removed = 0
    for line in output.splitlines():
        if line.startswith('+') and not line.startswith('+++'): added += len(line[1:].split())
        if line.startswith('-') and not line.startswith('---'): removed += len(line[1:].split())
    denominator = len(old.split())
    return {'added_words': added, 'removed_words': removed,
            'percent': 100*max(added, removed)/denominator if denominator else (100 if new else 0),
            'empty_baseline': not denominator}


def settings(registry, page):
    result = {**registry['defaults'], **page.get('overrides', {})}
    if set(result) != set(DEFAULTS): raise ValueError('unknown/missing threshold setting')
    for key, value in result.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
            raise ValueError(f'invalid threshold {key}')
    return result


def load(root):
    raw = read(inside(root, REGISTRY)); registry = json.loads(raw)
    if registry.get('schema_version') != 1: raise ValueError('unsupported registry schema')
    if not isinstance(registry.get('pages'), list): raise ValueError('registry pages must be a list')
    ids, paths = set(), set()
    for p in registry['pages']:
        if p.get('id') in ids or p.get('path') in paths: raise ValueError('duplicate page identity/path')
        ids.add(p['id']); paths.add(p['path']); inside(root, p['path'])
        if p.get('role') not in ROLES or not p.get('rationale'): raise ValueError('page role needs a rationale')
        if not isinstance(p.get('onboarded'), bool): raise ValueError('page onboarded must be boolean')
        settings(registry, p)
    for p in registry.get('retired', []): inside(root, p['path'])
    settings(registry, {})
    return registry, raw


def lint(root, path, text, role='subject', onboarded=True):
    issues = []
    if md.unresolved_references(text): issues.append('unresolved reference-style citation')
    try:
        for link in md.citations(text):
            target = md.local_target(root, root/path, link.target)
            if target is None: continue
            destination, anchor = target
            if not destination.exists(): issues.append(f'missing citation target: {link.target}')
            elif anchor and destination.suffix == '.md' and anchor not in md.anchors(read(destination).decode('utf-8-sig')):
                issues.append(f'missing citation heading: {link.target}')
    except (OSError, UnicodeError, ValueError) as exc:
        issues.append(str(exc))
    if role == 'subject' and onboarded:
        found = md.units(text)
        if not found: issues.append('subject has no marked reference units')
        for parent in found:
            if any(parent['start'] < child['start'] < parent['end'] for child in found):
                issues.append('nested reference units: '+parent['id'])
        for heading in md.HEADING.finditer(md.masked(text, False)):
            if heading[2].startswith(('Finding ', 'Contract ', 'Negative result ')) and not md.UNIT.fullmatch(heading[2]):
                issues.append('malformed reference-unit heading: '+heading[2])
        for unit in found:
            if not any(not c.definition for c in md.citations(unit['text'])):
                # Reference definitions may be page-wide.
                expanded = md.expand_references(unit['text'], text)
                if not md.citations(expanded): issues.append(f'unit lacks source citation: {unit["id"]}')
    return sorted(set(issues))


def audit(root=ROOT):
    registry, _ = load(root)
    pages = {p['path']: p for p in registry['pages']}
    files = {p.relative_to(root).as_posix() for p in (root/'docs/research').rglob('*.md')}
    rows, errors, seen_units = [], [], {}
    for path in sorted(files | set(pages)):
        p = pages.get(path)
        row = {'path': path, 'id': p['id'] if p else None, 'reasons': [], 'issues': [], 'review_needed': False}
        try:
            source_raw = read(inside(root, path)); text = source_raw.decode('utf-8-sig'); row['sha256'] = digest(source_raw)
            row['metrics'] = metrics(text)
            for unit in md.units(text): seen_units.setdefault(unit['id'], []).append(path)
            if not p:
                row['reasons'].append('unclassified'); row['review_needed'] = True
            else:
                row['role'] = p['role']; row['settings'] = settings(registry, p)
                row['issues'] = lint(root, path, text, p['role'], p['onboarded'])
                if p['role'] == 'subject':
                    if not p['onboarded']:
                        row['reasons'].append('legacy-onboarding'); row['review_needed'] = True
                        row['authoritative_unit_count'] = False
                    else: row['authoritative_unit_count'] = True
                    limits = row['settings']
                    oversized = row['metrics']['words'] > limits['word_threshold'] or row['metrics']['unit_count'] > limits['unit_threshold']
                    row['size_exceeded'] = oversized
                    baseline = p.get('baseline')
                    if baseline:
                        inside(root, baseline['path'])
                        original = git_blob(root, baseline['commit'], baseline['path'])
                        if digest(original) != baseline['sha256']: raise ValueError('baseline content hash mismatch')
                        if baseline['measurement_version'] != MEASUREMENT:
                            row['reasons'].append('measurement-version'); row['review_needed'] = True
                        else:
                            row['change'] = changed(root, original.decode('utf-8-sig'), text)
                            if row['change']['empty_baseline']:
                                row['issues'].append('empty retained comparison baseline')
                            if oversized and row['change']['percent'] >= limits['change_percent']:
                                row['reasons'].append('retained-growth'); row['review_needed'] = True
                    elif oversized:
                        row['reasons'].append('unretained-size'); row['review_needed'] = True
        except (OSError, UnicodeError, ValueError, KeyError) as exc:
            row['issues'].append(str(exc))
        for issue in row['issues']: errors.append({'path': path, 'issue': issue})
        rows.append(row)
    for unit, owners in seen_units.items():
        if len(owners) > 1: errors.append({'id': unit, 'issue': 'duplicate unit ID', 'owners': owners})
    return {'measurement_version': MEASUREMENT, 'pages': rows, 'errors': errors,
            'review_count': sum(r['review_needed'] for r in rows), 'complete': not errors}


def atomic(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    name = path.with_name(f'.{path.name}.{uuid4().hex}.tmp')
    try:
        with name.open('xb') as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if name.exists(): name.unlink()


def encoded(value):
    return (json.dumps(value, indent=2, ensure_ascii=False)+'\n').encode('utf-8')


def propose(root, output, paths=None):
    report = audit(root); registry, raw = load(root)
    chosen = [r for r in report['pages'] if (r['path'] in paths if paths else r['review_needed'])]
    if paths and set(paths) - {r['path'] for r in chosen}: raise ValueError('unknown proposal page')
    pages = {p['path']: p for p in registry['pages']}
    items = []
    for r in chosen:
        if 'sha256' not in r: raise ValueError(f'unreadable proposal source: {r["path"]}')
        p = pages.get(r['path'], {'id': Path(r['path']).stem, 'role': 'subject'})
        items.append({'id': p['id'], 'action': 'retain', 'approval': 'pending',
                      'sources': [{'path': r['path'], 'sha256': r['sha256']}],
                      'triggers': r['reasons'], 'metrics': r['metrics'], 'rationale': '',
                      'citation_support': 'pending', 'technical_evidence': 'pending',
                      'unit_ownership': [], 'content_relocations': [], 'factual_changes': [],
                      'unresolved': r['issues'], 'patches': [], 'retire': [],
                      'outputs': [{'id': p['id'], 'path': r['path'], 'sha256': r['sha256'],
                                   'role': p['role'], 'onboarded': True}]})
    value = {'schema_version': 1, 'measurement_version': MEASUREMENT,
             'batch_id': uuid4().hex, 'created_at': datetime.now(timezone.utc).isoformat(),
             'registry_sha256': digest(raw), 'items': items}
    destination = inside(root, output)
    if not destination.is_relative_to(root/'experiments'): raise ValueError('proposal belongs in a dated investigation')
    if destination.exists(): raise ValueError('proposal already exists; do not overwrite human decisions')
    atomic(destination, encoded(value))
    return value


def finalize(root, proposal_path, dry_run=False):
    proposal = json.loads(read(inside(root, proposal_path)))
    if proposal.get('schema_version') != 1 or proposal.get('measurement_version') != MEASUREMENT:
        raise ValueError('proposal schema/measurement mismatch')
    if any(i.get('approval') not in {'pending', 'approved', 'rejected'} for i in proposal['items']):
        raise ValueError('unknown human decision state')
    approved = [i for i in proposal['items'] if i.get('approval') == 'approved']
    if not approved:
        return {'ok': True, 'errors': [], 'updated': [], 'retired': [], 'changed': False, 'dry_run': dry_run}
    registry, raw = load(root); result = deepcopy(registry)
    head = git(root, 'rev-parse', 'HEAD').decode().strip()
    errors, updates, retire = [], {}, set()
    output_paths = set(); checked_outputs = {}
    for item in approved:
        try:
            if item.get('action') not in {'retain', 'split', 'onboard'}: raise ValueError('unknown review action')
            if not item.get('rationale') or item.get('unresolved'): raise ValueError('rationale missing or unresolved review issues')
            if item.get('citation_support') != 'accepted' or item.get('technical_evidence') not in {'unchanged', 'reviewed'}:
                raise ValueError('citation support and technical evidence require explicit review')
            for patch in item.get('patches', []):
                if digest(read(inside(root, patch['path']))) != patch['sha256']: raise ValueError('approved patch changed')
            if not item.get('outputs'): raise ValueError('approved item has no outputs')
            retire.update(item.get('retire', []))
            for output in item['outputs']:
                path = output['path']; source = inside(root, path)
                if path in output_paths or output['id'] in updates: raise ValueError('duplicate approved output')
                output_paths.add(path)
                committed = git_blob(root, head, path)
                if digest(committed) != output['sha256'] or read(source) != committed or git_blob(root, '', path) != committed:
                    raise ValueError(f'approved/HEAD/worktree/index mismatch: {path}')
                checked_outputs[path] = output['sha256']
                revision = git(root, 'log', '-1', '--format=%H', head, '--', path).decode().strip()
                if not revision or git_blob(root, revision, path) != committed: raise ValueError(f'latest document commit disagrees with HEAD: {path}')
                if output.get('role') not in ROLES or not isinstance(output.get('onboarded'), bool): raise ValueError('invalid output classification')
                if output['role'] == 'subject' and not output['onboarded']: raise ValueError('subject onboarding not complete')
                text = committed.decode('utf-8-sig')
                issues = lint(root, path, text, output['role'], output['onboarded'])
                if issues: raise ValueError('; '.join(issues))
                if output.get('track', True) is False:
                    continue  # Validate auxiliary navigation/evidence, without registering it as a subject page.
                previous = next((p for p in result['pages'] if p['id'] == output['id']), {})
                page = {**previous, 'id': output['id'], 'path': path, 'role': output['role'],
                        'onboarded': output['onboarded'],
                        'rationale': previous.get('rationale', f'{output["role"]} owner established by approved batch'),
                        'accepted_rationale': {'proposal': proposal_path, 'item': item['id']},
                        'decision': item['action'], 'proposal': proposal_path,
                        'baseline': {'commit': revision, 'path': path, 'sha256': output['sha256'],
                                     'measurement_version': MEASUREMENT, 'metrics': metrics(text)}}
                settings(result, page); updates[page['id']] = page
        except (OSError, UnicodeError, ValueError, KeyError) as exc:
            errors.append({'item': item.get('id'), 'issue': str(exc)})
    existing = {p['id']: p for p in result['pages']}
    for page_id in retire:
        if page_id not in existing:
            if not any(p['id'] == page_id and p.get('retired_by') == proposal_path for p in result.get('retired', [])):
                errors.append({'item': page_id, 'issue': 'retired ID not registered'})
        elif page_id in updates: errors.append({'item': page_id, 'issue': 'cannot retire and update same ID'})
        else:
            record = {**existing.pop(page_id), 'retired_by': proposal_path}
            if record not in result.setdefault('retired', []): result['retired'].append(record)
    existing.update(updates); result['pages'] = sorted(existing.values(), key=lambda p: p['path'])
    ids, paths, unit_ids = set(), set(), set()
    for page in result['pages']:
        if page['id'] in ids or page['path'] in paths: errors.append({'issue': 'duplicate resulting page identity/path'})
        ids.add(page['id']); paths.add(page['path'])
        try:
            if page['role'] == 'subject':
                for unit in md.units(read(inside(root, page['path'])).decode('utf-8-sig')):
                    if unit['id'] in unit_ids: errors.append({'issue': f'duplicate resulting unit: {unit["id"]}'})
                    unit_ids.add(unit['id'])
        except (OSError, UnicodeError, ValueError) as exc: errors.append({'issue': str(exc)})
    if errors: return {'ok': False, 'errors': errors, 'updated': [], 'dry_run': dry_run}
    deleted = {p for item in approved for p in item.get('deleted_paths', [])}
    supporting_sources = {s['path']: s['sha256'] for item in approved for s in item['sources']
                          if s['path'] not in output_paths | deleted}
    for path, expected_hash in supporting_sources.items():
        if digest(read(inside(root, path))) != expected_hash:
            raise ValueError('reviewed support changed before finalization: '+path)
    new = encoded(result)
    summary = {'ok': True, 'errors': [], 'updated': sorted(updates), 'retired': sorted(retire),
               'changed': new != raw, 'dry_run': dry_run, 'head': head}
    if dry_run: return summary
    lock = root/'local/research-doc-maintenance/finalize.lock'
    lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        stream = lock.open('xb')
    except FileExistsError as exc:
        raise ValueError(f'finalization lock held; no takeover: {lock}') from exc
    try:
        with stream:
            stream.write(encoded({'pid': os.getpid(), 'batch': proposal['batch_id']})); stream.flush()
            if read(inside(root, REGISTRY)) != raw: raise ValueError('registry changed during validation')
            if git(root, 'rev-parse', 'HEAD').decode().strip() != head: raise ValueError('HEAD changed during validation')
            for path, expected_hash in checked_outputs.items():
                if digest(read(inside(root, path))) != expected_hash:
                    raise ValueError('document changed during finalization')
                if git_blob(root, '', path) != git_blob(root, head, path):
                    raise ValueError('index changed during finalization')
            if read(inside(root, REGISTRY)) != raw: raise ValueError('registry changed before publication')
            if git(root, 'rev-parse', 'HEAD').decode().strip() != head: raise ValueError('HEAD changed before publication')
            if json.loads(read(inside(root, proposal_path))) != proposal: raise ValueError('proposal changed during finalization')
            for path, expected_hash in supporting_sources.items():
                if digest(read(inside(root, path))) != expected_hash:
                    raise ValueError('reviewed support changed during finalization: '+path)
            if new != raw: atomic(inside(root, REGISTRY), new)
    finally:
        lock.unlink()
    return summary


def validate_sources(root, proposal):
    """Call immediately before applying approved patches, never after applying."""
    for item in proposal['items']:
        if item.get('approval') != 'approved': continue
        for source in item['sources']:
            if digest(read(inside(root, source['path']))) != source['sha256']:
                raise ValueError(f'stale approved source: {source["path"]}')
        for patch in item.get('patches', []):
            if digest(read(inside(root, patch['path']))) != patch['sha256']:
                raise ValueError('approved patch changed')


def commit_batch(root, proposal_path, message):
    """Explicit operator API: commit approved outputs using an isolated index.

    Never called by audit/propose/finalize. Preserves unrelated regular-index
    entries, refuses overlapping staged changes, and never invents approvals.
    """
    proposal = json.loads(read(inside(root, proposal_path)))
    approved = [i for i in proposal['items'] if i.get('approval') == 'approved']
    outputs = {o['path']: o for i in approved for o in i['outputs']}
    if len(outputs) != sum(len(i['outputs']) for i in approved): raise ValueError('duplicate approved commit output')
    deleted = {p for i in approved for p in i.get('deleted_paths', [])}
    paths = set(outputs) | deleted
    if not paths: raise ValueError('no approved commit paths')
    for item in approved:
        if item.get('unresolved') or not item.get('rationale'): raise ValueError('incomplete approved proposal')
    for path, output in outputs.items():
        if digest(read(inside(root, path))) != output['sha256']: raise ValueError('commit differs from approved output')
    for path in deleted:
        if inside(root, path).exists(): raise ValueError('approved deletion not applied')
    head = git(root, 'rev-parse', 'HEAD').decode().strip()
    original_entries = git(root, 'ls-files', '--stage', '-z', '--', *sorted(paths))
    staged = set(git(root, 'diff', '--cached', '--name-only', '--no-renames', '-z').decode().strip('\0').split('\0'))-{''}
    if staged & paths: raise ValueError('preexisting staged changes overlap approved paths')
    with tempfile.TemporaryDirectory(prefix='research-doc-index-') as directory:
        temporary_index = Path(directory)/'index'
        git(root, 'read-tree', head, index=temporary_index)
        for path in sorted(outputs):
            oid = git(root, 'hash-object', '-w', '--stdin', input=read(inside(root, path))).decode().strip()
            git(root, 'update-index', '--add', '--cacheinfo', f'100644,{oid},{path}', index=temporary_index)
        for path in sorted(deleted): git(root, 'update-index', '--force-remove', '--', path, index=temporary_index)
        git(root, '-c', 'core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol',
            'diff', '--cached', '--check', index=temporary_index)
        if git(root, 'rev-parse', 'HEAD').decode().strip() != head: raise ValueError('HEAD changed before commit')
        if git(root, 'ls-files', '--stage', '-z', '--', *sorted(paths)) != original_entries:
            raise ValueError('regular index changed for batch paths')
        # Verify staged bytes, not just a path list.
        for path, output in outputs.items():
            raw = git(root, 'show', ':'+path, index=temporary_index)
            if digest(raw) != output['sha256']: raise ValueError('temporary index output mismatch')
        if not git(root, 'diff', '--cached', '--name-only', index=temporary_index).strip(): return head
        git(root, 'commit', '-m', message, index=temporary_index)
    revision = git(root, 'rev-parse', 'HEAD').decode().strip()
    # Only batch paths are synchronized; unrelated staged blobs remain exact.
    for path in sorted(outputs):
        oid = git(root, 'rev-parse', revision+':'+path).decode().strip()
        git(root, 'update-index', '--add', '--cacheinfo', f'100644,{oid},{path}')
    for path in sorted(deleted): git(root, 'update-index', '--force-remove', '--', path)
    return revision


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    commands = parser.add_subparsers(dest='command', required=True)
    check = commands.add_parser('audit'); check.add_argument('--format', choices=['text', 'json'], default='text')
    draft = commands.add_parser('propose'); draft.add_argument('--output', required=True); draft.add_argument('--paths', nargs='+')
    finish = commands.add_parser('finalize'); finish.add_argument('--proposal', required=True); finish.add_argument('--dry-run', action='store_true')
    args = parser.parse_args(argv); root = args.root.resolve()
    try:
        if args.command == 'audit':
            value = audit(root)
            if args.format == 'json': print(json.dumps(value, indent=2))
            else:
                for row in value['pages']:
                    print(f'{row["path"]}: {", ".join(row["reasons"]) or "no size review"}; issues={len(row["issues"])}')
                for error in value['errors'][:20]: print(json.dumps(error))
                print(f'{len(value["pages"])} pages; {value["review_count"]} reviews; {len(value["errors"])} errors')
            return 2 if not value['complete'] else int(bool(value['review_count']))
        if args.command == 'propose': value = propose(root, args.output, args.paths)
        else: value = finalize(root, args.proposal, args.dry_run)
        print(json.dumps(value, indent=2))
        return 0 if value.get('ok', True) else 2
    except (OSError, ValueError, KeyError, UnicodeError) as exc:
        print(json.dumps({'ok': False, 'error': str(exc)})); return 2


if __name__ == '__main__': raise SystemExit(main())
