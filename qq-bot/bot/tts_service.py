import hashlib
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


class TTSServiceError(RuntimeError):
    pass


class TTSService:
    def __init__(self, output_dir: str | Path):
        self.output_dir = Path(output_dir).expanduser().resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _normalize_text(text: str) -> str:
        value = str(text or '').strip()
        if not value:
            raise TTSServiceError('TTS 文本不能为空')
        return value

    def synthesize_to_wav(self, text: str, *, voice: str = 'slt', sample_rate: int = 16000) -> Path:
        value = self._normalize_text(text)
        voice_name = str(voice or 'slt').strip() or 'slt'
        digest = hashlib.sha1(f'{voice_name}|{sample_rate}|{value}'.encode('utf-8')).hexdigest()[:16]
        output_path = self.output_dir / f'tts-{digest}.wav'
        if output_path.exists() and output_path.stat().st_size > 1024:
            return output_path

        cmd = [
            'ffmpeg', '-y',
            '-f', 'lavfi',
            '-i', f'flite=text={self._escape_flite_text(value)}:voice={voice_name}',
            '-ac', '1',
            '-ar', str(int(sample_rate)),
            '-c:a', 'pcm_s16le',
            str(output_path),
        ]
        try:
            completed = subprocess.run(cmd, check=True, capture_output=True, text=True)
        except FileNotFoundError as e:
            raise TTSServiceError('未找到 ffmpeg，无法执行本地 TTS') from e
        except subprocess.CalledProcessError as e:
            stderr = (e.stderr or '').strip()
            raise TTSServiceError(f'ffmpeg flite 合成失败: {stderr[:300]}') from e

        if not output_path.exists() or output_path.stat().st_size <= 1024:
            detail = (completed.stderr or completed.stdout or '').strip()
            raise TTSServiceError(f'TTS 输出文件异常: {detail[:300]}')
        logger.info('TTS 合成完成: %s', output_path)
        return output_path

    @staticmethod
    def _escape_flite_text(text: str) -> str:
        value = text.replace('\\', '\\\\')
        value = value.replace(':', '\\:')
        value = value.replace("'", "\\'")
        value = value.replace('[', '\\[').replace(']', '\\]')
        value = value.replace('%', '\\%').replace(',', '\\,').replace(';', '\\;').replace('=', '\\=')
        value = value.replace('\n', ' ')
        return value
