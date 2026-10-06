#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build
if command -v cmake >/dev/null; then
  cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
  cmake --build build -j 2
else
  echo 'CMake unavailable; using equivalent direct C++20 build.'
  g++ -std=c++20 -O2 -Wall -Wextra -Wpedantic -Icore apps/node.cpp -lcrypto -o build/opennet-node
  g++ -std=c++20 -O2 -Icore tests/packet_test.cpp -lcrypto -o build/packet-tests
fi
