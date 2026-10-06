# Local API

Base URL: `http://127.0.0.1:3000`. Requests must use Host `localhost:<port>` or `127.0.0.1:<port>`; other names are rejected to reduce DNS-rebinding risk. CORS is not enabled. The API is intended for a trusted local machine, not Internet exposure.

| Method | Path | Response / purpose |
|---|---|---|
| GET | `/api/session` | Local dashboard session token |
| GET | `/api/state` | Nodes, links, routes, metrics, recent events |
| POST | `/api/request` | End-to-end operation |
| POST | `/api/fault` | Kill, stop, restart or impair node |
| POST | `/api/link` | Administrative link up/down in dynamic mode |
| POST | `/api/stop` | Shutdown controller and child processes |
| GET + Upgrade | `/ws?token=...` | Read-only JSON snapshots every ~500ms |

POST requires `Content-Type: application/json` and `X-OpenNet-Token`. Local CLI reads the token from `.runtime/session.json` (mode 0600). This is not an account/login system: a same-machine client can retrieve the dashboard token from `/api/session`.

Request examples:

```json
{"kind":"ping","source":"node-a","target":"server.local","ttl":16}
```

```json
{"kind":"send","target":"node-b","payload":"hello"}
```

```json
{"kind":"dns","target":"server.local"}
```

```json
{"kind":"http","target":"server.local","path":"/"}
```

Fault examples:

```json
{"node":"router-2","action":"kill"}
```

```json
{"node":"router-2","action":"impair","loss":0.1,"delay_ms":20}
```

Link example:

```json
{"source":"router-1","target":"router-2","enabled":false}
```

Requests return `ok`, string request ID, source/target node IDs, RTT milliseconds, an observed event trace, and either payload or an error. HTTP response transport success does not mean a 200 application status: a valid 404 remains `ok: true` because the response was delivered. DNS NXDOMAIN becomes `ok: false`. DNS cache hits retain the original lookup trace/RTT and explicitly set `cached: true`.

Invalid request bodies return HTTP 400; token/Host errors 403; content-type mismatch 415. A valid operation that times out returns HTTP 200 with `ok: false` to distinguish transport/API errors from simulated network outcomes.

WebSocket supports server text messages and client close/ping/pong control frames. It is read-only: client data frames are rejected. It is intentionally not a general-purpose bidirectional WebSocket application framework.
