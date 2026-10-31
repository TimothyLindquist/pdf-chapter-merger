"""Build an offline source bundle from an explicit publication allowlist."""
import hashlib
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from fetch_wheels import ensure_wheels


def main():
    manifest = ensure_wheels(verify_only=True)
    import tomllib
    metadata = tomllib.loads((ROOT / 'pyproject.toml').read_text())
    version = metadata['project']['version']
    dist = ROOT / 'dist'
    dist.mkdir(exist_ok=True)
    archive = dist / f'pdf-chapter-merger-{version}-windows-x64.zip'
    files = [ROOT / name for name in (
        'README.md', 'LICENSE', 'SECURITY.md', 'THIRD_PARTY_NOTICES.md', 'CONTRIBUTING.md', 'CHANGELOG.md',
        'Start PDF Merger.bat', 'install-manifest.json', 'requirements.txt',
        'pyproject.toml')]
    for directory, pattern in (('src/pdf_chapter_merger', '*.py'), ('scripts', '*.py'),
                               ('tests', '*.py'), ('docs', '*.md')):
        files.extend(sorted((ROOT / directory).glob(pattern)))
    files.extend(ROOT / 'wheelhouse' / item['filename'] for item in manifest)
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as output:
        for source in files:
            if not source.is_file() or source.is_symlink():
                raise ValueError(f'Missing or unsupported release input: {source.name}')
            relative = source.relative_to(ROOT)
            if not source.resolve().is_relative_to(ROOT):
                raise ValueError('Release input escaped the repository.')
            info = zipfile.ZipInfo('pdf-chapter-merger/' + relative.as_posix(), date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            output.writestr(info, source.read_bytes())
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix('.zip.sha256').write_text(f'{digest}  {archive.name}\n')
    print(f'Built {archive.name}\nSHA-256: {digest}')


if __name__ == '__main__':
    main()
