# Troubleshooting

| Symptom | Fix |
|---|---|
| `g++: command not found` or OpenSSL headers missing | In Ubuntu: `sudo apt install build-essential cmake libssl-dev python3` |
| `ModuleNotFoundError: fcntl` | You are using native Windows Python; switch to WSL2 Ubuntu or Docker |
| `make: command not found` | Install `build-essential`, or use `bash scripts/build.sh` and `bash scripts/start_demo.sh` |
| Permission denied executing scripts | `chmod +x opennet scripts/*.sh`; alternatively `python3 opennet ...` |
| `OpenNet is already running` | Stop the existing instance from its original terminal or `./opennet stop` |
| Dashboard port already in use | `./opennet start --port 3001`; open the matching browser URL |
| Node startup failed / bind error | Read `.runtime/<node>.stderr.log`; free the listed port or change node ports in your JSON |
| No moving packets | The network is idle. Send a ping from the dashboard or CLI |
| PING fails right after killing a router | Wait for heartbeat detection and route installation, usually ~3–4 seconds |
| PING still fails | Check alternate path exists, routers are ACTIVE, TTL is sufficient, and loss is not 1. Static routing does not recover automatically |
| DNS NXDOMAIN | Use a hostname from your JSON; default is `server.local` |
| HTTP-like 404 | Only `GET /` is implemented in the sample server |
| CLI cannot reach controller | Run it in the same project folder/environment as the running instance; for Docker use `docker compose exec` |
| Browser says Host rejected | Use `http://localhost:<port>` or `http://127.0.0.1:<port>`; custom hostnames are not allowed |
| No route for a destination | Check links and role settings; only role `router` forwards transit packets |
| Routes look stale after editing JSON | Stop and restart; arbitrary topology reload is not implemented |
| Docker cannot connect to daemon | Start Docker Desktop, enable Linux containers, then retry |
| Large log file | Stop OpenNet, archive or delete `.runtime/events.jsonl`; this release does not rotate logs |

Node processes listen on both UDP and TCP for their configured port. Demo ports: 5101, 5102, 5110, 5120, 5130, 5150, 5153. The dashboard API uses 3000 by default. No root privileges are required to bind these ports.

The controller holds an operating-system file lock, so a stale `.runtime/controller.lock` file alone does not block a new launch. Do not delete the lock while another controller is running. Ctrl+C / `opennet stop` clean up children. If the controller is force-killed, child processes notice control-pipe EOF and exit.
