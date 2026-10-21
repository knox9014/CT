"""Compare local files with public hashes; local paths are never printed."""
import argparse
import hashlib
import json
import platform
from pathlib import Path
from compatibility_registry import validate_toolchain, validate_tool_execution


def observed_platform():
    if platform.system() == 'Windows' and platform.machine().lower() in ('amd64', 'x86_64'):
        return 'windows-x64'
    return 'other'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('tool_id')
    parser.add_argument('directory', type=Path)
    parser.add_argument('--lock', type=Path, default=Path(__file__).resolve().parents[1]/'docs/compatibility/toolchain-lock-v1.json')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    try:
        lock = json.loads(args.lock.read_text())
        errors = validate_toolchain(lock)
        if errors:
            raise ValueError('invalid lock')
        tool = next(t for t in lock['tools'] if t['id'] == args.tool_id)
        observed = {role: hashlib.sha256((args.directory / role).read_bytes()).hexdigest()
                    for role in tool['files']}
        errors = validate_tool_execution(tool, observed_platform=observed_platform(),
                                        observed_hashes=observed, required=True)
    except (OSError, ValueError, StopIteration):
        errors = ['tool_unavailable']
    print('tool files match pin' if not errors else 'tool verification failed')
    return int(bool(errors))


if __name__ == '__main__':
    raise SystemExit(main())
