#!/usr/bin/env python3
"""US English OBD installation video review and export."""
import argparse
import io
import json
from pathlib import Path
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
import zipfile

ROOT = Path(__file__).resolve().parent
ASSETS = {
    'en-video': ('en.mp4', 'English_OBD_install.mp4', 'video/mp4'),
    'en-subtitles': ('en.srt', 'English_OBD_install.srt', 'application/x-subrip'),
}


class ExportServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, data_dir):
        self.data_dir = Path(data_dir).resolve()
        super().__init__(address, Handler)


class Handler(BaseHTTPRequestHandler):
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
        elif path in ('/download/english.zip', '/download/bilingual.zip'):
            if not all(self.exists(key) for key in ASSETS):
                self.reply(b'The English video and subtitle file are required.', 'text/plain', 409)
                return
            archive = io.BytesIO()
            with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_STORED) as output:
                for key, (source, name, _) in ASSETS.items():
                    output.write(self.server.data_dir / source, name)
                output.writestr('README.txt', 'US English OBD installation guide.\nOriginal source color and original audio retained. English captions added. No synthesized voiceover.\n')
            self.reply(archive.getvalue(), 'application/zip', filename='English_OBD_exports.zip')
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
