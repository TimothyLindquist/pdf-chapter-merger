"""Launch source code without site hooks or ambient Python import paths."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from pdf_chapter_merger.app import main

if __name__ == '__main__':
    main()
