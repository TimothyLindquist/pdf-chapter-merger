import _support
import json
from pathlib import Path
import tempfile
import tomllib
import unittest
from unittest.mock import patch

from pdf_chapter_merger import __version__
from scripts import fetch_wheels

ROOT = Path(__file__).resolve().parents[1]


class RepositoryTests(unittest.TestCase):
    def test_metadata_and_dependency_locks_agree(self):
        project = tomllib.loads((ROOT / 'pyproject.toml').read_text())['project']
        manifest = json.loads((ROOT / 'install-manifest.json').read_text())
        self.assertEqual(project['version'], __version__)
        self.assertEqual({p['name'] for p in manifest}, {'pip', 'pypdf'})
        runtime = next(p for p in manifest if p['name'] == 'pypdf')
        self.assertEqual(project['dependencies'], [f"pypdf=={runtime['version']}"])
        lock = [line for line in (ROOT / 'requirements.txt').read_text().splitlines() if line and not line.startswith('#')]
        self.assertEqual(lock, [f"{p['name']}=={p['version']} --hash=sha256:{p['sha256']}" for p in manifest])

    def test_download_host_policy(self):
        self.assertTrue(fetch_wheels.approved_url('https://files.pythonhosted.org/packages/example.whl'))
        for url in ('http://files.pythonhosted.org/example.whl', 'https://example.com/package.whl',
                    'https://files.pythonhosted.org.evil.test/package.whl',
                    'https://user:password@files.pythonhosted.org/package.whl'):
            self.assertFalse(fetch_wheels.approved_url(url))

    def test_tampered_cached_wheel_is_not_replaced_or_executed(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            folder = Path(directory)
            (folder / 'wheelhouse').mkdir()
            (folder / 'wheelhouse/package.whl').write_bytes(b'altered')
            (folder / 'install-manifest.json').write_text(json.dumps([{
                'name': 'package', 'version': '1', 'filename': 'package.whl', 'sha256': '0' * 64}]))
            with patch.object(fetch_wheels.urllib.request, 'build_opener') as opener:
                with self.assertRaisesRegex(ValueError, 'Altered wheel'):
                    fetch_wheels.ensure_wheels(folder)
                opener.return_value.open.assert_not_called()
