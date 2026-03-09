#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

DEFAULT_UI_DIST = Path('/home/paperclip/paperclip/server/ui-dist')
DEFAULT_PUBLIC_BASE_PATH = '/paperclip/'
PATCH_FILENAME = 'zh-patch.js'

EXACT_TRANSLATIONS = {
    'Paperclip': 'Paperclip 控制台',
    'Dashboard': '仪表盘',
    'Agents': '智能体',
    'Projects': '项目',
    'Issues': '问题',
    'Goals': '目标',
    'Approvals': '审批',
    'Costs': '成本',
    'Activity': '动态',
    'Inbox': '收件箱',
    'Company': '公司',
    'Settings': '设置',
    'Company Settings': '公司设置',
    'Documentation': '文档',
    'Work': '工作',
    'Org': '组织架构',
    'Loading...': '加载中...',
    'Loading…': '加载中…',
    'Failed to load app state': '加载应用状态失败',
    'Instance setup required': '实例需要初始化',
    'No instance admin exists yet. Run this command in your Paperclip environment to generate the first admin invite URL:': '当前还没有实例管理员。请在你的 Paperclip 环境中执行下面这条命令，生成首个管理员邀请链接：',
    'New Company': '新建公司',
    'New Agent': '新建智能体',
    'New Goal': '新建目标',
    'New goal': '新建目标',
    'New sub-goal': '新建子目标',
    'New issue': '新建问题',
    'Add Project': '添加项目',
    'Add Goal': '添加目标',
    'Add a new agent': '添加新智能体',
    'Create a new agent': '创建新智能体',
    'Create your first agent to get started.': '创建你的第一个智能体即可开始。',
    'Welcome to Paperclip. Set up your first company and agent to get started.': '欢迎使用 Paperclip。先创建第一个公司和智能体即可开始。',
    'Create or select a company to view the dashboard.': '创建或选择一个公司后即可查看仪表盘。',
    'Select a company to view agents.': '请选择一个公司后查看智能体。',
    'Select a company to view projects.': '请选择一个公司后查看项目。',
    'Select a company to view issues.': '请选择一个公司后查看问题。',
    'Select a company to view goals.': '请选择一个公司后查看目标。',
    'Select a company first.': '请先选择一个公司。',
    'Select a company to view costs.': '请选择一个公司后查看成本。',
    'Select a company to view activity.': '请选择一个公司后查看动态。',
    'Select a company to view inbox.': '请选择一个公司后查看收件箱。',
    'No tasks yet.': '还没有任务。',
    'No goals yet.': '还没有目标。',
    'No projects yet.': '还没有项目。',
    'No activity yet.': '还没有动态。',
    'No cost events yet.': '还没有成本记录。',
    'No project-attributed run costs yet.': '还没有归属到项目的运行成本。',
    'Agents Enabled': '已启用智能体',
    'Tasks In Progress': '进行中的任务',
    'Month Spend': '本月花费',
    'Pending Approvals': '待审批',
    'Run Activity': '运行活动',
    'Issues by Priority': '问题优先级分布',
    'Issues by Status': '问题状态分布',
    'Success Rate': '成功率',
    'Last 14 days': '最近 14 天',
    'All': '全部',
    'Active': '活跃',
    'Paused': '已暂停',
    'Error': '异常',
    'Pending': '待处理',
    'Backlog': '积压',
    'Todo': '待办',
    'In Progress': '进行中',
    'In Review': '评审中',
    'Done': '已完成',
    'Planned': '计划中',
    'Completed': '已完成',
    'Cancelled': '已取消',
    'Critical': '紧急',
    'High': '高',
    'Medium': '中',
    'Low': '低',
    'Minimal': '极低',
    'Max': '最大',
    'Default': '默认',
    'Issue title': '问题标题',
    'Goal title': '目标标题',
    'Project name': '项目名称',
    'Add description...': '添加描述...',
    'Assignee': '负责人',
    'Project': '项目',
    'Model': '模型',
    'Default model': '默认模型',
    'Thinking effort': '思考强度',
    'Enable Chrome (--chrome)': '启用 Chrome（--chrome）',
    'Use project workspace': '使用项目工作区',
    'For': '给',
    'No assignee': '无负责人',
    'Search assignees...': '搜索负责人...',
    'No assignees found.': '未找到负责人。',
    'Search models...': '搜索模型...',
    'Search...': '搜索...',
    'No parent': '无上级目标',
    'All goals already selected.': '所有目标都已选择。',
    'Target date': '目标日期',
    'Failed to create project.': '创建项目失败。',
    'Create project': '创建项目',
    'Create goal': '创建目标',
    'Create sub-goal': '创建子目标',
    'Create Issue': '创建问题',
    'Create issue': '创建问题',
    'Creating...': '创建中...',
    'Creating…': '创建中…',
    'Discard Draft': '丢弃草稿',
    'Start date': '开始日期',
    'Due date': '截止日期',
    'Where will work be done on this project?': '这个项目的工作将在哪里进行？',
    'Add local folder and/or GitHub repo workspace hints.': '添加本地目录和/或 GitHub 仓库工作区提示。',
    'Use a full path on this machine.': '请填写这台机器上的完整路径。',
    'Paste a GitHub URL.': '粘贴一个 GitHub 地址。',
    'Configure local + repo hints.': '同时配置本地目录和仓库提示。',
    'Local folder (full path)': '本地目录（完整路径）',
    'GitHub repo URL': 'GitHub 仓库地址',
    'By Agent': '按智能体',
    'By Project': '按项目',
    'Filter by type': '按类型筛选',
    'All types': '全部类型',
    'Category': '分类',
    'All categories': '全部分类',
    'My recent issues': '我最近处理的问题',
    'Join requests': '加入申请',
    'Failed runs': '失败运行',
    'Alerts': '提醒',
    'Stale work': '滞后工作',
    'Approval status': '审批状态',
    'All approval statuses': '全部审批状态',
    'Needs action': '待处理',
    'Resolved': '已处理',
    'Dismiss': '忽略',
    'View inbox': '查看收件箱',
    'View agent': '查看智能体',
    'View run': '查看运行',
    'timed out': '超时',
    'title changed': '标题已变更',
    'description changed': '描述已变更',
    'A new join request is waiting for approval.': '有新的加入申请等待审批。',
    'Name': '名称',
    'Agent name': '智能体名称',
    'Title': '头衔',
    'e.g. VP of Engineering': '例如：工程副总裁',
    'Capabilities': '能力说明',
    'Describe what this agent can do...': '描述这个智能体能做什么...',
    'Adapter type': '适配器类型',
    'Working directory': '工作目录',
    'Prompt Template': '提示词模板',
    'Command': '命令',
    'Bootstrap prompt (first run)': '初始化提示（首次运行）',
    'Optional initial setup prompt for the first run': '首次运行时可选的初始化提示',
    'Extra args (comma-separated)': '附加参数（逗号分隔）',
    'e.g. --verbose, --foo=bar': '例如：--verbose, --foo=bar',
    'Environment variables': '环境变量',
    'Timeout (sec)': '超时时间（秒）',
    'Interrupt grace period (sec)': '中断宽限期（秒）',
    'Heartbeat on interval': '按间隔发送心跳',
    'Run heartbeat every': '每隔多久运行一次心跳',
    'Advanced Run Policy': '高级运行策略',
    'Wake on demand': '按需唤醒',
    'Cooldown (sec)': '冷却时间（秒）',
    'Max concurrent runs': '最大并发运行数',
    'Secret name': '密钥名称',
    'Create secret from current plain value': '用当前明文值创建密钥',
    'Select a company to create secrets': '请先选择公司再创建密钥',
    'Select a company to upload images': '请先选择公司再上传图片',
    'Failed to create secret': '创建密钥失败',
    'Environment test failed': '环境测试失败',
    'Failed to load adapter models.': '加载适配器模型失败。',
    'Agent instructions file': '智能体说明文件',
    'Enable Chrome': '启用 Chrome',
    'Skip permissions': '跳过权限确认',
    'Max turns per run': '每次运行最大轮数',
    'Bypass sandbox': '绕过沙箱',
    'Enable search': '启用搜索',
    'Webhook URL': 'Webhook 地址',
    'Gateway URL': '网关地址',
    'Paperclip API URL override': '覆盖 Paperclip API 地址',
    'Session strategy': '会话策略',
    'Session key': '会话键',
    'Gateway auth token (x-openclaw-token)': '网关鉴权令牌（x-openclaw-token）',
    'OpenClaw gateway token': 'OpenClaw 网关令牌',
    'Role': '角色',
    'Scopes (comma-separated)': '作用域（逗号分隔）',
    'Wait timeout (ms)': '等待超时（毫秒）',
    'Device auth': '设备认证',
    'Close sidebar': '关闭侧边栏',
    'Mobile navigation': '移动端导航',
    'Switch to dark mode': '切换到深色模式',
    'Switch to light mode': '切换到浅色模式',
    'Company name': '公司名称',
    'The display name for your company.': '公司显示名称。',
    'Description': '描述',
    'Optional company description': '可选的公司描述',
    'Brand color': '品牌颜色',
    'Auto': '自动',
    'Saved': '已保存',
    'Require board approval for new hires': '新成员加入需要董事会审批',
    'Open Finder and navigate to the folder.': '打开 Finder 并进入该文件夹。',
    'Right-click (or Control-click) the folder.': '右键该文件夹（或按住 Control 再点按）。',
    'Hold the Option (⌥) key — "Copy" changes to "Copy as Pathname".': '按住 Option（⌥）键，此时“Copy”会变成“Copy as Pathname”。',
    'Click "Copy as Pathname", then paste here.': '点击“Copy as Pathname”，然后粘贴到这里。',
    'Open File Explorer and navigate to the folder.': '打开资源管理器并进入该文件夹。',
    'Click in the address bar at the top — the full path will appear.': '点击顶部地址栏，此时会显示完整路径。',
    'Copy the path, then paste here.': '复制该路径，然后粘贴到这里。',
    'Alternatively, hold Shift and right-click the folder, then select "Copy as path".': '或者按住 Shift 并右键文件夹，然后选择“Copy as path”。',
    'Open a terminal and navigate to the directory with cd.': '打开终端并使用 cd 进入该目录。',
    'Run pwd to print the full path.': '执行 pwd 打印完整路径。',
    'Copy the output and paste here.': '复制输出结果并粘贴到这里。',
    'In most file managers, Ctrl+L reveals the full path in the address bar.': '在大多数文件管理器中，按 Ctrl+L 可以在地址栏显示完整路径。',
    'What is this company trying to achieve?': '这家公司想达成什么目标？',
    'Research competitor pricing': '调研竞争对手定价',
    'Add more detail about what the agent should do...': '补充更多关于该智能体要做什么的细节...',
    'Test now': '立即测试',
    'Unset ANTHROPIC_API_KEY': '取消设置 ANTHROPIC_API_KEY',
    'Local Pi agent': '本地 Pi 智能体',
    'Local Cursor agent': '本地 Cursor 智能体',
    'We recommend letting your CEO handle agent setup — they know the org structure and can configure reporting, permissions, and adapters.': '我们建议让 CEO 负责智能体配置——他们更了解组织结构，也能配置汇报关系、权限和适配器。',
    'Ask the CEO to create a new agent': '让 CEO 来创建新智能体',
    'I want advanced configuration myself': '我要自己进行高级配置',
    'Back': '返回',
}

