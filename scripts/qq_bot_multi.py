#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

import yaml

REPO_ROOT = Path('/root/brain-secretary')
QQ_BOT_MAIN = REPO_ROOT / 'qq-bot' / 'main.py'
QQ_BOT_CWD = REPO_ROOT / 'qq-bot'
DEFAULT_ROOT = Path('/root/qq-bot-multi')
DEFAULT_INSTANCES = [
    {
        'slug': 'brain',
        'role': '大脑号',
        'agent_id': 'qq-main',
        'bridge_port': 8011,
        'onebot_port': 3001,
        'thinking': 'low',
        'evolution_auto_trigger': True,
        'prompt_prefix': '你当前对应的是【大脑号】。你是总协调入口，优先负责理解任务、拆解任务、决定是否委派技术号或验收号，再给用户汇报。你可以直接干活，但涉及工程实施时优先调用子 agent。',
    },
    {
        'slug': 'tech',
        'role': '技术号',
        'agent_id': 'brain-secretary-dev',
        'bridge_port': 8012,
        'onebot_port': 3002,
        'thinking': 'low',
        'evolution_auto_trigger': False,
        'prompt_prefix': '你当前对应的是【技术号】。默认站在工程实施、代码修复、联调排障、验证结果的角度回答。先给结论，再给动作；能验证就先验证。',
    },
    {
        'slug': 'review',
        'role': '方案验收号',
        'agent_id': 'brain-secretary-review',
        'bridge_port': 8013,
        'onebot_port': 3003,
        'thinking': 'low',
        'evolution_auto_trigger': False,
        'prompt_prefix': '你当前对应的是【方案验收号】。默认站在方案补充、风险提醒、验收检查、第二意见的角度回答。先给结论，再给风险点和验收项。',
    },
]
BASE_CONFIG_PATH = REPO_ROOT / 'qq-bot' / 'config.yaml'
PID_POLL_INTERVAL = 0.2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='QQ Bot 多实例桥接管理脚本')
    parser.add_argument('action', choices=['init', 'start', 'stop', 'restart', 'status', 'summary', 'bootstrap'])
    parser.add_argument('--root', default=str(DEFAULT_ROOT), help='桥接实例根目录')
    parser.add_argument('--instance', nargs='*', help='实例名，可选 brain tech review；默认全部')
    parser.add_argument('--json', action='store_true', help='JSON 输出')
    return parser.parse_args()


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open('r', encoding='utf-8') as handle:
        return yaml.safe_load(handle) or {}


def dump_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8') as handle:
        yaml.safe_dump(data, handle, allow_unicode=True, sort_keys=False)


def instance_dir(root: Path, slug: str) -> Path:
    return root / slug


def pid_path(root: Path, slug: str) -> Path:
    return instance_dir(root, slug) / 'run' / 'bridge.pid'


def config_path(root: Path, slug: str) -> Path:
    return instance_dir(root, slug) / 'config.yaml'


def runtime_root(root: Path, slug: str) -> Path:
    return instance_dir(root, slug) / 'runtime'


def metadata_path(root: Path, slug: str) -> Path:
    return instance_dir(root, slug) / 'instance.json'


def wrapper_path(root: Path, slug: str, action: str) -> Path:
    return instance_dir(root, slug) / f'{action}.sh'


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding='utf-8'))


def dump_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def ensure_dirs(base: Path) -> None:
    for relative in ('run', 'runtime/data', 'runtime/logs'):
        (base / relative).mkdir(parents=True, exist_ok=True)


def write_text(path: Path, content: str, mode: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding='utf-8')
    if mode is not None:
        path.chmod(mode)


def build_wrapper(script_path: Path, action: str, slug: str) -> str:
    return (
        '#!/usr/bin/env bash\n'
        'set -euo pipefail\n'
        f'exec python3 {script_path} {action} --instance {slug} "$@"\n'
    )


