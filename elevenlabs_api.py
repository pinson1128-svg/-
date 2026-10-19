"""Server-side ElevenLabs adapter. Keys never go to the browser."""
import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

MODEL = 'eleven_multilingual_v2'


class VoiceError(Exception):
    def __init__(self, message, status=502):
        super().__init__(message)
        self.status = status


def request(path, payload=None):
    key = os.environ.get('ELEVENLABS_API_KEY', '').strip()
    if not key:
        raise VoiceError('请先在 Render 配置 ELEVENLABS_API_KEY。', 503)
    headers = {'xi-api-key': key, 'Accept': 'audio/mpeg' if payload else 'application/json'}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode()
        headers['Content-Type'] = 'application/json'
    try:
        with urlopen(Request('https://api.elevenlabs.io' + path, data=data, headers=headers), timeout=60) as response:
            content = response.read(8 * 1024 * 1024 + 1)
            if len(content) > 8 * 1024 * 1024:
                raise VoiceError('语音响应过大，请缩短文案。')
            return content
    except HTTPError as error:
        messages = {401: 'ElevenLabs 密钥无效，请在 Render 检查。',
                    403: 'ElevenLabs 拒绝访问，请检查密钥权限和账号套餐。',
                    429: 'ElevenLabs 额度或请求频率受限，请检查账号后重试。'}
        raise VoiceError(messages.get(error.code, 'ElevenLabs 请求失败，请检查账号额度或稍后重试。')) from None
    except (URLError, TimeoutError, OSError):
        raise VoiceError('暂时无法连接 ElevenLabs，请稍后重试。') from None


def voices():
    try:
        items = json.loads(request('/v1/voices'))['voices']
        return [{'voice_id': item['voice_id'], 'name': item.get('name', 'Voice'),
                 'labels': {key: item.get('labels', {}).get(key, '') for key in ('accent', 'language', 'gender')}}
                for item in items]
    except (ValueError, TypeError, KeyError):
        raise VoiceError('ElevenLabs 返回的声音列表无法读取。') from None


def synthesize(text, voice_id):
    if not isinstance(text, str) or not 1 <= len(text.strip()) <= 1000:
        raise VoiceError('请输入 1–1000 字符的英文旁白。', 400)
    if not isinstance(voice_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', voice_id):
        raise VoiceError('请选择有效的声音。', 400)
    audio = request(f'/v1/text-to-speech/{voice_id}?output_format=mp3_44100_128', {
        'text': text.strip(), 'model_id': MODEL,
        'voice_settings': {'stability': 0.5, 'similarity_boost': 0.75}})
    if not (audio.startswith(b'ID3') or (len(audio) >= 2 and audio[0] == 255 and audio[1] & 224 == 224)):
        raise VoiceError('未收到有效 MP3，未提供下载。')
    return audio
