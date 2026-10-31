"""Run the Windows regression suite against the verified project environment."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT), str(ROOT / '.venv/Lib/site-packages')]

if __name__ == '__main__':
    if sys.platform != 'win32' or sys.version_info[:2] != (3, 11):
        sys.exit('Tests require Windows with Python 3.11.')
    suite = unittest.defaultTestLoader.discover(str(ROOT / 'tests'))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(not result.wasSuccessful())
