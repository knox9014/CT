"""Validate the bounded static CT manifest; never infer test execution results."""
import json
from pathlib import Path, PurePosixPath
import re


def expected_exports(root: Path) -> dict:
    header = (root / 'include/ct_cuda.h').read_text(encoding='utf-8')
    signatures = {name: name + ':' + ' '.join(args.split())
                  for name, args in re.findall(r'\bX\((cu\w+),\s*(\([^\n]*\))\)', header)}
    source = (root / 'crates/ct-cuda/src/entrypoints.rs').read_text(encoding='utf-8')
    ranges = {}
    for canonical, name, minimum, maximum in re.findall(
            r'e!\(\s*b"([^"]+)",\s*(?:modules::)?(\w+),\s*(\d+)(?:,\s*(\d+))?\s*,?\s*\)', source):
        ranges.setdefault(name, []).append(dict(symbol=canonical, minimum=int(minimum), maximum=int(maximum or 12000)))
    return {name: dict(signature_id=sig, lookup_ranges=ranges.get(name, [])) for name, sig in signatures.items()}


def _reference_valid(reference, root: Path) -> bool:
    if not isinstance(reference, str) or reference.count('#') != 1:
        return False
    name, marker = reference.split('#')
    path = PurePosixPath(name)
    if (not marker or path.is_absolute() or ':' in name or '\\' in name
            or '..' in path.parts or not path.parts
            or path.parts[0] not in ('tests', 'crates', 'scripts')
            or any(p.startswith('.') or p in ('target', 'vendor', 'node_modules') for p in path.parts)):
        return False
    target = (root / name).resolve()
    try:
        return target.is_relative_to(root.resolve()) and target.is_file() and marker in target.read_text(encoding='utf-8')
    except (OSError, UnicodeError):
        return False


def validate_profile(data: dict, root: Path) -> list[str]:
    errors = []
    if not isinstance(data, dict) or set(data) != {'schema_version', 'baseline', 'platform', 'exports', 'features'}:
        return ['invalid manifest fields; execution reports are separate']
    if type(data['schema_version']) is not int or data['schema_version'] != 1:
        errors.append('invalid schema version')
    if not isinstance(data['baseline'], str) or not re.fullmatch(r'[0-9a-f]{7,40}', data['baseline']):
        errors.append('invalid baseline commit')
    platform = data['platform']
    if not isinstance(platform, dict) or set(platform) != {'os', 'host', 'gpu'} or any(
            not isinstance(v, str) or not v.strip() for v in platform.values()):
        errors.append('invalid bounded platform')
    expected = expected_exports(root)
    exports = data['exports']
    seen = set()
    if not isinstance(exports, list):
        return errors + ['invalid exports']
    for entry in exports:
        if not isinstance(entry, dict) or set(entry) != {'symbol', 'signature_id', 'lookup_ranges', 'behavior', 'test_ids'}:
            errors.append('invalid export fields'); continue
        symbol = entry['symbol']
        if not isinstance(symbol, str) or symbol not in expected or symbol in seen:
            errors.append('unknown or duplicate export'); continue
        seen.add(symbol)
        for field in ('signature_id', 'lookup_ranges'):
            if entry[field] != expected[symbol][field]: errors.append('export ABI/lookup drift: ' + symbol)
        if not isinstance(entry['behavior'], str) or not entry['behavior'].strip():
            errors.append('missing export behavior')
        if symbol == 'cuDriverGetVersion' and entry['behavior'] != 'NOT_SUPPORTED':
            errors.append('driver version must remain unsupported')
        refs = entry['test_ids']
        if not isinstance(refs, list) or not refs or any(not _reference_valid(r, root) for r in refs):
            errors.append('invalid export test reference')
    if seen != set(expected): errors.append('export set differs from header')
    features = data['features']
    if not isinstance(features, list) or not features:
        return errors + ['invalid features']
    seen = set()
    for feature in features:
        if not isinstance(feature, dict) or not {'id', 'state', 'limits', 'test_ids'} <= set(feature) or set(feature) - {'id', 'state', 'limits', 'test_ids', 'reason'}:
            errors.append('invalid feature fields'); continue
        ident = feature['id']
        if not isinstance(ident, str) or not re.fullmatch(r'[a-z][a-z0-9_.-]*', ident) or ident in seen:
            errors.append('invalid or duplicate feature id'); continue
        seen.add(ident)
        state = feature['state']
        if state not in ('experimental', 'unsupported'): errors.append('invalid feature declaration state')
        if not isinstance(feature['limits'], dict) or not feature['limits']: errors.append('missing feature limits')
        if state == 'unsupported' and (not isinstance(feature.get('reason'), str) or not feature['reason'].strip()):
            errors.append('unsupported feature requires reason')
        refs = feature['test_ids']
        if not isinstance(refs, list) or (state == 'experimental' and not refs) or (
                isinstance(refs, list) and any(not _reference_valid(r, root) for r in refs)):
            errors.append('invalid feature test reference')
    return errors


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    try:
        data = json.loads((root / 'docs/compatibility/profile-v1.json').read_text(encoding='utf-8'))
        errors = validate_profile(data, root)
    except (OSError, ValueError, UnicodeError):
        errors = ['static manifest could not be read']
    for error in errors: print(error)
    if errors: return 1
    print('Static compatibility manifest valid; this is not test execution evidence.')
    return 0


if __name__ == '__main__': raise SystemExit(main())
