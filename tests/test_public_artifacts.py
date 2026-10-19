"""All sensitive-looking test values are synthetic and never uploaded as data."""
import sys
import subprocess
import tempfile
import os
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from check_public_artifacts import inspect_blob


class PublicationChecks(unittest.TestCase):
    def setUp(self):
        repo = Path(__file__).resolve().parents[1]
        self.temp_root = (repo / '.cache/privacy-tests').resolve()
        assert self.temp_root.is_relative_to(repo)
        self.temp_root.mkdir(parents=True, exist_ok=True)

    def test_rejects_private_paths_keys_and_contact_email_without_echoing_values(self):
        values = [
            b"C:" + b"\\" + b"Users" + b"\\" + b"synthetic-user\\file.txt",
            b"/ho" + b"me/synthetic-user/file.txt",
            b"gh" + b"p_" + b"a" * 36,
            b"sk-" + b"proj-" + b"a" * 40,
            b"-----BEGIN " + b"PRIVATE KEY-----",
            b"synthetic-person" + b"@" + b"mail.invalid",
        ]
        for data in values:
            with self.subTest(kind=values.index(data)):
                findings = inspect_blob("sample.txt", b"first line\n" + data)
                self.assertTrue(findings)
                self.assertEqual(findings[0].line, 2)
                self.assertNotIn(data.decode(), findings[0].render())

    def test_rejects_sensitive_files_and_unreviewed_binary(self):
        for name in [".env", "nested/.env.production", ".aws/credentials", "results/local/run.json",
                     "private/input.txt", "clip.wav", "notes.pdf", "secret.pem", "unknown.spv"]:
            with self.subTest(name=name):
                self.assertTrue(inspect_blob(name, b"\x00\x01\x02"))

    def test_allows_source_and_placeholder_environment_example(self):
        self.assertEqual(inspect_blob("src/lib.rs", b"pub fn add(a:u32,b:u32)->u32 { a+b }"), [])
        self.assertEqual(inspect_blob(".env.example", b"API_KEY=replace_me\n"), [])
        self.assertEqual(inspect_blob("docs/link.md", b"https://github.com/knox9014/CT"), [])

    def test_reads_staged_blob_instead_of_safe_worktree_replacement(self):
        with tempfile.TemporaryDirectory(dir=self.temp_root) as directory:
            root = Path(directory)
            subprocess.run(['git', 'init', '-q', directory], check=True)
            sample = root / 'sample.txt'
            sample.write_bytes(b'gh' + b'p_' + b'a' * 36)
            subprocess.run(['git', '-C', directory, 'add', 'sample.txt'], check=True)
            sample.write_text('safe unstaged replacement')
            result = subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1] / 'scripts/check_public_artifacts.py'), '--staged'],
                                    cwd=directory, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn('credential pattern', result.stderr)
            self.assertNotIn('a' * 36, result.stderr)

    def test_checks_deleted_sensitive_content_in_outbound_history(self):
        with tempfile.TemporaryDirectory(dir=self.temp_root) as directory:
            root = Path(directory)
            def git(*args):
                return subprocess.run(['git', '-C', directory, *args], check=True, capture_output=True)
            git('init', '-q')
            git('config', 'user.name', 'ct-synthetic-test')
            git('config', 'user.email', '123+ct-test@users.noreply.github.com')
            (root / 'sample.txt').write_bytes(b'gh' + b'p_' + b'a' * 36)
            git('add', 'sample.txt'); git('commit', '-qm', 'synthetic fixture')
            git('rm', '-q', 'sample.txt'); git('commit', '-qm', 'remove synthetic fixture')
            result = subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1] / 'scripts/check_public_artifacts.py'), '--revision', 'HEAD'],
                                    cwd=directory, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn('credential pattern', result.stderr)
            self.assertNotIn('a' * 36, result.stderr)

    def test_blocks_tag_pushes_pending_explicit_metadata_review(self):
        with tempfile.TemporaryDirectory(dir=self.temp_root) as directory:
            root = Path(directory)
            def git(*args, env=None):
                return subprocess.run(['git', '-C', directory, *args], check=True,
                                      capture_output=True, env=env)
            git('init', '-q'); git('config', 'user.name', 'ct-synthetic-test')
            git('config', 'user.email', '123+ct-test@users.noreply.github.com')
            (root / 'safe.txt').write_text('safe source')
            git('add', 'safe.txt'); git('commit', '-qm', 'safe')
            tag_env = dict(os.environ, GIT_COMMITTER_EMAIL='synthetic-contact' + '@' + 'mail.invalid')
            git('tag', '-a', 'synthetic-release', '-m', 'gh' + 'p_' + 'a' * 36, env=tag_env)
            oid = git('rev-parse', 'refs/tags/synthetic-release').stdout.decode().strip()
            refs = f'refs/tags/synthetic-release {oid} refs/tags/synthetic-release {"0"*40}\n'
            result = subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1] / 'scripts/check_public_artifacts.py'), '--pre-push'],
                                    cwd=directory, capture_output=True, text=True, input=refs)
            self.assertEqual(result.returncode, 1)
            self.assertNotIn('a' * 36, result.stderr)
            self.assertNotIn(tag_env['GIT_COMMITTER_EMAIL'], result.stderr)


if __name__ == "__main__":
    unittest.main()
