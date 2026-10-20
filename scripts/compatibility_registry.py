"""Closed, static declarations and independently supplied execution expectations.

Validation checks consistency, not whether a subprocess really executed. Runners
must supply their observed artifacts and build expectations from validated inputs.
"""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
import re

KINDS = frozenset(('resolver', 'abi', 'behavior', 'semantic', 'validator', 'native',
                   'application', 'performance'))
LANES = frozenset(('cpu', 'validator', 'producer', 'arc', 'combined'))
CATEGORIES = frozenset(('abi', 'loader', 'compiler', 'memory', 'context', 'parallel',
                        'runtime', 'library', 'backend', 'product'))
TIERS = frozenset(('synthetic', 'upstream_adjusted_build', 'upstream_original_build',
                   'distributed_binary'))
REASONS = frozenset(('passed', 'test_failed', 'not_run', 'tool_unavailable',
    'tool_hash_mismatch', 'tool_platform_mismatch', 'tool_timeout', 'validation_rejected',
    'unsupported', 'input_invalid', 'artifact_missing', 'artifact_hash_mismatch',
    'capture_only', 'classification_pending', 'hardware_unavailable', 'execution_failed'))


def canonical_hash(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def fields(value, names) -> bool:
    return isinstance(value, dict) and set(value) == set(names.split())


def text(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def member(value, allowed) -> bool:
    return isinstance(value, str) and value in allowed


def ident(value) -> bool:
    return isinstance(value, str) and re.fullmatch(r'[A-Za-z][A-Za-z0-9_.-]*', value) is not None


def digest(value, size=64) -> bool:
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{' + str(size) + '}', value) is not None


def hashes(value) -> bool:
    return isinstance(value, dict) and all(ident(k) and digest(v) for k, v in value.items())


def strings(value, predicate=text) -> bool:
    return (isinstance(value, list) and all(predicate(x) for x in value)
            and len(value) == len(set(value)))


def public_json(value) -> bool:
    from check_public_artifacts import inspect_blob
    try:
        raw = json.dumps(value, allow_nan=False).encode()
    except (TypeError, ValueError):
        return False
    return not inspect_blob('manifest.json', raw)


def public_file(reference, root: Path, *, marker=False) -> bool:
    if not text(reference) or '\x00' in reference or '\\' in reference or ':' in reference:
        return False
    if marker:
        if reference.count('#') != 1:
            return False
        name, anchor = reference.split('#')
        if not anchor:
            return False
    else:
        name, anchor = reference, None
        if '#' in name:
            return False
    p = PurePosixPath(name)
    if (p.is_absolute() or not p.parts or p.parts[0] not in ('tests', 'scripts', 'crates', 'docs')
            or any(x.startswith('.') or x in ('..', 'target', 'vendor', 'node_modules') for x in p.parts)):
        return False
    try:
        target = (root / name).resolve()
        return (target.is_relative_to(root.resolve()) and target.is_file()
                and (anchor is None or anchor in target.read_text(encoding='utf-8')))
    except (OSError, ValueError, UnicodeError):
        return False


def envelope(data, items) -> bool:
    return (fields(data, 'schema_version source_baseline ' + items)
            and type(data['schema_version']) is int and data['schema_version'] == 1
            and digest(data['source_baseline'], 40) and isinstance(data[items], list))


def catalog_index(entries, root):
    errors, catalog = [], {}
    if not isinstance(entries, list):
        return {}, ['invalid test catalog']
    for item in entries:
        if (not fields(item, 'id kind') or not public_file(item['id'], root, marker=True)
                or not member(item['kind'], KINDS) or item['id'] in catalog):
            errors.append('invalid or duplicate test catalog entry')
        else:
            catalog[item['id']] = item
    return catalog, errors


def validate_coverage(data: dict, root: Path) -> list[str]:
    if (not fields(data, 'schema_version source_baseline features test_catalog')
            or type(data['schema_version']) is not int or data['schema_version'] != 1
            or not digest(data['source_baseline'], 40) or not isinstance(data['features'], list)):
        return ['invalid coverage fields']
    catalog, errors = catalog_index(data['test_catalog'], root)
    seen = set()
    for f in data['features']:
        if (not fields(f, 'id category implementation limits test_ids') or not ident(f['id'])
                or f['id'] in seen or not member(f['category'], CATEGORIES)
                or not member(f['implementation'], ('missing', 'partial', 'implemented', 'research'))
                or not isinstance(f['limits'], dict) or not f['limits'] or not public_json(f['limits'])
                or not isinstance(f['test_ids'], dict)):
            errors.append('invalid or duplicate feature'); continue
        seen.add(f['id'])
        for kind, refs in f['test_ids'].items():
            if not member(kind, KINDS) or not strings(refs):
                errors.append('invalid feature test references'); continue
            if any(r not in catalog or catalog[r]['kind'] != kind for r in refs):
                errors.append('unknown test or evidence kind mismatch')
    if not seen:
        errors.append('empty feature registry')
    return errors


def source_valid(source, root):
    return (fields(source, 'repository revision recipe_ref') and text(source['repository'])
            and source['repository'].startswith('https://') and digest(source['revision'], 40)
            and public_file(source['recipe_ref'], root))


def validate_applications(data: dict, root: Path, feature_ids: set[str]) -> list[str]:
    if not envelope(data, 'applications'):
        return ['invalid application registry fields']
    errors, seen = [], set()
    paths = ('driver_external', 'runtime_dynamic', 'runtime_static', 'block_parallel', 'library', 'jit')
    for a in data['applications']:
        if (not fields(a, 'id execution_path evidence_tier inventory_state source artifacts required_features test_ids')
                or not ident(a['id']) or a['id'] in seen or not member(a['execution_path'], paths)
                or not member(a['evidence_tier'], TIERS)
                or not member(a['inventory_state'], ('candidate', 'pinned'))
                or not source_valid(a['source'], root) or not isinstance(a['artifacts'], list)
                or not a['artifacts'] or not strings(a['required_features'], ident)
                or not set(a['required_features']) <= feature_ids or not strings(a['test_ids'])
                or any(not public_file(t, root, marker=True) for t in a['test_ids'])):
            errors.append('invalid or duplicate application'); continue
        seen.add(a['id'])
        roles = set()
        for artifact in a['artifacts']:
            if (not fields(artifact, 'role sha256 availability') or not ident(artifact['role'])
                    or artifact['role'] in roles
                    or not member(artifact['availability'], ('missing', 'local_only', 'public_reference'))):
                errors.append('invalid application artifact'); continue
            roles.add(artifact['role'])
            if artifact['availability'] == 'missing':
                if artifact['sha256'] is not None or a['inventory_state'] == 'pinned':
                    errors.append('missing artifact cannot be pinned')
            elif not digest(artifact['sha256']):
                errors.append('invalid artifact hash')
    return errors


def validate_environment(data: dict) -> list[str]:
    if (not fields(data, 'schema_version os host_abi gpu_model driver_version runtime_versions compiler_versions')
            or type(data['schema_version']) is not int or data['schema_version'] != 1
            or any(not text(data[k]) for k in ('os', 'host_abi'))
            or any(data[k] is not None and not text(data[k]) for k in ('gpu_model', 'driver_version'))
            or any(not isinstance(data[k], dict) or any(not ident(n) or not text(v) for n, v in data[k].items())
                   for k in ('runtime_versions', 'compiler_versions')) or not public_json(data)):
        return ['invalid environment manifest']
    return []


def validate_configuration(data: dict, *, test_catalog: dict) -> list[str]:
    if (not fields(data, 'schema_version lane cases') or type(data['schema_version']) is not int
            or data['schema_version'] != 1 or not member(data['lane'], LANES)
            or not isinstance(data['cases'], list)):
        return ['invalid configuration fields']
    errors, seen = [], set()
    for c in data['cases']:
        if (not fields(c, 'case_id test_id execution_kind application_id parameters artifact_requirements tool_ids')
                or not ident(c['case_id']) or c['case_id'] in seen or not text(c['test_id'])
                or c['test_id'] not in test_catalog
                or c['execution_kind'] != test_catalog[c['test_id']]['kind']
                or (c['application_id'] is not None and not ident(c['application_id']))
                or not isinstance(c['parameters'], dict) or not public_json(c['parameters'])
                or not hashes(c['artifact_requirements']) or not strings(c['tool_ids'], ident)):
            errors.append('invalid or duplicate configuration case'); continue
        seen.add(c['case_id'])
    return errors


@dataclass(frozen=True)
class RegistryContext:
    expected_commit: str
    expected_profile: str
    expected_environment_id: str
    expected_toolchain_lock_sha256: str
    expected_test_catalog_sha256: str
    expected_configuration_sha256: str
    test_catalog: dict[str, dict]
    case_catalog: dict[str, dict]
    applications: dict[str, dict]
    toolchain: dict[str, dict]
    required_cases: frozenset[str]
    expected_lane: str = 'cpu'


def validate_report(data: dict, *, context: RegistryContext) -> list[str]:
    names = ('schema_version source_commit target_profile lane environment_id toolchain_lock_sha256 '
             'test_catalog_sha256 configuration_sha256 cases')
    if (not fields(data, names) or type(data['schema_version']) is not int or data['schema_version'] != 1
            or not isinstance(data['cases'], list)):
        return ['invalid report fields']
    errors, seen = [], set()
    identities = dict(source_commit=context.expected_commit, target_profile=context.expected_profile,
        lane=context.expected_lane, environment_id=context.expected_environment_id,
        toolchain_lock_sha256=context.expected_toolchain_lock_sha256,
        test_catalog_sha256=context.expected_test_catalog_sha256,
        configuration_sha256=context.expected_configuration_sha256)
    for k, expected in identities.items():
        if data[k] != expected:
            errors.append('report identity mismatch: ' + k)
    for c in data['cases']:
        if (not fields(c, 'case_id test_id execution_kind application_id status reason artifact_hashes tool_ids')
                or not ident(c['case_id']) or c['case_id'] in seen or c['case_id'] not in context.case_catalog
                or not member(c['status'], ('pass', 'fail', 'skipped', 'not_run'))
                or not member(c['reason'], REASONS) or not hashes(c['artifact_hashes'])
                or not strings(c['tool_ids'], ident)):
            errors.append('invalid or duplicate report case'); continue
        seen.add(c['case_id'])
        configured = context.case_catalog[c['case_id']]
        for field in ('test_id', 'execution_kind', 'application_id', 'tool_ids'):
            if c[field] != configured[field]:
                errors.append('case configuration mismatch: ' + field)
        test = context.test_catalog.get(c['test_id']) if text(c['test_id']) else None
        if test is None or c['execution_kind'] != test['kind']:
            errors.append('report evidence kind mismatch')
        if (c['status'] == 'pass') != (c['reason'] == 'passed'):
            errors.append('inconsistent result reason')
        if c['case_id'] in context.required_cases and c['status'] != 'pass':
            errors.append('required case did not pass')
        if c['status'] != 'pass':
            continue
        if c['artifact_hashes'] != configured['artifact_requirements']:
            errors.append('case artifact mismatch')
        for tool in c['tool_ids']:
            if context.toolchain.get(tool, {}).get('pin_state') != 'pinned':
                errors.append('pass requires pinned tools')
        app_id = c['application_id']
        if c['execution_kind'] == 'application' and app_id is None:
            errors.append('application pass requires application identity')
        if app_id is not None:
            app = context.applications.get(app_id) if ident(app_id) else None
            if app is None or app['inventory_state'] != 'pinned':
                errors.append('application pass requires pinned inventory')
            elif any(a['availability'] == 'missing' or c['artifact_hashes'].get(a['role']) != a['sha256']
                     for a in app['artifacts']):
                errors.append('application artifact mismatch')
    if not context.required_cases <= seen:
        errors.append('missing required cases')
    if seen != set(context.case_catalog):
        errors.append('report case set differs from configuration')
    return errors


def validate_toolchain(data: dict) -> list[str]:
    if not envelope(data, 'tools'):
        return ['invalid toolchain fields']
    errors, seen = [], set()
    for t in data['tools']:
        if (not fields(t, 'id pin_state version source_url source_revision artifact_sha256 platform recipe_ref files validation_target')
                or not ident(t['id']) or t['id'] in seen
                or not member(t['pin_state'], ('unresolved', 'pinned')) or not text(t['platform'])
                or not text(t['source_url']) or not t['source_url'].startswith('https://')
                or (t['source_revision'] is not None and not digest(t['source_revision'], 40))
                or not public_file(t['recipe_ref'], Path(__file__).resolve().parents[1]) or not hashes(t['files'])
                or (t['validation_target'] is not None and not text(t['validation_target']))):
            errors.append('invalid or duplicate tool'); continue
        seen.add(t['id'])
        if t['pin_state'] == 'pinned':
            if not text(t['version']) or not digest(t['artifact_sha256']) or not t['files']:
                errors.append('pinned tool requires version, package and file hashes')
        elif ((t['version'] is not None and not text(t['version']))
              or (t['artifact_sha256'] is not None and not digest(t['artifact_sha256']))):
            errors.append('invalid unresolved tool metadata')
    if not public_json(data):
        errors.append('toolchain contains nonpublic metadata')
    return errors


def validate_tool_execution(entry: dict, *, observed_platform: str,
                            observed_hashes: dict[str, str], required: bool) -> list[str]:
    if entry.get('pin_state') != 'pinned':
        return ['tool_unavailable' if required else 'skipped:tool_unavailable']
    if observed_platform != entry.get('platform'):
        return ['tool_platform_mismatch']
    if observed_hashes != entry.get('files'):
        return ['tool_hash_mismatch']
    return []
