"""Read-only headroom guard for bounded local development; never removes data."""
import argparse
import json
import os
from pathlib import Path
import shutil

GIB=1024**3
CACHE_LIMIT=40*GIB
FREE_FLOOR=30*GIB


def assess(cache_bytes,free_bytes,peak_bytes,*,cache_limit=CACHE_LIMIT,free_floor=FREE_FLOOR):
    if any(type(n) is not int or n<0 for n in (cache_bytes,free_bytes,peak_bytes,cache_limit,free_floor)):
        raise ValueError('invalid_budget_size')
    if cache_bytes+peak_bytes>cache_limit:raise ValueError('cache_limit')
    if free_bytes-peak_bytes<free_floor:raise ValueError('free_space_floor')
    return dict(status='pass',cache_bytes=cache_bytes,free_bytes=free_bytes,peak_bytes=peak_bytes,
                cache_limit_bytes=cache_limit,free_floor_bytes=free_floor,
                projected_cache_bytes=cache_bytes+peak_bytes,projected_free_bytes=free_bytes-peak_bytes)


def cache_bytes(root):
    folder=Path(root)/'.cache'
    if folder.is_symlink() or folder.is_junction():raise ValueError('linked_cache')
    if not folder.exists():return 0
    if not folder.is_dir():raise ValueError('cache_not_directory')
    stack=[folder];total=0
    while stack:
        with os.scandir(stack.pop()) as entries:
            for entry in entries:
                if entry.is_symlink() or entry.is_junction():raise ValueError('linked_cache_entry')
                if entry.is_dir(follow_symlinks=False):stack.append(Path(entry.path))
                elif entry.is_file(follow_symlinks=False):total+=entry.stat(follow_symlinks=False).st_size
                else:raise ValueError('unsupported_cache_entry')
    return total


def ensure_budget(root,peak_bytes,*,cache_limit=CACHE_LIMIT,free_floor=FREE_FLOOR):
    root=Path(root).resolve(strict=True)
    if not root.is_dir():raise ValueError('workspace_not_directory')
    return assess(cache_bytes(root),shutil.disk_usage(root).free,peak_bytes,cache_limit=cache_limit,free_floor=free_floor)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--reserve-gib',type=int,default=0)
    args=parser.parse_args()
    try:print(json.dumps(ensure_budget(args.workspace,args.reserve_gib*GIB)))
    except (OSError,ValueError) as error:
        reason=str(error) if isinstance(error,ValueError) else 'cache_inspection_failed'
        print(json.dumps(dict(status='refused',reason=reason)));raise SystemExit(1)
