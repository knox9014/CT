"""Check static declarations; this command never claims execution coverage."""
import json
from pathlib import Path
from compatibility_registry import canonical_hash, validate_applications, validate_coverage, validate_toolchain


def validate_scope_alignment(profile, coverage, runtime):
    try:
        declarations={f['id']:f for f in profile['features']}
        inventory={f['id']:f for f in coverage['features']}
        errors=[]
        for name in ('runtime','streams','driver.streams','product.virtual_target'):
            p,c=declarations[name],inventory[name]
            state='unsupported' if name=='driver.streams' else 'experimental'
            implementation='missing' if name=='driver.streams' else 'partial'
            if p['state']!=state or c['implementation']!=implementation or canonical_hash(p['limits'])!=canonical_hash(c['limits']):
                errors.append('bounded feature scope drift: '+name)
        r=declarations['runtime']['limits'];s=declarations['streams']['limits'];v=declarations['product.virtual_target']['limits']
        if (r.get('implementation')!='partial' or r.get('general_cuda_compatibility') is not False
                or type(r.get('api_exports')) is not int or r['api_exports']!=len(runtime['exports'])):
            errors.append('Runtime declaration exceeds bounded ABI')
        if s.get('driver_streams') is not False or s.get('native_overlap') is not False:
            errors.append('Runtime streams cannot imply Driver/native queue support')
        if v.get('target')!='ct-sm52-subset-v1' or v.get('default')!='strict' or v.get('nvidia_conformance') is not False:
            errors.append('virtual target declaration exceeds selection contract')
        return errors
    except (KeyError,TypeError):
        return ['bounded feature scope could not be read']


def main():
    root = Path(__file__).resolve().parents[1]
    try:
        folder = root / 'docs/compatibility'
        coverage = json.loads((folder / 'coverage-v1.json').read_text(encoding='utf-8'))
        apps = json.loads((folder / 'applications.json').read_text(encoding='utf-8'))
        errors = validate_coverage(coverage, root)
        if not errors:
            profile=json.loads((folder/'profile-v1.json').read_text(encoding='utf-8'))
            runtime=json.loads((folder/'runtime-profile-v1.json').read_text(encoding='utf-8'))
            errors += validate_scope_alignment(profile,coverage,runtime)
        if not errors:
            errors += validate_applications(apps, root, {f['id'] for f in coverage['features']})
        lock = folder / 'toolchain-lock-v1.json'
        if lock.exists():
            tools = json.loads(lock.read_text(encoding='utf-8'))
            tool_errors = validate_toolchain(tools)
            errors += tool_errors
            corpus = folder / 'producer-corpus-v1.json'
            if not errors and corpus.exists():
                from run_compiler_corpus import validate_corpus
                producer = json.loads(corpus.read_text(encoding='utf-8'))
                errors += validate_corpus(producer, root, {t['id'] for t in tools['tools']})
                features = {f['id'] for f in coverage['features']}
                if not errors and any(not set(c['required_features']) <= features for c in producer['cases']):
                    errors.append('unknown corpus feature reference')
    except (OSError, ValueError, UnicodeError):
        errors = ['registry could not be read']
    for error in errors:
        print(error)
    if not errors:
        print('Static registries valid; no execution or compatibility pass inferred.')
    return int(bool(errors))


if __name__ == '__main__':
    raise SystemExit(main())
