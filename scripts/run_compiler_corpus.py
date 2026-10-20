"""Capture original NVRTC output, then replay immutable, reviewed PTX fixtures."""
import argparse
import ctypes as c
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
from compatibility_registry import (RegistryContext, digest, envelope, fields, ident, member,
    public_file, strings, validate_tool_execution)
from validate_spirv import run_validator


def sha(data):
    return hashlib.sha256(data).hexdigest()


def verify_fixture(data: bytes, expected_sha256: str) -> bool:
    return digest(expected_sha256) and sha(data) == expected_sha256


def validate_corpus(data: dict, root: Path, tool_ids: set[str]) -> list[str]:
    if not envelope(data, 'cases'):
        return ['invalid corpus fields']
    errors, seen = [], set()
    for case in data['cases']:
        if (not fields(case, 'id source_ref source_sha256 recipe_ref recipe_sha256 tool_id options output_sha256 capture_state expected_class expected_rejection required_features evidence_tier')
                or not ident(case['id']) or case['id'] in seen or not ident(case['tool_id'])
                or case['tool_id'] not in tool_ids or not strings(case['options'])
                or not strings(case['required_features'], ident)
                or not member(case['evidence_tier'], ('synthetic', 'upstream_adjusted_build', 'upstream_original_build'))
                or not member(case['capture_state'], ('pending', 'captured'))):
            errors.append('invalid or duplicate corpus case'); continue
        seen.add(case['id'])
        for role in ('source', 'recipe'):
            ref, expected = case[role + '_ref'], case[role + '_sha256']
            if not public_file(ref, root) or not digest(expected):
                errors.append('invalid corpus reference'); continue
            if not verify_fixture((root / ref).read_bytes(), expected):
                errors.append('corpus input hash mismatch')
        try:
            if public_file(case['recipe_ref'], root):
                recipe = json.loads((root / case['recipe_ref']).read_text())
                expected = dict(schema_version=1, source_ref=case['source_ref'],
                                tool_id=case['tool_id'], options=case['options'])
                if recipe != expected or type(recipe.get('schema_version')) is not int:
                    errors.append('corpus recipe mismatch')
        except (OSError, ValueError, AttributeError):
            errors.append('invalid corpus recipe')
        if case['capture_state'] == 'pending':
            if any(case[k] is not None for k in ('output_sha256', 'expected_class', 'expected_rejection')):
                errors.append('pending fixture cannot declare an expectation')
        else:
            if not digest(case['output_sha256']) or case['expected_class'] not in (None, 'supported', 'unsupported'):
                errors.append('invalid captured expectation')
            rejection = dict(stage='translation', category='unsupported') if case['expected_class'] == 'unsupported' else None
            if case['expected_rejection'] != rejection:
                errors.append('invalid rejection expectation')
    return errors


@dataclass(frozen=True)
class CorpusContext:
    root: Path
    cache_root: Path
    toolchain: dict[str, dict]
    tool_bindings: dict[str, Path]
    translator_path: Path
    validator_path: Path
    registry_context: RegistryContext | None


