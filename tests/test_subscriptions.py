import base64
import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from urllib.parse import parse_qs, urlsplit

from src.subscriptions import FORMATS, nginx_config, subscription, xray_config
from deploy import settings


def fixture():
    return dict(name='Example "node" / 节点', server='203.0.113.10', port=443, sni='example.com',
                uuid='00000000-0000-4000-8000-000000000001', public_key='A'*43, short_id='aabb')


class RenderTests(unittest.TestCase):
    def test_uri_formats_and_encoding(self):
        for fmt in ('shadowrocket','fancyss'):
            uri = base64.b64decode(subscription([fixture()],fmt)).decode().strip()
            parsed = urlsplit(uri)
            self.assertEqual(parsed.hostname, '203.0.113.10')
            self.assertEqual(parse_qs(parsed.query)['flow'], ['xtls-rprx-vision'])
            self.assertNotIn(' ', uri)

    def test_stash_and_meta_fields(self):
        for fmt, key in [('stash','sni'),('clashmeta','servername')]:
            output = subscription([fixture()], fmt)
            proxy = json.loads(output.split('proxies:\n  - ',1)[1].split('\n',1)[0])
            self.assertEqual(proxy[key], 'example.com')
            self.assertNotIn('servername' if key == 'sni' else 'sni', proxy)
            self.assertIn('203.0.113.10/32,DIRECT',output)
            self.assertNotIn('privateKey', output)

    def test_ipv6_and_multi_node(self):
        n=fixture();n.update(server='2001:db8::1',name='IPv6')
        output=base64.b64decode(subscription([fixture(),n],'fancyss')).decode()
        self.assertEqual(len(output.splitlines()),2)
        self.assertIn('@[2001:db8::1]:443',output)
        self.assertIn('2001:db8::1/128,DIRECT',subscription([n],'stash'))

    def test_unsafe_or_invalid_input(self):
        for key,value in [('sni','example.com; injected'),('server','host/../../'),('name','bad\nname'),('port',True),('short_id','f')]:
            n=fixture();n[key]=value
            with self.assertRaises(ValueError):subscription([n],'stash')
        with self.assertRaises(ValueError):subscription([fixture(),fixture()],'stash')
        with self.assertRaises(ValueError):subscription([fixture()],'unknown')
        with self.assertRaises(ValueError):nginx_config('example.com;bad',8443,'a'*43)
        with self.assertRaises(ValueError):nginx_config('example.com',8443,'../secret')

    def test_nginx_exact_paths_only(self):
        output=nginx_config('vpn.example.com',8443,'a'*43)
        self.assertEqual(output.count('location = /sub/'),4)
        self.assertIn('location / { return 404; }',output)
        self.assertNotIn('autoindex on',output)
        self.assertIn('access_log off',output)

    def test_settings_reject_example_and_port_collision(self):
        data=json.loads(Path('settings.example.json').read_text())
        with self.assertRaises(ValueError):settings(data)
        data.update(domain='vpn.test.invalid',email='a@test.invalid',https_port=443)
        with self.assertRaises(ValueError):settings(data)

    def test_yaml_parse_if_available(self):
        try:import yaml
        except ImportError:self.skipTest('Optional PyYAML not installed')
        for fmt in ('stash','clashmeta'):
            data=yaml.safe_load(subscription([fixture()],fmt))
            self.assertEqual(data['proxies'][0]['name'],fixture()['name'])
            self.assertEqual(data['rules'][-1],'MATCH,PROXY')

    @unittest.skipUnless(os.environ.get('XRAY_TEST_BIN'),'Set XRAY_TEST_BIN for real binary check')
    def test_real_xray_config(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'config.json';p.write_text(json.dumps(xray_config(fixture(),'A'*43)))
            subprocess.run([os.environ['XRAY_TEST_BIN'],'run','-test','-config',str(p)],check=True,capture_output=True)


if __name__=='__main__':unittest.main()
