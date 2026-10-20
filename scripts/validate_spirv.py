"""Run a pinned SPIRV-Tools validator under CT's Kernel/OpenCL profile."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess


def run_validator(module: Path, tool_path: Path, lock: dict,
                  *, required: bool, timeout_s: int = 30) -> dict:
    def result(status, reason):
        return dict(status=status, reason=reason)
    if lock.get('validation_target') != 'opencl1.2':
        return result('fail', 'validation_rejected')
    if lock.get('pin_state') != 'pinned' or not tool_path.is_file():
        return result('fail' if required else 'skipped', 'tool_unavailable')
    expected_platform = 'windows-x64' if platform.system() == 'Windows' and platform.machine().lower() in ('amd64', 'x86_64') else 'other'
    if lock.get('platform') != expected_platform:
        return result('fail', 'tool_platform_mismatch')
    try:
        actual = hashlib.sha256(tool_path.read_bytes()).hexdigest()
        if lock.get('files') != {'spirv-val.exe': actual}:
            return result('fail', 'tool_hash_mismatch')
        # Freeze the validated input in memory; feed via stdin to avoid a second
        # read of a path that could have changed after the reported input hash.
        data = module.read_bytes()
        completed = subprocess.run([str(tool_path.resolve()), '--target-env', 'opencl1.2', '-'],
            input=data, capture_output=True, timeout=timeout_s)
    except subprocess.TimeoutExpired:
        return result('fail', 'tool_timeout')
    except OSError:
        return result('fail', 'tool_unavailable')
    out = result('pass', 'passed') if completed.returncode == 0 else result('fail', 'validation_rejected')
    out['module_sha256'] = hashlib.sha256(data).hexdigest()
    out['tool_sha256'] = actual
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('module', type=Path)
    parser.add_argument('--tool', required=True, type=Path)
    parser.add_argument('--optional', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    try:
        lock = json.loads((root / 'docs/compatibility/toolchain-lock-v1.json').read_text())
        entry = next(t for t in lock['tools'] if t['id'] == 'spirv-val')
        result = run_validator(args.module, args.tool, entry, required=not args.optional)
    except (OSError, ValueError, StopIteration):
        result = dict(status='fail', reason='tool_unavailable')
    print(json.dumps(result))
    return int(result['status'] == 'fail')


if __name__ == '__main__':
    raise SystemExit(main())