REGEX_RULES = [
    (r'^Last (\\d+) days$', '最近 {0} 天'),
    (r'^(\\d+) agents?$', '{0} 个智能体'),
    (r'^Agent ([A-Za-z0-9_-]+)$', '智能体 {0}'),
    (r'^run ([A-Za-z0-9_-]+)$', '运行 {0}'),
]


def normalize_base_path(path: str) -> str:
    value = '/' + path.strip().strip('/') if path.strip() else '/paperclip'
    return value.rstrip('/') + '/'


def build_patch_js(base_path: str) -> str:
    exact_json = json.dumps(EXACT_TRANSLATIONS, ensure_ascii=False, indent=2, sort_keys=True)
    regex_json = json.dumps(REGEX_RULES, ensure_ascii=False, indent=2)
    return f"""(() => {{
  const EXACT = {exact_json};
  const REGEX_RULES = {regex_json}.map(([pattern, template]) => [new RegExp(pattern, 'i'), template]);
  const ATTRS = ['placeholder', 'title', 'aria-label'];
  const SKIP_TAGS = new Set(['SCRIPT', 'STYLE', 'CODE', 'PRE', 'TEXTAREA']);
  const basePath = {json.dumps(base_path, ensure_ascii=False)};

  function normalize(text) {{
    return text.replace(/\\s+/g, ' ').trim();
  }}

  function translateCore(text) {{
    if (!text || !/[A-Za-z]/.test(text)) return null;
    const normalized = normalize(text);
    if (!normalized) return null;
    if (Object.prototype.hasOwnProperty.call(EXACT, normalized)) return EXACT[normalized];
    for (const [regex, template] of REGEX_RULES) {{
      const match = normalized.match(regex);
      if (!match) continue;
      return template.replace(/\\{{(\\d+)\\}}/g, (_, index) => match[Number(index) + 1] ?? '');
    }}
    if (/^(.+) · Paperclip$/.test(normalized)) {{
      const left = normalized.replace(/ · Paperclip$/, '');
      const translatedLeft = EXACT[left] || left;
      return `${{translatedLeft}} · Paperclip`;
    }}
    return null;
  }}

  function preserveWhitespace(raw, translated) {{
    const prefix = raw.match(/^\\s*/)?.[0] ?? '';
    const suffix = raw.match(/\\s*$/)?.[0] ?? '';
    return `${{prefix}}${{translated}}${{suffix}}`;
  }}

  function applyTextNode(node) {{
    if (!node || node.nodeType !== Node.TEXT_NODE) return;
    const parent = node.parentElement;
    if (parent && SKIP_TAGS.has(parent.tagName)) return;
    const raw = node.nodeValue ?? '';
    const translated = translateCore(raw);
    if (!translated) return;
    const next = preserveWhitespace(raw, translated);
    if (next !== raw) node.nodeValue = next;
  }}

  function applyElement(el) {{
    if (!(el instanceof Element)) return;
    if (SKIP_TAGS.has(el.tagName)) return;
    for (const attr of ATTRS) {{
      const raw = el.getAttribute(attr);
      if (!raw) continue;
      const translated = translateCore(raw);
      if (translated && translated !== raw) el.setAttribute(attr, translated);
    }}
  }}

  function walk(node) {{
    if (!node) return;
    if (node.nodeType === Node.TEXT_NODE) {{
      applyTextNode(node);
      return;
    }}
    if (node.nodeType !== Node.ELEMENT_NODE && node.nodeType !== Node.DOCUMENT_NODE) return;
    if (node.nodeType === Node.ELEMENT_NODE) applyElement(node);
    for (const child of node.childNodes) walk(child);
  }}

  function patchTitle() {{
    const translated = translateCore(document.title);
    if (translated && translated !== document.title) document.title = translated;
  }}

  function patchManifestLink() {{
    const manifest = document.querySelector('link[rel="manifest"]');
    if (manifest && manifest.getAttribute('href') === '/site.webmanifest') {{
      manifest.setAttribute('href', `${{basePath}}site.webmanifest`);
    }}
  }}

  let raf = 0;
  function schedule(root) {{
    if (raf) cancelAnimationFrame(raf);
    raf = requestAnimationFrame(() => {{
      raf = 0;
      walk(root || document.body || document.documentElement);
      patchTitle();
      patchManifestLink();
    }});
  }}

  schedule(document.documentElement);
  document.addEventListener('DOMContentLoaded', () => schedule(document.documentElement), {{ once: true }});
  window.addEventListener('load', () => schedule(document.documentElement), {{ once: true }});

  const observer = new MutationObserver((mutations) => {{
    for (const mutation of mutations) {{
      if (mutation.type === 'characterData') {{
        applyTextNode(mutation.target);
        continue;
      }}
      if (mutation.type === 'attributes') {{
        applyElement(mutation.target);
        continue;
      }}
      for (const node of mutation.addedNodes) walk(node);
    }}
    patchTitle();
  }});

  observer.observe(document.documentElement, {{
    subtree: true,
    childList: true,
    characterData: true,
    attributes: true,
    attributeFilter: ATTRS,
  }});

  window.__paperclipZhPatchVersion = '2026-03-09';
}})();
"""


