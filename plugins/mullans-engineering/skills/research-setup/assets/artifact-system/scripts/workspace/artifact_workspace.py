"""Portable experiment workspaces, consumer claims, reuse and assessed cleanup."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
from uuid import uuid4

LIMIT = 1024 * 1024


def utc():
    return datetime.now(timezone.utc)


def digest(path):
    with Path(path).open('rb') as stream:
        value = hashlib.sha256()
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
        return value.hexdigest()


def read_json(path):
    if Path(path).stat().st_size > LIMIT:
        raise ValueError('Metadata exceeds 1 MiB')
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def stamp(path):
    value = Path(path).stat()
    return [value.st_size, value.st_mtime_ns, value.st_dev, value.st_ino]


class Store:
    def __init__(self, project):
        self.project = Path(project).resolve()
        self.local = self.project / 'local'
        self.local.mkdir(exist_ok=True)
        database = self.path(self.local / 'artifacts/index.sqlite3')
        database.parent.mkdir(exist_ok=True)
        self.db = sqlite3.connect(database, timeout=30, isolation_level=None)
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS experiments(id TEXT PRIMARY KEY, state TEXT);
            CREATE TABLE IF NOT EXISTS efforts(owner TEXT PRIMARY KEY, experiment TEXT,
                test TEXT, session TEXT, state TEXT, assessment TEXT);
            CREATE TABLE IF NOT EXISTS roots(path TEXT PRIMARY KEY, owner TEXT);
            CREATE TABLE IF NOT EXISTS files(path TEXT PRIMARY KEY, owner TEXT, signature TEXT);
            CREATE TABLE IF NOT EXISTS claims(path TEXT, consumer TEXT, PRIMARY KEY(path,consumer));
            CREATE TABLE IF NOT EXISTS keeps(id TEXT PRIMARY KEY, files TEXT, reason TEXT, expires TEXT);
            CREATE TABLE IF NOT EXISTS guards(owner TEXT, journal TEXT, proof TEXT, sha TEXT,
                PRIMARY KEY(owner,journal));
            CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, owner TEXT, state TEXT, recipe TEXT);
            CREATE TABLE IF NOT EXISTS recipes(key TEXT PRIMARY KEY, output TEXT, files TEXT);
            CREATE TABLE IF NOT EXISTS receipts(id INTEGER PRIMARY KEY, value TEXT);
        """)

    def close(self):
        self.db.close()

    @contextmanager
    def locked(self):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            yield
            self.db.execute('COMMIT')
        except BaseException:
            self.db.execute('ROLLBACK')
            raise

    def path(self, value):
        path = Path(os.path.abspath(value if Path(value).is_absolute() else self.project / value))
        if not path.is_relative_to(self.local) or path == self.local:
            raise ValueError('Artifact paths must be beneath project local/')
        for part in (path, *path.parents):
            if part.is_symlink() or getattr(part, 'is_junction', lambda: False)():
                raise ValueError('Linked artifact paths are review-only: ' + str(part))
            if part == self.project:
                break
        return path

    def scan(self, root):
        root = self.path(root)
        if root.is_file():
            return [root]
        if not root.is_dir():
            raise ValueError('Missing input directory: ' + str(root))
        result = []
        for current, directories, files in os.walk(root, followlinks=False):
            for name in directories + files:
                self.path(Path(current) / name)
            result += [Path(current) / name for name in files]
        return sorted(result)

    def context(self, path):
        path = self.path(path)
        matches = [(Path(root), owner) for root, owner in self.db.execute('SELECT path,owner FROM roots')
                   if path.is_relative_to(Path(root))]
        if not matches:
            raise ValueError('Register the destination with artifact_workspace.py begin first')
        return max(matches, key=lambda item: len(item[0].parts))[1]

    def active(self, owner):
        row = self.db.execute('SELECT state FROM efforts WHERE owner=?', (owner,)).fetchone()
        if row is None or row[0] != 'active':
            raise ValueError('Owning experiment/test is absent or closed')

    def begin(self, experiment, test='main', root=None, session=None):
        if not all(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,100}', name)
                   for name in (experiment, test)):
            raise ValueError('Use short alphanumeric, hyphen or underscore identities')
        owner = experiment + ':' + test
        root = self.path(root or self.local / 'experiments' / experiment)
        if not root.is_relative_to(self.local / 'experiments' / experiment):
            raise ValueError('New workspaces belong under local/experiments/EXPERIMENT')
        with self.locked():
            experiment_state = self.db.execute('SELECT state FROM experiments WHERE id=?', (experiment,)).fetchone()
            if experiment_state and experiment_state[0] == 'closed':
                raise ValueError('Use a new experiment identity after closeout')
            self.db.execute("INSERT OR IGNORE INTO experiments VALUES (?,'active')", (experiment,))
            row = self.db.execute('SELECT owner FROM roots WHERE path=?', (str(root),)).fetchone()
            if row and row[0] != owner:
                raise ValueError('Root belongs to another test')
            if not row and root.exists() and any(root.iterdir()):
                raise ValueError('Nonempty historical roots need a separate reviewed adoption')
            existing = self.db.execute('SELECT state FROM efforts WHERE owner=?', (owner,)).fetchone()
            if existing and existing[0] != 'active':
                raise ValueError('Use a new identity after closeout')
            self.db.execute('INSERT OR IGNORE INTO efforts VALUES (?,?,?,?,?,?)',
                            (owner, experiment, test, session or os.getenv('CODEX_THREAD_ID', 'local'), 'active', ''))
            self.db.execute('INSERT OR IGNORE INTO roots VALUES (?,?)', (str(root), owner))
            root.mkdir(parents=True, exist_ok=True)
        return dict(owner=owner, root=str(root))

    def reconcile(self, owners=None):
        for root, root_owner in list(self.db.execute('SELECT path,owner FROM roots')):
            if owners and root_owner not in owners:
                continue
            if not Path(root).exists():
                continue
            for path in self.scan(root):
                owner = self.context(path)
                if owners and owner not in owners:
                    continue
                if self.db.execute('SELECT state FROM efforts WHERE owner=?', (owner,)).fetchone()[0] != 'active':
                    continue
                self.db.execute('INSERT OR REPLACE INTO files VALUES (?,?,?)',
                                (str(path), owner, json.dumps(stamp(path))))

    def manifest(self, paths):
        rows = []
        for value in paths:
            for path in self.scan(value):
                rows.append(dict(path=str(path), signature=stamp(path), sha256=digest(path)))
        return sorted({r['path']: r for r in rows}.values(), key=lambda row: row['path'])

    def verify(self, rows):
        for row in rows:
            path = self.path(row['path'])
            if not path.is_file() or stamp(path) != row['signature'] or digest(path) != row['sha256']:
                raise ValueError('Retained artifact changed or disappeared: ' + str(path))

    def claim(self, owner, rows):
        self.active(owner)
        self.verify(rows)
        for row in rows:
            self.db.execute('INSERT OR IGNORE INTO claims VALUES (?,?)', (row['path'], owner))

    def keep(self, paths, reason, days=None, approval=None):
        if not reason.strip():
            raise ValueError('State a specific unresolved question, expected reuse or unique verification value')
        rows = self.manifest(paths)
        if not rows:
            raise ValueError('Select nonempty artifacts')
        if sum(r['signature'][0] for r in rows) > 200 * 1024**2 and not approval:
            raise ValueError('Preservation above 200 MiB needs recorded approval')
        identity = uuid4().hex
        self.db.execute('INSERT INTO keeps VALUES (?,?,?,?)', (identity, json.dumps(rows), reason,
            (utc() + timedelta(days=days)).isoformat() if days else None))
        return dict(id=identity, files=rows)

    def pool(self):
        return [dict(id=i, files=json.loads(files), reason=reason, expires=expires,
                     expired=bool(expires and expires <= utc().isoformat()))
                for i, files, reason, expires in self.db.execute(
                    'SELECT id,files,reason,expires FROM keeps WHERE expires IS NOT NULL')]

    def protected(self, path):
        if self.db.execute('SELECT 1 FROM claims WHERE path=?', (str(path),)).fetchone():
            return True
        for files, expires in self.db.execute('SELECT files,expires FROM keeps'):
            if (not expires or expires > utc().isoformat()) and any(
                    r['path'] == str(path) for r in json.loads(files)):
                return True
        return False

    def assert_writable(self, path, owner):
        self.active(owner)
        if self.context(path) != owner:
            raise ValueError('Destination belongs to another test')
        if Path(path).exists():
            for child in self.scan(path):
                foreign = self.db.execute('SELECT 1 FROM claims WHERE path=? AND consumer<>?',
                                          (str(child), owner)).fetchone()
                kept = any((not expiry or expiry > utc().isoformat()) and any(
                    row['path'] == str(child) for row in json.loads(files))
                    for files, expiry in self.db.execute('SELECT files,expires FROM keeps'))
                if foreign or kept:
                    raise ValueError('Shared or preserved files are immutable; choose a new output')

    def recover(self, root, journal, proof=None):
        owner = self.context(root)
        self.active(owner)
        journal = str(self.path(journal))
        if proof:
            proof = self.path(proof)
            if not proof.is_file() or not proof.stat().st_size:
                raise ValueError('Recovery requires a nonempty operation-specific proof')
        self.db.execute('INSERT OR REPLACE INTO guards VALUES (?,?,?,?)',
                        (owner, journal, str(proof) if proof else None, digest(proof) if proof else None))

    def finish(self, root, assessment, *, experiment=False, writers_closed=False, apply=False):
        if not assessment.strip() or not writers_closed:
            raise ValueError('Assess results and confirm writer closure before finishing')
        owner = self.context(root)
        if not self.db.execute('SELECT 1 FROM roots WHERE path=?', (str(self.path(root)),)).fetchone():
            raise ValueError('Finish requires an exact registered root')
        name = self.db.execute('SELECT experiment FROM efforts WHERE owner=?', (owner,)).fetchone()[0]
        owners = [r[0] for r in self.db.execute('SELECT owner FROM efforts WHERE experiment=?', (name,))] if experiment else [owner]
        with self.locked():
            self.reconcile(owners)
            released_paths = [r[0] for target in owners for r in self.db.execute(
                'SELECT path FROM claims WHERE consumer=?', (target,))]
            affected = {r[0] for path in released_paths for r in self.db.execute(
                'SELECT owner FROM files WHERE path=?', (path,))}
            if all(self.db.execute('SELECT state FROM efforts WHERE owner=?', (target,)).fetchone()[0] == 'closed'
                   for target in owners):
                if experiment:
                    self.db.execute("UPDATE experiments SET state='closed' WHERE id=?", (name,))
                return self.cleanup(apply=apply, owners=owners)
            for target in owners:
                if self.db.execute('SELECT state FROM efforts WHERE owner=?', (target,)).fetchone()[0] == 'closed':
                    continue
                if self.db.execute("SELECT 1 FROM jobs WHERE owner=? AND state='running'", (target,)).fetchone():
                    raise ValueError('Unresolved running/interrupted writer; assess the job before closeout')
                for proof, sha in self.db.execute('SELECT proof,sha FROM guards WHERE owner=?', (target,)):
                    if not proof or digest(self.path(proof)) != sha:
                        raise ValueError('Unresolved recovery; use the restoration helper to create valid proof')
            if experiment:
                self.db.execute("UPDATE experiments SET state='closed' WHERE id=?", (name,))
            for target in owners:
                self.db.execute("UPDATE efforts SET state='closed',assessment=? WHERE owner=?", (assessment, target))
                self.db.execute('DELETE FROM claims WHERE consumer=?', (target,))
            return self.cleanup(apply=apply, owners=owners+list(affected))

    def retirement_receipt(self, value):
        # Independent of the SQLite transaction: a later I/O failure must not
        # erase the record of files already removed.
        path = self.path(self.local / 'artifacts/retirement.jsonl')
        if path.exists() and path.stat().st_size >= LIMIT:
            previous = self.path(path.with_suffix('.previous.jsonl'))
            os.replace(path, previous)
        with path.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(value) + '\n')
            stream.flush()
            os.fsync(stream.fileno())

    def cleanup(self, *, apply=False, owners=None):
        self.reconcile(owners)
        candidates, blocked = [], []
        for name, owner, signature in list(self.db.execute('SELECT path,owner,signature FROM files')):
            if owners and owner not in owners:
                continue
            path = self.path(name)
            if not path.exists():
                self.db.execute('DELETE FROM files WHERE path=?', (name,))
                continue
            state = self.db.execute('SELECT state FROM efforts WHERE owner=?', (owner,)).fetchone()[0]
            if state != 'closed' or self.protected(path):
                continue
            if stamp(path) != json.loads(signature):
                blocked.append(dict(path=name, reason='Changed file; assess before cleanup'))
                continue
            candidates.append(dict(path=name, signature=stamp(path), sha256=digest(path), owner=owner))
        removed = []
        if apply:
            for row in candidates:
                self.verify([row])
                if self.protected(Path(row['path'])):
                    raise ValueError('Artifact gained a consumer; rerun cleanup')
                self.db.execute('INSERT INTO receipts(value) VALUES (?)', (json.dumps(dict(
                    utc=utc().isoformat(), action='retire', path=row['path'], sha256=row['sha256'])),))
                self.retirement_receipt(dict(action='retire-intent', utc=utc().isoformat(),
                    path=row['path'], sha256=row['sha256']))
                self.path(row['path']).unlink()
                self.db.execute('DELETE FROM files WHERE path=?', (row['path'],))
                removed.append(row['path'])
            for root, root_owner in self.db.execute('SELECT path,owner FROM roots'):
                if owners and root_owner not in owners:
                    continue
                if not Path(root).exists():
                    continue
                for current, _, _ in os.walk(root, topdown=False, followlinks=False):
                    directory = self.path(current)
                    directory_owner = self.context(directory)
                    if owners and directory_owner not in owners:
                        continue
                    state = self.db.execute('SELECT state FROM efforts WHERE owner=?', (directory_owner,)).fetchone()[0]
                    if state == 'closed':
                        try:
                            directory.rmdir()
                        except OSError:
                            pass  # Nonempty directories and retained/active children remain.
            self.db.execute('DELETE FROM keeps WHERE expires IS NOT NULL AND expires<?', (utc().isoformat(),))
            self.db.execute('DELETE FROM recipes WHERE key IN (SELECT key FROM recipes) AND NOT EXISTS '
                            '(SELECT 1 FROM files WHERE files.path LIKE recipes.output || ?)', (os.sep + '%',))
            self.db.execute("DELETE FROM jobs WHERE state<>'running' AND owner IN (SELECT owner FROM efforts WHERE state='closed')")
            self.db.execute('DELETE FROM receipts WHERE id NOT IN (SELECT id FROM receipts ORDER BY id DESC LIMIT 1000)')
        known = [Path(r[0]) for r in self.db.execute('SELECT path FROM roots')]
        exceptions = [str(p) for p in self.local.iterdir()
            if p.name not in ('artifacts', 'experiments', 'tools', 'releases') and not any(p == r for r in known)]
        experiments = self.local / 'experiments'
        if experiments.exists():
            for child in experiments.iterdir():
                if not any(child.is_relative_to(root) or root.is_relative_to(child) for root in known):
                    exceptions.append(str(child))
        for root in known:
            if owners and self.context(root) not in owners:
                continue
            if root.exists():
                for path in self.scan(root):
                    if not self.db.execute('SELECT 1 FROM files WHERE path=?', (str(path),)).fetchone() and str(path) not in removed:
                        exceptions.append(str(path))
        jobs = [dict(id=i, owner=o) for i, o in self.db.execute("SELECT id,owner FROM jobs WHERE state='running'")]
        return dict(candidates=candidates, removed=removed, blocked=blocked, unclassified=exceptions, unresolved_jobs=jobs)

    def resolve(self, root, path):
        owner = self.context(root)
        path = self.path(path)
        reference = path / 'artifact.reference.json'
        if reference.exists():
            data = read_json(reference)
            self.claim(owner, data['files'])
            return self.path(data['output'])
        self.claim(owner, self.manifest([path]))
        return path

    def run(self, root, command, inputs=(), output=None, recipe=None, verify=None):
        owner = self.context(root)
        self.active(owner)
        if not command:
            raise ValueError('Provide the command after --')
        with self.locked():
            resolved_inputs = []
            for value in inputs:
                original = self.path(value)
                canonical = self.resolve(root, original) if (original / 'artifact.reference.json').is_file() else original
                for spelling in {str(value), Path(value).as_posix()}:
                    command = [str(v).replace(spelling, str(canonical)) for v in command]
                    verify = [str(v).replace(spelling, str(canonical)) for v in verify] if verify else None
                resolved_inputs.append(canonical)
            inputs = resolved_inputs
            rows = self.manifest(inputs)
            self.claim(owner, rows)
            self.assert_writable(self.path(output or root), owner)
            key = None
            if recipe:
                if not output:
                    raise ValueError('Recipe runs require an explicit output directory')
                spec = read_json(recipe)
                if not isinstance(spec, dict) or not all(k in spec for k in ('operation', 'implementation', 'settings', 'retain')):
                    raise ValueError('Recipes need operation, implementation paths, settings and retained relative files')
                if (not isinstance(spec['implementation'], list) or not spec['implementation']
                        or not all(isinstance(p, str) and p for p in spec['implementation'])
                        or not isinstance(spec['settings'], dict) or not isinstance(spec['retain'], list)
                        or not spec['retain'] or not all(isinstance(p, str) and p for p in spec['retain'])):
                    raise ValueError('Declare nonempty implementation/retained file lists and effective settings')
                if spec.get('candidate') and not verify:
                    raise ValueError('New candidates require a fresh independent verification command')
                implementation = [self.project / p for p in spec['implementation']]
                def normalized(argv):
                    values = [str(v) for v in argv]
                    for index, path in enumerate(inputs):
                        values = [v.replace(str(path), '<INPUT' + str(index) + '>') for v in values]
                    return [v.replace(str(output), '<OUTPUT>') for v in values]
                identity = dict(recipe=spec, inputs=[dict(sha256=r['sha256'], bytes=r['signature'][0]) for r in rows], implementation={str(p): digest(p) for p in implementation},
                    runtime=sys.version, helper=digest(__file__),
                    command=normalized(command), verification=normalized(verify or []))
                key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
                hit = self.db.execute('SELECT output,files FROM recipes WHERE key=?', (key,)).fetchone()
                if hit:
                    try:
                        retained = json.loads(hit[1])
                        self.claim(owner, retained)
                    except (ValueError, OSError):
                        hit = None
                    if hit:
                        target = self.path(output)
                        target.mkdir(parents=True, exist_ok=False)
                        (target/'artifact.reference.json').write_text(json.dumps(dict(
                            output=hit[0], files=retained)), encoding='utf-8')
                        self.reconcile([owner])
                        return dict(reused=True, output=hit[0], reference=str(target))
                if self.path(output).exists():
                    raise ValueError('Use a fresh output directory for a recipe miss')
            if key and self.db.execute("SELECT 1 FROM jobs WHERE recipe=? AND state='running'", (key,)).fetchone():
                raise ValueError('The same recipe is running or interrupted; assess its job before retrying')
            job = uuid4().hex
            self.db.execute("INSERT INTO jobs VALUES (?,?,'running',?)", (job, owner, key))
        print('Artifact job: ' + job, file=sys.stderr)
        scratch = self.path(Path(root) / 'scratch' / job)
        scratch.mkdir(parents=True, exist_ok=False)
        environment = os.environ.copy()
        environment.update(TEMP=str(scratch), TMP=str(scratch), TMPDIR=str(scratch),
                           RESEARCH_ARTIFACT_ROOT=str(self.path(root)),
                           RESEARCH_ARTIFACT_OWNER=owner)
        state = 'failed'
        try:
            if output:
                self.path(output).mkdir(parents=True, exist_ok=not bool(key))
            subprocess.run(command, cwd=self.project, env=environment, check=True)
            if verify:
                subprocess.run(verify, cwd=self.project, env=environment, check=True)
            with self.locked():
                self.reconcile([owner])
                if key:
                    paths = [self.path(Path(output) / name) for name in spec['retain']]
                    if not paths or any(not p.is_relative_to(self.path(output)) for p in paths):
                        raise ValueError('Retained outputs must be nonempty and stay inside output')
                    retained = self.manifest(paths)
                    if not retained:
                        raise ValueError('No completed retained outputs')
                    self.db.execute('INSERT OR REPLACE INTO recipes VALUES (?,?,?)',
                                    (key, str(self.path(output)), json.dumps(retained)))
                state = 'completed'
            return dict(reused=False, job=job, output=str(output) if output else str(root))
        finally:
            with self.locked():
                self.reconcile([owner])
                self.db.execute('UPDATE jobs SET state=? WHERE id=?', (state, job))


