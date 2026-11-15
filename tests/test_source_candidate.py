import json
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from prepare_source_candidate import prepare,verify

class SourceCandidateTests(unittest.TestCase):
    def test_refused_paths_are_not_read_by_fingerprint(self):
        with patch('prepare_source_candidate.git',return_value=str(Path.cwd()).encode()),patch('prepare_source_candidate.index_bytes',return_value=None),patch('prepare_source_candidate.working_tree_blobs',return_value=({},['unsafe path'])),patch('prepare_source_candidate.source_fingerprint') as fingerprint:
            with self.assertRaises(ValueError):prepare(Path.cwd())
            fingerprint.assert_not_called()

    def test_snapshot_output_must_be_ignored_before_any_copy(self):
        base=Path(__file__).resolve().parents[1]/'.cache'
        with tempfile.TemporaryDirectory(dir=base) as temp:
            root=Path(temp).resolve();subprocess.run(['git','init','-q',str(root)],check=True)
            (root/'source.txt').write_text('safe source')
            with self.assertRaises((ValueError,subprocess.SubprocessError)):prepare(root)
            self.assertFalse((root/'.cache/source-candidates').exists())

    def test_private_snapshot_preserves_bytes_and_original_index(self):
        base=Path(__file__).resolve().parents[1]/'.cache'
        with tempfile.TemporaryDirectory(dir=base) as temp:
            root=Path(temp).resolve();subprocess.run(['git','init','-q',str(root)],check=True)
            (root/'.gitignore').write_text('.cache/\n');(root/'scripts').mkdir()
            (root/'scripts/example.py').write_bytes(b'print(1)\r\n')
            subprocess.run(['git','-C',str(root),'add','.gitignore','scripts/example.py'],check=True)
            index=(root/'.git/index').read_bytes()
            (root/'scripts/example.py').write_bytes(b'print(2)\r\n')
            (root/'new.txt').write_text('untracked source')
            saved=prepare(root);m=verify(saved)
            self.assertEqual((root/'.git/index').read_bytes(),index)
            self.assertFalse(m['published']);self.assertEqual(m['scope'],'local_source_candidate')
            self.assertEqual((saved.parent/'source/scripts/example.py').read_bytes(),b'print(2)\r\n')
            self.assertEqual((saved.parent/'source/new.txt').read_text(),'untracked source')
            self.assertFalse((saved.parent/'source/.cache').exists())
            (saved.parent/'source/new.txt').write_text('changed')
            with self.assertRaises(ValueError):verify(saved)

    def test_sensitive_working_bytes_refuse_snapshot(self):
        base=Path(__file__).resolve().parents[1]/'.cache'
        with tempfile.TemporaryDirectory(dir=base) as temp:
            root=Path(temp).resolve();subprocess.run(['git','init','-q',str(root)],check=True)
            (root/'.gitignore').write_text('.cache/\n')
            (root/'new.txt').write_bytes(b'gh'+b'p_'+b'a'*36)
            with self.assertRaises(ValueError):prepare(root)

if __name__=='__main__':unittest.main()
