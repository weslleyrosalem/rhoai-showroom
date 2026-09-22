#!/usr/bin/env python3
"""Offline public-content checks. Never prints matched secret values."""
from pathlib import Path
import re, subprocess, sys
root=Path(__file__).resolve().parents[1]
paths=subprocess.check_output(['git','ls-files','-z'],cwd=root).decode().split('\0')
patterns=[r'BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY',r'gh[pousr]_[A-Za-z0-9]{30,}',r'sk-ant-[A-Za-z0-9_-]{20,}',r'AKIA[A-Z0-9]{16}',r'eyJhbGci[A-Za-z0-9_.-]{80,}']
errors=[]
for name in paths:
 if not name or name==__file__:continue
 path=root/name
 if not path.is_file():continue
 content=path.read_text(errors='replace')
 for pattern in patterns:
  if re.search(pattern,content):errors.append(name+': potential secret')
 if re.search(r'\.apps\.rosa\.[a-z0-9.-]+\.openshiftapps\.com',content):errors.append(name+': cluster-specific hostname')
 if '.credentials.' in name or name.endswith('.local.json'):errors.append(name+': private configuration')
if errors:
 print('\n'.join(sorted(set(errors))));sys.exit(1)
print('PASS: tracked files contain no matching credential or private-host patterns.')