def console(value):
    if isinstance(value, list):
        return dict(count=len(value), shown=min(20, len(value)), items=[console(v) for v in value[:20]])
    if isinstance(value, dict):
        return {key: console(item) for key, item in value.items()}
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root', type=Path, default=Path(__file__).resolve().parents[2])
    commands = parser.add_subparsers(dest='action', required=True)
    begin = commands.add_parser('begin')
    begin.add_argument('experiment')
    begin.add_argument('--test', default='main')
    begin.add_argument('--root', type=Path)
    begin.add_argument('--session')
    for action in ('run', 'finish', 'claim', 'resolve', 'recovery'):
        part = commands.add_parser(action)
        part.add_argument('--root', type=Path, required=True)
    run = commands.choices['run']
    run.add_argument('--input', type=Path, action='append', default=[])
    run.add_argument('--output', type=Path)
    run.add_argument('--recipe', type=Path)
    run.add_argument('--verify-command', help='JSON array for fresh independent verification after generation')
    run.add_argument('command', nargs=argparse.REMAINDER)
    finish = commands.choices['finish']
    finish.add_argument('--assessment', required=True)
    finish.add_argument('--experiment', action='store_true')
    finish.add_argument('--writers-closed', action='store_true')
    finish.add_argument('--apply', action='store_true')
    commands.choices['claim'].add_argument('paths', type=Path, nargs='+')
    commands.choices['resolve'].add_argument('path', type=Path)
    commands.choices['recovery'].add_argument('--journal', type=Path, required=True)
    commands.choices['recovery'].add_argument('--proof', type=Path)
    for action in ('preserve', 'publish'):
        part = commands.add_parser(action)
        part.add_argument('paths', type=Path, nargs='+')
        part.add_argument('--reason', required=True)
        part.add_argument('--approval')
    commands.add_parser('pool')
    renew = commands.add_parser('renew')
    renew.add_argument('id')
    renew.add_argument('--reason', required=True)
    claim_pool = commands.add_parser('claim-pool')
    claim_pool.add_argument('id')
    claim_pool.add_argument('--root', type=Path, required=True)
    retire = commands.add_parser('retire')
    retire.add_argument('id')
    retire.add_argument('--reason', required=True)
    assess = commands.add_parser('assess-job')
    assess.add_argument('id')
    assess.add_argument('--assessment', required=True)
    assess.add_argument('--writers-closed', required=True, action='store_true')
    commands.add_parser('cleanup').add_argument('--apply', action='store_true')
    args = parser.parse_args(argv)
    store = Store(args.project_root)
    try:
        if args.action == 'begin':
            result = store.begin(args.experiment, args.test, args.root, args.session)
        elif args.action == 'run':
            command = args.command[1:] if args.command[:1] == ['--'] else args.command
            result = store.run(args.root, command, args.input, args.output, args.recipe,
                               json.loads(args.verify_command) if args.verify_command else None)
        else:
            with store.locked():
                if args.action == 'finish':
                    # finish owns its transaction.
                    result = None
                elif args.action == 'cleanup':
                    result = store.cleanup(apply=args.apply)
                elif args.action in ('claim', 'resolve'):
                    result = str(store.resolve(args.root, args.path)) if args.action == 'resolve' else store.claim(
                        store.context(args.root), store.manifest(args.paths))
                elif args.action in ('preserve', 'publish'):
                    result = store.keep(args.paths, args.reason, 7 if args.action == 'publish' else None, args.approval)
                elif args.action == 'recovery':
                    result = store.recover(args.root, args.journal, args.proof)
                elif args.action == 'pool':
                    result = store.pool()
                elif args.action == 'claim-pool':
                    entry = next((p for p in store.pool() if p['id'] == args.id and not p['expired']), None)
                    if entry is None:
                        raise ValueError('Pool entry missing or expired')
                    result = store.claim(store.context(args.root), entry['files'])
                elif args.action == 'renew':
                    entry = next((p for p in store.pool() if p['id'] == args.id), None)
                    if entry is None or not args.reason.strip():
                        raise ValueError('Require an existing entry and a current reuse reason')
                    store.verify(entry['files'])
                    store.db.execute('UPDATE keeps SET reason=?,expires=? WHERE id=?',
                        (args.reason, (utc()+timedelta(days=7)).isoformat(), args.id))
                    result = dict(renewed=args.id)
                elif args.action == 'retire':
                    if not args.reason.strip():
                        raise ValueError('Assess why preservation is no longer needed')
                    store.db.execute('DELETE FROM keeps WHERE id=?', (args.id,))
                    result = dict(retired=args.id)
                else:
                    if not args.assessment.strip():
                        raise ValueError('Assess the interrupted writer before releasing its job')
                    store.db.execute("UPDATE jobs SET state='assessed' WHERE id=?", (args.id,))
                    store.db.execute('INSERT INTO receipts(value) VALUES (?)', (json.dumps(dict(
                        action='assess-job', id=args.id, assessment=args.assessment, utc=utc().isoformat())),))
                    result = dict(assessed=args.id)
            if args.action == 'finish':
                result = store.finish(args.root, args.assessment, experiment=args.experiment,
                                      writers_closed=args.writers_closed, apply=args.apply)
        print(json.dumps(console(result), indent=2))
    finally:
        store.close()


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, sqlite3.Error, subprocess.SubprocessError) as error:
        print(json.dumps(dict(ok=False, error=str(error))), file=sys.stderr)
        raise SystemExit(2)
