import uvicorn
import asyncio
import re
from fastapi import FastAPI, Request, Query, HTTPException
from fastapi.responses import HTMLResponse
import yaml
import os
from pathlib import Path
import logging
from datetime import datetime
from bot.ai_client import PenguinAI
from bot.openclaw_client import OpenClawClient, OpenClawError, OpenClawTurnResult
from bot.qq_sender import QQSender
from bot.command_handler import execute_command
from bot.scheduler import setup_scheduled_tasks
from bot.task_db import (
    init_db,
    get_recent_tasks,
    get_task,
    register_project,
    get_all_projects,
    seed_capability_checklist,
    set_bridge_route_state,
)
from bot.agent_manager import dispatch_task
from bot.workspace import init_workspace_db, add_knowledge, search_knowledge, list_knowledge, get_knowledge, post_bulletin, get_unread_bulletins
from bot.monitor import get_status_report, refresh_agent_status
from bot.chat_history import build_chat_history_payload, render_chat_history_page
from bot.media_context import build_user_message_with_media_context, extract_plain_text
from bot.ops_patrol import build_patrol_report, looks_like_ops_patrol_request
from bot.evolution import build_evolution_prompt, build_remember_prompt, should_trigger_evolution
from bot.evolution_loop import (
    begin_evolution_request,
    build_evolution_ack_text,
    update_evolution_request_from_sync_reply,
)
from bot.tts_service import TTSService, TTSServiceError
from bot.runtime_paths import (
    BOT_LOG_PATH,
    CONFIG_PATH,
    OPENCLAW_TRANSCRIPT_DIR as DEFAULT_OPENCLAW_TRANSCRIPT_DIR,
    TEST_FILE_PATH,
    TEST_IMAGE_PATH,
    TEST_VIDEO_PATH,
    TEST_VOICE_PATH,
    TTS_OUTPUT_DIR,
    ensure_runtime_dirs,
)

# 配置日志
ensure_runtime_dirs()

