#!/usr/bin/env python3
"""US English silent dash cam unboxing review and export."""
import argparse
import io
import json
import hmac
import os
import threading
import time
from pathlib import Path
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
import zipfile
import elevenlabs_api

ROOT = Path(__file__).resolve().parent
ASSETS = {
    'en-video': ('en.mp4', 'English_Dashcam_Unboxing.mp4', 'video/mp4'),
    'en-subtitles': ('en.srt', 'English_Dashcam_Unboxing.srt', 'application/x-subrip'),
}


class ExportServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, data_dir):
        self.data_dir = Path(data_dir).resolve()
        self.voice_lock = threading.Lock()
        self.last_voice_request = 0.0
        super().__init__(address, Handler)


class Handler(BaseHTTPRequestHandler):
    def voice_auth(self):
        token = os.environ.get('VOICE_ACCESS_TOKEN', '')
        if len(token) < 20:
            self.json_reply({'error': '请先在 Render 设置至少 20 位的 VOICE_ACCESS_TOKEN。'}, 503)
            return False
        actual = self.headers.get('Authorization', '')
        if not hmac.compare_digest(actual.encode(), ('Bearer ' + token).encode()):
            self.json_reply({'error': '访问口令不正确。'}, 401)
            return False
        return True

    def json_reply(self, value, status=200):
        self.reply(json.dumps(value, ensure_ascii=False).encode(), 'application/json; charset=utf-8', status)

    def do_POST(self):
        if urlsplit(self.path).path != '/api/voiceover':
            self.send_error(404)
            return
        if not self.voice_auth():
            return
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if size <= 0 or size > 8192:
                self.json_reply({'error': '文案请求过大或为空。'}, 413)
                return
            data = json.loads(self.rfile.read(size))
            if not isinstance(data, dict):
                raise ValueError()
        except (ValueError, UnicodeDecodeError):
            self.json_reply({'error': '请求格式无效。'}, 400)
            return
        if not self.server.voice_lock.acquire(blocking=False):
            self.json_reply({'error': '已有配音正在生成，请稍后再试。'}, 429)
            return
        try:
            if time.monotonic() - self.server.last_voice_request < 10:
                self.json_reply({'error': '请等待 10 秒再生成下一条，避免重复消耗额度。'}, 429)
                return
            audio = elevenlabs_api.synthesize(data.get('text'), data.get('voice_id'))
            self.server.last_voice_request = time.monotonic()
            self.reply(audio, 'audio/mpeg', filename='English_voiceover.mp3')
        except elevenlabs_api.VoiceError as error:
            self.json_reply({'error': str(error)}, error.status)
        finally:
            self.server.voice_lock.release()

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        try:
            self.route()
        except (BrokenPipeError, ConnectionResetError):
            pass  # Browser canceled a preview or download.

    def exists(self, asset):
        path = self.server.data_dir / ASSETS[asset][0]
        return path.is_file() and path.stat().st_size > 0 and not path.is_symlink()

    def reply(self, content, mime, status=200, filename=None):
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(content)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Cache-Control', 'no-store')
        if filename:
            self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(content)

    def route(self):
        path = urlsplit(self.path).path
        if path == '/':
            self.reply((ROOT / 'web/index.html').read_bytes(), 'text/html; charset=utf-8')
        elif path == '/healthz':
            ready = all(self.exists(key) for key in ASSETS)
            self.reply(json.dumps({'ready': ready}).encode(), 'application/json', 200 if ready else 503)
        elif path == '/api/assets':
            self.reply(json.dumps({key: {'available': self.exists(key),
                'filename': item[1], 'size': (self.server.data_dir / item[0]).stat().st_size if self.exists(key) else 0}
                for key, item in ASSETS.items()}).encode(), 'application/json')
        elif path == '/api/voices':
            if not self.voice_auth():
                return
            try:
                self.json_reply({'voices': elevenlabs_api.voices()})
            except elevenlabs_api.VoiceError as error:
                self.json_reply({'error': str(error)}, error.status)
        elif path in ('/download/english.zip', '/download/bilingual.zip'):
            if not all(self.exists(key) for key in ASSETS):
                self.reply(b'The English video and subtitle file are required.', 'text/plain', 409)
                return
            archive = io.BytesIO()
            with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_STORED) as output:
                for key, (source, name, _) in ASSETS.items():
                    output.write(self.server.data_dir / source, name)
                output.writestr('README.txt', 'US English dash cam unboxing.\nOriginal source color retained. Original audio removed; silent video. English action captions added.\n')
            self.reply(archive.getvalue(), 'application/zip', filename='English_Unboxing_exports.zip')
        elif path.startswith(('/media/', '/download/')):
            asset = path.rsplit('/', 1)[-1]
            if asset not in ASSETS or not self.exists(asset):
                self.send_error(404, 'Export not found')
                return
            source, name, mime = ASSETS[asset]
            self.stream(self.server.data_dir / source, mime, name if path.startswith('/download/') else None)
        else:
            self.send_error(404)

    def stream(self, path, mime, filename):
        # Byte ranges let browsers seek without fetching the whole MP4.
        with path.open('rb') as source:
            size = path.stat().st_size
            start, end, status = 0, size - 1, 200
            value = self.headers.get('Range')
            if value:
                match = re.fullmatch(r'bytes=(\d*)-(\d*)', value)
                if not match or not any(match.groups()):
                    self.invalid_range(size)
                    return
                left, right = match.groups()
                if left:
                    start = int(left)
                    end = min(int(right), size - 1) if right else size - 1
                else:
                    start = max(0, size - int(right))
                if start > end or start >= size:
                    self.invalid_range(size)
                    return
                status = 206
            self.send_response(status)
            self.send_header('Content-Type', mime)
            self.send_header('Accept-Ranges', 'bytes')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(end - start + 1))
            self.send_header('X-Content-Type-Options', 'nosniff')
            if status == 206:
                self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
            if filename:
                self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
            self.end_headers()
            if self.command == 'HEAD':
                return
            source.seek(start)
            remaining = end - start + 1
            while remaining:
                chunk = source.read(min(256 * 1024, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)

    def invalid_range(self, size):
        self.send_response(416)
        self.send_header('Content-Range', f'bytes */{size}')
        self.send_header('Content-Length', '0')
        self.end_headers()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8080)
    parser.add_argument('--data-dir', type=Path, default=ROOT / 'data')
    args = parser.parse_args()
    server = ExportServer((args.host, args.port), args.data_dir)
    print(f'Export application listening on port {server.server_port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
