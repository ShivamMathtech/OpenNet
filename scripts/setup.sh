#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ "$(uname -s)" != Linux ]]; then
  echo 'This release targets Linux. On Windows use WSL2 Ubuntu or Docker Desktop.' >&2
  exit 1
fi
missing=0
for tool in g++ python3; do
  if ! command -v "$tool" >/dev/null; then echo "Missing: $tool" >&2; missing=1; fi
done
if [[ ! -f /usr/include/openssl/hmac.h ]]; then echo 'Missing OpenSSL development headers' >&2; missing=1; fi
if ((missing)); then
  echo 'On Ubuntu/Debian: sudo apt update && sudo apt install -y build-essential cmake libssl-dev python3' >&2
  exit 1
fi
python3 -c 'import sys; assert sys.version_info >= (3,10), "Python 3.10+ required"'
chmod +x opennet scripts/*.sh
bash scripts/build.sh
./build/packet-tests
printf '\nSetup complete. Start: ./opennet start\nDashboard: http://localhost:3000\n'
