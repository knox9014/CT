"""Explicit source build: fixed archives in, a separate local execution lock out."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import urllib.request
import uuid
import zipfile

PINS={
    'SPIRV-Tools':('7f2d9ee926f98fc77a3ed1e1e0f113b8c9c49458',
                   '713643963d2fab54a626a9054406d80e37c3d291b45b18ad43d5f033beeb0049'),
    'SPIRV-Headers':('01e0577914a75a2569c846778c2f93aa8e6feddd',
                     'b96204f9a68cf5aca4fcad17c60feb51176af52b9790609e7439fa589f87d5f2')}


def extract_pinned(archive,expected,destination):
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=expected:
        raise ValueError('source archive hash mismatch')
    with zipfile.ZipFile(archive) as source:
        for entry in source.infolist():
            target=(destination/entry.filename).resolve()
            if not target.is_relative_to(destination.resolve()) or (entry.external_attr>>16)&0o170000==0o120000:
                raise ValueError('unsafe archive entry')
        source.extractall(destination)


def main():
    root=Path(__file__).resolve().parents[1]
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cmake',required=True,type=Path)
    parser.add_argument('--generator',default='Visual Studio 18 2026')
    parser.add_argument('--output-lock',required=True,type=Path)
    args=parser.parse_args()
    try:
        output=args.output_lock.resolve()
        if not output.is_relative_to(root/'results/local'):raise ValueError('output must be local')
        output.parent.mkdir(parents=True,exist_ok=True)
        cache=root/'.cache/universal-foundation';cache.mkdir(parents=True,exist_ok=True)
        workspace=cache/('build-'+uuid.uuid4().hex);workspace.mkdir()
        for project,(revision,expected) in PINS.items():
            archive=cache/(project+'.zip')
            if not archive.exists():
                url='https://codeload.github.com/KhronosGroup/'+project+'/zip/'+revision
                with urllib.request.urlopen(url,timeout=60) as response:
                    archive.write_bytes(response.read())
            extract_pinned(archive,expected,workspace)
        tools=workspace/('SPIRV-Tools-'+PINS['SPIRV-Tools'][0])
        headers=workspace/('SPIRV-Headers-'+PINS['SPIRV-Headers'][0])
        shutil.copytree(headers,tools/'external/spirv-headers')
        build=workspace/'build'
        env=dict(os.environ,FORCED_BUILD_VERSION_DESCRIPTION=PINS['SPIRV-Tools'][0])
        commands=[[str(args.cmake.resolve()),'-S',str(tools),'-B',str(build),'-G',args.generator,'-A','x64',
            '-DSPIRV_SKIP_TESTS=ON','-DSPIRV_SKIP_EXECUTABLES=OFF','-DSPIRV_BUILD_FUZZER=OFF',
            '-DSPIRV_TOOLS_USE_MIMALLOC=OFF','-DSPIRV_TOOLS_BUILD_STATIC=ON',
            '-DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreaded'],
            [str(args.cmake.resolve()),'--build',str(build),'--config','Release','--target','spirv-val',
             '--parallel','1','--','/nodeReuse:false']]
        for i,command in enumerate(commands):
            with (workspace/('build-'+str(i)+'.log')).open('wb') as log:
                subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=900)
        binary=build/'tools/Release/spirv-val.exe'
        lock=json.loads((root/'docs/compatibility/toolchain-lock-v1.json').read_text())
        entry=next(t for t in lock['tools'] if t['id']=='spirv-val')
        entry.update(pin_state='pinned',source_revision=PINS['SPIRV-Tools'][0],
            artifact_sha256=PINS['SPIRV-Tools'][1],files={'spirv-val.exe':hashlib.sha256(binary.read_bytes()).hexdigest()})
        output.write_text(json.dumps(lock,indent=2)+'\n')
        # This local binding is consumed explicitly, never committed or printed.
        (output.parent/'validator-binding.json').write_text(json.dumps({'executable':str(binary)})+'\n')
        print('Pinned-source validator built; new executable identity recorded in local execution lock.')
        return 0
    except (OSError,ValueError,StopIteration,subprocess.SubprocessError,zipfile.BadZipFile):
        print('Validator preparation failed; source or binary pins were not replaced.')
        return 1


if __name__=='__main__':raise SystemExit(main())
