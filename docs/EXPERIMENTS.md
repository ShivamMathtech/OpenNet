# Measured experiments

Start `make demo` first. Run experiments in a second terminal from the project folder. Every measurement sends real application packets and waits for a reply or an observed failure. No performance numbers are hard-coded.

```bash
python3 scripts/experiment.py latency --target server.local --count 100
python3 scripts/experiment.py throughput --count 200 --concurrency 8
python3 scripts/experiment.py loss --router router-2 --loss 0.2 --count 100
python3 scripts/experiment.py recovery --router router-2
```

Each run writes one JSON report (summary + samples + initial links) and one CSV with individual measurements. Use `--out PATH` to choose a directory.

- **Latency:** sequential ping round trips. Compare `--target router-1`, `router-2`, `server` to vary path length. All share the local host's scheduler.
- **Throughput:** concurrent, acknowledged, 1,000-byte request messages; reports successful requests/s and acknowledged request payload bytes/s. This includes controller, API and logging overhead; it is not raw socket or link capacity. Replies and protocol overhead are not counted in useful payload throughput.
- **Loss:** inject independent random drops at every application forwarding operation on the selected router, including replies. An end-to-end failure ratio need not equal the configured probability. Make sure that router lies on the measured path. Loss is reset in a `finally` block if the script exits normally or through a handled exception.
- **Recovery:** verify baseline connectivity, kill the router, wait until FAILED is observed, then measure a request on the recovered route. Reported detection time uses a 100ms polling interval. Time to first success is measured after waiting for FAILED; it is an upper bound, not the earliest possible recovery time. Restart is requested in cleanup. The next experiment should wait for ACTIVE state.

The per-request API RTT uses a monotonic clock around command dispatch and controller observation of a response. Overall experiment elapsed time includes control API overhead, trace draining, fault setup and restoration requests. A 20ms trace-drain interval is excluded from RTT but included in overall experiment wall time.

To compare UDP/TCP, stop the current demo and run `./opennet start --config configs/tcp.json`. To compare static/dynamic routing, use `configs/static.json` and repeat a router kill; static mode deliberately does not choose the alternate path. Save reports separately and compare success fraction and recovery behavior.

For different topologies, copy `configs/demo.json`, alter the nodes/links/positive costs, start with `--config`, then rerun the same workload. Keep transport, packet sizes, hardware, OS and sample counts fixed for fair comparisons. Delay injection blocks the event loop rather than modeling a bandwidth-limited link. Do not label this a congestion simulator or use these figures as published research results without a rigorous experimental design.
