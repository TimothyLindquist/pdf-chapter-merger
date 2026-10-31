"""Offline, hash-verified setup for the supported Windows Python environment."""
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    if sys.version_info[:2] != (3, 11) or sys.platform != 'win32' or platform.machine().lower() not in ('amd64', 'x86_64'):
        raise RuntimeError('This verified package set requires 64-bit Python 3.11 on Windows.')
    manifest = json.loads((ROOT / 'install-manifest.json').read_text())
    wheels = ROOT / 'wheelhouse'
    for item in manifest:
        filename = item['filename']
        if Path(filename).name != filename or not filename.endswith('.whl'):
            raise RuntimeError('Invalid wheel filename in installation manifest.')
        artifact = wheels / filename
        if not artifact.is_file() or hashlib.sha256(artifact.read_bytes()).hexdigest() != item['sha256']:
            raise RuntimeError(f'Missing or altered package: {filename}. Restore the verified wheelhouse.')
    # The requirements and manifest must agree before any package code is executed.
    expected_lock = [f"{p['name']}=={p['version']} --hash=sha256:{p['sha256']}" for p in manifest]
    actual_lock = [line.strip() for line in (ROOT / 'requirements.txt').read_text().splitlines()
                   if line.strip() and not line.lstrip().startswith('#')]
    if actual_lock != expected_lock:
        raise RuntimeError('Installation manifest and requirements do not agree.')
    executable = ROOT / '.venv/Scripts/python.exe'
    if not executable.exists():
        subprocess.run([sys.executable, '-I', '-m', 'venv', '--without-pip', str(ROOT / '.venv')], check=True)
    expected = {item['name']: item['version'] for item in manifest}
    site_packages = str(ROOT / '.venv/Lib/site-packages')
    check = 'import importlib.metadata as m,json,sys; print(json.dumps({d.metadata["Name"].lower():d.version for d in m.distributions(path=[sys.argv[1]])}))'
    installed = json.loads(subprocess.check_output([str(executable), '-I', '-S', '-c', check, site_packages], text=True))
    # These packages were used by the earlier title-page implementation. Remove
    # them rather than leaving their initialization/configuration hooks available.
    retired = [name for name in ('reportlab', 'pillow', 'charset-normalizer', 'setuptools') if name in installed]
    pip_wheel = wheels / next(p['filename'] for p in manifest if p['name'] == 'pip')
    bootstrap = 'import sys,runpy; sys.path.insert(0,sys.argv.pop(1)); runpy.run_module("pip",run_name="__main__")'
    environment = os.environ.copy()
    environment['PIP_CONFIG_FILE'] = os.devnull
    if retired:
        subprocess.run([str(executable), '-I', '-c', bootstrap, str(pip_wheel),
            '--isolated', '--disable-pip-version-check', 'uninstall', '-y', *retired], env=environment, check=True)
    if any(installed.get(name) != version for name, version in expected.items()):
        # Bootstrap from the verified NEW pip wheel, never the old installed pip.
        subprocess.run([str(executable), '-I', '-c', bootstrap, str(pip_wheel),
            '--isolated', '--disable-pip-version-check', 'install', '--no-index',
            '--find-links', str(wheels), '--only-binary=:all:', '--require-hashes',
            '--no-deps', '--upgrade', '-r', str(ROOT / 'requirements.txt')],
            env=environment, check=True)
        installed = json.loads(subprocess.check_output([str(executable), '-I', '-S', '-c', check, site_packages], text=True))
        if any(installed.get(name) != version for name, version in expected.items()):
            raise RuntimeError('Installed versions do not match the verified lock.')
    print('Verified package set ready. Setup uses no network or source-build scripts.')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'Setup failed: {exc}', file=sys.stderr)
        sys.exit(1)
