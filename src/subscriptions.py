"""Pure renderers. No network requests and no third-party subscription converter."""
import base64
import ipaddress
import json
import re
import uuid
from urllib.parse import quote, urlencode

FORMATS = ('stash', 'clashmeta', 'shadowrocket', 'fancyss')


def hostname(value):
    if not isinstance(value, str) or len(value) > 253:
        raise ValueError('Invalid hostname')
    labels = value.split('.')
    if len(labels) < 2 or any(not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?', x) for x in labels):
        raise ValueError('Use a DNS hostname without scheme, port or path')
    return value.lower()


def port(value):
    if type(value) is not int or not 1 <= value <= 65535:
        raise ValueError('Invalid port')
    return value


def node(value):
    n = dict(value)
    ip = ipaddress.ip_address(n['server'])
    n['server'] = str(ip)
    n['port'] = port(n['port'])
    n['sni'] = hostname(n['sni'])
    n['uuid'] = str(uuid.UUID(n['uuid']))
    if not isinstance(n['name'], str) or not 1 <= len(n['name']) <= 80 or any(ord(c) < 32 for c in n['name']):
        raise ValueError('Invalid node name')
    if not re.fullmatch(r'[A-Za-z0-9_-]{43}', n['public_key']):
        raise ValueError('Invalid REALITY public key')
    if not re.fullmatch(r'(?:[0-9a-f]{2}){1,8}', n['short_id']):
        raise ValueError('Invalid short ID')
    return n


def subscription(nodes, fmt):
    if fmt not in FORMATS or not nodes or len(nodes) > 32:
        raise ValueError('Invalid format or node count')
    nodes = [node(n) for n in nodes]
    names = [n['name'] for n in nodes]
    if len(set(names)) != len(names) or any(x in ('PROXY', 'DIRECT', 'REJECT') for x in names):
        raise ValueError('Node names must be unique and not reserved')
    uris, proxies, direct = [], [], []
    for n in nodes:
        ip = ipaddress.ip_address(n['server'])
        address = '[' + str(ip) + ']' if ip.version == 6 else str(ip)
        query = urlencode(dict(encryption='none', security='reality', sni=n['sni'], fp='chrome',
                               pbk=n['public_key'], sid=n['short_id'], type='tcp', flow='xtls-rprx-vision'))
        uris.append(f"vless://{n['uuid']}@{address}:{n['port']}?{query}#{quote(n['name'], safe='')}")
        p = dict(name=n['name'], type='vless', server=n['server'], port=n['port'], uuid=n['uuid'],
                 network='tcp', tls=True, udp=True, flow='xtls-rprx-vision')
        p.update({'client-fingerprint': 'chrome', 'reality-opts': {'public-key': n['public_key'], 'short-id': n['short_id']}})
        p['sni' if fmt == 'stash' else 'servername'] = n['sni']
        proxies.append(p)
        direct.append(f"{'IP-CIDR6' if ip.version == 6 else 'IP-CIDR'},{ip}/{ip.max_prefixlen},DIRECT,no-resolve")
    if fmt in ('shadowrocket', 'fancyss'):
        return base64.b64encode(('\n'.join(uris) + '\n').encode()).decode() + '\n'
    # JSON flow objects are valid YAML, avoiding a runtime YAML dependency.
    lines = ['mixed-port: 7890', 'allow-lan: false', 'mode: rule', 'log-level: warning', 'ipv6: true', 'proxies:']
    lines += ['  - ' + json.dumps(p, ensure_ascii=False) for p in proxies]
    lines += ['proxy-groups:', '  - ' + json.dumps({'name': 'PROXY', 'type': 'select', 'proxies': names + ['DIRECT']}, ensure_ascii=False), 'rules:']
    rules = direct + ['IP-CIDR,127.0.0.0/8,DIRECT,no-resolve', 'IP-CIDR,10.0.0.0/8,DIRECT,no-resolve',
                      'IP-CIDR,172.16.0.0/12,DIRECT,no-resolve', 'IP-CIDR,192.168.0.0/16,DIRECT,no-resolve',
                      'IP-CIDR6,::1/128,DIRECT,no-resolve', 'IP-CIDR6,fc00::/7,DIRECT,no-resolve',
                      'DOMAIN-SUFFIX,local,DIRECT', 'GEOIP,CN,DIRECT', 'MATCH,PROXY']
    return '\n'.join(lines + ['  - ' + json.dumps(r) for r in rules]) + '\n'


def xray_config(n, private_key):
    n = node(n)
    if not re.fullmatch(r'[A-Za-z0-9_-]{43}', private_key):
        raise ValueError('Invalid REALITY private key')
    return {'log': {'loglevel': 'warning'}, 'inbounds': [{
        'tag': 'vless-reality', 'listen': '0.0.0.0', 'port': n['port'], 'protocol': 'vless',
        'settings': {'clients': [{'id': n['uuid'], 'flow': 'xtls-rprx-vision'}], 'decryption': 'none'},
        'streamSettings': {'network': 'tcp', 'security': 'reality', 'realitySettings': {
            'show': False, 'dest': n['sni'] + ':443', 'xver': 0, 'serverNames': [n['sni']],
            'privateKey': private_key, 'shortIds': [n['short_id']]}}
    }], 'outbounds': [{'protocol': 'freedom', 'tag': 'direct'}]}


def nginx_config(domain, https_port, token):
    domain = hostname(domain)
    port(https_port)
    if not re.fullmatch(r'[A-Za-z0-9_-]{43}', token):
        raise ValueError('Invalid subscription token')
    locations = '\n'.join(f'''    location = /sub/{token}/{fmt} {{
        alias /var/lib/xray-subscription/current/{fmt};
        default_type text/plain;
        add_header Cache-Control "no-store" always;
        add_header profile-update-interval "24";
    }}''' for fmt in FORMATS)
    return f'''server {{
    listen 80;
    server_name {domain};
    access_log off;
    error_log /var/log/nginx/xray-subscription-error.log crit;
    location /.well-known/acme-challenge/ {{ root /var/www/html; }}
    location / {{ return 404; }}
}}
server {{
    listen {https_port} ssl;
    server_name {domain};
    ssl_certificate /etc/letsencrypt/live/{domain}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/{domain}/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    server_tokens off;
    access_log off;
    error_log /var/log/nginx/xray-subscription-error.log crit;
    autoindex off;
{locations}
    location / {{ return 404; }}
}}
'''
