# Feature status

This checklist maps the original development brief to this delivered release. The original was a specification, not an existing source repository.

| Area | Status | Details |
|---|---|---|
| C++20 real socket core | Implemented | Linux/POSIX; TCP and UDP |
| Independent node/router/DNS/server processes | Implemented | Seven-process default topology |
| Custom packet serialization, TTL, integrity | Implemented | Binary codec + HMAC-SHA256 |
| Static and shortest-path routing | Implemented | Explicit consistent static paths; centralized Dijkstra |
| Dynamic failure recovery | Implemented | Heartbeat and neighbor failure triggers |
| Discovery | Implemented, scoped | Announcements to configured neighbors only |
| DNS-like service and TTL cache | Implemented | Overlay query to DNS process |
| HTTP-like application | Implemented, scoped | GET `/`, 404 for other paths |
| CLI | Implemented | See README exact commands |
| Trace, logs, measured metrics | Implemented | Event-derived hops; process CPU time and RSS on Linux |
| REST + WebSocket | Implemented | Standard-library server, local use |
| Live dashboard | Implemented | Plain JS/CSS/SVG; no React/TypeScript/Tailwind build |
| Packet animations | Implemented | Slowed replay from real forwarding events |
| Node faults / packet loss / delay | Implemented | Process kill/restart and bounded impairments |
| Runtime topology changes | Partial | Link withdrawal/restoration; edit JSON + restart for node changes |
| JSON/YAML configuration | Partial | JSON only |
| Experiments and reports | Implemented, scoped | Latency, request throughput, random loss, recovery; real JSON/CSV |
| Congestion research model | Planned | No modeled queues, bandwidth shaping or congestion-control algorithm |
| Unit and integration tests | Implemented | C++ executable + Python unittest, not GoogleTest |
| Docker/Compose/CI definitions | Included | Linux tests executed; Docker/hosted CI not run in delivery environment |
| Node authentication | Basic | Shared session HMAC; no per-node identity isolation |
| Encryption and replay defense | Planned | Not implemented |
| Multi-machine operation | Experimental socket foundation | Configurable hosts; no remote agent/distributed controller |
| Distributed route advertisements | Planned | ROUTE_UPDATE packet type reserved; tables installed via stdin |
| Per-hop RTT measurement | Planned | Hop receive timestamps + whole-request RTT available |
| Automatic UDP retries/deduplication | Planned | Loss is visible, not masked |
| Research ML/adaptive routing | Planned | No claimed trained model or research results |
| Native Windows/macOS | Planned | Use Linux, Windows WSL2 or Docker |

This release is suitable for local learning and controlled networking experiments. It does not claim feature-for-feature completion of a production research platform.