def run_case(case: dict, *, mode: str, required: bool, context: CorpusContext) -> dict:
    def outcome(status, reason, **extra):
        return dict(case_id=case.get('id'), status=status, reason=reason,
                    feature_supported=False, **extra)
    if mode not in ('capture', 'replay'):
        return outcome('fail', 'input_invalid')
    if validate_corpus(dict(schema_version=1, source_baseline='0'*40, cases=[case]),
                       context.root, {case.get('tool_id', '')}):
        return outcome('fail', 'input_invalid')
    context.cache_root.mkdir(parents=True, exist_ok=True)
    if mode == 'capture':
        tool = context.toolchain.get(case['tool_id'], {})
        binding = context.tool_bindings.get(case['tool_id'])
        try:
            if binding is None:
                return outcome('fail' if required else 'skipped', 'tool_unavailable')
            if tool.get('id') != 'nvrtc' or binding.name != 'nvrtc64_120_0.dll':
                return outcome('fail', 'tool_hash_mismatch')
            observed = {role: sha((binding.parent / role).read_bytes()) for role in tool.get('files', {})}
            actual_platform = 'windows-x64' if platform.system() == 'Windows' and platform.machine().lower() in ('amd64', 'x86_64') else 'other'
            errors = validate_tool_execution(tool, observed_platform=actual_platform,
                                             observed_hashes=observed, required=required)
            if errors:
                return outcome('fail' if required else 'skipped', errors[0].removeprefix('skipped:'))
            with tempfile.TemporaryDirectory(dir=context.cache_root) as directory:
                output = Path(directory) / 'output.ptx'
                command = [sys.executable, str(Path(__file__).resolve()), '--nvrtc-child',
                           str(binding.resolve()), str((context.root / case['source_ref']).resolve()),
                           str(output.resolve()), json.dumps(case['options'])]
                completed = subprocess.run(command, capture_output=True, timeout=60)
                if completed.returncode:
                    return outcome('fail', 'execution_failed')
                data = output.read_bytes()
            observed_hash = sha(data)
            if case['output_sha256'] is not None and observed_hash != case['output_sha256']:
                return outcome('fail', 'artifact_hash_mismatch', observed_sha256=observed_hash)
            target = context.cache_root / 'sha256' / (observed_hash + '.ptx')
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() and target.read_bytes() != data:
                return outcome('fail', 'artifact_hash_mismatch')
            target.write_bytes(data)
            return outcome('not_run', 'capture_only', observed_sha256=observed_hash)
        except subprocess.TimeoutExpired:
            return outcome('fail', 'tool_timeout')
        except OSError:
            return outcome('fail', 'tool_unavailable')
    if case['capture_state'] != 'captured' or case['expected_class'] is None:
        return outcome('fail' if required else 'not_run', 'classification_pending')
    fixture = context.cache_root / 'sha256' / (case['output_sha256'] + '.ptx')
    try:
        data = fixture.read_bytes()
    except OSError:
        return outcome('fail' if required else 'skipped', 'artifact_missing')
    if not verify_fixture(data, case['output_sha256']):
        return outcome('fail', 'artifact_hash_mismatch')
    try:
        with tempfile.TemporaryDirectory(dir=context.cache_root) as directory:
            # Translate a snapshot of exactly the hashed bytes.
            source, output = Path(directory) / 'input.ptx', Path(directory) / 'output.spv'
            source.write_bytes(data)
            completed = subprocess.run([str(context.translator_path.resolve()), str(source), str(output)],
                                       capture_output=True, timeout=60)
            if case['expected_class'] == 'unsupported':
                return outcome('pass', 'passed', input_sha256=sha(data)) if completed.returncode == 3 else outcome('fail', 'test_failed')
            if completed.returncode != 0:
                return outcome('fail', 'unsupported' if completed.returncode == 3 else 'execution_failed')
            result = run_validator(output, context.validator_path, context.toolchain.get('spirv-val', {}),
                                   required=required)
            if result['status'] != 'pass':
                return outcome(result['status'], result['reason'])
            result = outcome('pass', 'passed', output_sha256=case['output_sha256'],
                             input_sha256=sha(data),module_sha256=result.get('module_sha256'))
            result['feature_supported'] = True
            return result
    except subprocess.TimeoutExpired:
        return outcome('fail', 'tool_timeout')
    except OSError:
        return outcome('fail', 'execution_failed')


