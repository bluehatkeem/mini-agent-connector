#!/bin/sh
# Run from any working directory. Does not install global packages or launch services.
set -eu
cd "$(dirname "$0")/.."
python3 -c 'import sys; assert sys.version_info >= (3, 10), "Python 3.10+ required"'
python3 -m venv .venv
if [ ! -e config.json ]; then
  (umask 077; cp config.example.json config.json)
fi
printf '%s\n' 'Ready. Edit config.json, then run:' \
  '.venv/bin/python server.py --config config.json --doctor' \
  '.venv/bin/python server.py --config config.json'
