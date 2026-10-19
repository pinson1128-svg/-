"""Server-side ElevenLabs adapter. Keys never go to the browser."""
import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

MODEL = 'eleven_multilingual_v2'
ERROR_REASONS = {
    'invalid_api_key': 'API Key 无效，请检查 Render 中的 ELEVENLABS_API_KEY。',
    'missing_permissions': '密钥缺少权限；加载声音需要 Voices Read，生成需要 Text to Speech。',
    'quota_exceeded': '账号 API 额度不足，请到 ElevenLabs 查看使用量。',
    'rate_limit_exceeded': '请求频率受限，请稍后重试。',
    'too_many_concurrent_requests': '账号同时请求过多，请稍后重试。',
    'detected_unusual_activity': 'ElevenLabs 限制了此账号或服务器的访问，请在其后台或支持渠道确认。',
    'voice_not_found': '所选声音不可用，请重新加载声音列表。',
    'model_not_found': '当前账号无法使用所请求的模型，请检查模型权限。',
    'ip_not_allowed': '密钥的 IP 限制未允许此服务器，请检查 ElevenLabs 密钥设置。',
}


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
        messages = {400: '请求被拒绝，请检查 ElevenLabs 账号和 API 设置。',
                    401: 'ElevenLabs 未授权，请检查 API Key 和密钥权限。',
                    402: '请在 ElevenLabs 查看 API 额度与套餐限制。',
                    403: 'ElevenLabs 拒绝访问，请检查密钥权限和账号套餐。',
                    404: '请求的接口或声音不存在，请检查接口及声音选择。',
                    422: 'ElevenLabs 无法处理请求参数，请检查接口配置。',
                    429: '请求频率或并发受到限制，请稍后重试。'}
        reason = None
        try:
            detail = json.loads(error.read(65536)).get('detail', {})
            status = detail.get('status') if isinstance(detail, dict) else None
            if isinstance(status, str) and status in ERROR_REASONS:
                reason = status
        except (ValueError, AttributeError, OSError):
            pass
        # Do not expose the provider's free-text body: it may echo credentials or user text.
        message = ERROR_REASONS[reason] if reason else messages.get(error.code, 'ElevenLabs 服务返回错误，请稍后重试。')
        operation = '加载声音' if payload is None else '生成配音'
        code = f'HTTP {error.code}' + (f' / {reason}' if reason else '')
        raise VoiceError(f'{operation}失败（ElevenLabs {code}）：{message}') from None
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
