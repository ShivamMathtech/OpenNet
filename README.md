# OpenNet

**Build the Internet From First Principles**

OpenNet is a runnable educational overlay network. Seven independent C++20 processes communicate over actual operating-system sockets. A Python controller supervises them, installs routes, and streams observed events to a browser dashboard.

This is an educational implementation, not the real Internet and not a production network stack. The source ZIP contains the working implementation, tests, demo configurations, CLI, dashboard, and setup files. It has no Python packages, npm dependencies, CDN scripts, or mandatory cloud services.

## Start here

- **Windows:** read [SETUP_WINDOWS.md](SETUP_WINDOWS.md). Use **WSL2 Ubuntu** or **Docker Desktop with Linux containers**. Native Windows compilation is not supported by this POSIX release.
- **Linux / WSL2 Ubuntu:** run the following commands inside the extracted `opennet` folder.

```bash
sudo apt update
sudo apt install -y build-essential cmake libssl-dev python3
bash scripts/setup.sh
make test
make demo
```

Open **http://localhost:3000**. Leave the terminal running. Stop with **Ctrl+C**.

Already built? Use `./opennet start` or `bash scripts/start_demo.sh`.

No CMake? The build script has an equivalent direct `g++` fallback. Python 3.10+ and a C++20 compiler with OpenSSL development headers are required. No `pip install` or virtual environment is necessary.

## First experiment

Open a **second terminal** in the same folder:

```bash
./opennet ping server.local
./opennet traceroute server.local
./opennet dns resolve server.local
./opennet curl http://server.local/
./opennet send node-b "Hello through the routers"
./opennet fault kill router-2
```

Watch the dashboard: the router becomes SUSPECTED after about 2 seconds without a process heartbeat, then FAILED after about 3.2 seconds. Peer-to-peer heartbeats independently detect a missing neighbor after about 3 seconds. When a route is withdrawn, the controller installs the alternate path. After detection:

```bash
./opennet traceroute server.local
./opennet curl http://server.local/
./opennet fault restart router-2
```

Default primary route: `node-a → router-1 → router-2 → server`.
Alternate route: `node-a → router-1 → router-3 → server`.

The dashboard has no generated background traffic: send a request to see pulses. Pulses are slowed-down replays of real forwarding events, not representations of wall-clock packet speed. Click an event or visible pulse to inspect packet details. Select a node to inspect its routing table.

## Implemented

- Separate C++ processes for nodes, routers, DNS, and the application server.
- Real UDP datagrams and length-framed TCP connections; both listen on each configured node port.
- Bounded binary packets, version/type/length/TTL validation, 64-bit request IDs, HMAC-SHA256 integrity with a per-session shared key.
- Weighted, centralized Dijkstra routing and explicit static route configurations.
- Peer discovery announcements to configured neighbors; real peer heartbeat traffic.
- Process liveness, ACTIVE/SUSPECTED/FAILED states, route withdrawal, alternate paths, restart recovery.
- DNS-like queries/responses, NXDOMAIN and per-source TTL cache; HTTP-like GET over the overlay.
- End-to-end acknowledged DATA and PING/PONG; event-derived traceroute.
- Local REST controls, authenticated mutations, read-only WebSocket snapshots, responsive dark/light dashboard.
- Packet counters, bytes, request successes/failures, measured RTT, Linux process CPU time/RSS, structured JSONL logs, route-change records.
- Process kill/restart, administrative link withdrawal, random loss and per-forward delay injection.
- Real latency, request-throughput, packet-loss and failure-recovery experiments with CSV/JSON exports.
- Unit, real-socket integration, API and WebSocket tests; CMake, Makefile, Docker and CI definitions.

## Scope and deliberate choices

The supplied brief describes a larger research platform. See [docs/FEATURE_STATUS.md](docs/FEATURE_STATUS.md) for the precise implemented / experimental / planned boundary.

This release uses a **dependency-free HTML/CSS/JavaScript dashboard**, rather than the proposed React/TypeScript/Vite/Tailwind stack. This keeps setup offline after installing the system toolchain. Topologies are JSON, not YAML. C++ tests are dependency-free executable checks rather than GoogleTest. All three are documented implementation choices, not hidden dependencies.

Routing is centrally computed, not BGP/OSPF/RIP. Discovery only announces to configured neighbors; it is not broadcast LAN discovery. DNS and HTTP are custom overlay services, not public DNS or a complete HTTP server. UDP has no automatic delivery retries; TCP uses the OS's reliable transport and opens one short connection per hop. The software does not require root privileges, TUN/TAP devices or kernel routing changes.

## Docker

From the `opennet` directory:

```bash
docker compose up --build
```

