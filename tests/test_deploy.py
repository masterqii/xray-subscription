import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import deploy
from test_subscriptions import fixture


class DeployTests(unittest.TestCase):
    def setUp(self):
        self.arch=patch('platform.machine',return_value='x86_64')
        self.arch.start()
        self.addCleanup(self.arch.stop)

    def test_checksum_failure_does_not_install(self):
        with tempfile.TemporaryDirectory() as td, patch('urllib.request.urlopen', return_value=io.BytesIO(b'bad download')):
            target=Path(td)/'xray'
            with self.assertRaises(ValueError):deploy.fetch_xray('26.3.27','0'*64,target)
            self.assertFalse(target.exists())

    def test_verified_zip_extracts_only_binary(self):
        data=io.BytesIO()
        with zipfile.ZipFile(data,'w') as z:
            z.writestr('xray',b'test-binary')
            z.writestr('../unexpected',b'not extracted')
        raw=data.getvalue()
        with tempfile.TemporaryDirectory() as td, patch('urllib.request.urlopen', return_value=io.BytesIO(raw)):
            target=Path(td)/'xray'
            deploy.fetch_xray('26.3.27',hashlib.sha256(raw).hexdigest(),target)
            self.assertEqual(target.read_bytes(),b'test-binary')
            self.assertEqual([p.name for p in Path(td).iterdir()],['xray'])

    def test_publish_validates_everything_before_touching_disk(self):
        with tempfile.TemporaryDirectory() as td, patch.object(deploy,'WEB',Path(td)):
            bad=fixture();bad['uuid']='invalid'
            with self.assertRaises(ValueError):deploy.publish({'nodes':[bad]})
            self.assertEqual(list(Path(td).iterdir()),[])

    def test_invalid_download_arguments_do_not_use_network(self):
        with patch('urllib.request.urlopen') as request:
            with self.assertRaises(ValueError):deploy.fetch_xray('../latest','0'*64,Path('unused'))
            request.assert_not_called()

    @unittest.skipUnless(__import__('sys').platform=='linux','POSIX symlink/chown test')
    def test_publish_preserves_url_and_switches_all_formats(self):
        with tempfile.TemporaryDirectory() as td, patch.object(deploy,'WEB',Path(td)), patch('shutil.chown'):
            state={'nodes':[fixture()], 'token':'a'*43}
            deploy.publish(state)
            original=(Path(td)/'current').resolve()
            state['nodes'][0]['name']='Renamed'
            deploy.publish(state)
            self.assertNotEqual((Path(td)/'current').resolve(),original)
            self.assertFalse(original.exists())
            self.assertEqual(state['token'],'a'*43)
            self.assertIn('Renamed',(Path(td)/'current'/'stash').read_text())
            self.assertEqual(len(list(Path(td).glob('release-*'))),1)
