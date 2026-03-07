from __future__ import annotations

import os
from pathlib import Path

QQ_BOT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = QQ_BOT_ROOT.parent
CONFIG_PATH = Path(os.environ.get('QQ_BOT_CONFIG_PATH') or (QQ_BOT_ROOT / 'config.yaml'))
RUNTIME_ROOT = Path(os.environ.get('QQ_BOT_RUNTIME_ROOT') or QQ_BOT_ROOT)
DATA_DIR = RUNTIME_ROOT / 'data'
LOG_DIR = RUNTIME_ROOT / 'logs'
BOT_LOG_PATH = LOG_DIR / 'bot.log'
TASK_DB_PATH = DATA_DIR / 'tasks.db'
INBOX_ROOT = DATA_DIR / 'inbox'
TTS_OUTPUT_DIR = DATA_DIR / 'generated_tts'
OPENCLAW_TRANSCRIPT_DIR = Path(
    os.environ.get('QQ_BOT_OPENCLAW_TRANSCRIPT_DIR')
    or (Path.home() / '.openclaw' / 'agents' / 'qq-main' / 'sessions')
)
TEST_IMAGE_PATH = DATA_DIR / 'openclaw-test-image.png'
TEST_FILE_PATH = DATA_DIR / 'openclaw-test-file.txt'
TEST_VOICE_PATH = DATA_DIR / 'openclaw-test-voice.wav'
TEST_VIDEO_PATH = DATA_DIR / 'openclaw-test-video.mp4'


def ensure_runtime_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    INBOX_ROOT.mkdir(parents=True, exist_ok=True)
    TTS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
