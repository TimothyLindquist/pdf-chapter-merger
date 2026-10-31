import _support
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from scripts import bootstrap as secure_setup


class InstallerTests(unittest.TestCase):
    def check_rejection(self, altered):
        secure_setup.platform.machine()  # Resolve Windows information before mocking subprocess.
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            root = Path(directory)
            (root / 'wheelhouse').mkdir()
            (root / 'wheelhouse/package.whl').write_bytes(b'altered' if altered else b'expected')
            (root / 'install-manifest.json').write_text(json.dumps([{
                'name': 'package', 'version': '1', 'filename': 'package.whl',
                'sha256': hashlib.sha256(b'expected').hexdigest()}]))
            (root / 'requirements.txt').write_text('package==2')
            with patch.object(secure_setup, 'ROOT', root), patch.object(secure_setup.subprocess, 'run') as run:
                with self.assertRaisesRegex(RuntimeError, 'Missing or altered package' if altered else 'do not agree'):
                    secure_setup.main()
                run.assert_not_called()

    def test_altered_wheel_rejected_before_execution(self):
        self.check_rejection(True)

    def test_lock_disagreement_rejected_before_execution(self):
        self.check_rejection(False)


if __name__ == '__main__':
    unittest.main()
