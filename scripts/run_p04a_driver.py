"""Fresh Driver replay using the bound global Runtime build artifacts."""
import json
from pathlib import Path
from p04a_evidence import audit_manifest
ROOT=Path(__file__).resolve().parents[1]
def main():
 target=ROOT/'.cache/p04a-driver-latest.json';target.unlink(missing_ok=True)
 value=json.loads((ROOT/'.cache/p04a-runtime-latest.json').read_bytes())
 if set(value)!={'manifest'}:raise ValueError('invalid global pointer')
 path=(ROOT/value['manifest']).resolve()
 if not path.is_relative_to(ROOT/'.cache/p04a-smoke') or audit_manifest(path,ROOT,execute=True):raise ValueError('global Driver artifacts failed replay')
 target.write_text(json.dumps(value),encoding='utf-8');print('Global Driver fresh replay passed')
if __name__=='__main__':
 try:main()
 except (OSError,ValueError,KeyError):print('Global Driver evidence unavailable');raise SystemExit(1)
