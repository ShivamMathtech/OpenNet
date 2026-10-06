# Security and LAN boundaries

## Local educational security

The default network binds to loopback. Every encoded packet carries HMAC-SHA256 over the header and payload using a new random session key inherited by child processes. This protects integrity and gates participation on possession of the shared key. All members share the key and therefore can impersonate another logical source if compromised. There is no replay protection, encryption, public-key identity, access policy per node, or secure key exchange.

The dashboard API is for trusted local use. POST operations need a session token. Host checks reduce DNS rebinding; no cross-origin API access is enabled. The token can be obtained by local clients from `/api/session`, so it does not isolate one local user from another. Do not publish the API on the Internet. Docker's supplied mapping binds to host `127.0.0.1`.

Payloads appear in logs as hex and can be decoded. Do not send passwords or other sensitive data through an educational demo. Input/frame/payload limits and timeouts reduce accidental malformed-input failures, not all resource-exhaustion attacks. The simple HTTP server is not intended to resist hostile traffic or large numbers of connections.

## Multi-machine extension

Node configs use configurable IPv4 bind hosts and peer endpoints, not hard-coded loopback in the core. The core can exchange sockets between machines with suitable manual configs, shared keys and open ports. However, this release's controller **spawns all processes locally** and reads their local stdout/stdin pipes. Changing a demo node to another laptop's IP does not remotely launch it and will normally fail to bind.

A complete supported LAN mode requires a remote agent or SSH supervision, separate bind/advertised-address handling where needed, secure key distribution, authenticated remote control and telemetry, and synchronized timestamps. These are future work. Do not treat the shipped demo as a turnkey multi-machine deployment.

For controlled manual experiments an advanced user can launch `build/opennet-node NODE.conf` on each Linux host with the same securely supplied `OPENNET_KEY`, connect stdin control commands locally, and use real reachable peer IPs. Keep the key at least 32 characters, never commit it, and understand that the bundled dashboard will not automatically aggregate remote stdout. No public-internet exposure is required.
