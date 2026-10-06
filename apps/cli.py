"""CLI client for the local authenticated controller API."""
import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[1]


def call(path='/api/state',data=None):
    try:
        session=json.loads((ROOT/'.runtime/session.json').read_text())
    except (FileNotFoundError,json.JSONDecodeError) as exc:
        raise RuntimeError('OpenNet is not running. Start it in another terminal: ./opennet start') from exc
    headers={'Content-Type':'application/json','X-OpenNet-Token':session['token']}
    request=urllib.request.Request(session['url']+path, json.dumps(data).encode() if data is not None else None,headers)
    try:
        with urllib.request.urlopen(request,timeout=15) as response:return json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(exc.read().decode()) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError('Cannot reach controller; start OpenNet first') from exc


def main():
    p=argparse.ArgumentParser(prog='opennet',description='Build the Internet From First Principles')
    sub=p.add_subparsers(dest='command',required=True)
    start=sub.add_parser('start');start.add_argument('--config',default=str(ROOT/'configs/demo.json'));start.add_argument('--port',type=int,default=3000);start.add_argument('--bind',default='127.0.0.1')
    for name in ('stop','status','nodes','routes','topology','metrics'):
        sub.add_parser(name)
    logs=sub.add_parser('logs');logs.add_argument('--node')
    for name in ('ping','traceroute','send'):
        a=sub.add_parser(name);a.add_argument('target');a.add_argument('--source');a.add_argument('--ttl',type=int,default=16)
        if name=='send':a.add_argument('message')
    dns=sub.add_parser('dns');dns.add_argument('operation',choices=['resolve']);dns.add_argument('hostname');dns.add_argument('--source')
    curl=sub.add_parser('curl');curl.add_argument('url');curl.add_argument('--source')
    fault=sub.add_parser('fault');fault.add_argument('action',choices=['kill','stop','restart','impair']);fault.add_argument('node');fault.add_argument('--loss',type=float,default=0);fault.add_argument('--delay-ms',type=int,default=0)
    link=sub.add_parser('link');link.add_argument('action',choices=['up','down']);link.add_argument('source');link.add_argument('target')
    args=p.parse_args()
    if args.command=='start':
        import os
        config_path=str(Path(args.config).resolve())
        os.chdir(ROOT)
        os.execv(sys.executable,[sys.executable,'-m','controller.main','--config',config_path,'--port',str(args.port),'--bind',args.bind])
    elif args.command=='stop':result=call('/api/stop',{})
    elif args.command in ('ping','traceroute','send'):
        result=call('/api/request',{'kind':args.command,'target':args.target,'source':args.source,'ttl':args.ttl,'payload':getattr(args,'message','')})
    elif args.command=='dns':result=call('/api/request',{'kind':'dns','target':args.hostname,'source':args.source})
    elif args.command=='curl':
        url=urlsplit(args.url)
        if url.scheme!='http' or not url.hostname or url.port not in (None,80):raise ValueError('use http://hostname/path (overlay service has no public TCP port)')
        result=call('/api/request',{'kind':'http','target':url.hostname,'path':url.path or '/','source':args.source})
    elif args.command=='fault':result=call('/api/fault',{'node':args.node,'action':args.action,'loss':args.loss,'delay_ms':args.delay_ms})
    elif args.command=='link':result=call('/api/link',{'source':args.source,'target':args.target,'enabled':args.action=='up'})
    else:
        state=call()
        key={'status':'nodes','nodes':'nodes','routes':'routes','metrics':'metrics','logs':'events'}.get(args.command)
        result=state.get(key,state)
        if args.command=='logs' and args.node:result=[e for e in result if e.get('node')==args.node]
    if args.command=='curl' and result.get('ok'):
        print(result['payload'])
    elif args.command=='traceroute' and result.get('ok'):
        print('Observed forward-path receive events (timestamps from local process clocks):')
        events=sorted((e for e in result['trace'] if e['event']=='receive' and e['type']==2),key=lambda e:e['time_ms'])
        print('0  '+result['source'])
        for i,e in enumerate(events,1):print(f"{i}  {e['node']}  TTL={e['ttl']}")
        print(f"Round-trip: {result['rtt_ms']:.3f} ms")
    else:print(json.dumps(result,indent=2))
    if isinstance(result,dict) and result.get('ok') is False:return 1
    return 0


if __name__=='__main__':
    try:sys.exit(main())
    except (ValueError,RuntimeError,OSError) as exc:print('OpenNet: '+str(exc),file=sys.stderr);sys.exit(1)