def is_running(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def read_pid(path: Path) -> int | None:
    if not path.exists():
        return None
    raw = path.read_text(encoding='utf-8').strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def select_definitions(root: Path, selected: list[str] | None) -> list[dict[str, Any]]:
    definitions = []
    for definition in DEFAULT_INSTANCES:
        metadata = load_json(metadata_path(root, definition['slug']), {})
        definitions.append({**definition, **metadata})
    if not selected:
        return definitions
    selected_set = set(selected)
    missing = [item for item in selected if item not in {definition['slug'] for definition in definitions}]
    if missing:
        raise SystemExit(f'unknown instance: {", ".join(missing)}')
    return [definition for definition in definitions if definition['slug'] in selected_set]


def socket_listening(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def transcript_dir_for(agent_id: str) -> str:
    return f'/root/.openclaw/agents/{agent_id}/sessions'


def base_admin_qq() -> int:
    config = load_yaml(BASE_CONFIG_PATH)
    admin = (config.get('admin') or {}).get('qq_number')
    try:
        return int(admin)
    except Exception:
        return 854875058


def whitelist_commands() -> list[str]:
    config = load_yaml(BASE_CONFIG_PATH)
    commands = (config.get('commands') or {}).get('whitelist') or []
    cleaned = []
    for item in commands:
        text = str(item).strip()
        if text and text not in cleaned:
            cleaned.append(text)
    return cleaned or ['/status', '/disk', '/crawl', '/logs', '/help', '/projects', '/tasks', '/task', '/evolve', '/remember']


def render_config(definition: dict[str, Any]) -> dict[str, Any]:
    return {
        'napcat': {
            'url': f"http://127.0.0.1:{definition['onebot_port']}",
        },
        'openclaw': {
            'enabled': True,
            'agent_id': definition['agent_id'],
            'thinking': definition.get('thinking', 'low'),
            'timeout_seconds': 600,
            'prompt_prefix': definition.get('prompt_prefix', ''),
        },
        'admin': {
            'qq_number': base_admin_qq(),
        },
        'security': {
            'admin_only': True,
        },
        'web': {
            'public_base_url': '',
            'history_require_token': False,
            'history_token': '',
        },
        'evolution': {
            'auto_trigger': bool(definition.get('evolution_auto_trigger', False)),
            'extra_keywords': [],
        },
        'project_dirs': [],
        'commands': {
            'whitelist': whitelist_commands(),
        },
    }


def prepare_instance(root: Path, definition: dict[str, Any]) -> dict[str, Any]:
    base = instance_dir(root, definition['slug'])
    ensure_dirs(base)
    dump_yaml(config_path(root, definition['slug']), render_config(definition))
    dump_json(metadata_path(root, definition['slug']), definition)
    script_path = REPO_ROOT / 'scripts' / 'qq_bot_multi.py'
    write_text(wrapper_path(root, definition['slug'], 'start'), build_wrapper(script_path, 'start', definition['slug']), 0o755)
    write_text(wrapper_path(root, definition['slug'], 'stop'), build_wrapper(script_path, 'stop', definition['slug']), 0o755)
    write_text(wrapper_path(root, definition['slug'], 'status'), build_wrapper(script_path, 'status', definition['slug']), 0o755)
    return definition


def env_for(root: Path, definition: dict[str, Any]) -> dict[str, str]:
    env = os.environ.copy()
    env['PYTHONUNBUFFERED'] = '1'
    env['QQ_BOT_CONFIG_PATH'] = str(config_path(root, definition['slug']))
    env['QQ_BOT_RUNTIME_ROOT'] = str(runtime_root(root, definition['slug']))
    env['QQ_BOT_OPENCLAW_TRANSCRIPT_DIR'] = transcript_dir_for(definition['agent_id'])
    env['QQ_BOT_HOST'] = '127.0.0.1'
    env['QQ_BOT_PORT'] = str(definition['bridge_port'])
    return env


def start_instance(root: Path, definition: dict[str, Any]) -> dict[str, Any]:
    prepare_instance(root, definition)
    pid_file = pid_path(root, definition['slug'])
    pid = read_pid(pid_file)
    if pid and is_running(pid):
        return {'slug': definition['slug'], 'status': 'already_running', 'pid': pid}

    log_file = runtime_root(root, definition['slug']) / 'logs' / 'bot.log'
    with log_file.open('ab') as handle:
        process = subprocess.Popen(
            ['python3', str(QQ_BOT_MAIN)],
            cwd=QQ_BOT_CWD,
            env=env_for(root, definition),
            stdin=subprocess.DEVNULL,
            stdout=handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text(f'{process.pid}\n', encoding='utf-8')
    return {'slug': definition['slug'], 'status': 'started', 'pid': process.pid}


def stop_instance(root: Path, definition: dict[str, Any]) -> dict[str, Any]:
    pid_file = pid_path(root, definition['slug'])
    pid = read_pid(pid_file)
    if not pid or not is_running(pid):
        pid_file.unlink(missing_ok=True)
        return {'slug': definition['slug'], 'status': 'not_running', 'pid': pid}
    try:
        os.killpg(pid, signal.SIGTERM)
    except OSError:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
    deadline = time.time() + 8
    while time.time() < deadline:
        if not is_running(pid):
            pid_file.unlink(missing_ok=True)
            return {'slug': definition['slug'], 'status': 'stopped', 'pid': pid}
        time.sleep(PID_POLL_INTERVAL)
    try:
        os.killpg(pid, signal.SIGKILL)
    except OSError:
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass
    pid_file.unlink(missing_ok=True)
    return {'slug': definition['slug'], 'status': 'killed', 'pid': pid}


def health_url(definition: dict[str, Any]) -> str:
    return f"http://127.0.0.1:{definition['bridge_port']}/"


def fetch_health(definition: dict[str, Any]) -> dict[str, Any] | None:
    try:
        with urlopen(health_url(definition), timeout=2) as response:
            body = response.read().decode('utf-8', errors='replace')
        return json.loads(body)
    except (OSError, URLError, ValueError, json.JSONDecodeError):
        return None


def status_info(root: Path, definition: dict[str, Any]) -> dict[str, Any]:
    pid = read_pid(pid_path(root, definition['slug']))
    running = bool(pid and is_running(pid))
    health = fetch_health(definition) if running else None
    return {
        'slug': definition['slug'],
        'role': definition['role'],
        'agent_id': definition['agent_id'],
        'pid': pid,
        'running': running,
        'bridge_port': definition['bridge_port'],
        'onebot_port': definition['onebot_port'],
        'health': health,
        'config_path': str(config_path(root, definition['slug'])),
        'log_path': str(runtime_root(root, definition['slug']) / 'logs' / 'bot.log'),
    }


def wait_ready(root: Path, definition: dict[str, Any], timeout: int = 20) -> dict[str, Any]:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if socket_listening('127.0.0.1', int(definition['bridge_port'])):
            break
        time.sleep(0.5)
    return status_info(root, definition)


def print_records(records: list[dict[str, Any]], as_json: bool) -> None:
    if as_json:
        print(json.dumps(records, ensure_ascii=False, indent=2))
        return
    for item in records:
        print(json.dumps(item, ensure_ascii=False))


def write_root_readme(root: Path) -> None:
    lines = [
        '# QQ Bot 多实例桥接',
        '',
        '这组目录用于把 3 个 NapCat QQ 号分别桥接到不同 OpenClaw agent。',
        '',
        '默认映射：',
    ]
    for definition in DEFAULT_INSTANCES:
        lines.append(
            f"- {definition['slug']}: {definition['role']} -> agent `{definition['agent_id']}` | bridge {definition['bridge_port']} | onebot {definition['onebot_port']}"
        )
    lines.extend([
        '',
        '常用命令：',
        '- python3 /root/brain-secretary/scripts/qq_bot_multi.py bootstrap',
        '- python3 /root/brain-secretary/scripts/qq_bot_multi.py status --json',
        '- python3 /root/brain-secretary/scripts/qq_bot_multi.py stop',
    ])
    write_text(root / 'README.md', '\n'.join(lines) + '\n')


def main() -> int:
    args = parse_args()
    root = Path(args.root)
    root.mkdir(parents=True, exist_ok=True)
    write_root_readme(root)
    selected = select_definitions(root, args.instance)

    if args.action == 'init':
        records = [prepare_instance(root, definition) for definition in selected]
        print_records(records, args.json)
        return 0

    if args.action == 'start':
        records = [start_instance(root, definition) for definition in selected]
        print_records(records, args.json)
        return 0

    if args.action == 'stop':
        records = [stop_instance(root, definition) for definition in selected]
        print_records(records, args.json)
        return 0

    if args.action == 'restart':
        records = []
        for definition in selected:
            records.append(stop_instance(root, definition))
            records.append(start_instance(root, definition))
        print_records(records, args.json)
        return 0

    if args.action == 'status':
        print_records([status_info(root, definition) for definition in selected], args.json)
        return 0

    if args.action == 'summary':
        records = []
        for definition in selected:
            info = status_info(root, definition)
            info['health_url'] = health_url(definition)
            records.append(info)
        print_records(records, args.json)
        return 0

    if args.action == 'bootstrap':
        for definition in selected:
            prepare_instance(root, definition)
        start_records = [start_instance(root, definition) for definition in selected]
        ready_records = [wait_ready(root, definition) for definition in selected]
        records = []
        for start_record, ready_record in zip(start_records, ready_records):
            records.append({**start_record, **ready_record})
        print_records(records, args.json)
        return 0

    raise SystemExit(f'unsupported action: {args.action}')


if __name__ == '__main__':
    sys.exit(main())
