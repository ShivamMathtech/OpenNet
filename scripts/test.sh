#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
bash scripts/build.sh
./build/packet-tests
python3 -m unittest discover -s tests -v
