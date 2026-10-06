#!/usr/bin/env python3
"""Real request measurements, exported as JSON and CSV. Run after make demo."""
import argparse
import concurrent.futures
import csv
import json
import math
import statistics
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from apps.cli import call


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('experiment',choices=['latency','throughput','loss','recovery'])
    p.add_argument('--target',default='server.local')
    p.add_argument('--count',type=int,default=50)
    p.add_argument('--concurrency',type=int,default=4)
    p.add_argument('--router',default='router-2')
    p.add_argument('--loss',type=float,default=.2)
    p.add_argument('--out',default='reports')
    args=p.parse_args()
    if not 1<=args.count<=10000 or not 1<=args.concurrency<=16 or not 0<=args.loss<=1:
        p.error('count 1..10000, concurrency 1..16, loss 0..1')
    initial=call();rows=[]
    start=time.perf_counter()
    modified=False
    def measure(i):
        t=time.perf_counter()
        r=call('/api/request',{'kind':'send' if args.experiment=='throughput' else 'ping','target':args.target,'payload':'x'*1000 if args.experiment=='throughput' else ''})
        return {'request':i,'ok':r['ok'],'rtt_ms':r['rtt_ms'],'wall_ms':(time.perf_counter()-t)*1000,'error':r.get('error',''),'request_payload_bytes':1000 if args.experiment=='throughput' else 0}
    recovery=None
    try:
        if args.experiment=='recovery':
            baseline=measure(0)
            if not baseline['ok']:raise RuntimeError('baseline request failed')
            call('/api/fault',{'node':args.router,'action':'kill'});modified=True
            killed=time.perf_counter();detected=None
            while time.perf_counter()-killed<15:
                snapshot=call()
                if next(n for n in snapshot['nodes'] if n['id']==args.router)['status']=='FAILED':
                    detected=time.perf_counter();break
                time.sleep(.1)
            if detected is None:raise RuntimeError('failure was not detected in 15 seconds')
            row=measure(1);rows.append(row)
            recovery={'detection_ms':(detected-killed)*1000,'first_success_after_detection_ms':(time.perf_counter()-killed)*1000 if row['ok'] else None,'baseline_rtt_ms':baseline['rtt_ms'],'routes_after_failure':call()['routes']}
        else:
            if args.experiment=='loss':
                call('/api/fault',{'node':args.router,'action':'impair','loss':args.loss});modified=True
            if args.experiment=='throughput':
                with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:rows=list(pool.map(measure,range(args.count)))
            else:
                rows=[measure(i) for i in range(args.count)]
    finally:
        if modified:
            call('/api/fault',{'node':args.router,'action':'restart' if args.experiment=='recovery' else 'impair'})
    elapsed=time.perf_counter()-start
    latencies=[r['rtt_ms'] for r in rows if r['ok']]
    summary={'experiment':args.experiment,'transport':initial['transport'],'elapsed_s':elapsed,'requests':len(rows),'successful':len(latencies),'failed':len(rows)-len(latencies),'success_fraction':len(latencies)/len(rows) if rows else 0,'completed_requests_per_s':len(latencies)/elapsed,'mean_rtt_ms':statistics.mean(latencies) if latencies else None,'median_rtt_ms':statistics.median(latencies) if latencies else None,'p95_rtt_ms':sorted(latencies)[max(0,math.ceil(len(latencies)*.95)-1)] if latencies else None,'acknowledged_request_payload_bytes_per_s':sum(r['request_payload_bytes'] for r in rows if r['ok'])/elapsed,'recovery':recovery,'notes':'Application-level requests, includes controller/IPC overhead. TCP opens a connection per hop. Not link capacity or a congestion model. No automatic retries.'}
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    stamp=time.strftime('%Y%m%d-%H%M%S')
    path=out/f'{args.experiment}-{stamp}'
    path.with_suffix('.json').write_text(json.dumps({'summary':summary,'measurements':rows,'initial_topology':initial['links']},indent=2))
    with path.with_suffix('.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['request','ok','rtt_ms','wall_ms','error','request_payload_bytes']);writer.writeheader();writer.writerows(rows)
    print(json.dumps(summary,indent=2));print('Reports:',path.with_suffix('.json'),path.with_suffix('.csv'))


if __name__=='__main__':
    try:main()
    except (RuntimeError,ValueError,OSError) as exc:raise SystemExit('Experiment: '+str(exc))