Open http://localhost:3000. To use the CLI inside the container:

```bash
docker compose exec opennet python3 opennet ping server.local
docker compose exec opennet python3 opennet curl http://server.local/
```

Stop with Ctrl+C followed by `docker compose down`. Only the dashboard port is published, bound to host loopback. Docker requires an internet connection for the initial base image and package download. Docker files are supplied but were not executed in the delivery environment; see [docs/VALIDATION.md](docs/VALIDATION.md).

## CLI reference

| Command | Purpose |
|---|---|
| `./opennet start [--config configs/demo.json] [--port 3000]` | Start all processes and dashboard in the foreground |
| `./opennet stop` | Stop the running controller and its child processes |
| `./opennet status` / `nodes` | Node state, PID, heartbeat age and metrics |
| `./opennet routes` / `topology` | Installed route paths / complete snapshot |
| `./opennet ping server.local [--source node-b] [--ttl 16]` | PING/PONG through the overlay |
| `./opennet traceroute server.local` | Observed forward-path hops and round-trip time |
| `./opennet send node-b "hello"` | DATA and acknowledgment |
| `./opennet dns resolve server.local` | DNS-like lookup through the DNS process |
| `./opennet curl http://server.local/` | Resolve hostname, then overlay GET |
| `./opennet logs [--node router-2]` | Recent observed events |
| `./opennet metrics` | Packet and request counters |
| `./opennet fault kill router-2` | Kill a real child process |
| `./opennet fault stop router-2` | Gracefully terminate a node |
| `./opennet fault restart router-2` | Restart a stopped node |
| `./opennet fault impair router-1 --loss 0.2 --delay-ms 10` | Apply independent per-forward loss and blocking delay |
| `./opennet fault impair router-1` | Reset loss and delay to zero |
| `./opennet link down router-1 router-2` / `link up ...` | Withdraw or restore a link in dynamic routing |

IDs, hostnames and logical addresses are accepted as destinations. `ping` resolves them from the controller's topology; `dns resolve` and `curl` demonstrate real DNS queries over the overlay. All mutations are local API calls. CLI JSON outputs are suitable for piping to other tools.

## Configuration

- `configs/demo.json`: UDP, dynamic routing, seven processes, alternate path.
- `configs/tcp.json`: same network using TCP for application packets; peer heartbeats remain UDP.
- `configs/static.json`: explicit route paths; failures **do not** trigger rerouting in this mode.

```bash
./opennet start --config configs/tcp.json
```

Stop an existing instance before starting another. Each node has an ID, logical address, hostname, role, real bind host/port and optional dashboard coordinates. Each undirected link has a positive routing cost. Edit the JSON before startup to create your own topology. Non-router nodes cannot forward transit traffic.

Static configurations define `static_routes[source][destination]` as a complete node-ID path. Tables are checked for valid links, cycles, transit roles and next-hop consistency. Live arbitrary node/topology creation is not implemented; link withdrawal and node restart are available at runtime.

## Experiments

Run these while the demo is running:

```bash
python3 scripts/experiment.py latency --count 100
python3 scripts/experiment.py throughput --count 200 --concurrency 8
python3 scripts/experiment.py loss --router router-2 --loss 0.2 --count 100
python3 scripts/experiment.py recovery --router router-2
```

Results go to `reports/*.json` and `reports/*.csv`. Read [docs/EXPERIMENTS.md](docs/EXPERIMENTS.md) before interpreting them. No benchmark constants are displayed as live results.

## Project map

```text
opennet/
  core/                 binary packet codec, HMAC, socket/frame helpers
  apps/                 C++ process implementation and Python CLI
  controller/           topology, routing, process manager, API, WebSocket
  dashboard/            browser UI; no build step
  configs/              UDP, TCP and static examples
  scripts/              setup, build, tests and measured experiments
  tests/                packet, routing, socket, failure and API tests
  docs/                 protocol, architecture, limitations and validation
  examples/             reproducible walk-through
  CMakeLists.txt
  Makefile
  Dockerfile
  docker-compose.yml
  opennet               executable CLI entry point
```

## Documentation

- [Windows setup](SETUP_WINDOWS.md)
- [Architecture and interfaces](ARCHITECTURE.md)
- [Packet protocol](PROTOCOL.md)
- [API reference](docs/API.md)
- [Feature status and roadmap](docs/FEATURE_STATUS.md)
- [Experiments and measurement caveats](docs/EXPERIMENTS.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Security and multi-machine limitations](docs/SECURITY_AND_LAN.md)
- [Validation record](docs/VALIDATION.md)
- [Contribution guide](CONTRIBUTING.md)

MIT licensed. No fabricated badges, test counts or performance claims.
