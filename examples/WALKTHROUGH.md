# Ten-minute OpenNet lab

1. Start `make demo`; open http://localhost:3000.
2. Choose PING in the packet console, destination `server.local`, and Send.
3. Inspect the successful response and click Router 1 to see its routing table.
4. Send a request with TTL 1. Observe the TTL-expired drop at Router 1.
5. Choose DNS query, destination `server.local`. First request traverses the network; subsequent requests within 30 seconds use the per-source cache.
6. Choose HTTP GET, destination `server.local`, path `/`. Read the server's actual response.
7. Kill Router 2 using its control button. Watch ACTIVE → SUSPECTED → FAILED and route changes.
8. Send another ping after recovery. Observe Router 3 carrying the request.
9. Restart Router 2. The cheaper route becomes available after neighbor heartbeats recover.
10. Run `python3 scripts/experiment.py recovery` from a second terminal, then examine the generated CSV/JSON reports.

For an intentional disconnected destination, kill Router 2 and query `node-b`. Node B has no alternate link in this demo. The network must report failure, not invent a path.
