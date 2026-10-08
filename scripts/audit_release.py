#!/usr/bin/env python3
"""Audit index content before commit; excludes ignored local runtime by design.
Heuristic check, not a replacement for reviewing every staged file.
"""
from pathlib import Path
import re
import subprocess

root = Path(__file__).resolve().parents[1]
paths = subprocess.check_output(['git', 'ls-files', '-z'], cwd=root).decode().split('\0')
patterns = [
    ('private home path', re.compile(rb'/(?:Users|home)/[A-Za-z0-9_.-]+/')),
    ('private LAN IP', re.compile(rb'\b(?:192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3})\b')),
    ('key material', re.compile(rb'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----')),
    ('provider token', re.compile(rb'\b(?:sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{25,})')),
    ('phone number', re.compile(rb'\+1[2-9][0-9]{9}\b')),
]
failures = []
for name in filter(None, paths):
    if any(part in ('.runtime', '.venv', '__pycache__') for part in Path(name).parts) or name in ('config.json', '.env') or name.endswith(('.bin', '.wav', '.pcm', '.mp3', '.pt', '.log')):
        failures.append((name, 'private/generated file'))
    content = subprocess.check_output(['git', 'show', ':' + name], cwd=root)
    for label, pattern in patterns:
        if pattern.search(content):
            failures.append((name, label))
for name, label in failures:
    print(f'FAIL {name}: {label}')  # Never print matched secrets.
if failures:
    raise SystemExit(1)
print(f'PASS: {len(list(filter(None, paths)))} indexed files checked; review the staged diff too.')
