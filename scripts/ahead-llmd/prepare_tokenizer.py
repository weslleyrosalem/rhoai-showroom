#!/usr/bin/env python3
"""Fetch the public tokenizer at the exact revision used by the existing model."""
import argparse
import hashlib
from pathlib import Path
import urllib.request

REVISION = 'cdbee75f17c01a7cc42f958dc650907174af0554'
FILES = {
 'tokenizer.json':'aeb13307a71acd8fe81861d94ad54ab689df773318809eed3cbe794b4492dae4',
 'tokenizer_config.json':'a62ff0a2472a0fa1b8eaabcb57c59b58afa42a22831dc141400b6e0cf2b65ce3',
 'config.json':'5beea1a4a34c62782bfb2f911c606741a3bab8f92d80a118fa053c28af12e8ba',
}
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('directory',type=Path)
 a=p.parse_args();a.directory.mkdir(parents=True,exist_ok=True)
 for name,sha in FILES.items():
  target=a.directory/name
  raw=target.read_bytes() if target.exists() else urllib.request.urlopen(
    f'https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507/resolve/{REVISION}/{name}',timeout=40).read(30_000_000)
  if hashlib.sha256(raw).hexdigest()!=sha:raise ValueError('Tokenizer checksum mismatch: '+name)
  target.write_bytes(raw)
  print(name,sha)
