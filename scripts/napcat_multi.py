#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

BASE_WORKDIR = Path('/root/Napcat/opt/QQ/resources/app/app_launcher/napcat')
QQ_BIN = Path('/root/Napcat/opt/QQ/qq')
DEFAULT_ROOT = Path('/root/napcat-multi')
QR_URL_RE = re.compile(r'二维码解码URL:\s*(\S+)')
PID_POLL_INTERVAL = 0.2

DEFAULT_INSTANCES = [
    {
        'slug': 'brain',
        'role': '大脑号',
        'agent_id': 'qq-main',
        'webui_port': 6101,
        'onebot_port': 3001,
        'bridge_port': 8011,
    },
    {
        'slug': 'tech',
        'role': '技术号',
        'agent_id': 'brain-secretary-dev',
        'webui_port': 6102,
        'onebot_port': 3002,
        'bridge_port': 8012,
    },
    {
        'slug': 'review',
        'role': '方案验收号',
        'agent_id': 'brain-secretary-review',
        'webui_port': 6103,
        'onebot_port': 3003,
        'bridge_port': 8013,
    },
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='NapCat 多实例管理脚本')
    parser.add_argument('action', choices=['init', 'start', 'stop', 'restart', 'status', 'summary', 'qr', 'bootstrap'])
    parser.add_argument('--root', default=str(DEFAULT_ROOT), help='实例根目录')
    parser.add_argument('--instance', nargs='*', help='实例名，可选 brain tech review；默认全部')
    parser.add_argument('--refresh-workdir', action='store_true', help='重新复制 NapCat workdir')
    parser.add_argument('--timeout', type=int, default=90, help='等待二维码超时秒数')
    parser.add_argument('--json', action='store_true', help='以 JSON 输出 summary/status/qr')
    return parser.parse_args()


def instance_dir(root: Path, slug: str) -> Path:
    return root / slug


def log_path(root: Path, slug: str) -> Path:
    return instance_dir(root, slug) / 'logs' / 'qq.log'


def pid_path(root: Path, slug: str) -> Path:
    return instance_dir(root, slug) / 'run' / 'qq.pid'


def qr_path(root: Path, slug: str) -> Path:
    return instance_dir(root, slug) / 'workdir' / 'cache' / 'qrcode.png'


def instance_metadata_path(root: Path, slug: str) -> Path:
    return instance_dir(root, slug) / 'instance.json'


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding='utf-8'))


def dump_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def ensure_dirs(base: Path) -> None:
    for relative in ('home', 'xdg-config', 'xdg-cache', 'xdg-data', 'xdg-state', 'logs', 'run'):
        (base / relative).mkdir(parents=True, exist_ok=True)


def write_text(path: Path, content: str, mode: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding='utf-8')
    if mode is not None:
        path.chmod(mode)


