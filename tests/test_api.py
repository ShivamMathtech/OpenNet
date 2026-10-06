import base64
import http.client
import json
import os
import socket
import struct
import threading
import unittest
from controller.api import Server
import test_network as network_tests


class APITests(unittest.TestCase):
    transport='udp'
    @classmethod
    def setUpClass(cls):
        network_tests.UDPIntegration.setUpClass.__func__(cls)
        cls.server=Server(('127.0.0.1',0),cls.network)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join()
        network_tests.UDPIntegration.tearDownClass.__func__(cls)

    def request(self,path,body=None,token=True,host=None):
        conn=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=10)
        headers={'Content-Type':'application/json'}
        if token:headers['X-OpenNet-Token']=self.server.token
        if host:headers['Host']=host
        try:
            conn.request('POST' if body is not None else 'GET',path,json.dumps(body) if body is not None else None,headers)
            r=conn.getresponse();return r.status,r.read()
        finally:conn.close()

    def test_dashboard_and_state(self):
        status,body=self.request('/');self.assertEqual(status,200);self.assertIn(b'Live topology',body)
        status,body=self.request('/api/state');self.assertEqual(status,200);self.assertEqual(len(json.loads(body)['nodes']),7)
        self.assertEqual(self.request('/notfound')[0],404)

    def test_auth_validation_and_rebinding(self):
        self.assertEqual(self.request('/api/fault',{'node':'router-1','action':'kill'},False)[0],403)
        self.assertEqual(self.request('/api/state',host='evil.example')[0],403)
        self.assertEqual(self.request('/api/request',{'kind':'ping','target':'unknown'})[0],400)
        self.assertEqual(self.request('/api/request',{'kind':'ping','target':'server','ttl':0})[0],400)

    def test_real_http_overlay(self):
        status,body=self.request('/api/request',{'kind':'http','target':'server.local'})
        result=json.loads(body);self.assertEqual(status,200);self.assertTrue(result['ok']);self.assertIn('Hello from OpenNet',result['payload'])
        self.assertIn('router-2',[e['node'] for e in result['trace']])

    def test_websocket_frames_and_close(self):
        s=socket.create_connection(('127.0.0.1',self.server.server_port),timeout=5)
        f=s.makefile('rb')
        try:
            key=base64.b64encode(os.urandom(16)).decode()
            request=f'GET /ws?token={self.server.token} HTTP/1.1\r\nHost: 127.0.0.1:{self.server.server_port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Key: {key}\r\n\r\n'
            s.sendall(request.encode());self.assertIn(b'101',f.readline())
            while f.readline()!=b'\r\n':pass
            def read_frame():
                h=f.read(2);length=h[1]&127
                if length==126:length=struct.unpack('!H',f.read(2))[0]
                elif length==127:length=struct.unpack('!Q',f.read(8))[0]
                return h[0]&15,f.read(length)
            opcode,payload=read_frame();self.assertEqual(opcode,1);self.assertEqual(len(json.loads(payload)['nodes']),7)
            # Masked client close, no payload.
            s.sendall(b'\x88\x80abcd')
            opcode,_=read_frame();self.assertEqual(opcode,8)
        finally:f.close();s.close()