def inject_index(index_path: Path, script_src: str) -> bool:
    text = index_path.read_text(encoding='utf-8')
    if script_src in text:
        updated = text
    else:
        module_match = re.search(r'<script\s+type="module"[^>]*src="[^"]+"[^>]*></script>', text)
        if not module_match:
            raise SystemExit(f'failed to find module script in {index_path}')
        injection = f'    <script defer src="{script_src}"></script>\n'
        updated = text[:module_match.start()] + injection + text[module_match.start():]
    updated = updated.replace('<title>Paperclip</title>', '<title>Paperclip 控制台</title>')
    if updated != text:
        index_path.write_text(updated, encoding='utf-8')
        return True
    return False


def patch_manifest(manifest_path: Path) -> bool:
    if not manifest_path.exists():
        return False
    text = manifest_path.read_text(encoding='utf-8')
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return False
    changed = False
    for key, value in {'name': 'Paperclip 控制台', 'short_name': 'Paperclip', 'description': 'AI 项目管理与智能体协同控制台'}.items():
        if data.get(key) != value:
            data[key] = value
            changed = True
    if changed:
        manifest_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return changed


def main() -> None:
    parser = argparse.ArgumentParser(description='Patch Paperclip ui-dist with Chinese UI overlay.')
    parser.add_argument('--ui-dist', default=str(DEFAULT_UI_DIST), help='Paperclip ui-dist directory')
    parser.add_argument('--public-base-path', default=DEFAULT_PUBLIC_BASE_PATH, help='Public base path, e.g. /paperclip/')
    args = parser.parse_args()

    ui_dist = Path(args.ui_dist).expanduser().resolve()
    if not ui_dist.exists():
        raise SystemExit(f'ui-dist not found: {ui_dist}')
    index_path = ui_dist / 'index.html'
    if not index_path.exists():
        raise SystemExit(f'index.html not found: {index_path}')

    base_path = normalize_base_path(args.public_base_path)
    patch_path = ui_dist / PATCH_FILENAME
    patch_path.write_text(build_patch_js(base_path), encoding='utf-8')
    inject_index(index_path, f'{base_path}{PATCH_FILENAME}')
    patch_manifest(ui_dist / 'site.webmanifest')
    print(json.dumps({
        'ui_dist': str(ui_dist),
        'patch_file': str(patch_path),
        'public_base_path': base_path,
        'index_injected': True,
    }, ensure_ascii=False))


if __name__ == '__main__':
    main()
