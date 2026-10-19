import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import zipfile

from server import ASSETS, ExportServer


class ExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.directory = Path(cls.temp.name)
        cls.payloads = {}
        for key, (filename, _, _) in ASSETS.items():
            payload = (b'\x00\x00\x00\x18ftypmp42' + bytes(range(256))) if filename.endswith('mp4') else '1\n00:00:00,000 --> 00:00:01,000\nสวัสดี Hello\n'.encode()
            cls.payloads[key] = payload
            (cls.directory / filename).write_bytes(payload)
        cls.server = ExportServer(('127.0.0.1', 0), cls.directory)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.temp.cleanup()

    def get(self, path, **kwargs):
        return urlopen(Request(self.base + path, **kwargs), timeout=5)

    def test_dashboard_and_readiness(self):
        with self.get('/') as response:
            self.assertIn('双语打包下载', response.read().decode())
        with self.get('/api/assets') as response:
            assets = json.load(response)
        self.assertEqual(set(assets), set(ASSETS))
        self.assertTrue(all(asset['available'] for asset in assets.values()))
        with self.get('/healthz') as response:
            self.assertTrue(json.load(response)['ready'])

    def test_each_download_is_exact_and_named(self):
        for key, (_, filename, mime) in ASSETS.items():
            with self.subTest(key=key), self.get('/download/' + key) as response:
                self.assertEqual(response.read(), self.payloads[key])
                self.assertEqual(response.headers['Content-Disposition'], f'attachment; filename="{filename}"')
                self.assertEqual(response.headers['Content-Type'], mime)

    def test_browser_seeking_and_head(self):
        with self.get('/media/th-video', headers={'Range': 'bytes=7-19'}) as response:
            self.assertEqual(response.status, 206)
            self.assertEqual(response.read(), self.payloads['th-video'][7:20])
            self.assertEqual(response.headers['Content-Range'], f'bytes 7-19/{len(self.payloads["th-video"])}')
        with self.get('/media/en-video', headers={'Range': 'bytes=-12'}) as response:
            self.assertEqual(response.read(), self.payloads['en-video'][-12:])
        with self.get('/download/th-video', method='HEAD') as response:
            self.assertEqual(int(response.headers['Content-Length']), len(self.payloads['th-video']))
            self.assertEqual(response.read(), b'')

    def test_invalid_ranges_and_unknown_paths(self):
        for value in ('bytes=999999-', 'bytes=20-2', 'bytes=-0', 'bytes=1-2,3-4', 'nonsense'):
            with self.subTest(value=value), self.assertRaises(HTTPError) as error:
                self.get('/media/th-video', headers={'Range': value})
            self.assertEqual(error.exception.code, 416)
        for path in ('/download/server.py', '/media/../../server.py', '/data/th.mp4'):
            with self.subTest(path=path), self.assertRaises(HTTPError) as error:
                self.get(path)
            self.assertEqual(error.exception.code, 404)

    def test_bilingual_archive_contains_all_files(self):
        with self.get('/download/bilingual.zip') as response:
            self.assertEqual(response.headers['Content-Type'], 'application/zip')
            self.assertIn('attachment', response.headers['Content-Disposition'])
            archive = zipfile.ZipFile(io.BytesIO(response.read()))
        for key, (_, filename, _) in ASSETS.items():
            self.assertEqual(archive.read(filename), self.payloads[key])
        self.assertIsNone(archive.testzip())

    def test_missing_file_disables_export_and_archive(self):
        path = self.directory / 'th.srt'
        path.unlink()
        try:
            with self.assertRaises(HTTPError) as error:
                self.get('/healthz')
            self.assertEqual(error.exception.code, 503)
            with self.get('/api/assets') as response:
                self.assertFalse(json.load(response)['th-subtitles']['available'])
            with self.assertRaises(HTTPError) as error:
                self.get('/download/th-subtitles')
            self.assertEqual(error.exception.code, 404)
            with self.assertRaises(HTTPError) as error:
                self.get('/download/bilingual.zip')
            self.assertEqual(error.exception.code, 409)
        finally:
            path.write_bytes(self.payloads['th-subtitles'])


if __name__ == '__main__':
    unittest.main()
