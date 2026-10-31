"""Verify a freshly extracted release without touching user documents."""
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    version = tomllib.loads((ROOT / 'pyproject.toml').read_text())['project']['version']
    archive = ROOT / 'dist' / f'pdf-chapter-merger-{version}-windows-x64.zip'
    expected = archive.with_suffix('.zip.sha256').read_text().split()[0]
    if hashlib.sha256(archive.read_bytes()).hexdigest() != expected:
        raise ValueError('Release archive checksum mismatch.')
    build = ROOT / 'build'
    build.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=build) as directory:
        temporary = Path(directory).resolve()
        if not temporary.is_relative_to(build.resolve()):
            raise ValueError('Smoke-test path escaped the build folder.')
        with zipfile.ZipFile(archive) as bundle:
            for item in bundle.infolist():
                if not (temporary / item.filename).resolve().is_relative_to(temporary):
                    raise ValueError('Unsafe archive entry.')
            bundle.extractall(temporary)
        extracted = temporary / 'pdf-chapter-merger'
        subprocess.run([sys._base_executable, '-I', str(extracted / 'scripts/bootstrap.py')], check=True)
        code = """from pathlib import Path
import sys
root = Path.cwd()
sys.path[:0] = [str(root/'src'), str(root/'.venv/Lib/site-packages')]
import tkinter as tk
from pdf_chapter_merger.app import MergerApp
window = tk.Tk()
window.withdraw()
app = MergerApp(window)
window.update()
assert 'pypdf' not in sys.modules
app.close_window()
from pypdf import PdfReader, PdfWriter
from pdf_chapter_merger.merge import chapter_page, merge_pdfs
source, target = root/'synthetic.pdf', root/'merged.pdf'
writer = PdfWriter()
writer.add_page(chapter_page('Synthetic smoke check', 1))
writer.write(source)
writer.close()
assert merge_pdfs([source], target) == 2
reader = PdfReader(target)
assert reader.outline[0].title == 'synthetic'
assert 'Synthetic smoke check' in reader.pages[1].extract_text()
print('Extracted release: offline setup, GUI initialization, bounded merge, and bookmark checks passed.')
"""
        subprocess.run([str(extracted / '.venv/Scripts/python.exe'), '-I', '-S', '-c', code],
                       cwd=extracted, check=True, timeout=180)


if __name__ == '__main__':
    main()
