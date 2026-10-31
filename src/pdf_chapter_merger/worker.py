"""Wait for job assignment before importing the PDF parser."""
import json
import os
from pathlib import Path
import sys

if __name__ == '__main__':
    request = json.loads(sys.stdin.readline(131072))
    package_parent = Path(__file__).resolve().parents[1]
    repository = package_parent.parent
    packages = repository / '.venv/Lib/site-packages' if (repository / 'install-manifest.json').is_file() else package_parent
    sys.path[:0] = [str(package_parent), str(packages)]
    try:
        import msvcrt
        from pdf_chapter_merger.merge import build_pdf
        descriptor = msvcrt.open_osfhandle(request['output_handle'], os.O_RDWR | os.O_BINARY)
        with os.fdopen(descriptor, 'w+b') as stream:
            count = build_pdf(request['files'], stream, request['titles'])
        print(json.dumps({'pages': count}), flush=True)
    except Exception as exc:
        print(json.dumps({'error': str(exc)[:1500]}), flush=True)
        sys.exit(1)
