"""Private raw-byte source checkpoint; never stages or commits the original repository."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import uuid
import zlib
from check_public_artifacts import working_tree_blobs
from run_validation import source_fingerprint
from compatibility_registry import canonical_hash

ROOT=Path(__file__).resolve().parents[1]

def sha(data):return hashlib.sha256(data).hexdigest()

def git(root,*args,input=None,private=False):
    env=None
    if private:
        env={k:v for k,v in os.environ.items() if not k.upper().startswith('GIT_')}
        env.update(GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_GLOBAL=os.devnull,
                   GIT_AUTHOR_NAME='CT source candidate',GIT_COMMITTER_NAME='CT source candidate',
                   GIT_AUTHOR_EMAIL='source-candidate@users.noreply.github.com',
                   GIT_COMMITTER_EMAIL='source-candidate@users.noreply.github.com')
    return subprocess.check_output(['git',*args],cwd=root,input=input,env=env,stderr=subprocess.DEVNULL)

def index_bytes(root):
    p=Path(git(root,'rev-parse','--git-path','index').decode().strip())
    if not p.is_absolute():p=root/p
    return p.read_bytes() if p.is_file() else None

def committed_files(source):
    entries=[]
    for entry in filter(None,git(source,'ls-tree','-rz','HEAD',private=True).split(b'\0')):
        info,name=entry.split(b'\t',1);mode,kind,oid=info.split()
        if mode not in (b'100644',b'100755') or kind!=b'blob':raise ValueError('candidate contains non-source entry')
        entries.append((name.decode(),oid))
    output=git(source,'cat-file','--batch',input=b''.join(oid+b'\n' for _,oid in entries),private=True)
    at=0;files={}
    for name,oid in entries:
        end=output.index(b'\n',at);header=output[at:end].split();at=end+1
        if len(header)!=3 or header[0]!=oid or header[1]!=b'blob':raise ValueError('candidate object mismatch')
        size=int(header[2]);data=output[at:at+size];at+=size
        if len(data)!=size or output[at:at+1]!=b'\n':raise ValueError('candidate object extent')
        at+=1;files[name]=sha(data)
    if at!=len(output):raise ValueError('candidate object tail')
    return files

def verify(path):
    path=Path(path).resolve();m=json.loads(path.read_bytes());source=path.parent/'source'
    fields={'schema_version','scope','published','source_fingerprint','source_tree_sha256','git_commit','git_tree','files'}
    if (set(m)!=fields or type(m['schema_version']) is not int or m['schema_version']!=1
            or m['scope']!='local_source_candidate' or m['published'] is not False
            or type(m['files']) is not dict or not m['files']
            or any(type(n) is not str or type(s) is not str or not re.fullmatch('[0-9a-f]{64}',s) for n,s in m['files'].items())
            or source.is_symlink() or source.is_junction()):raise ValueError('candidate schema/scope')
    blobs,findings=working_tree_blobs(source)
    files={n:sha(b) for n,b in blobs.items()}
    if findings or files!=m['files'] or canonical_hash(files)!=m['source_tree_sha256']:raise ValueError('candidate working bytes changed')
    if source_fingerprint(source)!=m['source_fingerprint']:raise ValueError('candidate source fingerprint changed')
    if (git(source,'rev-parse','HEAD',private=True).decode().strip()!=m['git_commit']
            or git(source,'rev-parse','HEAD^{tree}',private=True).decode().strip()!=m['git_tree']
            or committed_files(source)!=files):raise ValueError('candidate commit bytes changed')
    return m

def prepare(root):
    root=Path(root).resolve()
    if Path(git(root,'rev-parse','--show-toplevel').decode().strip()).resolve()!=root:raise ValueError('source must be repository root')
    index=index_bytes(root)
    blobs,findings=working_tree_blobs(root)
    if findings or not blobs:raise ValueError('publication scan refused snapshot; matched content withheld')
    fingerprint=source_fingerprint(root)
    # Reject missing product paths rather than silently dropping tracked deletions.
    names=set(filter(None,git(root,'ls-files','--cached','--others','--exclude-standard','-z').decode().split('\0')))
    if set(blobs)!=names:raise ValueError('missing tracked paths need explicit source review')
    files={n:sha(b) for n,b in blobs.items()}
    parent=root/'.cache/source-candidates'
    for p in (root/'.cache',parent):
        if p.is_symlink() or p.is_junction() or not p.resolve().is_relative_to(root):raise ValueError('candidate output escape')
    git(root,'check-ignore','-q','.cache/source-candidates/probe')
    base=parent/uuid.uuid4().hex;source=base/'source';source.mkdir(parents=True)
    for name,data in blobs.items():
        out=source/name;out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(data)
    empty=base/'empty-template';empty.mkdir()
    git(source,'init','-q','-b','candidate','--object-format=sha1','--template='+str(empty),private=True)
    git(source,'config','core.autocrlf','false',private=True)
    git(source,'config','core.filemode','false',private=True)
    info=source/'.git/info';info.mkdir(exist_ok=True)
    (info/'attributes').write_text('* -text -filter -working-tree-encoding\n',encoding='ascii')
    modes={}
    for entry in filter(None,git(root,'ls-files','--stage','-z').split(b'\0')):
        header,name=entry.split(b'\t',1);mode,_,stage=header.split()
        if stage!=b'0' or mode not in (b'100644',b'100755'):raise ValueError('source index needs explicit review')
        modes[name.decode()]=mode
    records=[]
    for name,data in blobs.items():
        raw=b'blob '+str(len(data)).encode()+b'\0'+data
        oid=hashlib.sha1(raw).hexdigest() # Git object identity; SHA256 above binds content.
        obj=source/'.git/objects'/oid[:2]/oid[2:];obj.parent.mkdir(exist_ok=True)
        if not obj.exists():obj.write_bytes(zlib.compress(raw))
        records.append(modes.get(name,b'100644')+b' '+oid.encode()+b'\t'+name.encode()+b'\0')
    git(source,'update-index','-z','--index-info',input=b''.join(records),private=True)
    tree=git(source,'write-tree',private=True).decode().strip()
    commit=git(source,'-c','commit.gpgsign=false','commit-tree',tree,input=b'Local unpublished CT source candidate\n',private=True).decode().strip()
    git(source,'update-ref','refs/heads/candidate',commit,private=True)
    after,found=working_tree_blobs(root)
    if found or {n:sha(b) for n,b in after.items()}!=files or source_fingerprint(root)!=fingerprint or index_bytes(root)!=index:
        raise ValueError('source/index changed during snapshot; private partial candidate retained')
    m=dict(schema_version=1,scope='local_source_candidate',published=False,source_fingerprint=fingerprint,
           source_tree_sha256=canonical_hash(files),git_commit=commit,git_tree=tree,files=files)
    path=base/'manifest.json';path.write_text(json.dumps(m,indent=2)+'\n',encoding='utf-8')
    verify(path);return path

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--verify',type=Path);args=p.parse_args()
    try:
        path=args.verify or prepare(ROOT);m=verify(path)
        print(json.dumps(dict(status='pass',manifest=str(Path(path).resolve().relative_to(ROOT)),git_tree=m['git_tree'],source_fingerprint=m['source_fingerprint'],published=False)))
    except (ValueError,OSError,subprocess.SubprocessError,KeyError):
        print(json.dumps(dict(status='fail',reason='source_candidate_refused',matched_content_withheld=True)));raise SystemExit(1)
