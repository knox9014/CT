"""Opt-in Intel clock probe with source/binary-bound local evidence."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import uuid

from run_validation import source_fingerprint

ROOT = Path(__file__).resolve().parents[1]
MARKER = re.compile(r"^GPU_CLOCK_OK frequency=([0-9]+) bits=([0-9]+) delta_ticks=([0-9]+) roundtrips=8 words=1024$", re.M)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(device):
    fingerprint = source_fingerprint(ROOT)
    folder = ROOT / '.cache/gpu-clock-runs' / uuid.uuid4().hex
    folder.mkdir(parents=True)
    env = os.environ.copy()
    env['CARGO_INCREMENTAL'] = '0'
    env['CT_TEST_DEVICE'] = device
    build_command = ['cargo', 'test', '-p', 'ct-backend-intel', '--test', 'gpu_clock',
                     '--no-run', '--message-format=json', '--target-dir', str(folder / 'target')]
    build = subprocess.run(build_command, cwd=ROOT, env=env, capture_output=True, timeout=180)
    (folder / 'build.jsonl').write_bytes(build.stdout)
    (folder / 'build-stderr.txt').write_bytes(build.stderr)
    if build.returncode:
        raise ValueError('GPU clock test build failed; see ignored local build logs')
    executables = [row['executable'] for line in build.stdout.splitlines()
                   if (row := json.loads(line)).get('reason') == 'compiler-artifact'
                   and row.get('target', {}).get('name') == 'gpu_clock' and row.get('executable')]
    if len(executables) != 1:
        raise ValueError('expected exactly one authenticated clock test executable')
    binary = Path(executables[0]).resolve()
    if not binary.is_relative_to(folder.resolve()):
        raise ValueError('test executable escaped local evidence directory')
    binary_hash = digest(binary)
    result = subprocess.run([str(binary), '--ignored', '--exact',
                             'native_gpu_clock_survives_memory_roundtrips', '--nocapture'],
                            cwd=ROOT, env=env, capture_output=True, timeout=60)
    (folder / 'stdout.txt').write_bytes(result.stdout)
    (folder / 'stderr.txt').write_bytes(result.stderr)
    matches = MARKER.findall(result.stdout.decode('utf-8'))
    if result.returncode or result.stderr or len(matches) != 1:
        raise ValueError('native clock probe failed or did not execute exactly once')
    frequency, bits, delta = map(int, matches[0])
    if frequency <= 0 or not 1 <= bits <= 64 or not 0 < delta < (1 << bits):
        raise ValueError('invalid GPU counter result')
    if digest(binary) != binary_hash or source_fingerprint(ROOT) != fingerprint:
        raise ValueError('source or executable changed during probe')
    manifest = dict(scope='diagnostic_gpu_clock', release_claim=False,
                    source_fingerprint=fingerprint, device_name_filter=device,
                    binary=binary.relative_to(folder).as_posix(), binary_sha256=binary_hash,
                    frequency_hz=frequency, valid_bits=bits, delta_ticks=delta,
                    roundtrips=8, words_per_roundtrip=1024, exit_code=result.returncode,
                    stdout_sha256=digest(folder / 'stdout.txt'),
                    stderr_sha256=digest(folder / 'stderr.txt'))
    target = folder / 'manifest.json'
    target.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    (ROOT / '.cache/gpu-clock-latest.json').write_text(
        json.dumps(dict(manifest=target.relative_to(ROOT).as_posix())) + '\n', encoding='utf-8')
    return target


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--device-name-contains', default='B390')
    options = parser.parse_args()
    if not options.device_name_contains.strip():
        parser.error('a nonempty Intel device name filter is required')
    print(json.dumps(dict(status='pass', manifest=run(options.device_name_contains).relative_to(ROOT).as_posix(),
                          release_claim=False)))
