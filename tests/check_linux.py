"""Run on an isolated Linux CI runner, never on the production host."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from deploy import keypair
from src.subscriptions import xray_config, nginx_config
from test_subscriptions import fixture

with tempfile.TemporaryDirectory() as td:
    root=Path(td)
    private,public=keypair()
    n=fixture();n['public_key']=public
    config=root/'xray.json';config.write_text(json.dumps(xray_config(n,private)))
    subprocess.run([os.environ['XRAY_TEST_BIN'],'run','-test','-config',str(config)],check=True)
    # Use a temporary self-signed cert ONLY for nginx syntax validation, never deployment.
    cert=root/'cert.pem';key=root/'key.pem'
    subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','1',
                    '-subj','/CN=vpn.example.com','-keyout',str(key),'-out',str(cert)],check=True,capture_output=True)
    site=nginx_config('vpn.example.com',8443,'a'*43)
    site=site.replace('/etc/letsencrypt/live/vpn.example.com/fullchain.pem',str(cert)).replace('/etc/letsencrypt/live/vpn.example.com/privkey.pem',str(key))
    site=site.replace('/var/log/nginx/xray-subscription-error.log',str(root/'error.log'))
    conf=root/'nginx.conf';conf.write_text(f'pid {root}/nginx.pid;\nerror_log {root}/error.log;\nevents {{}}\nhttp {{\n{site}\n}}\n')
    subprocess.run(['nginx','-t','-p',td,'-c',str(conf)],check=True)
print('Linux real-key Xray config and nginx syntax passed; ACME/network/client acceptance not tested.')