def nvrtc_child(binding, source, output, options):
    """Isolated producer process; no compiler diagnostics leak into public output."""
    with os.add_dll_directory(str(binding.parent.resolve())):
        builtins = c.WinDLL(str(binding.parent / 'nvrtc-builtins64_120.dll'))
        compiler = c.WinDLL(str(binding))
        compiler.nvrtcCreateProgram.argtypes = [c.POINTER(c.c_void_p), c.c_char_p, c.c_char_p, c.c_int, c.c_void_p, c.c_void_p]
        compiler.nvrtcCompileProgram.argtypes = [c.c_void_p, c.c_int, c.POINTER(c.c_char_p)]
        compiler.nvrtcGetPTXSize.argtypes = [c.c_void_p, c.POINTER(c.c_size_t)]
        compiler.nvrtcGetPTX.argtypes = [c.c_void_p, c.c_void_p]
        compiler.nvrtcDestroyProgram.argtypes = [c.POINTER(c.c_void_p)]
        program = c.c_void_p()
        if compiler.nvrtcCreateProgram(c.byref(program), source.read_bytes(), source.name.encode(), 0, None, None):
            return 1
        try:
            argv = (c.c_char_p * len(options))(*(x.encode() for x in options))
            if compiler.nvrtcCompileProgram(program, len(options), argv): return 1
            size = c.c_size_t()
            if compiler.nvrtcGetPTXSize(program, c.byref(size)) or not 0 < size.value <= 4 * 1024 * 1024: return 1
            data = c.create_string_buffer(size.value)
            if compiler.nvrtcGetPTX(program, data): return 1
            # API size includes the terminating NUL; PTX text does not.
            output.write_bytes(data.raw[:-1])
        finally:
            compiler.nvrtcDestroyProgram(c.byref(program))
        return 0


def main():
    if len(sys.argv) == 6 and sys.argv[1] == '--nvrtc-child':
        try:
            return nvrtc_child(Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]), json.loads(sys.argv[5]))
        except (OSError, ValueError): return 1
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('capture', 'replay'))
    parser.add_argument('--tool', type=Path, default=Path('.cache/reference/nvrtc-12.0/bin/nvrtc64_120_0.dll'))
    parser.add_argument('--validator', type=Path, default=Path('.cache/universal-foundation/spirv-build/tools/Release/spirv-val.exe'))
    parser.add_argument('--translator', type=Path, default=Path('target/debug/examples/translate_module.exe'))
    parser.add_argument('--output', type=Path, default=Path('results/local/corpus.json'))
    parser.add_argument('--lock', type=Path, default=Path(__file__).resolve().parents[1]/'docs/compatibility/toolchain-lock-v1.json')
    parser.add_argument('--case', help='Execute exactly one declared corpus case')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    try:
        folder = root / 'docs/compatibility'
        corpus = json.loads((folder / 'producer-corpus-v1.json').read_text())
        lock = json.loads(args.lock.read_text())
        from compatibility_registry import validate_toolchain
        if validate_toolchain(lock):
            raise ValueError('invalid lock')
        tools = {t['id']: t for t in lock['tools']}
        errors = validate_corpus(corpus, root, set(tools))
        if errors:
            print(json.dumps(dict(status='fail', reason='input_invalid'))); return 1
        context = CorpusContext(root, root/'.cache/universal-foundation/corpus', tools,
            {'nvrtc': args.tool.resolve()}, args.translator.resolve(), args.validator.resolve(), None)
        selected=[case for case in corpus['cases'] if args.case is None or case['id']==args.case]
        if not selected:raise ValueError('unknown corpus case')
        results = [run_case(case, mode=args.mode, required=True, context=context) for case in selected]
        output = args.output.resolve()
        if not output.is_relative_to(root/'results/local'):
            print(json.dumps(dict(status='fail', reason='input_invalid'))); return 1
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(dict(mode=args.mode, cases=results), indent=2)+'\n')
        print(json.dumps(dict(mode=args.mode, cases=results)))
        return int(any(r['status'] == 'fail' for r in results))
    except (OSError, ValueError):
        print(json.dumps(dict(status='fail', reason='input_invalid'))); return 1


if __name__ == '__main__': raise SystemExit(main())
