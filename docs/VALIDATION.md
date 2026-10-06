# Delivery validation

Validation was performed on Linux with Python 3.12 and the available C++20 g++ compiler.

Executed successfully:

- Direct C++20 optimized build linked against OpenSSL libcrypto, with `-Wall -Wextra -Wpedantic` and no build warnings in the final run.
- C++ packet test executable: binary roundtrip, IPv4 conversion, HMAC rejection, corruption, bounds, zero-TTL rejection and hex validation.
- **23 Python unittest cases**: topology validation; router-only transit; shortest/alternate routes; static non-recovery; real UDP and TCP multihop requests; self-ping; DNS/cache/NXDOMAIN; HTTP 200/404; DATA acknowledgments; TTL expiry; injected loss; link withdrawal; process kill/detection/recovery/restart; malformed datagram rejection; fragmented TCP reads; API controls, authentication/Host validation; WebSocket handshake/snapshot/close.
- Separate foreground-controller smoke run using the public CLI: traceroute, overlay HTTP, real latency and recovery reports, and graceful shutdown.
- Python bytecode compilation and dashboard JavaScript syntax check.

`test-output.txt` contains the actual test runner output. `cli-experiment-validation.json` contains actual CLI output from the validation machine. These are recorded observations, not promised performance on another computer. Experiment artifacts should be regenerated after any source or environment change.

Not executed in this environment:

- CMake/CTest path (CMake was unavailable; equivalent g++ path was used).
- Docker image/Compose and hosted GitHub Actions (definitions supplied).
- Windows WSL2 or Docker Desktop on an actual Windows machine.
- Browser rendering, interaction or visual QA. Playwright was present but its Chromium binary was absent. JavaScript syntax, HTTP assets and live WebSocket protocol were checked, but this is not a substitute for a browser test.
- Multi-machine operation, sustained-load security testing or large-scale performance characterization.

The README and feature-status document explicitly describe the scope and remaining work.
