"""Validated topology and deterministic, weighted shortest-path routing."""
import heapq
import ipaddress
import json
import math
import re
from pathlib import Path


def load(path):
    config = json.loads(Path(path).read_text())
    nodes = config.get('nodes', [])
    if not isinstance(nodes, list) or not 2 <= len(nodes) <= 100:
        raise ValueError('topology must have between 2 and 100 nodes')
    ids, addresses, ports, names = set(), set(), set(), set()
    for node in nodes:
        ident = node['id']
        if not re.fullmatch(r'[a-zA-Z0-9_-]{1,40}', ident) or ident in ids:
            raise ValueError('invalid or duplicate node ID')
        ipaddress.IPv4Address(node['address'])
        ipaddress.IPv4Address(node.get('host', '127.0.0.1'))
        port = node['port']
        if type(port) is not int or not 1024 <= port <= 65535:
            raise ValueError('node port must be an integer between 1024 and 65535')
        endpoint = (node.get('host', '127.0.0.1'), port)
        if endpoint in ports or node['address'] in addresses:
            raise ValueError('duplicate address or endpoint')
        if node['role'] not in ('node', 'router', 'dns', 'server'):
            raise ValueError('invalid node role')
        name = node.get('hostname', ident + '.local')
        if not re.fullmatch(r'[a-zA-Z0-9.-]{1,80}', name) or name in names:
            raise ValueError('invalid or duplicate hostname')
        node['hostname'] = name
        node.setdefault('host', '127.0.0.1')
        names.add(name); ids.add(ident); addresses.add(node['address']); ports.add(endpoint)
    seen = set()
    links = config.get('links', [])
    for link in links:
        a, b = link['source'], link['target']
        key = tuple(sorted((a, b)))
        cost = link.get('cost', 1)
        if a not in ids or b not in ids or a == b or key in seen:
            raise ValueError('invalid or duplicate link')
        if isinstance(cost, bool) or not isinstance(cost, (float, int)) or not math.isfinite(cost) or cost <= 0:
            raise ValueError('link cost must be finite and positive')
        link['cost'] = cost
        seen.add(key)
    config.setdefault('source', nodes[0]['id'])
    if config['source'] not in ids:
        raise ValueError('unknown source node')
    if config.get('transport', 'udp') not in ('udp', 'tcp'):
        raise ValueError('transport must be udp or tcp')
    if config.get('routing_mode', 'dynamic') not in ('dynamic', 'static'):
        raise ValueError('routing_mode must be dynamic or static')
    if config.get('routing_mode') == 'static':
        tables = config.get('static_routes')
        if not isinstance(tables, dict) or set(tables) != ids:
            raise ValueError('static_routes must contain a table for every node')
        roles = {n['id']:n['role'] for n in nodes}
        for src, table in tables.items():
            for dst, path in table.items():
                if dst not in ids or not isinstance(path,list) or not path or path[0]!=src or path[-1]!=dst or len(path)!=len(set(path)):
                    raise ValueError('invalid static route path')
                if any(n not in ids for n in path) or any(roles[n]!='router' for n in path[1:-1]):
                    raise ValueError('static transit hops must be routers')
                if any(tuple(sorted((a,b))) not in seen for a,b in zip(path,path[1:])):
                    raise ValueError('static route uses a nonexistent link')
        for src, table in tables.items():
            for dst,path in table.items():
                for i,hop in enumerate(path[1:-1],1):
                    if tables[hop].get(dst) != path[i:]:
                        raise ValueError('static routing tables must agree at every hop')
    return config


def shortest_paths(nodes, links, source, unavailable=(), blocked=()):
    graph = {n['id']: [] for n in nodes}
    roles = {n['id']: n['role'] for n in nodes}
    for link in links:
        a, b = link['source'], link['target']
        if a in unavailable or b in unavailable or tuple(sorted((a,b))) in blocked:
            continue
        graph[a].append((b, link['cost']))
        graph[b].append((a, link['cost']))
    if source in unavailable:
        return {}
    dist, paths, queue = {source: 0}, {source: [source]}, [(0, source)]
    while queue:
        cost, node = heapq.heappop(queue)
        if cost != dist[node] or (node != source and roles[node] != 'router'):
            continue
        for peer, weight in graph[node]:
            new = cost + weight
            if new < dist.get(peer, float('inf')):
                dist[peer], paths[peer] = new, paths[node] + [peer]
                heapq.heappush(queue, (new, peer))
    return paths
