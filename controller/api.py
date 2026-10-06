"""Dependency-free HTTP/1.1 control API and read-only WebSocket snapshots."""
import base64
import hashlib
import hmac
import json
import mimetypes
import secrets
import select
import socket
import struct
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit
from .network import ROOT


class Server(ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self, address, network):
        self.network = network
        self.token = secrets.token_urlsafe(32)
        super().__init__(address, Handler)


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    def log_message(self, *_):
        pass

    def json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header('Content-Type','application/json')
        self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.end_headers()
        self.wfile.write(body)

    def allowed_host(self):
        # Reject DNS rebinding. For container port mapping use the same internal/external port.
        return self.headers.get('Host','') in {f'localhost:{self.server.server_port}',f'127.0.0.1:{self.server.server_port}'}

    def do_GET(self):
        if not self.allowed_host():
            self.json({'error':'Host rejected: open localhost or 127.0.0.1'},403);return
        url = urlsplit(self.path)
        if url.path=='/api/session':
            self.json({'token':self.server.token});return
        if url.path=='/api/state':
            self.json(self.server.network.snapshot());return
        if url.path=='/ws':
            self.websocket(parse_qs(url.query).get('token',[''])[0]);return
        routes={'/':'index.html','/app.js':'app.js','/style.css':'style.css'}
        if url.path not in routes:
            self.json({'error':'not found'},404);return
        path=ROOT/'dashboard'/routes[url.path]
        body=path.read_bytes()
        self.send_response(200)
        self.send_header('Content-Type',mimetypes.guess_type(path)[0] or 'application/octet-stream')
        self.send_header('Content-Length',str(len(body)))
        self.send_header('Content-Security-Policy',"default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'")
        self.end_headers();self.wfile.write(body)

    def do_POST(self):
        if not self.allowed_host() or not hmac.compare_digest(self.headers.get('X-OpenNet-Token',''),self.server.token):
            self.json({'error':'invalid control token'},403);return
        if self.headers.get('Content-Type','').split(';')[0] != 'application/json':
            self.json({'error':'application/json required'},415);return
        try:
            size=int(self.headers.get('Content-Length','0'))
            if not 0<size<=16384:
                raise ValueError('request body must be 1..16384 bytes')
            self.connection.settimeout(6)
            data=json.loads(self.rfile.read(size))
            if not isinstance(data,dict):
                raise ValueError('JSON body must be an object')
            n=self.server.network
            if self.path=='/api/request':
                kind=data.get('kind','ping')
                if kind=='dns':result=n.resolve(data['target'],data.get('source'))
                elif kind=='http':result=n.http(data['target'],data.get('path','/'),data.get('source'))
                else:result=n.request(kind,data['target'],data.get('source'),data.get('payload',''),data.get('ttl',16))
            elif self.path=='/api/fault':
                result=n.fault(data['node'],data['action'],data.get('loss',0),data.get('delay_ms',0))
            elif self.path=='/api/link':
                if type(data.get('enabled')) is not bool:raise ValueError('enabled must be boolean')
                result=n.link(data['source'],data['target'],data['enabled'])
            elif self.path=='/api/stop':
                import threading
                threading.Thread(target=self.server.shutdown,daemon=True).start()
                result={'ok':True}
            else:
                self.json({'error':'not found'},404);return
            self.json(result)
        except (ValueError,KeyError,TypeError,OverflowError) as exc:
            self.json({'error':str(exc)},400)
        except (BrokenPipeError,ConnectionResetError,socket.timeout):
            self.close_connection=True
        except Exception as exc:
            self.server.network.record({'event':'api_error','detail':str(exc)})
            self.json({'error':'internal error; inspect events.jsonl'},500)

    def websocket(self, token):
        if not hmac.compare_digest(token,self.server.token):
            self.json({'error':'invalid token'},403);return
        if self.headers.get('Upgrade','').lower()!='websocket' or self.headers.get('Sec-WebSocket-Version')!='13':
            self.json({'error':'WebSocket version 13 required'},400);return
        key=self.headers.get('Sec-WebSocket-Key','')
        try:
            if len(base64.b64decode(key,validate=True))!=16:raise ValueError()
        except ValueError:
            self.json({'error':'invalid WebSocket key'},400);return
        accept=base64.b64encode(hashlib.sha1((key+'258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest()).decode()
        self.send_response(101)
        self.send_header('Upgrade','websocket');self.send_header('Connection','Upgrade');self.send_header('Sec-WebSocket-Accept',accept);self.end_headers()
        self.connection.settimeout(2)
        def frame(payload,opcode=1):
            length=len(payload)
            header=bytes([0x80|opcode])+(bytes([length]) if length<126 else (b'\x7e'+struct.pack('!H',length) if length<65536 else b'\x7f'+struct.pack('!Q',length)))
            self.connection.sendall(header+payload)
        def exact(n):
            output=b''
            while len(output)<n:
                part=self.connection.recv(n-len(output))
                if not part:raise ConnectionError()
                output+=part
            return output
        try:
            while not self.server.network.closed:
                frame(json.dumps(self.server.network.snapshot()).encode())
                if select.select([self.connection],[],[],.5)[0]:
                    header=exact(2);opcode=header[0]&15;length=header[1]&127
                    if not header[1]&128 or not header[0]&128 or length>125 or opcode not in (8,9,10):
                        frame(struct.pack('!H',1002),8);break
                    mask=exact(4);raw=exact(length);payload=bytes(b^mask[i%4] for i,b in enumerate(raw))
                    if opcode==8:
                        frame(payload,8);break
                    if opcode==9:frame(payload,10)
        except (OSError,ConnectionError):
            pass
        finally:
            self.close_connection=True