def copy_workdir(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def reset_runtime_dirs(workdir: Path) -> None:
    cache_dir = workdir / 'cache'
    cache_dir.mkdir(parents=True, exist_ok=True)

    logs_dir = workdir / 'logs'
    if logs_dir.exists():
        shutil.rmtree(logs_dir)
    logs_dir.mkdir(parents=True, exist_ok=True)


def remove_account_specific_configs(config_dir: Path) -> None:
    for pattern in ('onebot11_*.json', 'napcat_*.json', 'napcat_protocol_*.json'):
        for item in config_dir.glob(pattern):
            item.unlink(missing_ok=True)


def configure_workdir(workdir: Path, definition: dict[str, Any]) -> None:
    config_dir = workdir / 'config'
    remove_account_specific_configs(config_dir)
    webui = load_json(config_dir / 'webui.json', {})
    webui['host'] = '127.0.0.1'
    webui['port'] = int(definition['webui_port'])
    webui['token'] = definition.setdefault('webui_token', secrets.token_hex(6))
    webui['autoLoginAccount'] = ''
    dump_json(config_dir / 'webui.json', webui)

    onebot = load_json(config_dir / 'onebot11.json', {})
    http_cfg = onebot.setdefault('http', {})
    http_cfg['enable'] = True
    http_cfg['host'] = '127.0.0.1'
    http_cfg['port'] = int(definition['onebot_port'])
    bridge_port = definition.get('bridge_port')
    http_cfg['post'] = [
        {
            'url': f"http://127.0.0.1:{int(bridge_port)}/qq/message",
            'secret': '',
        }
    ] if bridge_port else []
    onebot.setdefault('ws', {})['enable'] = False
    onebot.setdefault('reverseWs', {})['enable'] = False
    onebot['token'] = ''
    dump_json(config_dir / 'onebot11.json', onebot)

    napcat = load_json(config_dir / 'napcat.json', {})
    napcat['fileLog'] = False
    napcat['consoleLog'] = True
    dump_json(config_dir / 'napcat.json', napcat)


def build_bridge_example(definition: dict[str, Any]) -> str:
    return (
        f"napcat:\n"
        f"  url: http://127.0.0.1:{definition['onebot_port']}\n\n"
        f"openclaw:\n"
        f"  enabled: true\n"
        f"  agent_id: {definition['agent_id']}\n"
        f"  thinking: low\n"
        f"  timeout_seconds: 600\n\n"
        f"admin:\n"
        f"  qq_number: 0\n\n"
        f"security:\n"
        f"  admin_only: false\n"
    )


def build_wrapper(script_path: Path, action: str, slug: str) -> str:
    return (
        '#!/usr/bin/env bash\n'
        'set -euo pipefail\n'
        f'exec python3 {script_path} {action} --instance {slug} "$@"\n'
    )


def prepare_instance(root: Path, definition: dict[str, Any], refresh_workdir: bool) -> dict[str, Any]:
    base = instance_dir(root, definition['slug'])
    ensure_dirs(base)
    if refresh_workdir or not (base / 'workdir').exists():
        copy_workdir(BASE_WORKDIR, base / 'workdir')
    reset_runtime_dirs(base / 'workdir')
    configure_workdir(base / 'workdir', definition)
    dump_json(instance_metadata_path(root, definition['slug']), definition)

    script_path = Path('/root/brain-secretary/scripts/napcat_multi.py')
    write_text(base / 'bridge-example.yaml', build_bridge_example(definition))
    write_text(base / 'start.sh', build_wrapper(script_path, 'start', definition['slug']), 0o755)
    write_text(base / 'stop.sh', build_wrapper(script_path, 'stop', definition['slug']), 0o755)
    write_text(base / 'status.sh', build_wrapper(script_path, 'status', definition['slug']), 0o755)
    return definition


def load_definitions(root: Path) -> list[dict[str, Any]]:
    results = []
    for default in DEFAULT_INSTANCES:
        meta = load_json(instance_metadata_path(root, default['slug']), {})
        results.append({**default, **meta})
    return results


def select_definitions(root: Path, selected: list[str] | None) -> list[dict[str, Any]]:
    definitions = load_definitions(root)
    if not selected:
        return definitions
    selected_set = set(selected)
    missing = [item for item in selected if item not in {definition['slug'] for definition in definitions}]
    if missing:
        raise SystemExit(f'unknown instance: {", ".join(missing)}')
    return [definition for definition in definitions if definition['slug'] in selected_set]


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


def build_env(base: Path) -> dict[str, str]:
    env = os.environ.copy()
    env['HOME'] = str(base / 'home')
    env['XDG_CONFIG_HOME'] = str(base / 'xdg-config')
    env['XDG_CACHE_HOME'] = str(base / 'xdg-cache')
    env['XDG_DATA_HOME'] = str(base / 'xdg-data')
    env['XDG_STATE_HOME'] = str(base / 'xdg-state')
    env['NAPCAT_WORKDIR'] = str(base / 'workdir')
    env.pop('DISPLAY', None)
    return env


def start_instance(root: Path, definition: dict[str, Any]) -> dict[str, Any]:
    base = instance_dir(root, definition['slug'])
    if not (base / 'workdir').exists():
        prepare_instance(root, definition, False)
    ensure_dirs(base)
    pid_file = pid_path(root, definition['slug'])
    pid = read_pid(pid_file)
    if pid and is_running(pid):
        return {'slug': definition['slug'], 'status': 'already_running', 'pid': pid}

    command = [
        'dbus-run-session',
        '--',
        'xvfb-run',
        '-a',
        '-s',
        '-screen 0 1280x800x24',
        str(QQ_BIN),
        '--no-sandbox',
    ]
    log_file = log_path(root, definition['slug'])
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open('ab') as handle:
        process = subprocess.Popen(
            command,
            cwd=base,
            env=build_env(base),
            stdin=subprocess.DEVNULL,
            stdout=handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
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


def extract_qr_url(log_file: Path) -> str | None:
    if not log_file.exists():
        return None
    content = log_file.read_text(encoding='utf-8', errors='ignore')
    matches = QR_URL_RE.findall(content)
    if not matches:
        return None
    return matches[-1]


def qr_info(root: Path, definition: dict[str, Any]) -> dict[str, Any]:
    path = qr_path(root, definition['slug'])
    return {
        'slug': definition['slug'],
        'role': definition['role'],
        'agent_id': definition['agent_id'],
        'qr_path': str(path),
        'qr_exists': path.exists(),
        'qr_url': extract_qr_url(log_path(root, definition['slug'])),
        'log_path': str(log_path(root, definition['slug'])),
    }


def status_info(root: Path, definition: dict[str, Any]) -> dict[str, Any]:
    pid = read_pid(pid_path(root, definition['slug']))
    return {
        'slug': definition['slug'],
        'role': definition['role'],
        'agent_id': definition['agent_id'],
        'pid': pid,
        'running': bool(pid and is_running(pid)),
        'webui_port': definition['webui_port'],
        'onebot_port': definition['onebot_port'],
        'log_path': str(log_path(root, definition['slug'])),
        'qr_path': str(qr_path(root, definition['slug'])),
    }


def wait_for_qr(root: Path, definition: dict[str, Any], timeout: int) -> dict[str, Any]:
    deadline = time.time() + timeout
    while time.time() < deadline:
        info = qr_info(root, definition)
        if info['qr_exists'] or info['qr_url']:
            return info
        time.sleep(1)
    return qr_info(root, definition)


def print_records(records: list[dict[str, Any]], as_json: bool) -> None:
    if as_json:
        print(json.dumps(records, ensure_ascii=False, indent=2))
        return
    for item in records:
        print(json.dumps(item, ensure_ascii=False))


def write_root_readme(root: Path) -> None:
    lines = [
        '# NapCat 多实例示例',
        '',
        '这组目录用于 3 个独立扫码 QQ 示例，每个实例都隔离了 HOME / XDG / NAPCAT_WORKDIR。',
        '',
        '默认实例：',
    ]
    for definition in DEFAULT_INSTANCES:
        lines.append(
            f"- {definition['slug']}: {definition['role']} -> agent `{definition['agent_id']}` | WebUI {definition['webui_port']} | OneBot {definition['onebot_port']}"
        )
    lines.extend([
        '',
        '常用命令：',
        '- python3 /root/brain-secretary/scripts/napcat_multi.py bootstrap',
        '- python3 /root/brain-secretary/scripts/napcat_multi.py status',
        '- python3 /root/brain-secretary/scripts/napcat_multi.py qr',
        '- python3 /root/brain-secretary/scripts/napcat_multi.py stop',
    ])
    write_text(root / 'README.md', '\n'.join(lines) + '\n')


def main() -> int:
    args = parse_args()
    root = Path(args.root)
    root.mkdir(parents=True, exist_ok=True)
    write_root_readme(root)

    if args.action == 'init':
        records = [prepare_instance(root, definition, args.refresh_workdir) for definition in select_definitions(root, args.instance)]
        print_records(records, args.json)
        return 0

    if args.action == 'bootstrap':
        selected = select_definitions(root, args.instance)
        for definition in selected:
            prepare_instance(root, definition, args.refresh_workdir)
        start_records = [start_instance(root, definition) for definition in selected]
        qr_records = [wait_for_qr(root, definition, args.timeout) for definition in selected]
        records = []
        for start_record, qr_record in zip(start_records, qr_records):
            records.append({**start_record, **qr_record})
        print_records(records, args.json)
        return 0

    selected = select_definitions(root, args.instance)

    if args.action == 'start':
        records = [start_instance(root, definition) for definition in selected]
        print_records(records, args.json)
        return 0

    if args.action == 'stop':
        records = [stop_instance(root, definition) for definition in selected]
        print_records(records, args.json)
        return 0

    if args.action == 'restart':
        stop_records = [stop_instance(root, definition) for definition in selected]
        start_records = [start_instance(root, definition) for definition in selected]
        print_records(stop_records + start_records, args.json)
        return 0

    if args.action == 'status':
        records = [status_info(root, definition) for definition in selected]
        print_records(records, args.json)
        return 0

    if args.action == 'summary':
        records = []
        for definition in selected:
            records.append({**status_info(root, definition), **qr_info(root, definition)})
        print_records(records, args.json)
        return 0

    if args.action == 'qr':
        records = [qr_info(root, definition) for definition in selected]
        print_records(records, args.json)
        return 0

    raise SystemExit(f'unsupported action: {args.action}')


if __name__ == '__main__':
    sys.exit(main())
