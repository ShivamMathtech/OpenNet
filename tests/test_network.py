import json
import socket
import tempfile
import time
import unittest
from pathlib import Path
from controller.network import Network, ROOT
from controller.topology import load, shortest_paths


def wait_for(predicate,timeout=8):
    until=time.monotonic()+timeout
    while time.monotonic()<until:
        if predicate():return
        time.sleep(.05)
    raise AssertionError('timed out waiting for condition')


class RoutingTests(unittest.TestCase):
    def test_shortest_and_alternate(self):
        config=load(ROOT/'configs/demo.json')
        paths=shortest_paths(config['nodes'],config['links'],'node-a')
        self.assertEqual(paths['server'],['node-a','router-1','router-2','server'])
        paths=shortest_paths(config['nodes'],config['links'],'node-a',{'router-2'})
        self.assertEqual(paths['server'],['node-a','router-1','router-3','server'])
        self.assertNotIn('node-b',paths)

    def test_endpoints_cannot_route(self):
        nodes=[{'id':'a','role':'node'},{'id':'b','role':'server'},{'id':'c','role':'node'}]
        paths=shortest_paths(nodes,[{'source':'a','target':'b','cost':1},{'source':'b','target':'c','cost':1}],'a')
        self.assertNotIn('c',paths)

    def test_duplicate_address_rejected(self):
        cfg=json.loads((ROOT/'configs/demo.json').read_text())
        cfg['nodes'][1]['address']=cfg['nodes'][0]['address']
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'bad.json';p.write_text(json.dumps(cfg))
            with self.assertRaises(ValueError):load(p)


class UDPIntegration(unittest.TestCase):
    transport='udp'
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        cfg=json.loads((ROOT/getattr(cls,'config_name','configs/demo.json')).read_text())
        cfg['transport']=cls.transport
        # Reserve both transport ports while selecting test endpoints.
        held=[]
        try:
            for n in cfg['nodes']:
                while True:
                    tcp=socket.socket();tcp.bind(('127.0.0.1',0));port=tcp.getsockname()[1]
                    udp=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
                    try:udp.bind(('127.0.0.1',port));break
                    except OSError:tcp.close();udp.close()
                held.extend([tcp,udp]);n['port']=port
            path=Path(cls.tmp.name)/'test.json';path.write_text(json.dumps(cfg))
        finally:
            for sock in held:sock.close()
        cls.network=Network(path,Path(cls.tmp.name)/'runtime');cls.network.start()

    @classmethod
    def tearDownClass(cls):
        cls.network.close();cls.tmp.cleanup()

    def test_01_ping_real_hops(self):
        result=self.network.request('ping','server')
        self.assertTrue(result['ok'],result)
        hops=[e['node'] for e in result['trace'] if e['event']=='receive' and e['type']==2]
        self.assertEqual(hops,['router-1','router-2','server'])

    def test_02_self_ping(self):
        self.assertTrue(self.network.request('ping','node-a')['ok'])

    def test_02_dns_http_and_data(self):
        self.assertEqual(self.network.resolve('server.local')['address'],'10.0.0.50')
        self.assertTrue(self.network.resolve('server.local')['cached'])
        self.assertFalse(self.network.resolve('missing.local')['ok'])
        result=self.network.http('server.local')
        self.assertTrue(result['ok'],result)
        self.assertIn('200 OK',result['payload'])
        self.assertIn('Hello from OpenNet',result['payload'])
        self.assertIn('404 Not Found',self.network.http('server.local','/missing')['payload'])
        result=self.network.request('send','node-b',payload='hello from test')
        self.assertTrue(result['ok'],result)
        self.assertEqual(result['payload'],'received: hello from test')

    def test_03_ttl_and_faults(self):
        result=self.network.request('ping','server',ttl=1)
        self.assertFalse(result['ok']);self.assertIn('TTL',result['error'])
        self.network.fault('router-1','impair',loss=1)
        try:
            result=self.network.request('ping','server')
            self.assertFalse(result['ok']);self.assertIn('injected loss',result['error'])
        finally:self.network.fault('router-1','impair')

    def test_04_link_reroute(self):
        self.network.link('router-1','router-2',False)
        try:
            result=self.network.request('ping','server');self.assertTrue(result['ok'],result)
            self.assertIn('router-3',[e['node'] for e in result['trace']])
        finally:self.network.link('router-1','router-2',True)

    def test_05_kill_detect_recover_restart(self):
        self.network.fault('router-2','kill')
        wait_for(lambda:self.network.nodes['router-2']['status']=='FAILED')
        result=self.network.http('server.local');self.assertTrue(result['ok'],result)
        self.assertIn('router-3',[e['node'] for e in result['trace']])
        self.assertNotIn('router-2',[e['node'] for e in result['trace']])
        self.network.fault('router-2','restart')
        wait_for(lambda:self.network.nodes['router-2']['status']=='ACTIVE' and self.network.routes['node-a'].get('server')==['node-a','router-1','router-2','server'])
        self.assertTrue(self.network.request('ping','server')['ok'])

    def test_06_invalid_datagram_survives(self):
        before=self.network.event_seq
        n=self.network.nodes['router-1']
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as s:s.sendto(b'not-an-opennet-packet',(n['host'],n['port']))
        wait_for(lambda:any(e['event']=='invalid' and e['event_seq']>before for e in list(self.network.events)))
        self.assertTrue(self.network.request('ping','server')['ok'])


class TCPIntegration(UDPIntegration):
    transport='tcp'

    def test_07_fragmented_tcp_frame(self):
        import hashlib
        import hmac
        import struct
        ident=987654321
        header=struct.pack('!4sBBBBQIIH',b'ONET',1,2,16,0,ident,int.from_bytes(socket.inet_aton('10.0.0.1'),'big'),int.from_bytes(socket.inet_aton('10.0.0.50'),'big'),4)
        payload=header+b'test'
        packet=payload+hmac.new(self.network.key.encode(),payload,hashlib.sha256).digest()
        frame=struct.pack('!I',len(packet))+packet
        target=self.network.nodes['server']
        with socket.create_connection((target['host'],target['port'])) as sock:
            for i in range(0,len(frame),7):
                sock.sendall(frame[i:i+7]);time.sleep(.001)
        wait_for(lambda:any(e.get('id')==str(ident) and e['event']=='deliver' and e['node']=='server' for e in list(self.network.events)))
        self.assertTrue(self.network.request('ping','server')['ok'])


class StaticIntegration(unittest.TestCase):
    transport='udp'
    config_name='configs/static.json'
    @classmethod
    def setUpClass(cls):UDPIntegration.setUpClass.__func__(cls)
    @classmethod
    def tearDownClass(cls):UDPIntegration.tearDownClass.__func__(cls)
    def test_static_routes_do_not_failover(self):
        self.assertTrue(self.network.request('ping','server')['ok'])
        self.network.fault('router-2','kill')
        wait_for(lambda:self.network.nodes['router-2']['status']=='FAILED')
        self.assertEqual(self.network.routes['node-a']['server'],['node-a','router-1','router-2','server'])
        self.assertFalse(self.network.request('ping','server',timeout=.5)['ok'])



if __name__=='__main__':unittest.main(verbosity=2)
