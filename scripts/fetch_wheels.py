"""Download only the exact, hash-locked wheels. Never execute downloaded code."""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
MAX_DOWNLOAD = 64 * 1024 * 1024


def approved_url(url):
    parsed = urllib.parse.urlsplit(url)
    return (parsed.scheme == 'https' and parsed.hostname == 'files.pythonhosted.org'
            and parsed.port in (None, 443) and not parsed.username and not parsed.password)


class WheelRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, newurl):
        if not approved_url(newurl):
            raise ValueError('Wheel redirect left the approved HTTPS download host.')
        return super().redirect_request(request, response, code, message, headers, newurl)


def ensure_wheels(root=ROOT, *, verify_only=False):
    manifest = json.loads((root / 'install-manifest.json').read_text())
    cache = root / 'wheelhouse'
    cache.mkdir(exist_ok=True)
    opener = urllib.request.build_opener(WheelRedirects())
    for package in manifest:
        filename = package['filename']
        if Path(filename).name != filename or not filename.endswith('.whl'):
            raise ValueError('Invalid wheel filename.')
        destination = cache / filename
        if destination.exists():
            if hashlib.sha256(destination.read_bytes()).hexdigest() != package['sha256']:
                raise ValueError(f'Altered wheel: {filename}. Remove it and restore the verified copy.')
        else:
            if verify_only:
                raise ValueError(f'Missing wheel: {filename}. Run scripts/fetch_wheels.py first.')
            if not approved_url(package['url']):
                raise ValueError('Wheel URL must use the approved HTTPS download host.')
            with opener.open(package['url'], timeout=60) as response:
                data = response.read(MAX_DOWNLOAD + 1)
            if len(data) > MAX_DOWNLOAD or hashlib.sha256(data).hexdigest() != package['sha256']:
                raise ValueError(f'Download size/hash verification failed: {filename}')
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(dir=cache, suffix='.download', delete=False) as stream:
                    temporary = Path(stream.name)
                    stream.write(data)
                temporary.replace(destination)
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
        print(f"Verified {package['name']} {package['version']}", flush=True)
    return manifest


def check_advisories(manifest, root=ROOT):
    checks = {}
    for package in manifest:
        request = urllib.request.Request('https://api.osv.dev/v1/query',
            data=json.dumps({'package': {'name': package['name'], 'ecosystem': 'PyPI'},
                             'version': package['version']}).encode(),
            headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=45) as response:
            checks[package['name']] = json.load(response)
    folder = root / 'build'
    folder.mkdir(exist_ok=True)
    (folder / 'dependency-audit.json').write_text(json.dumps(checks, indent=2) + '\n')
    affected = [name for name, result in checks.items() if result.get('vulns')]
    if affected:
        raise ValueError('Known advisories found: ' + ', '.join(affected) + '. Review build/dependency-audit.json.')
    print('No known OSV advisories for the locked versions.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-only', action='store_true', help='Verify existing files without downloading wheels.')
    parser.add_argument('--check-advisories', action='store_true', help='Query OSV with package names/versions.')
    args = parser.parse_args()
    try:
        packages = ensure_wheels(verify_only=args.verify_only)
        if args.check_advisories:
            check_advisories(packages)
    except Exception as exc:
        parser.exit(1, f'Package preparation failed: {exc}\n')
