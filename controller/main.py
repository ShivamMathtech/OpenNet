import argparse
import fcntl
import json
import signal
import threading
from .network import Network, ROOT
from .api import Server


def main():
    parser=argparse.ArgumentParser(description='OpenNet controller + dashboard')
    parser.add_argument('--config',default=str(ROOT/'configs/demo.json'))
    parser.add_argument('--port',type=int,default=3000)
    parser.add_argument('--bind',default='127.0.0.1')
    args=parser.parse_args()
    runtime=ROOT/'.runtime';runtime.mkdir(exist_ok=True)
    with (runtime/'controller.lock').open('w') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:parser.exit(1,'OpenNet is already running in this folder.\n')
        network=Network(args.config)
        server=None
        try:
            server=Server((args.bind,args.port),network)
            network.start()
            (runtime/'session.json').write_text(json.dumps({'url':f'http://127.0.0.1:{args.port}','token':server.token}))
            (runtime/'session.json').chmod(0o600)
            def stop(*_):threading.Thread(target=server.shutdown,daemon=True).start()
            signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
            print(f'OpenNet running: http://localhost:{args.port} | {len(network.nodes)} processes | Ctrl+C to stop',flush=True)
            server.serve_forever(poll_interval=.2)
        finally:
            network.close()
            if server:server.server_close()
            (runtime/'session.json').unlink(missing_ok=True)


if __name__=='__main__':
    try:main()
    except (OSError,ValueError,RuntimeError) as exc:raise SystemExit('OpenNet: '+str(exc))
