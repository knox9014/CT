"""Check static declarations; this command never claims execution coverage."""
import json
from pathlib import Path
from compatibility_registry import validate_applications, validate_coverage, validate_toolchain


def main():
    root = Path(__file__).resolve().parents[1]
    try:
        folder = root / 'docs/compatibility'
        coverage = json.loads((folder / 'coverage-v1.json').read_text(encoding='utf-8'))
        apps = json.loads((folder / 'applications.json').read_text(encoding='utf-8'))
        errors = validate_coverage(coverage, root)
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
