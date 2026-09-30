#!/usr/bin/env python3
"""Fresh Ubuntu host installer; never imports an existing deployment."""
import argparse
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import uuid
import zipfile

from src.subscriptions import FORMATS, hostname, nginx_config, node, port, subscription, xray_config

ROOT = Path('/etc/xray-subscription')
WEB = Path('/var/lib/xray-subscription')
BIN = Path('/usr/local/bin/xray')
CONFIG = Path('/usr/local/etc/xray/config.json')
NGINX = Path('/etc/nginx/sites-available/xray-subscription')


def run(*args, **kwargs):
    return subprocess.run(args, check=True, text=True, **kwargs)


def write(path, text, mode=0o600):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')
    path.chmod(mode)


def settings(data):
    c = dict(data)
    c['domain'] = hostname(c['domain'])
    c['sni'] = hostname(c['sni'])
    # Initial installer binds IPv4; rendering additional nodes supports IPv6.
    c['server'] = str(ipaddress.IPv4Address(c['server']))
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', c['email']):
        raise ValueError('Invalid ACME email')
    if any(x.endswith('.example.com') or x == 'example.com' for x in (c['domain'], c['email'].split('@')[-1])):
        raise ValueError('Replace example domain and email')
    if not isinstance(c['name'], str) or not 1 <= len(c['name']) <= 80 or any(ord(x) < 32 for x in c['name']) or c['name'] in ('PROXY','DIRECT','REJECT'):
        raise ValueError('Invalid node name')
    for k in ('vpn_port', 'https_port'): port(c[k])
    if len({80, c['vpn_port'], c['https_port']}) != 3:
        raise ValueError('HTTP, VPN and subscription ports must differ')
    return c


def preflight(c):
    if sys.platform != 'linux' or os.geteuid() != 0:
        raise ValueError('Run as root on fresh Ubuntu 24.04')
    release = Path('/etc/os-release').read_text()
    if 'ID=ubuntu' not in release or 'VERSION_ID="24.04"' not in release:
        raise ValueError('Only Ubuntu 24.04 is supported by this installer')
    for p in (ROOT, CONFIG, BIN, WEB, NGINX, Path('/etc/systemd/system/xray.service')):
        if p.exists(): raise ValueError('Existing installation or partial attempt: inspect before retrying: ' + str(p))
    sites = Path('/etc/nginx/sites-enabled')
    if any(p.name != 'default' for p in sites.iterdir()) or list(Path('/etc/nginx/conf.d').glob('*.conf')):
        raise ValueError('Existing custom nginx configuration; use a fresh host')
    for cmd in ('nginx', 'certbot', 'openssl', 'systemctl', 'useradd'):
        if not shutil.which(cmd): raise ValueError('Missing dependency: ' + cmd)
    # Certificate validation needs DNS pointing to this server, not a CDN proxy.
    addresses = {x[4][0] for x in socket.getaddrinfo(c['domain'], 80, socket.AF_INET)}
    if addresses != {c['server']}:
        raise ValueError('Domain A record must point only to the configured server')
    for p in (c['vpn_port'], c['https_port']):
        with socket.socket() as s: s.bind(('0.0.0.0', p))


def fetch_xray(version, digest, dest):
    if not re.fullmatch(r'\d+\.\d+\.\d+', version) or not re.fullmatch(r'[0-9a-fA-F]{64}', digest):
        raise ValueError('Supply an explicit Xray version and official ZIP SHA256')
    import platform
    arch = {'x86_64':'64', 'aarch64':'arm64-v8a'}.get(platform.machine())
    if not arch: raise ValueError('Only x86_64 and aarch64 are supported')
    url = f'https://github.com/XTLS/Xray-core/releases/download/v{version}/Xray-linux-{arch}.zip'
    with tempfile.TemporaryDirectory() as td:
        archive = Path(td)/'xray.zip'
        with urllib.request.urlopen(url, timeout=90) as r, archive.open('wb') as f: shutil.copyfileobj(r, f)
        if hashlib.sha256(archive.read_bytes()).hexdigest().lower() != digest.lower():
            raise ValueError('Xray SHA256 mismatch; nothing installed')
        with zipfile.ZipFile(archive) as z:
            with z.open('xray') as source, dest.open('xb') as target: shutil.copyfileobj(source, target)
        dest.chmod(0o755)


def keypair():
    # Standard X25519 DER encodings; public key is derived locally, never sent away.
    import base64
    private = subprocess.check_output(['openssl','genpkey','-algorithm','X25519','-outform','DER'])
    public = subprocess.check_output(['openssl','pkey','-inform','DER','-pubout','-outform','DER'], input=private)
    return tuple(base64.urlsafe_b64encode(x[-32:]).decode().rstrip('=') for x in (private, public))


def publish(state):
    """Build all formats before atomic symlink switch; URLs and Xray stay unchanged."""
    outputs = {fmt: subscription(state['nodes'], fmt) for fmt in FORMATS}
    generation = WEB/('release-' + str(time.time_ns()))
    generation.mkdir(mode=0o750)
    shutil.chown(generation, user='root', group='www-data')
    for fmt, content in outputs.items():
        p = generation/fmt
        write(p, content, 0o640)
        shutil.chown(p, user='root', group='www-data')
    link = WEB/('next-' + secrets.token_hex(8))
    link.symlink_to(generation)
    link.replace(WEB/'current')
    # Old releases contain credentials; retain only the current generation.
    for old in WEB.glob('release-*'):
        if old != generation and old.is_dir() and not old.is_symlink(): shutil.rmtree(old)


