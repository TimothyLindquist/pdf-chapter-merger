"""Maintainer-only explicit dependency updates; does not install or build code."""
import argparse
import json
from pathlib import Path
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from fetch_wheels import check_advisories, ensure_wheels


def main():
    current = {p['name']: p['version'] for p in json.loads((ROOT / 'install-manifest.json').read_text())}
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pip-version', default=current['pip'])
    parser.add_argument('--pypdf-version', default=current['pypdf'])
    args = parser.parse_args()
    import re
    versions = {'pip': args.pip_version, 'pypdf': args.pypdf_version}
    proposed = []
    for name, version in versions.items():
        if not re.fullmatch(r'\d+(?:\.\d+){1,3}', version):
            parser.error('Select an explicit stable numeric release version.')
        with urllib.request.urlopen(f'https://pypi.org/pypi/{name}/{version}/json', timeout=45) as response:
            metadata = json.load(response)
        candidates = [a for a in metadata['urls'] if not a.get('yanked') and a['filename'].endswith('py3-none-any.whl')]
        if len(candidates) != 1:
            raise ValueError(f'Expected one universal wheel for {name} {version}.')
        artifact = candidates[0]
        proposed.append({'name': name, 'version': version, 'filename': artifact['filename'],
                         'url': artifact['url'], 'sha256': artifact['digests']['sha256']})
    check_advisories(proposed)
    # These files fail closed if interrupted between replacements. Review both in the same PR.
    (ROOT / 'install-manifest.json').write_text(json.dumps(proposed, indent=2) + '\n')
    lock = '# CPython 3.11, Windows x64; hashed wheels only\n' + '\n'.join(
        f"{p['name']}=={p['version']} --hash=sha256:{p['sha256']}" for p in proposed) + '\n'
    (ROOT / 'requirements.txt').write_text(lock)
    ensure_wheels()
    print('Review manifest, requirements, advisory report, upstream changes, and test results before committing.')


if __name__ == '__main__':
    main()
