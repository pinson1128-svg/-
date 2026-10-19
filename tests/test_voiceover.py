import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import elevenlabs_api
from server import ExportServer


class VoiceoverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.server = ExportServer(('127.0.0.1', 0), Path(cls.temp.name))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.temp.cleanup()

    def setUp(self):
        self.environ = patch.dict('os.environ', {'ELEVENLABS_API_KEY': 'test-only-not-a-real-api-key',
                                                'VOICE_ACCESS_TOKEN': 'test-only-access-token-long-enough'})
        self.environ.start()
        self.addCleanup(self.environ.stop)
        self.server.last_voice_request = 0

    def get(self, path='/api/voices', payload=None, auth=True):
        headers = {'Authorization': 'Bearer test-only-access-token-long-enough'} if auth else {}
        data = None
        if payload is not None:
            data = json.dumps(payload).encode()
            headers['Content-Type'] = 'application/json'
        return urlopen(Request(self.base + path, data=data, headers=headers), timeout=5)

    def test_unauthorized_requests_never_call_provider(self):
        with patch('elevenlabs_api.urlopen') as provider:
            for path, payload in [('/api/voices', None), ('/api/voiceover', {'text': 'Hello', 'voice_id': 'voice'})]:
                with self.assertRaises(HTTPError) as error:
                    self.get(path, payload, auth=False)
                self.assertEqual(error.exception.code, 401)
            provider.assert_not_called()

    def test_configuration_is_required_without_leaking_values(self):
        with patch.dict('os.environ', {'VOICE_ACCESS_TOKEN': ''}):
            with self.assertRaises(HTTPError) as error:
                self.get()
            self.assertEqual(error.exception.code, 503)
        with patch.dict('os.environ', {'ELEVENLABS_API_KEY': ''}):
            with self.assertRaises(HTTPError) as error:
                self.get()
            self.assertEqual(error.exception.code, 503)
            self.assertIn('ELEVENLABS_API_KEY', error.exception.read().decode())

    def test_voices_are_sanitized_and_key_only_in_server_header(self):
        response = {'voices': [{'voice_id': 'voice123', 'name': 'Test voice',
                                'labels': {'accent': 'american'}, 'private_field': 'not-for-browser'}]}
        with patch('elevenlabs_api.urlopen', return_value=io.BytesIO(json.dumps(response).encode())) as provider:
            with self.get() as reply:
                data = json.load(reply)
            self.assertEqual(data['voices'][0]['labels']['accent'], 'american')
            self.assertNotIn('private_field', data['voices'][0])
            self.assertNotIn('test-only-not-a-real-api-key', json.dumps(data))
            request = provider.call_args.args[0]
            self.assertEqual(request.full_url, 'https://api.elevenlabs.io/v1/voices')
            self.assertEqual(request.get_header('Xi-api-key'), 'test-only-not-a-real-api-key')

    def test_generate_mp3_and_prevent_duplicate_generation(self):
        audio = b'ID3-test-response-not-real-audio'
        with patch('elevenlabs_api.urlopen', return_value=io.BytesIO(audio)) as provider:
            with self.get('/api/voiceover', {'text': 'Hello from the dash cam.', 'voice_id': 'voice123'}) as reply:
                self.assertEqual(reply.headers['Content-Type'], 'audio/mpeg')
                self.assertIn('English_voiceover.mp3', reply.headers['Content-Disposition'])
                self.assertEqual(reply.read(), audio)
            request = provider.call_args.args[0]
            self.assertIn('/v1/text-to-speech/voice123?', request.full_url)
            self.assertEqual(json.loads(request.data)['model_id'], elevenlabs_api.MODEL)
            with self.assertRaises(HTTPError) as error:
                self.get('/api/voiceover', {'text': 'Hello', 'voice_id': 'voice123'})
            self.assertEqual(error.exception.code, 429)
            self.assertEqual(provider.call_count, 1)

    def test_invalid_inputs_never_spend_credits(self):
        with patch('elevenlabs_api.urlopen') as provider:
            for payload in [{'text': '', 'voice_id': 'voice'}, {'text': 'x'*1001, 'voice_id': 'voice'},
                            {'text': 'Hello', 'voice_id': '../other/path'}]:
                with self.assertRaises(HTTPError) as error:
                    self.get('/api/voiceover', payload)
                self.assertEqual(error.exception.code, 400)
            provider.assert_not_called()

    def test_provider_errors_are_explained_and_bad_audio_rejected(self):
        with patch('elevenlabs_api.urlopen', side_effect=HTTPError('https://api.elevenlabs.io', 403, 'private upstream data', {}, None)):
            with self.assertRaises(HTTPError) as error:
                self.get()
            self.assertEqual(error.exception.code, 502)
            text = error.exception.read().decode()
            self.assertIn('权限', text)
            self.assertNotIn('private upstream data', text)
        with patch('elevenlabs_api.urlopen', return_value=io.BytesIO(b'{"unexpected":"json"}')):
            with self.assertRaises(HTTPError) as error:
                self.get('/api/voiceover', {'text': 'Hello', 'voice_id': 'voice'})
            self.assertEqual(error.exception.code, 502)

    def test_inflight_generation_is_rejected(self):
        self.server.voice_lock.acquire()
        try:
            with patch('elevenlabs_api.urlopen') as provider:
                with self.assertRaises(HTTPError) as error:
                    self.get('/api/voiceover', {'text': 'Hello', 'voice_id': 'voice'})
                self.assertEqual(error.exception.code, 429)
                provider.assert_not_called()
        finally:
            self.server.voice_lock.release()

    def test_provider_error_diagnostics_do_not_expose_free_text(self):
        for status in ('missing_permissions', 'detected_unusual_activity', 'quota_exceeded', 'unknown-private-status'):
            body = json.dumps({'detail': {'status': status, 'message': 'sensitive-provider-text-and-key'}}).encode()
            error = HTTPError('https://api.elevenlabs.io', 400, 'private', {}, io.BytesIO(body))
            with self.subTest(status=status), patch('elevenlabs_api.urlopen', side_effect=error):
                with self.assertRaises(HTTPError) as result:
                    self.get()
                message = json.load(result.exception)['error']
                self.assertIn('加载声音失败', message)
                self.assertIn('HTTP 400', message)
                self.assertNotIn('sensitive-provider-text-and-key', message)
                if status in elevenlabs_api.ERROR_REASONS:
                    self.assertIn(status, message)
                else:
                    self.assertNotIn(status, message)


if __name__ == '__main__':
    unittest.main()