def install(c, version, digest):
    preflight(c)
    os.umask(0o077)
    # Download and validate config BEFORE changing services or creating state.
    with tempfile.TemporaryDirectory() as td:
        binary = Path(td)/'xray'
        fetch_xray(version, digest, binary)
        private, public = keypair()
        n = node(dict(name=c['name'], server=c['server'], port=c['vpn_port'], sni=c['sni'],
                      uuid=str(uuid.uuid4()), public_key=public, short_id=secrets.token_hex(8)))
        candidate = Path(td)/'config.json'
        write(candidate, json.dumps(xray_config(n, private), indent=2))
        run(str(binary), 'run', '-test', '-config', str(candidate), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        ROOT.mkdir(mode=0o700)
        write(ROOT/'INSTALLING', 'Installation incomplete. Inspect services and state before retrying.\n')
        token = secrets.token_urlsafe(32)
        state = {'domain':c['domain'], 'https_port':c['https_port'], 'token':token, 'nodes':[n]}
        write(ROOT/'state.json', json.dumps(state, ensure_ascii=False, indent=2))
        import pwd
        try: pwd.getpwnam('xray')
        except KeyError: run('useradd','--system','--no-create-home','--shell','/usr/sbin/nologin','xray')
        BIN.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(binary, BIN); BIN.chmod(0o755)
        CONFIG.parent.mkdir(parents=True, exist_ok=True)
        CONFIG.parent.chmod(0o750)
        shutil.chown(CONFIG.parent, user='root', group='xray')
        write(CONFIG, candidate.read_text(), 0o640)
        shutil.chown(CONFIG, user='root', group='xray')
    WEB.mkdir(mode=0o750); shutil.chown(WEB, user='root', group='www-data')
    publish(state)
    unit = '''[Unit]
Description=Xray VLESS REALITY
After=network-online.target
Wants=network-online.target
[Service]
User=xray
Group=xray
ExecStart=/usr/local/bin/xray run -config /usr/local/etc/xray/config.json
Restart=on-failure
RestartSec=3
AmbientCapabilities=CAP_NET_BIND_SERVICE
CapabilityBoundingSet=CAP_NET_BIND_SERVICE
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
UMask=0077
[Install]
WantedBy=multi-user.target
'''
    write(Path('/etc/systemd/system/xray.service'), unit, 0o644)
    # Fresh nginx default only; certificate failure restarts it, leaves Xray unstarted.
    run('systemctl','stop','nginx')
    try:
        run('certbot','certonly','--standalone','--non-interactive','--agree-tos',
            '--email',c['email'],'--cert-name',c['domain'],'-d',c['domain'])
    finally:
        run('systemctl','start','nginx')
    write(NGINX, nginx_config(c['domain'], c['https_port'], token), 0o640)
    enabled = Path('/etc/nginx/sites-enabled/xray-subscription')
    enabled.symlink_to(NGINX)
    try: run('nginx','-t')
    except Exception:
        enabled.unlink()
        raise
    # Future HTTP-01 renewals use the nginx webroot and do not stop services.
    # Use certbot's supported reconfigure flow instead of editing renewal internals.
    run('systemctl','reload','nginx')
    run('certbot','reconfigure','--cert-name',c['domain'],'--webroot','-w','/var/www/html','--non-interactive')
    write(Path('/etc/letsencrypt/renewal-hooks/deploy/xray-subscription'),
          '#!/bin/sh\nset -eu\nnginx -t\nsystemctl reload nginx\n', 0o755)
    run('systemctl','daemon-reload')
    run('systemctl','enable','--now','xray','nginx','certbot.timer')
    run('systemctl','is-active','--quiet','xray','nginx')
    urls = {fmt: f"https://{c['domain']}:{c['https_port']}/sub/{token}/{fmt}" for fmt in FORMATS}
    write(Path('/root/xray-subscription-delivery.json'), json.dumps(urls, indent=2))
    (ROOT/'INSTALLING').unlink()
    print('Installed. Subscription URLs: /root/xray-subscription-delivery.json (root only).')
    print('Verify real client exit IP and HTTPS before accepting the deployment.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('install', help='Fresh Ubuntu 24.04 only; requires root')
    p.add_argument('--settings', required=True)
    p.add_argument('--xray-version', required=True)
    p.add_argument('--xray-sha256', required=True, help='SHA256 of the architecture-specific official ZIP')
    sub.add_parser('publish', help='Regenerate subscriptions from root-only state; does not modify Xray')
    args = parser.parse_args()
    if args.command == 'install':
        install(settings(json.loads(Path(args.settings).read_text(encoding='utf-8-sig'))), args.xray_version, args.xray_sha256)
    else:
        if sys.platform != 'linux' or os.geteuid() != 0: raise ValueError('Root required')
        if (ROOT/'INSTALLING').exists(): raise ValueError('Installation is incomplete')
        os.umask(0o077)
        import fcntl
        with (ROOT/'publish.lock').open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            publish(json.loads((ROOT/'state.json').read_text()))
        print('Published all formats. Existing subscription URLs unchanged.')


if __name__ == '__main__':
    try: main()
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        # No subprocess output or generated credentials in error messages.
        print('Operation failed (' + type(exc).__name__ + '). Check prerequisites and local service logs. Do not blindly rerun installation.', file=sys.stderr)
        sys.exit(1)
