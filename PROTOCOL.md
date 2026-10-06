# OpenNet packet protocol v1

All integer fields use big-endian byte order. UDP sends one entire packet per datagram. TCP prefixes each packet with a 4-byte unsigned length and reads exactly that many bytes, so stream fragmentation is handled.

| Byte offset | Size | Field |
|---|---:|---|
| 0 | 4 | Magic ASCII `ONET` |
| 4 | 1 | Version = 1 |
| 5 | 1 | Packet type, 1..12 |
| 6 | 1 | TTL, nonzero |
| 7 | 1 | Flags, reserved = 0 |
| 8 | 8 | Request/sequence ID |
| 16 | 4 | Source logical IPv4 |
| 20 | 4 | Destination logical IPv4 |
| 24 | 2 | Payload length, 0..4096 |
| 26 | variable | Payload |
| 26 + payload length | 32 | HMAC-SHA256 over header + payload |

Maximum encoded packet size is 4,154 bytes. HMAC replaces a separate noncryptographic checksum, covering accidental corruption as well as unauthenticated modification. Comparison uses `CRYPTO_memcmp`. A router decrements TTL and recomputes the HMAC before forwarding. A local destination accepts TTL=1; a transit router drops TTL<=1.

| Type | Value | Behavior |
|---|---:|---|
| DATA | 1 | Endpoint returns ACK with `received: ` and the payload |
| PING | 2 | Endpoint returns PONG |
| PONG | 3 | Correlated request response |
| DISCOVERY | 4 | Configured neighbor announcement: ID, role, port |
| ROUTE_UPDATE | 5 | Reserved; tables currently use the control pipe |
| HEARTBEAT | 6 | One-way periodic peer heartbeat; both peers send independently |
| DNS_QUERY | 7 | UTF-8 hostname |
| DNS_RESPONSE | 8 | `address ttl_seconds`, `NXDOMAIN` or service error |
| HTTP_REQUEST | 9 | UTF-8 `GET /path` |
| HTTP_RESPONSE | 10 | HTTP-like status/headers/body text |
| ERROR | 11 | Reserved; errors currently use structured observation events |
| ACK | 12 | DATA acknowledgment |

CLI/API requests have TTL 1..64; replies use TTL 32. Request IDs start at a random 40-bit seed and increase, unique within a controller session, not globally persistent identifiers. Peer heartbeat IDs are zero and are excluded from request correlation.

The receiver rejects incorrect magic/version/type/reserved bits, zero TTL, oversized/short/length-mismatched packets and invalid HMACs. UDP invalid packets produce an `invalid` event. TCP also enforces frame bounds and incomplete-frame timeouts. Unknown routes, endpoint transit, TTL expiry and injected loss produce `drop` events. The sender eventually receives a timeout if no response or observed drop arrives.

HMAC is shared by all session members. It is not TLS, identity-isolated authentication, encryption or replay protection. Services do not implement real DNS resource record encoding, TCP congestion control from scratch, ICMP traceroute, HTTP cookies/TLS/streaming, fragmentation, or arbitrary Internet access.
