"""Process supervision and control plane. Payloads never bypass the C++ routers."""
import collections
import json
import os
import secrets
import subprocess
import threading
import time
from pathlib import Path
from .topology import load, shortest_paths

ROOT = Path(__file__).resolve().parents[1]
REQUEST_TYPES = {'send': 1, 'ping': 2, 'traceroute': 2, 'dns': 7, 'http': 9}
REPLIES = {1: 12, 2: 3, 7: 8, 9: 10}


class Network:
    def __init__(self, config, runtime=None):
        self.config = load(config)
        self.nodes = {n['id']: dict(n, status='STOPPED') for n in self.config['nodes']}
        self.runtime = Path(runtime or ROOT / '.runtime')
        self.runtime.mkdir(parents=True, exist_ok=True)
        self.key = secrets.token_hex(32)
        self.lock = threading.RLock()
        self.procs, self.metrics, self.last, self.routes = {}, {}, {}, {}
        self.events = collections.deque(maxlen=1500)
        self.pending = {}
        self.cache = {}
        self.blocked = set()
        self.manual_blocks = set()
        self.seq = secrets.randbits(40)
        self.event_seq = 0
        self.closed = False
        self.start_time = time.monotonic()
        self.log = (self.runtime / 'events.jsonl').open('a', buffering=1)
        self.monitor = threading.Thread(target=self._monitor, daemon=True)
        self.totals = collections.Counter()
        self.recoveries = collections.deque(maxlen=100)

    def record(self, event):
        with self.lock:
            self.event_seq += 1
            event['event_seq'] = self.event_seq
            event.setdefault('time_ms', time.time() * 1000)
            self.events.append(event)
            self.log.write(json.dumps(event) + '\n')

    def start(self):
        if not (ROOT / 'build/opennet-node').exists():
            raise RuntimeError('Build the C++ engine first: bash scripts/build.sh')
        try:
            for node in self.nodes:
                self.spawn(node)
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                with self.lock:
                    if all(n['status'] == 'ACTIVE' for n in self.nodes.values()):
                        break
                    failed = [n for n,p in self.procs.items() if p.poll() is not None]
                if failed:
                    raise RuntimeError('Node startup failed: ' + ', '.join(failed) + '; inspect .runtime/*.stderr.log')
                time.sleep(.05)
            else:
                raise RuntimeError('Node startup timed out; inspect .runtime/*.stderr.log')
            with self.lock:
                self.recompute('startup')
            self.monitor.start()
        except BaseException:
            self.close()
            raise

    def spawn(self, ident):
        with self.lock:
            node = self.nodes[ident]
            if ident in self.procs and self.procs[ident].poll() is None:
                raise ValueError('node is already running')
            previous = self.procs.get(ident)
            if previous is not None:
                previous.wait()
                previous.stdin.close()
            peers = []
            for link in self.config['links']:
                if ident in (link['source'], link['target']):
                    other = self.nodes[link['target'] if link['source'] == ident else link['source']]
                    peers.append(f"peer {other['address']} {other['host']} {other['port']}")
            records = [f"record {n['hostname']} {n['address']}" for n in self.nodes.values()]
            path = self.runtime / f'{ident}.conf'
            path.write_text(f"{ident} {node['address']} {node['host']} {node['port']} {node['role']} {self.config.get('transport','udp')}\n" + '\n'.join(peers + records) + '\n')
            with (self.runtime / f'{ident}.stderr.log').open('a') as err:
                process = subprocess.Popen([str(ROOT / 'build/opennet-node'), str(path)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=err, text=True, bufsize=1, env=dict(os.environ, OPENNET_KEY=self.key))
            self.procs[ident] = process
            node['status'] = 'STARTING'
            node['pid'] = process.pid
            self.last[ident] = time.monotonic()
            threading.Thread(target=self._read, args=(ident,process), daemon=True).start()

    def _read(self, ident, process):
        try:
            for line in process.stdout:
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    self.record({'event':'log_error','node':ident,'detail':line[:200]})
                    continue
                with self.lock:
                    if self.closed or self.procs.get(ident) is not process:
                        break
                    if event['event'] in ('heartbeat', 'started'):
                        old = self.nodes[ident]['status']
                        self.last[ident] = time.monotonic()
                        self.nodes[ident]['status'] = 'ACTIVE'
                        if event['event'] == 'heartbeat':
                            self.metrics[ident] = {k:event[k] for k in ('sent','received','dropped','bytes_sent','bytes_received')}
                        if old in ('FAILED','SUSPECTED','STARTING') and self.routes:
                            self.recompute('node active: ' + ident)
                    if event['event'] in ('neighbor_down','neighbor_up'):
                        peer = next((n['id'] for n in self.nodes.values() if n['address']==event.get('detail')), None)
                        if peer:
                            edge = tuple(sorted((ident,peer)))
                            if event['event']=='neighbor_down':
                                self.blocked.add(edge)
                            else:
                                self.blocked.discard(edge)
                            self.recompute(event['event'] + ': ' + ident + ' / ' + peer)
                    self.record(event)
                    pending = self.pending.get(event.get('id'))
                    if pending is not None:
                        pending['trace'].append(event)
                        if event['event']=='deliver' and ident==pending['source'] and event['type']==pending['expected']:
                            pending['response'] = event
                            pending['completed_at'] = time.perf_counter()
                            pending['done'].set()
                        if event['event']=='drop':
                            pending['error'] = event['detail']
                            pending['done'].set()
        except (ValueError, OSError) as exc:
            if not self.closed:
                self.record({'event':'reader_error','node':ident,'detail':str(exc)})
        finally:
            process.stdout.close()

    def command(self, ident, text):
        with self.lock:
            p = self.procs.get(ident)
            if p is None or p.poll() is not None:
                raise ValueError('node is not running: ' + ident)
            try:
                p.stdin.write(text + '\n'); p.stdin.flush()
            except (BrokenPipeError, OSError) as exc:
                raise ValueError('node control pipe is closed: ' + ident) from exc

    def recompute(self, reason):
        start = time.perf_counter()
        unavailable = {i for i,n in self.nodes.items() if n['status'] != 'ACTIVE'}
        updated = {}
        for ident in self.nodes:
            paths = (self.config['static_routes'][ident] if self.config.get('routing_mode')=='static' else shortest_paths(list(self.nodes.values()), self.config['links'], ident, unavailable, self.blocked | self.manual_blocks))
            updated[ident] = paths
            if ident not in unavailable:
                pairs = [f"{self.nodes[dst]['address']} {self.nodes[path[1]]['address']}" for dst,path in paths.items() if len(path)>1]
                try:
                    self.command(ident, 'ROUTES ' + ' '.join(pairs))
                except ValueError as exc:
                    self.record({'event':'route_install_error','node':ident,'detail':str(exc)})
        if updated != self.routes:
            recovery = {'event':'route_change','detail':reason,'old_routes':self.routes,'new_routes':updated,'compute_and_dispatch_ms':(time.perf_counter()-start)*1000}
            self.routes = updated
            self.recoveries.append(recovery)
            self.record(recovery)

    def _monitor(self):
        while not self.closed:
            time.sleep(.2)
            with self.lock:
                if self.closed:
                    break
                changed = False
                for ident,n in self.nodes.items():
                    age = time.monotonic() - self.last.get(ident,0)
                    old = n['status']
                    state = 'FAILED' if age>3.2 else ('SUSPECTED' if age>2 else old)
                    if state != old:
                        n['status']=state
                        self.record({'event':'node_status','node':ident,'detail':state,'heartbeat_age_s':age})
                        changed=True
                if changed:
                    self.recompute('heartbeat timeout')

    def lookup(self, target):
        for ident,n in self.nodes.items():
            if target in (ident,n['address'],n['hostname']):
                return ident
        raise ValueError('unknown destination: ' + target)

    def request(self, kind, target, source=None, payload='', ttl=16, timeout=4):
        if kind not in REQUEST_TYPES:
            raise ValueError('unknown request kind')
        if not isinstance(payload,str) or len(payload.encode())>4000:
            raise ValueError('payload must be text of at most 4000 UTF-8 bytes')
        if type(ttl) is not int or not 1<=ttl<=64:
            raise ValueError('TTL must be between 1 and 64')
        source = self.lookup(source or self.config['source'])
        target = self.lookup(target)
        with self.lock:
            if self.nodes[source]['status'] != 'ACTIVE':
                raise ValueError('source is not active')
            if len(self.pending)>=64:
                raise ValueError('too many concurrent requests')
            self.seq += 1
            seq = str(self.seq)
            packet_type = REQUEST_TYPES[kind]
            pending = {'done':threading.Event(), 'source':source, 'expected':REPLIES[packet_type], 'trace':[]}
            self.pending[seq] = pending
            self.totals['requests'] += 1
        start = time.perf_counter()
        try:
            self.command(source, f"SEND {seq} {packet_type} {self.nodes[target]['address']} {ttl} {payload.encode().hex() or '-'}")
            pending['done'].wait(timeout)
            completed_at = pending.get('completed_at', time.perf_counter())
            # Drain independently scheduled stdout readers; exclude this from RTT.
            time.sleep(.02)
            with self.lock:
                response = pending.get('response')
                ok = response is not None
                self.totals['successful' if ok else 'failed'] += 1
                result = {'ok':ok,'id':seq,'rtt_ms':(completed_at-start)*1000,'source':source,'target':target,'trace':sorted(pending['trace'], key=lambda e:e['time_ms'])}
                if response:
                    result['payload'] = bytes.fromhex(response['payload_hex']).decode(errors='replace')
                else:
                    result['error'] = pending.get('error','request timeout; no response through the overlay')
                return result
        finally:
            with self.lock:
                self.pending.pop(seq,None)

    def resolve(self, hostname, source=None):
        source = self.lookup(source or self.config['source'])
        cache_key = (source,hostname)
        with self.lock:
            cached = self.cache.get(cache_key)
            if cached and cached['expires']>time.monotonic():
                return dict(cached['result'], cached=True, ttl_s=round(cached['expires']-time.monotonic(),1))
        dns = next((n['id'] for n in self.nodes.values() if n['role']=='dns'),None)
        if not dns:
            raise ValueError('topology has no DNS node')
        result = self.request('dns',dns,source,hostname)
        if result['ok']:
            try:
                address, ttl = result['payload'].split()
                self.lookup(address)
                result.update(address=address,ttl_s=int(ttl),cached=False)
                with self.lock:
                    self.cache[cache_key] = {'expires':time.monotonic()+int(ttl),'result':result}
            except (ValueError,KeyError):
                result.update(ok=False,error='DNS resolution failed: '+result['payload'])
        return result

    def http(self, hostname, path='/', source=None):
        dns = self.resolve(hostname,source)
        if not dns['ok']:
            return dns
        result = self.request('http',dns['address'],source,'GET '+path)
        result['dns'] = dns
        return result

    def fault(self, ident, action, loss=0, delay_ms=0):
        ident = self.lookup(ident)
        with self.lock:
            if action in ('kill','stop'):
                p = self.procs.get(ident)
                if not p or p.poll() is not None:
                    raise ValueError('node is already stopped')
                p.kill() if action=='kill' else p.terminate()
                # Liveness changes only after observed heartbeat timeouts.
            elif action=='restart':
                self.spawn(ident)
            elif action=='impair':
                if isinstance(loss,bool) or not isinstance(loss,(int,float)) or not 0<=loss<=1 or type(delay_ms) is not int or not 0<=delay_ms<=500:
                    raise ValueError('loss must be 0..1; delay_ms must be integer 0..500')
                self.command(ident,f'FAULT {loss} {delay_ms}')
            else:
                raise ValueError('unknown fault action')
            self.record({'event':'fault','node':ident,'detail':action,'loss':loss,'delay_ms':delay_ms})
        return {'ok':True}

    def link(self, source, target, enabled):
        edge = tuple(sorted((self.lookup(source), self.lookup(target))))
        if not any(tuple(sorted((e['source'],e['target'])))==edge for e in self.config['links']):
            raise ValueError('unknown link')
        with self.lock:
            if enabled:
                self.manual_blocks.discard(edge)
            else:
                self.manual_blocks.add(edge)
            self.recompute('administrative link ' + ('up' if enabled else 'down'))
        return {'ok':True}

    def snapshot(self):
        with self.lock:
            nodes = []
            for i,n in self.nodes.items():
                resources = {}
                if self.procs.get(i) and self.procs[i].poll() is None:
                    try:
                        fields = Path(f"/proc/{n['pid']}/stat").read_text().rsplit(')',1)[1].split()
                        resources = {'cpu_time_s':(int(fields[11])+int(fields[12]))/os.sysconf('SC_CLK_TCK'), 'rss_bytes':int(fields[21])*os.sysconf('SC_PAGE_SIZE')}
                    except (OSError,ValueError,IndexError):
                        pass
                nodes.append(dict(n,heartbeat_age_s=round(time.monotonic()-self.last.get(i,time.monotonic()),2),metrics=dict(self.metrics.get(i,{}),**resources)))
            totals = dict(self.totals)
            totals.update({k:sum(m.get(k,0) for m in self.metrics.values()) for k in ('sent','received','dropped','bytes_sent','bytes_received')})
            return {'nodes':nodes,'links':[dict(e,enabled=tuple(sorted((e['source'],e['target']))) not in (self.blocked|self.manual_blocks)) for e in self.config['links']], 'routes':self.routes,'metrics':totals,'events':list(self.events)[-180:],'uptime_s':time.monotonic()-self.start_time,'transport':self.config.get('transport','udp'),'source':self.config['source'],'routing_mode':self.config.get('routing_mode','dynamic')}

    def close(self):
        with self.lock:
            if self.closed:
                return
            self.closed=True
            processes=list(self.procs.values())
        for p in processes:
            if p.poll() is None:
                p.terminate()
        for p in processes:
            try:
                p.wait(timeout=2)
            except subprocess.TimeoutExpired:
                p.kill();p.wait()
            if p.stdin:
                p.stdin.close()
        with self.lock:
            self.log.close()
