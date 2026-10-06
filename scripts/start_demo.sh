#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -x build/opennet-node ]]; then bash scripts/build.sh; fi
exec python3 -m controller.main "$@"
