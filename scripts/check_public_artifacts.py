"""Repository-local publication checks. Never print matched sensitive content."""
from dataclasses import dataclass
import argparse
import hashlib
from pathlib import PurePosixPath
import re
import subprocess
import sys

PRIVATE_PARTS = {'.aws', '.ssh', '.codex', '.agents', '.local', '.cache', 'target',
                 '.venv', 'node_modules', 'private', 'personal', 'recordings'}
PRIVATE_SUFFIXES = {'.pem', '.key', '.pfx', '.p12', '.log', '.dmp', '.dump', '.etl',
                    '.wav', '.mp3', '.m4a', '.flac', '.ogg', '.mp4', '.mov', '.mkv',
                    '.pdf', '.docx', '.xlsx', '.pptx', '.zip', '.7z', '.tar', '.gz',
                    '.exe', '.dll', '.obj', '.pdb', '.lib', '.exp'}
PATTERNS = [
    ('personal Windows home path', re.compile(rb'(?i)\b[A-Z]:[\\/]+Users[\\/]+[^\\/\s"\']+')),
    ('personal Unix home path', re.compile(rb'/(?:home|Users)/[^/\s"\']+')),
    ('GitHub credential pattern', re.compile(rb'gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}')),
    ('API credential pattern', re.compile(rb'sk-(?:proj-)?[A-Za-z0-9_-]{30,}')),
    ('private key material', re.compile(rb'-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----')),
    ('contact email', re.compile(rb'[A-Za-z0-9.!#$%&\x27*+/=?^_`{|}~-]+@(?!(?:users\.)?noreply\.github\.com\b)[A-Za-z0-9.-]+\.[A-Za-z]{2,}')),
]
REVIEWED_BINARIES = {
    'tests/fixtures/vector_add.spv': '78c122989c637046319c5661a18aa0f2b9206407c63ea28ac261d1b6f6e64ca4',
}


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    reason: str

    def render(self) -> str:
        return f"{self.path}:{self.line}: {self.reason}"


def inspect_blob(path: str, data: bytes) -> list[Finding]:
    name = PurePosixPath(path)
    lower = path.lower()
    if (set(p.lower() for p in name.parts) & PRIVATE_PARTS
        or lower.startswith(('results/local/', 'inputs/local/', 'data/local/'))
        or name.suffix.lower() in PRIVATE_SUFFIXES
        or (name.name.lower().startswith('.env') and name.name.lower() != '.env.example')
        or name.name.lower() in {'credentials.json', 'token.json', 'tokens.json'}):
        return [Finding(path, 1, 'sensitive/local artifact must not be published')]
    if path in REVIEWED_BINARIES:
        if hashlib.sha256(data).hexdigest() == REVIEWED_BINARIES[path]:
            return []
        return [Finding(path, 1, 'binary fixture changed; manual privacy review required')]
    try:
        data.decode('utf-8-sig')
        binary = b'\0' in data
    except UnicodeDecodeError:
        binary = True
    if binary:
        return [Finding(path, 1, 'unreviewed binary artifact')]
    findings = []
    for reason, pattern in PATTERNS:
        for match in pattern.finditer(data):
            findings.append(Finding(path, data[:match.start()].count(b'\n') + 1, reason))
    return findings


def git(*args: str) -> bytes:
    return subprocess.check_output(['git', *args], stderr=subprocess.DEVNULL)


def inspect_index(staged: bool) -> list[Finding]:
    args = ('diff', '--cached', '--diff-filter=ACMR', '--name-only', '-z') if staged else ('ls-files', '-z')
    findings = []
    for raw in filter(None, git(*args).split(b'\0')):
        path = raw.decode('utf-8')
        findings.extend(inspect_blob(path, git('show', ':' + path)))
    return findings


def safe_email(value: str) -> bool:
    return bool(re.fullmatch(r'[^\s@]+@users\.noreply\.github\.com', value, re.I))


def inspect_identity() -> list[Finding]:
    for variable in ('GIT_AUTHOR_EMAIL', 'GIT_COMMITTER_EMAIL'):
        import os
        if os.environ.get(variable) and not safe_email(os.environ[variable]):
            return [Finding('commit metadata', 1, 'use a GitHub noreply author/committer email')]
    email = git('config', '--get', 'user.email').decode().strip()
    return [] if safe_email(email) else [Finding('commit metadata', 1, 'use a GitHub noreply email')]


def inspect_history(tip: str, base: str | None = None) -> list[Finding]:
    commits = git('rev-list', tip, *(['^' + base] if base else [])).decode().splitlines()
    findings = []
    seen = set()
    for commit in commits:
        emails = git('show', '-s', '--format=%ae%n%ce', commit).decode().splitlines()
        if not all(safe_email(email) for email in emails):
            findings.append(Finding('commit ' + commit[:12], 1, 'non-noreply author/committer email'))
        findings.extend(inspect_blob('commit-message ' + commit[:12], git('show', '-s', '--format=%B', commit)))
        for entry in filter(None, git('ls-tree', '-r', '-z', commit).split(b'\0')):
            info, raw_path = entry.split(b'\t', 1)
            mode, kind, oid = info.split()
            path = raw_path.decode('utf-8')
            if kind != b'blob' or mode == b'120000':
                findings.append(Finding(path, 1, 'submodule/symlink needs explicit publication review'))
                continue
            key = (path, oid)
            if key not in seen:
                seen.add(key)
                findings.extend(inspect_blob(path, git('cat-file', 'blob', oid.decode())))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument('--staged', action='store_true')
    scope.add_argument('--tracked', action='store_true')
    scope.add_argument('--revision')
    scope.add_argument('--pre-push', action='store_true')
    parser.add_argument('--identity', action='store_true')
    args = parser.parse_args()
    try:
        findings = inspect_identity() if args.identity else []
        if args.pre_push:
            for line in sys.stdin:
                local_ref, local, remote_ref, remote = line.split()
                if not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', local) or not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', remote):
                    raise ValueError('invalid Git push reference')
                if set(local) != {'0'}:
                    if (not local_ref.startswith('refs/heads/') or not remote_ref.startswith('refs/heads/')
                        or git('cat-file', '-t', local).strip() != b'commit'):
                        findings.append(Finding('push references', 1, 'only branch commits are automatically reviewed; tags/other objects require explicit metadata review'))
                        continue
                    findings.extend(inspect_history(local, None if set(remote) == {'0'} else remote))
        elif args.revision:
            tip = git('rev-parse', '--verify', args.revision + '^{commit}').decode().strip()
            findings.extend(inspect_history(tip))
        else:
            findings.extend(inspect_index(args.staged))
        for finding in dict.fromkeys(findings):
            print(finding.render(), file=sys.stderr)
        if findings:
            print('Publication blocked; sensitive matched content is withheld.', file=sys.stderr)
            return 1
        print('Publication checks passed (matched content is never printed).')
        return 0
    except (subprocess.CalledProcessError, UnicodeError, ValueError, OSError):
        print('Publication check could not finish; refusing to publish. No file contents printed.', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
