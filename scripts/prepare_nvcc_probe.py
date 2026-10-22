"""Authenticated local nvcc preparation; output manifests/logs stay ignored."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT/'tests/fixtures/p09a2/vector.cu'
PINS = {
    'cuda_nvcc.zip': 'f67406f44263f0e4a110a8cf0200bff1d3d0e32917db8a7c9e417a87eb7ca372',
    'cuda_cudart.zip': '1cd8516feee068c6d718453e76b0dfcbee27844a35d4f3aa608a3d316190309c',
    'cuda_cccl.zip': 'dd422d4cc8462d112411659a56cc78cb6010d704f83db3e48c55a3f66eed5ec2',
    'stl.zip': 'ad92513bf0d77d544dad3a1a9f1b94152c4bdc9f7338475ece01657495b977c6',
}
STL_COMMIT = 'ab600751924207014ab02f7422ee00a6843e2f0f'
# Qualification needs a separately reviewed supported-host pin. A child manifest
# cannot qualify itself by changing a version string or removing an override.
QUALIFIED_CL = {}
ENV_POLICY = 'ct-nvcc-sanitized-v1'


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def decode_lz4(block, size):
    if not 0 < size <= 262152:
        raise ValueError('decoded limit')
    out = bytearray()
    pos = 0

    def length(n):
        nonlocal pos
        if n == 15:
            while True:
                if pos >= len(block):
                    raise ValueError('truncated length')
                byte = block[pos]
                pos += 1
                n += byte
                if byte < 255:
                    break
        return n

    while pos < len(block):
        token = block[pos]
        pos += 1
        count = length(token >> 4)
        if pos + count > len(block) or len(out) + count > size:
            raise ValueError('literal extent')
        out.extend(block[pos:pos+count])
        pos += count
        if pos == len(block):
            break
        if pos + 2 > len(block):
            raise ValueError('offset extent')
        offset = int.from_bytes(block[pos:pos+2], 'little')
        pos += 2
        count = length(token & 15) + 4
        if not 0 < offset <= len(out) or len(out) + count > size:
            raise ValueError('match extent')
        for _ in range(count):
            out.append(out[-offset])
    if len(out) != size:
        raise ValueError('decoded length')
    return bytes(out)


def payload(path, mode=None):
    b = Path(path).read_bytes()
    if not 96 <= len(b) <= 16*1024*1024:
        raise ValueError('container limit')
    magic, version, header, length = struct.unpack_from('<IHHQ', b)
    if (magic, version, header, length) != (0xba55ed50, 1, 16, len(b)-16):
        raise ValueError('container header')
    h = b[16:88]
    kind, version, header, size = struct.unpack_from('<HHIQ', h)
    flags = int.from_bytes(h[40:44], 'little')
    if mode is not None and flags != {'compressed': 0x2041, 'plain': 0x41}[mode]:
        raise ValueError('actual compression mode differs')
    if (kind, version, header, size) != (1, 0x101, 72, len(b)-88) or size % 8:
        raise ValueError('record extent')
    if flags not in (0x41, 0x2041) or h[20:40] != struct.pack('<IIIII', 64, 8 << 16, 52, 0, 0) or any(h[44:56]+h[64:72]):
        raise ValueError('record profile')
    comp = int.from_bytes(h[16:20], 'little')
    decoded = int.from_bytes(h[56:64], 'little')
    data = b[88:]
    if flags == 0x2041:
        if not 0 < comp <= len(data) or len(data)-comp >= 8 or any(data[comp:]):
            raise ValueError('compressed padding')
        data = decode_lz4(data[:comp], decoded)
    elif comp or decoded:
        raise ValueError('plain lengths')
    end = data.find(b'\0')
    if not 0 < end <= 262144 or not data[:end].isascii() or any(data[end:]):
        raise ValueError('PTX extent')
    return data[:end]


def vendor_members(packages):
    """Derive trusted member hashes from pinned archives, not child manifests."""
    members = {}
    for name, expected in PINS.items():
        archive = Path(packages)/name
        if digest(archive) != expected:
            raise ValueError('archive mismatch')
        with zipfile.ZipFile(archive) as z:
            for item in z.infolist():
                if item.is_dir():
                    continue
                parts = item.filename.split('/')[1:]
                if not parts or '..' in parts or any(':' in p for p in parts):
                    raise ValueError('member escape')
                if name == 'stl.zip':
                    if parts[:2] != ['stl', 'inc']:
                        continue
                    relative = 'stl/' + '/'.join(parts[2:])
                else:
                    if parts[0] not in ('bin', 'include', 'lib', 'nvvm'):
                        continue
                    relative = 'toolkit/' + '/'.join(parts)
                data = z.read(item)
                sha = hashlib.sha256(data).hexdigest()
                if relative in members and members[relative][0] != sha:
                    raise ValueError('conflicting archive member')
                members[relative] = (sha, name, item.filename)
    return members


def inventory(roots):
    return {str(p.resolve()): digest(p) for folder in roots
            for p in sorted(Path(folder).rglob('*')) if p.is_file()}


def validate_host(host):
    if set(host) != {'profile', 'compiler_version', 'override', 'roots', 'files', 'tools', 'vcvars', 'environment_policy'}:
        raise ValueError('host schema')
    if host['environment_policy'] != ENV_POLICY:
        raise ValueError('uncontrolled compiler environment')
    if host['profile'] not in ('diagnostic', 'qualified') or not host['files'] or not host['roots']:
        raise ValueError('host closure absent')
    if host['profile'] == 'qualified':
        if host['override'] or not re.fullmatch(r'19\.3[0-9](?:\.\d+)?', host['compiler_version']):
            raise ValueError('unsupported host cannot qualify')
        if QUALIFIED_CL.get(host['tools'].get('cl.exe', {}).get('sha256')) != host['compiler_version']:
            raise ValueError('supported host pin unavailable')
    elif host['override'] is not True:
        raise ValueError('diagnostic override must be explicit')
    if set(host['tools']) != {'cl.exe', 'link.exe'}:
        raise ValueError('host tools absent')
    if set(host['vcvars']) != {'path', 'sha256'} or digest(host['vcvars']['path']) != host['vcvars']['sha256']:
        raise ValueError('host environment recipe changed')
    for item in host['tools'].values():
        if set(item) != {'path', 'sha256'} or digest(item['path']) != item['sha256']:
            raise ValueError('host tool changed')
    if inventory(host['roots']) != host['files']:
        raise ValueError('host header/library closure changed')


def audit_probe(path):
    try:
        path = Path(path).resolve()
        value = json.loads(path.read_bytes())
        if set(value) != {'schema_version', 'source_sha256', 'packages', 'vendor_files', 'host', 'commands', 'artifacts', 'runtime_exercised'}:
            raise ValueError('manifest schema')
        if value['schema_version'] != 1 or value['runtime_exercised'] is not False or value['source_sha256'] != digest(SOURCE):
            raise ValueError('source/scope mismatch')
        if digest(path.parent/'vector.cu') != value['source_sha256']:
            raise ValueError('compiled source snapshot changed')
        members = vendor_members(value['packages'])
        expected = {name: info[0] for name, info in members.items()}
        if value['vendor_files'] != expected:
            raise ValueError('incomplete vendor closure')
        for name, sha in expected.items():
            if digest(path.parent/name) != sha:
                raise ValueError('vendor member changed')
        validate_host(value['host'])
        if set(value['commands']) != {'compressed', 'plain'}:
            raise ValueError('producer commands absent')
        for mode, argv in value['commands'].items():
            if argv != compiler_args(path.parent, value['host']['profile'], mode, str(Path(value['host']['tools']['cl.exe']['path']).parent)):
                raise ValueError('producer flags changed')
        if set(value['artifacts']) != {'compressed', 'plain'}:
            raise ValueError('producer modes absent')
        texts = []
        for mode, files in value['artifacts'].items():
            required = {mode+'.exe', 'keep-'+mode+'/vector.fatbin', 'keep-'+mode+'/vector.ptx', 'keep-'+mode+'/vector.cudafe1.stub.c'}
            if set(files) != required:
                raise ValueError('producer artifact absent')
            for relative, sha in files.items():
                if digest(path.parent/relative) != sha:
                    raise ValueError('producer artifact changed')
            texts.append(payload(path.parent/('keep-'+mode+'/vector.fatbin'), mode))
        if texts[0] != texts[1]:
            raise ValueError('independent payload mismatch')
        return []
    except (OSError, ValueError, TypeError, KeyError, struct.error, zipfile.BadZipFile):
        return ['nvcc evidence unavailable or changed']


def compiler_args(output, profile, mode, compiler_dir):
    argv = [str(output/'toolkit/bin/nvcc.exe'), '--compiler-bindir', compiler_dir, '-Xcompiler', '/utf-8',
            '--cudart=shared', '--cudadevrt=none', '--keep', '--keep-dir',
            'keep-'+mode, '--generate-code', 'arch=compute_52,code=compute_52', 'vector.cu', '-o', mode+'.exe']
    if profile == 'diagnostic':
        argv += ['-allow-unsupported-compiler', '-I', str(output/'stl')]
    if mode == 'plain':
        argv += ['--no-compress']
    return argv


def decode_host_env(data):
    return dict(line.split('=', 1) for line in data.decode('utf-16-le').splitlines()
                if '=' in line and not line.startswith('='))


def normalize_env(env):
    blocked = {'CL', '_CL_', 'LINK', '_LINK_', 'CUDAHOSTCXX', 'CUDACXX',
               'CPATH', 'CPLUS_INCLUDE_PATH', 'C_INCLUDE_PATH', 'OBJC_INCLUDE_PATH',
               'CPPFLAGS', 'CFLAGS', 'CXXFLAGS', 'LDFLAGS', 'COMPILER_PATH',
               'GCC_EXEC_PREFIX', 'LIBRARY_PATH'}
    return {k:v for k,v in env.items() if k.upper() not in blocked and not k.upper().startswith('NVCC_')}


def prepare(output, packages, profile, vcvars):
    output = output.resolve()
    if not output.is_relative_to(ROOT/'.cache'):
        raise ValueError('output must be ignored local cache')
    output.mkdir(parents=True, exist_ok=True)
    members = vendor_members(packages)
    for relative, (sha, archive, member) in members.items():
        dest = output/relative
        if not dest.is_file() or digest(dest) != sha:
            dest.parent.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(packages/archive) as z:
                dest.write_bytes(z.read(member))
    # Only installed vcvars is executed, never a path read from an evidence file.
    if any(c in str(vcvars) for c in '\r\n"&|<>%'):
        raise ValueError('unsupported vcvars path')
    env_script = output/'host-env.cmd'
    env_script.write_text('@echo off\ncall "'+str(vcvars)+'" >nul\nif errorlevel 1 exit /b 1\nset\n', encoding='utf-8')
    result = subprocess.run(['cmd.exe', '/d', '/u', '/c', str(env_script)], capture_output=True, check=True, timeout=90)
    env = normalize_env(decode_host_env(result.stdout))
    tools = {name: {'path': shutil.which(name, path=env.get('PATH', env.get('Path', '')))} for name in ('cl.exe', 'link.exe')}
    for item in tools.values():
        item['sha256'] = digest(item['path'])
    compiler_dir = str(Path(tools['cl.exe']['path']).parent)
    if Path(tools['link.exe']['path']).parent != Path(compiler_dir):
        raise ValueError('host compiler/linker selection differs')
    previous_path = next((v for k,v in env.items() if k.upper() == 'PATH'), '')
    env = {k:v for k,v in env.items() if k.upper() != 'PATH'}
    env['PATH'] = compiler_dir+os.pathsep+previous_path
    banner = subprocess.run([tools['cl.exe']['path']], env=env, capture_output=True, timeout=30).stderr.decode('mbcs', errors='replace')
    version = re.search(r'19\.\d+\.\d+', banner)
    if version is None:
        raise ValueError('host compiler version missing')
    roots = sorted({str(Path(p).resolve()) for key in ('INCLUDE', 'LIB') for p in env.get(key, '').split(';') if p})
    # Superset closure: include all local host headers/libraries and compiler-bin helpers.
    roots.append(str(Path(tools['cl.exe']['path']).parent))
    host = dict(profile=profile, compiler_version=version[0], override=profile == 'diagnostic',
                roots=roots, files=inventory(roots), tools=tools, vcvars=dict(path=str(vcvars), sha256=digest(vcvars)), environment_policy=ENV_POLICY)
    validate_host(host)
    shutil.copyfile(SOURCE, output/'vector.cu')
    artifacts, commands = {}, {}
    for mode in ('compressed', 'plain'):
        (output/('keep-'+mode)).mkdir(exist_ok=True)
        commands[mode] = compiler_args(output, profile, mode, compiler_dir)
        run = subprocess.run(commands[mode], cwd=output, env=env, capture_output=True, timeout=120)
        (output/('compiler-'+mode+'.log')).write_bytes(run.stdout+run.stderr)
        if run.returncode:
            raise ValueError('producer compilation failed; local log retained')
        names = [mode+'.exe'] + ['keep-'+mode+'/vector'+suffix for suffix in ('.fatbin', '.ptx', '.cudafe1.stub.c')]
        artifacts[mode] = {name: digest(output/name) for name in names}
    value = dict(schema_version=1, source_sha256=digest(SOURCE), packages=str(packages.resolve()),
                 vendor_files={name: info[0] for name, info in members.items()}, host=host,
                 commands=commands, artifacts=artifacts, runtime_exercised=False)
    path = output/'manifest.json'
    path.write_text(json.dumps(value, indent=2), encoding='utf-8')
    if audit_probe(path):
        raise ValueError('producer independent replay failed')
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    p = sub.add_parser('prepare')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--packages', type=Path, default=ROOT/'.cache/p09a2-probe')
    p.add_argument('--host-profile', choices=('diagnostic', 'qualified'), required=True)
    p.add_argument('--vcvars', type=Path, required=True)
    p = sub.add_parser('replay')
    p.add_argument('--manifest', type=Path, required=True)
    args = parser.parse_args()
    try:
        errors = audit_probe(args.manifest) if args.action == 'replay' else audit_probe(prepare(args.output, args.packages, args.host_profile, args.vcvars))
        print('nvcc producer replay passed; Runtime not exercised' if not errors else 'nvcc producer verification failed')
        return int(bool(errors))
    except (OSError, ValueError, subprocess.SubprocessError, zipfile.BadZipFile):
        print('nvcc producer preparation failed; local diagnostics retained')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