HTTP_HOST = os.environ.get('QQ_BOT_HOST', '127.0.0.1').strip() or '127.0.0.1'
HTTP_PORT = int(os.environ.get('QQ_BOT_PORT', '8000'))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(BOT_LOG_PATH, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 加载配置
with CONFIG_PATH.open('r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

app = FastAPI()

LOG_FILE = BOT_LOG_PATH
OPENCLAW_TRANSCRIPT_DIR = DEFAULT_OPENCLAW_TRANSCRIPT_DIR

# 初始化模块
openclaw_cfg = config.get("openclaw") or {}
OPENCLAW_ENABLED = bool(openclaw_cfg.get("enabled", True))
OPENCLAW_PROMPT_PREFIX = str(openclaw_cfg.get("prompt_prefix", "") or "").strip()
openclaw = OpenClawClient(
    agent_id=openclaw_cfg.get("agent_id", ""),
    thinking=openclaw_cfg.get("thinking", "minimal"),
    timeout_seconds=openclaw_cfg.get("timeout_seconds", 600),
)

penguin_cfg = config.get("penguin_api") or {}
ai = None
if penguin_cfg.get("base_url") and penguin_cfg.get("api_key") and penguin_cfg.get("model"):
    ai = PenguinAI(
        base_url=penguin_cfg["base_url"],
        api_key=penguin_cfg["api_key"],
        model=penguin_cfg["model"],
    )

qq = QQSender(napcat_url=config['napcat']['url'])
tts_service = TTSService(TTS_OUTPUT_DIR)
ADMIN_QQ = config['admin']['qq_number']
security_cfg = config.get("security") or {}
ADMIN_ONLY = bool(security_cfg.get("admin_only", True))

web_cfg = config.get("web") or {}
PUBLIC_BASE_URL = str(web_cfg.get("public_base_url", "") or "").rstrip("/")
HISTORY_REQUIRE_TOKEN = bool(web_cfg.get("history_require_token", False))
HISTORY_TOKEN = str(web_cfg.get("history_token", "") or "").strip()

evolution_cfg = config.get("evolution") or {}
EVOLUTION_AUTO_TRIGGER = bool(evolution_cfg.get("auto_trigger", True))
EVOLUTION_EXTRA_KEYWORDS = [
    str(item).strip()
    for item in (evolution_cfg.get("extra_keywords") or [])
    if str(item).strip()
]

# 自动扫描的项目目录
PROJECT_SCAN_DIRS = config.get('project_dirs', [
    r"E:\朗驰\软研院\AI数据集项目开发\测试文件夹"
])

IMAGE_REQUEST_KEYWORDS = [
    '发张图片', '发个图片', '来张图', '来个图', '发图', '图看看', '看图', '配图', '图片', '发一张图'
]
VIDEO_REQUEST_KEYWORDS = [
    '发个视频', '发段视频', '发视频', '来个视频', '来段视频', '给我发视频', '给我个视频'
]
FILE_REQUEST_KEYWORDS = [
    '发个文件', '发份文件', '发文件', '传文件', '给我个文件', '给我发个文件'
]
VOICE_REQUEST_KEYWORDS = [
    '发个语音', '发段语音', '发语音', '来段语音', '来个语音', '发个音频', '发段音频'
]
MEDIA_REQUEST_KEYWORDS = {
    'image': IMAGE_REQUEST_KEYWORDS,
    'video': VIDEO_REQUEST_KEYWORDS,
    'file': FILE_REQUEST_KEYWORDS,
    'voice': VOICE_REQUEST_KEYWORDS,
}
CAPABILITY_BACKLOG_TRIGGER_KEYWORDS = [
    '这8项技能都给我整好', '把这8项技能都整好', '逐步完成', '完成一件告诉我一件', '发图片发文件发语音发视频', '读图读文件读语音视频', '运维巡检技能', '子 agent 协调', '子agent 协调', '进化出来这些功能'
]
IMAGE_DIRECTIVE_LINE_RE = re.compile(r'^\s*\[\[(?:send_image|image)\]\]\s*(\S.*?)\s*$', re.MULTILINE)
IMAGE_DIRECTIVE_INLINE_RE = re.compile(r'\[\[(?:send_image|image):(.*?)\]\]')
VIDEO_DIRECTIVE_LINE_RE = re.compile(r'^\s*\[\[(?:send_video|video)\]\]\s*(\S.*?)\s*$', re.MULTILINE)
VIDEO_DIRECTIVE_INLINE_RE = re.compile(r'\[\[(?:send_video|video):(.*?)\]\]')
FILE_DIRECTIVE_LINE_RE = re.compile(r'^\s*\[\[(?:send_file|file)\]\]\s*(\S.*?)\s*$', re.MULTILINE)
FILE_DIRECTIVE_INLINE_RE = re.compile(r'\[\[(?:send_file|file):(.*?)\]\]')
VOICE_DIRECTIVE_LINE_RE = re.compile(r'^\s*\[\[(?:send_voice|voice|send_audio|audio)\]\]\s*(\S.*?)\s*$', re.MULTILINE)
VOICE_DIRECTIVE_INLINE_RE = re.compile(r'\[\[(?:send_voice|voice|send_audio|audio):(.*?)\]\]')
TTS_DIRECTIVE_LINE_RE = re.compile(r'^\s*\[\[(?:send_tts|tts)\]\]\s*(\S.*?)\s*$', re.MULTILINE)
TTS_DIRECTIVE_INLINE_RE = re.compile(r'\[\[(?:send_tts|tts):(.*?)\]\]')
CONTROL_MARKER_RE = re.compile(r'\[\[(?:reply_to_current)\]\]\s*')


async def auto_register_projects():
    """自动扫描并注册项目"""
    skip_dirs = {"qq-bot", ".claude", ".idea", "__pycache__", ".git", "venv", "node_modules"}
    for scan_dir in PROJECT_SCAN_DIRS:
        if not os.path.isdir(scan_dir):
            continue
        for name in os.listdir(scan_dir):
            full_path = os.path.join(scan_dir, name)
            if os.path.isdir(full_path) and name not in skip_dirs and not name.startswith("."):
                await register_project(name, full_path, f"自动扫描: {full_path}")
                logger.info(f"注册项目: {name} -> {full_path}")


@app.on_event("startup")
async def startup():
    logger.info("QQ Bot 启动中...")
    await init_db()
    await init_workspace_db()
    await auto_register_projects()
    setup_scheduled_tasks(qq, ADMIN_QQ, OPENCLAW_TRANSCRIPT_DIR)
    projects = await get_all_projects()
    logger.info(f"管理员 QQ: {ADMIN_QQ}")
    logger.info(f"已注册 {len(projects)} 个项目")

@app.on_event("shutdown")
async def shutdown():
    if ai is not None:
        await ai.aclose()
    await qq.aclose()



async def handle_agent_command(message: str, user_id: int, reply_func):
    """处理 Agent 调度指令"""
    parts = message.split(None, 2)  # @项目名 指令内容

    if len(parts) < 2:
        await reply_func(
            "Agent 指令格式:\n"
            "@项目名 你的指令\n\n"
            "例如:\n"
            "@ragflow 帮我看看项目结构\n"
            "@PDF-Excel 修复导入错误\n\n"
            "其他指令:\n"
            "/projects - 查看所有项目\n"
            "/tasks - 查看最近任务\n"
            "/task 编号 - 查看任务详情"
        )
        return

    project_name = parts[0].lstrip("@")
    prompt = parts[1] if len(parts) == 2 else parts[1] + " " + parts[2]

    # 异步执行任务，不阻塞
    asyncio.create_task(dispatch_task(project_name, prompt, user_id, qq, reply_func, openclaw))


async def handle_bot_command(cmd: str, user_id: int, reply_func):
    """处理 Bot 管理指令"""
    if cmd == "/projects":
        projects = await get_all_projects()
        if not projects:
            await reply_func("暂无注册项目")
            return
        text = "已注册项目:\n"
        for p in projects:
            text += f"  @{p['name']}\n    {p['path']}\n"
        await reply_func(text.strip())

    elif cmd == "/tasks":
        tasks = await get_recent_tasks(10)
        if not tasks:
            await reply_func("暂无任务记录")
            return
        text = "最近任务:\n"
        for t in tasks:
            status_icon = {"pending": "⏳", "running": "🔄", "done": "✅", "failed": "❌"}.get(t["status"], "?")
            text += f"  #{t['id']} {status_icon} [{t['project']}] {t['prompt'][:30]}\n"
        await reply_func(text.strip())

    elif cmd.startswith("/task "):
        try:
            task_id = int(cmd.split()[1])
        except (ValueError, IndexError):
            await reply_func("用法: /task 编号")
            return
        task = await get_task(task_id)
        if not task:
            await reply_func(f"任务 #{task_id} 不存在")
            return
        result_preview = (task["result"] or "无")[:800]
        text = (
            f"任务 #{task['id']}\n"
            f"项目: {task['project']}\n"
            f"状态: {task['status']}\n"
            f"指令: {task['prompt']}\n"
            f"创建: {task['created_at']}\n"
            f"结果:\n{result_preview}"
        )
        await reply_func(text)

    elif cmd == "/agents":
        await refresh_agent_status()
        report = await get_status_report()
        await reply_func(report)

    elif cmd == "/report":
        await refresh_agent_status()
        status = await get_status_report()
        tasks = await get_recent_tasks(5)
        report = f"📋 进度汇报\n\n{status}\n\n"
        if tasks:
            report += "最近任务:\n"
            for t in tasks:
                icon = {"pending": "⏳", "running": "🔄", "done": "✅", "failed": "❌"}.get(t["status"], "?")
                report += f"  #{t['id']} {icon} [{t['project']}] {t['prompt'][:30]}\n"
        bulletins = await get_unread_bulletins()
        if bulletins:
            report += f"\n未读公告: {len(bulletins)} 条\n"
            for b in bulletins[:3]:
                report += f"  [{b['source']}] {b['content'][:50]}\n"
        await reply_func(report.strip())

    elif cmd.startswith("/note "):
        # /note 标题|内容|标签
        content = cmd[6:].strip()
        parts = content.split("|", 2)
        if len(parts) < 2:
            await reply_func("用法: /note 标题|内容|标签(可选)")
            return
        title = parts[0].strip()
        body = parts[1].strip()
        tags = parts[2].strip() if len(parts) > 2 else ""
        await add_knowledge(title, body, tags, created_by="qq")
        await reply_func(f"已记录: {title}")

    elif cmd == "/notes":
        docs = await list_knowledge(10)
        if not docs:
            await reply_func("知识库为空")
            return
        text = "知识库:\n"
        for d in docs:
            tags = f" [{d['tags']}]" if d['tags'] else ""
            text += f"  #{d['id']} {d['title']}{tags}\n"
        await reply_func(text.strip())

    elif cmd.startswith("/search "):
        keyword = cmd[8:].strip()
        if not keyword:
            await reply_func("用法: /search 关键词")
            return
        results = await search_knowledge(keyword)
        if not results:
            await reply_func(f"未找到与 '{keyword}' 相关的内容")
            return
        text = f"搜索 '{keyword}' 结果:\n"
        for r in results:
            text += f"  #{r['id']} {r['title']}\n    {r['content'][:60]}\n"
        await reply_func(text.strip())

    elif cmd.startswith("/read "):
        try:
            doc_id = int(cmd.split()[1])
        except (ValueError, IndexError):
            await reply_func("用法: /read 编号")
            return
        doc = await get_knowledge(doc_id)
        if not doc:
            await reply_func(f"文档 #{doc_id} 不存在")
            return
        text = f"📄 {doc['title']}\n"
        if doc['tags']:
            text += f"标签: {doc['tags']}\n"
        text += f"创建: {doc['created_at']}\n\n{doc['content'][:1000]}"
        await reply_func(text)

    elif cmd.startswith("/broadcast "):
        content = cmd[11:].strip()
        if not content:
            await reply_func("用法: /broadcast 消息内容")
            return
        await post_bulletin("admin", content, msg_type="broadcast")
        await reply_func(f"公告已发布: {content[:50]}")

    else:
        # 原有系统指令
        result = await execute_command(cmd)
        await reply_func(result)


MEDIA_REQUEST_NEGATIVE_KEYWORDS = [
    '进化', '安排', '整好', '能力', '功能', '巡检', '协调', '读图', '读文件', '读语音', '读视频', '自诊断'
]


def should_seed_capability_backlog(message: str, evolution_mode: bool) -> bool:
    if not evolution_mode:
        return False
    text = (message or '').strip()
    if not text:
        return False
    return any(keyword in text for keyword in CAPABILITY_BACKLOG_TRIGGER_KEYWORDS)


async def remember_active_chat_route(message_type: str, user_id: int | None, self_id: str, group_id: int | None = None, message_id: int | None = None):
    await set_bridge_route_state({
        'chat_type': str(message_type or 'private'),
        'user_id': int(user_id) if user_id is not None else None,
        'group_id': int(group_id) if group_id not in (None, '', 0, '0') else None,
        'self_id': str(self_id or 'bot'),
        'message_id': int(message_id) if message_id is not None else None,
        'updated_at': datetime.now().astimezone().isoformat(),
    })


def detect_requested_media_types(message: str) -> list[str]:
    text = (message or '').strip()
    if not text:
        return []
    normalized = text.replace(' ', '')
    if any(keyword in normalized for keyword in MEDIA_REQUEST_NEGATIVE_KEYWORDS):
        explicit_request = any(keyword in normalized for keywords in MEDIA_REQUEST_KEYWORDS.values() for keyword in keywords if keyword not in {'图片'})
        if not explicit_request:
            return []
    media_types: list[str] = []
    for media_type, keywords in MEDIA_REQUEST_KEYWORDS.items():
        if any(keyword in normalized for keyword in keywords):
            media_types.append(media_type)
    if media_types:
        return media_types
    if '图片' in normalized and len(normalized) <= 16:
        return ['image']
    return []


def looks_like_image_request(message: str) -> bool:
    return 'image' in detect_requested_media_types(message)


def looks_like_media_send_request(message: str) -> bool:
    return bool(detect_requested_media_types(message))


def build_media_capability_prompt(user_message: str, media_types: list[str]) -> str:
    instruction_blocks: list[str] = []
    media_types = list(dict.fromkeys(media_types))
    if 'image' in media_types:
        instruction_blocks.append(
            '图片发送规则：\n'
            '1. 如已有图片直链，单独输出一行：`[[send_image]] <图片URL>`\n'
            f'2. 如只是验证能力，可直接用：`[[send_image]] {TEST_IMAGE_PATH.resolve().as_uri()}`\n'
            '3. 不要再说“不能发图片文件”'
        )
    if 'file' in media_types:
        instruction_blocks.append(
            '文件发送规则：\n'
            '1. 单独输出一行：`[[send_file]] <file://本地路径或URL>`\n'
            f'2. 如只是验证能力，可直接用：`[[send_file]] {TEST_FILE_PATH.resolve().as_uri()}`\n'
            '3. 可以附一句简短说明，但不要只给下载建议不执行'
        )
    if 'voice' in media_types:
        instruction_blocks.append(
            '语音发送规则：\n'
            '1. 单独输出一行：`[[send_voice]] <file://本地路径或URL>`\n'
            '2. 若你只有文本内容、需要桥接层现合成语音，优先输出：`[[send_tts]] 这里写要说的话`\n'
            f'3. 如只是验证能力，可直接用：`[[send_voice]] {TEST_VOICE_PATH.resolve().as_uri()}`\n'
            '4. 不要再说“不能发语音”'
        )
    if 'video' in media_types:
        instruction_blocks.append(
            '视频发送规则：\n'
            '1. 单独输出一行：`[[send_video]] <file://本地路径或URL>`\n'
            f'2. 如只是验证能力，可直接用：`[[send_video]] {TEST_VIDEO_PATH.resolve().as_uri()}`\n'
            '3. 不要再说“不能发视频”'
        )
    joined_types = ' / '.join(media_types) or '媒体'
    return (
        f'当前 QQ Bridge 已支持真实发送 {joined_types}。\n'
        '如果用户要你直接给 QQ 发媒体，请优先执行发送，而不是只解释能力。\n\n'
        + '\n\n'.join(instruction_blocks)
        + f'\n\n用户原话：{user_message}'
    )


def build_image_capability_prompt(user_message: str) -> str:
    return build_media_capability_prompt(user_message, ['image'])


def _extract_tts_text(raw_text: str) -> tuple[str, list[str]]:
    tts_texts: list[str] = []

    for match in TTS_DIRECTIVE_LINE_RE.finditer(raw_text):
        value = match.group(1).strip()
        if value and value not in tts_texts:
            tts_texts.append(value)

    def replace_tts_inline(match):
        value = match.group(1).strip()
        if value and value not in tts_texts:
            tts_texts.append(value)
        return ''

    cleaned = TTS_DIRECTIVE_INLINE_RE.sub(replace_tts_inline, raw_text)
    cleaned = TTS_DIRECTIVE_LINE_RE.sub('', cleaned)
    cleaned = '\n'.join(line.rstrip() for line in cleaned.splitlines()).strip()
    return cleaned, tts_texts


def extract_media_directives(text: str) -> tuple[str, list[str], list[str], list[str], list[str]]:
    raw_text = CONTROL_MARKER_RE.sub('', str(text or ''))
    raw_text, tts_texts = _extract_tts_text(raw_text)
    image_sources: list[str] = []
    video_sources: list[str] = []
    file_sources: list[str] = []
    voice_sources: list[str] = []

    for tts_text in tts_texts:
        try:
            wav_path = tts_service.synthesize_to_wav(tts_text)
        except TTSServiceError as e:
            logger.error(f'TTS 指令处理失败: {e}')
            continue
        voice_uri = wav_path.as_uri()
        if voice_uri not in voice_sources:
            voice_sources.append(voice_uri)

    for match in IMAGE_DIRECTIVE_LINE_RE.finditer(raw_text):
        value = match.group(1).strip()
        if value and value not in image_sources:
            image_sources.append(value)

    for match in VIDEO_DIRECTIVE_LINE_RE.finditer(raw_text):
        value = match.group(1).strip()
        if value and value not in video_sources:
            video_sources.append(value)

    for match in FILE_DIRECTIVE_LINE_RE.finditer(raw_text):
        value = match.group(1).strip()
        if value and value not in file_sources:
            file_sources.append(value)

    for match in VOICE_DIRECTIVE_LINE_RE.finditer(raw_text):
        value = match.group(1).strip()
        if value and value not in voice_sources:
            voice_sources.append(value)

    def replace_inline(match):
        value = match.group(1).strip()
        if value and value not in image_sources:
            image_sources.append(value)
        return ''

    def replace_video_inline(match):
        value = match.group(1).strip()
        if value and value not in video_sources:
            video_sources.append(value)
        return ''

    def replace_file_inline(match):
        value = match.group(1).strip()
        if value and value not in file_sources:
            file_sources.append(value)
        return ''

    def replace_voice_inline(match):
        value = match.group(1).strip()
        if value and value not in voice_sources:
            voice_sources.append(value)
        return ''

    cleaned = IMAGE_DIRECTIVE_INLINE_RE.sub(replace_inline, raw_text)
    cleaned = VIDEO_DIRECTIVE_INLINE_RE.sub(replace_video_inline, cleaned)
    cleaned = FILE_DIRECTIVE_INLINE_RE.sub(replace_file_inline, cleaned)
    cleaned = VOICE_DIRECTIVE_INLINE_RE.sub(replace_voice_inline, cleaned)
    cleaned = IMAGE_DIRECTIVE_LINE_RE.sub('', cleaned)
    cleaned = VIDEO_DIRECTIVE_LINE_RE.sub('', cleaned)
    cleaned = FILE_DIRECTIVE_LINE_RE.sub('', cleaned)
    cleaned = VOICE_DIRECTIVE_LINE_RE.sub('', cleaned)
    cleaned = '\n'.join(line.rstrip() for line in cleaned.splitlines()).strip()
    return cleaned, image_sources, video_sources, file_sources, voice_sources


async def deliver_private_turn(user_id: int, result: OpenClawTurnResult | str):
    if isinstance(result, str):
        text = result
        media_urls: list[str] = []
    else:
        text = result.text
        media_urls = list(result.media_urls)

    cleaned_text, directive_images, directive_videos, directive_files, directive_voices = extract_media_directives(text)
    image_sources: list[str] = []
    video_sources: list[str] = []
    file_sources: list[str] = []
    voice_sources: list[str] = []
    for item in directive_images:
        value = str(item or '').strip()
        if value and value not in image_sources:
            image_sources.append(value)
    for item in directive_videos:
        value = str(item or '').strip()
        if value and value not in video_sources:
            video_sources.append(value)
    for item in directive_files:
        value = str(item or '').strip()
        if value and value not in file_sources:
            file_sources.append(value)
    for item in directive_voices:
        value = str(item or '').strip()
        if value and value not in voice_sources:
            voice_sources.append(value)
    for item in media_urls:
        value = str(item or '').strip()
        if value and value not in video_sources:
            video_sources.append(value)

    if image_sources or video_sources or file_sources or voice_sources:
        await qq.send_private_media_msg(
            user_id,
            text=cleaned_text or None,
            image_sources=image_sources,
            video_sources=video_sources,
            file_sources=file_sources,
            voice_sources=voice_sources,
        )
        return

    await qq.send_private_msg(user_id, cleaned_text or '（OpenClaw 未返回可用内容）')


async def deliver_group_turn(group_id: int, user_id: int, result: OpenClawTurnResult | str):
    if isinstance(result, str):
        text = result
        media_urls: list[str] = []
    else:
        text = result.text
        media_urls = list(result.media_urls)

    cleaned_text, directive_images, directive_videos, directive_files, directive_voices = extract_media_directives(text)
    image_sources: list[str] = []
    video_sources: list[str] = []
    file_sources: list[str] = []
    voice_sources: list[str] = []
    for item in directive_images:
        value = str(item or '').strip()
        if value and value not in image_sources:
            image_sources.append(value)
    for item in directive_videos:
        value = str(item or '').strip()
        if value and value not in video_sources:
            video_sources.append(value)
    for item in directive_files:
        value = str(item or '').strip()
        if value and value not in file_sources:
            file_sources.append(value)
    for item in directive_voices:
        value = str(item or '').strip()
        if value and value not in voice_sources:
            voice_sources.append(value)
    for item in media_urls:
        value = str(item or '').strip()
        if value and value not in video_sources:
            video_sources.append(value)

    if image_sources or video_sources or file_sources or voice_sources:
        prefix = f"[CQ:at,qq={user_id}]"
        caption = f"{prefix} {cleaned_text}".strip() if cleaned_text else prefix
        await qq.send_group_media_msg(
            group_id,
            text=caption,
            image_sources=image_sources,
            video_sources=video_sources,
            file_sources=file_sources,
            voice_sources=voice_sources,
        )
        return

    plain = cleaned_text or '（OpenClaw 未返回可用内容）'
    await qq.send_group_msg(group_id, f"[CQ:at,qq={user_id}] {plain}")


def require_history_token(token: str | None) -> None:
    if not HISTORY_REQUIRE_TOKEN:
        return
    if not HISTORY_TOKEN:
        raise HTTPException(status_code=503, detail="history token 未配置")
    if token != HISTORY_TOKEN:
        raise HTTPException(status_code=403, detail="invalid history token")


def build_ai_prompt(message: str, source_text: str | None = None) -> tuple[str, bool, str | None]:
    text = (source_text if source_text is not None else message or "").strip()
    full_message = (message or "").strip()
    if not text and not full_message:
        raise ValueError("消息不能为空")

    if text == "/evolve" or text.startswith("/evolve "):
        detail = text[len("/evolve"):].strip()
        if not detail:
            raise ValueError("用法: /evolve 需要固化的规则、改进点或教训")
        return build_evolution_prompt(detail), True, "evolve"

    if text == "/remember" or text.startswith("/remember "):
        detail = text[len("/remember"):].strip()
        if not detail:
            raise ValueError("用法: /remember 需要记住的信息")
        return build_remember_prompt(detail), True, "remember"

    if EVOLUTION_AUTO_TRIGGER and should_trigger_evolution(text, extra_keywords=EVOLUTION_EXTRA_KEYWORDS):
        return build_evolution_prompt(text), True, "evolve"

    media_types = detect_requested_media_types(text)
    if media_types:
        return build_media_capability_prompt(text, media_types), False, None

    return full_message or message, False, None


def extract_turn_text(result: OpenClawTurnResult | str) -> str:
    if isinstance(result, str):
        return result
    return str(result.text or '').strip()


async def run_ai_turn(
    *,
    session_id: str,
    prompt: str,
    chat_type: str,
    user_id: int,
    group_id: int | None,
    evolution_mode: bool,
    evolution_kind: str | None,
    evolution_trigger_text: str,
    evolution_user_message: str,
    reply_func,
) -> OpenClawTurnResult | str:
    evolution_state = None
    chat_scope = '群聊' if chat_type == 'group' else '私聊'

    if evolution_mode:
        logger.info(
            f"触发自助进化: chat={chat_type} group_id={group_id} user_id={user_id} kind={evolution_kind}"
        )
        if should_seed_capability_backlog(evolution_trigger_text, evolution_mode):
            await seed_capability_checklist(user_id, chat_type=chat_type, group_id=group_id)
        if evolution_kind == 'evolve':
            evolution_state = await begin_evolution_request(
                chat_type=chat_type,
                user_qq=user_id,
                group_id=group_id,
                user_message=evolution_user_message,
            )
            await reply_func(build_evolution_ack_text(evolution_state))

    effective_prompt = prompt
    if OPENCLAW_PROMPT_PREFIX:
        effective_prompt = OPENCLAW_PROMPT_PREFIX + "\n\n" + prompt

    if evolution_mode and not OPENCLAW_ENABLED:
        reply: OpenClawTurnResult | str = '当前未启用 OpenClaw，自助进化/记忆固化无法真正落地到本地文件。'
    elif OPENCLAW_ENABLED:
        try:
            reply = await openclaw.agent_turn_result(session_id, effective_prompt)
        except OpenClawError as e:
            logger.error(f"OpenClaw {chat_scope}调用失败: {e}")
            reply = str(e)
    elif ai:
        reply = await ai.chat(effective_prompt)
    else:
        reply = 'AI 后端未配置：请启用 openclaw 或配置 penguin_api'

    if evolution_state is not None:
        await update_evolution_request_from_sync_reply(
            chat_type=chat_type,
            user_qq=user_id,
            group_id=group_id,
            reply_text=extract_turn_text(reply),
        )
    return reply


@app.post("/qq/message")
async def handle_message(request: Request):
    try:
        data = await request.json()
        logger.info(f"收到消息: {data}")

        if data.get("post_type") != "message":
            return {"status": "ok"}

        user_id = data.get("user_id")
        raw_message = str(data.get("raw_message", "") or "")
        message_payload = data.get("message")
        plain_message = extract_plain_text(message_payload, raw_message=raw_message)
        rich_message = await build_user_message_with_media_context(data, qq)
        message_type = data.get("message_type")
        self_id = str(data.get("self_id") or "bot")

        # 安全边界：默认仅管理员可用
        if ADMIN_ONLY and user_id is not None:
            try:
                if int(user_id) != int(ADMIN_QQ):
                    return {"status": "ok"}
            except Exception:
                return {"status": "ok"}

        group_id = data.get("group_id")
        if message_type == "private":
            async def reply_func(text):
                await qq.send_private_msg(user_id, text)
        else:
            async def reply_func(text):
                await qq.send_group_msg(group_id, f"[CQ:at,qq={user_id}] {text}")

        await remember_active_chat_route(
            message_type=message_type,
            user_id=user_id,
            self_id=str(self_id),
            group_id=group_id,
            message_id=data.get("message_id"),
        )

        # Agent 调度指令: @项目名 指令
        if plain_message.startswith("@") and not raw_message.startswith("[CQ:"):
            await handle_agent_command(plain_message, user_id, reply_func)
            return {"status": "ok"}

        special_ai_command = plain_message.startswith("/evolve") or plain_message.startswith("/remember")

        if plain_message.startswith("/") and not special_ai_command:
            await handle_bot_command(plain_message, user_id, reply_func)
            return {"status": "ok"}

        if looks_like_ops_patrol_request(plain_message):
            await reply_func(await build_patrol_report(plain_message))
            return {"status": "ok"}

        if message_type == "private":
            session_id = f"qq-{self_id}-private-{user_id}"
            try:
                prompt, evolution_mode, evolution_kind = build_ai_prompt(rich_message, source_text=plain_message)
            except ValueError as e:
                await reply_func(str(e))
                return {"status": "ok"}

            reply = await run_ai_turn(
                session_id=session_id,
                prompt=prompt,
                chat_type="private",
                user_id=int(user_id),
                group_id=None,
                evolution_mode=evolution_mode,
                evolution_kind=evolution_kind,
                evolution_trigger_text=plain_message,
                evolution_user_message=plain_message or rich_message,
                reply_func=reply_func,
            )
            await deliver_private_turn(user_id, reply)

        elif message_type == "group":
            has_at = f"[CQ:at,qq={self_id}]" in raw_message
            if not has_at and isinstance(message_payload, list):
                for item in message_payload:
                    if not isinstance(item, dict) or item.get('type') != 'at':
                        continue
                    qq_target = str((item.get('data') or {}).get('qq') or '')
                    if qq_target == self_id:
                        has_at = True
                        break
            if not has_at:
                return {"status": "ok"}

            clean_plain = plain_message.replace(f"@{self_id}", "").strip()
            group_rich_message = rich_message
            if plain_message and group_rich_message.startswith(plain_message):
                replacement = clean_plain or '用户在群里 @了你，并发送了以下内容。'
                group_rich_message = replacement + group_rich_message[len(plain_message):]
            if not clean_plain and '[QQ 媒体附件上下文]' not in group_rich_message:
                return {"status": "ok"}

            session_id = f"qq-{self_id}-group-{group_id}"
            try:
                prompt, evolution_mode, evolution_kind = build_ai_prompt(group_rich_message, source_text=clean_plain or plain_message)
            except ValueError as e:
                await reply_func(str(e))
                return {"status": "ok"}

            reply = await run_ai_turn(
                session_id=session_id,
                prompt=prompt,
                chat_type="group",
                user_id=int(user_id),
                group_id=int(group_id) if group_id else None,
                evolution_mode=evolution_mode,
                evolution_kind=evolution_kind,
                evolution_trigger_text=clean_plain or plain_message,
                evolution_user_message=clean_plain or plain_message or group_rich_message,
                reply_func=reply_func,
            )
            await deliver_group_turn(group_id, user_id, reply)

        return {"status": "ok"}

    except Exception as e:
        logger.error(f"处理消息失败: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}




def parse_optional_int_query(value: str | None, field_name: str) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return int(text)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"{field_name} 必须是整数") from e


def parse_bool_query(value: str | None) -> bool:
    text = str(value or "").strip().lower()
    return text in {"1", "true", "yes", "on"}


@app.get("/api/chat-history")
async def api_chat_history(
    user_id: str | None = Query(default=str(ADMIN_QQ)),
    group_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    chat_type: str = Query(default="private"),
    date: str | None = Query(default=None),
    task_status: str | None = Query(default=None),
    task_agent: str | None = Query(default=None),
    task_query: str | None = Query(default=None),
    agent_id: str | None = Query(default=None),
    agent_status: str | None = Query(default=None),
    agent_query: str | None = Query(default=None),
    show_completed: str | None = Query(default=None),
    token: str | None = Query(default=None),
):
    require_history_token(token)
    return build_chat_history_payload(
        log_path=LOG_FILE,
        transcript_dir=OPENCLAW_TRANSCRIPT_DIR,
        user_id=parse_optional_int_query(user_id, "user_id"),
        group_id=parse_optional_int_query(group_id, "group_id"),
        chat_type=chat_type,
        limit=limit,
        date=date,
        task_status=task_status,
        task_agent=task_agent,
        task_query=task_query,
        agent_id=agent_id,
        agent_status=agent_status,
        agent_query=agent_query,
        show_completed=parse_bool_query(show_completed),
    )


@app.get("/chat-history", response_class=HTMLResponse)
async def chat_history_page(
    user_id: str | None = Query(default=str(ADMIN_QQ)),
    group_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    chat_type: str = Query(default="private"),
    date: str | None = Query(default=None),
    task_status: str | None = Query(default=None),
    task_agent: str | None = Query(default=None),
    task_query: str | None = Query(default=None),
    agent_id: str | None = Query(default=None),
    agent_status: str | None = Query(default=None),
    agent_query: str | None = Query(default=None),
    show_completed: str | None = Query(default=None),
    token: str | None = Query(default=None),
):
    require_history_token(token)
    payload = build_chat_history_payload(
        log_path=LOG_FILE,
        transcript_dir=OPENCLAW_TRANSCRIPT_DIR,
        user_id=parse_optional_int_query(user_id, "user_id"),
        group_id=parse_optional_int_query(group_id, "group_id"),
        chat_type=chat_type,
        limit=limit,
        date=date,
        task_status=task_status,
        task_agent=task_agent,
        task_query=task_query,
        agent_id=agent_id,
        agent_status=agent_status,
        agent_query=agent_query,
        show_completed=parse_bool_query(show_completed),
    )
    return render_chat_history_page(payload, token=token)

@app.get("/")
async def root():
    projects = await get_all_projects()
    return {
        "status": "running",
        "projects": len(projects),
        "message": "Legacy QQ bridge compatibility service is running"
    }


if __name__ == "__main__":
    logger.info(f"启动 QQ Bot Agent Hub... host={HTTP_HOST} port={HTTP_PORT}")
    uvicorn.run(app, host=HTTP_HOST, port=HTTP_PORT)
