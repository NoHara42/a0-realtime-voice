"""Offline release audit: metadata, archive hygiene, and obvious credential patterns.

This is not a substitute for upstream CI or a comprehensive secret scanner.
Run after scripts/package.py. It never displays matched secret contents.
"""
from pathlib import Path
import re
import subprocess
import zipfile

root = Path(__file__).resolve().parents[1]
manifest = (root / 'plugin.yaml').read_text()
assert re.search(r'^name: realtime_voice$', manifest, re.M)
assert re.search(r'^version: 0\.1\.1$', manifest, re.M)
secret_patterns = [
    re.compile(rb'sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{24,}'),
    re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    re.compile(rb'gh[pousr]_[A-Za-z0-9]{30,}'),
]
with zipfile.ZipFile(root / 'dist/realtime_voice.zip') as archive:
    names = archive.namelist()
    for name in names:
        path = Path(name)
        assert path.parts[0] == 'realtime_voice' and '..' not in path.parts
        assert not any(part in {'.git', 'dev', '__pycache__', 'node_modules'} for part in path.parts)
        assert path.name not in {'.env', 'config.json', '.toggle-0', '.toggle-1'}
        assert path.suffix not in {'.wav', '.log', '.pyc'}
        data = archive.read(name)
        assert not any(pattern.search(data) for pattern in secret_patterns), f'Possible secret in {name}'
        source = root.joinpath(*path.parts[1:])
        assert data == source.read_bytes(), f'Archive/source mismatch: {name}'
    for name in ('plugin.yaml', 'README.md', 'LICENSE', 'SECURITY.md', 'webui/config.html'):
        assert f'realtime_voice/{name}' in names
publishable = subprocess.check_output(
    ['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=root
).split(b'\0')
checked = 0
for raw_path in publishable:
    if not raw_path:
        continue
    path = root / raw_path.decode()
    if not path.is_file():
        continue
    assert not path.is_symlink(), f'Publishable symlink: {path.relative_to(root)}'
    assert not any(pattern.search(path.read_bytes()) for pattern in secret_patterns), f'Possible secret in {path.relative_to(root)}'
    checked += 1
print(f'PASS: {len(names)} source-matched archive files; metadata and secret/artifact checks passed')
print(f'PASS: {checked} publishable source files scanned for high-confidence credential patterns')
