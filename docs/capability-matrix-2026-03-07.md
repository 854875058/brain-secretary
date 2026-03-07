# 8 类能力落地清单

更新时间：2026-03-07

本文记录“大脑秘书系统”针对 8 类能力的当前落地状态，优先区分：

- 已有基础
- 本轮新增最小可用版本
- 暂未完全落地的原因

---

## 1. 网页转 Markdown

### 当前状态
- **本轮新增最小版本**

### 已落地内容
- 新增脚本：`scripts/web_to_markdown.py`
- 新增本地 skill：`/root/.openclaw/workspace/skills/web-to-markdown/SKILL.md`
- 归档目录约定：`archives/web/`

### 触发方式
- 让 agent 执行：`python3 scripts/web_to_markdown.py <URL>`

### 验证
- 可对公开 URL 运行，脚本会输出生成的 `.md` 文件路径
- 当前仅做基础 HTML 提取，不保证对强 JS 页面有效

### 风险
- 不带浏览器渲染
- 不做登录态页面抓取
- Markdown 保真度有限

---

## 2. QQ 媒体中枢（图/语音/视频/文件发送）

### 当前状态
- **已有基础，且本轮补成本地 skill 入口**

### 已有基础
- QQBot 官方 skill：`qqbot-media`
- workspace skill：`send-image`
- 仓库测试素材：
  - `qq-bot/data/openclaw-test-image.png`
  - `qq-bot/data/openclaw-test-voice.wav`
  - `qq-bot/data/openclaw-test-video.mp4`
  - `qq-bot/data/openclaw-test-file.txt`

### 本轮新增
- 本地 skill：`/root/.openclaw/workspace/skills/qq-media-hub/SKILL.md`

### 触发方式
- QQ 通道回复时输出：
  - `<qqimg>...</qqimg>`
  - `<qqvoice>...</qqvoice>`
  - `<qqvideo>...</qqvideo>`
  - `<qqfile>...</qqfile>`

### 验证
- 已验证：本地测试素材文件存在
- 未在本轮做真实 QQ 端到端实发验证

### 风险
- 端到端表现仍依赖 qqbot 渠道与客户端兼容性
- 路径或 URL 不可达时会发送失败

---

## 3. 多模态读取（读图/读文件/读语音/读视频）

### 当前状态
- **已有基础，部分已真实落地，部分仍是最小版本**

### 已有基础
- `qq-bot/bot/media_context.py`
  - 图片：保存 + OCR（tesseract / NapCat OCR）
  - 文件：下载 + 文本摘录
  - 语音：拉取 wav 文件
  - 视频：记录链接/下载文件

### 本轮新增
- 本地 skill：`/root/.openclaw/workspace/skills/multimodal-intake/SKILL.md`

### 验证
- 已验证：本机存在 `tesseract`、`ffmpeg`
- 代码层面确认图片 OCR / 文件摘录可运行
- 语音转写：**当前未配置自动 ASR 后端**
- 视频理解：**当前未配置自动视频理解后端**

### 风险
- 语音/视频目前更多是“取回文件 + 留路径/元数据”，不是完整理解

---

## 4. 运维巡检

### 当前状态
- **已有真实实现，本轮补本地 skill 封装**

### 已有基础
- `scripts/ops_manager.py`
- `qq-bot/bot/ops_patrol.py`
- 真源：`ops/deployment_manifest.json`

### 本轮新增
- 本地 skill：`/root/.openclaw/workspace/skills/ops-patrol/SKILL.md`

### 触发方式
- 询问：巡检、健康检查、状态检查、看端口、看日志
- 或执行：
  - `python3 scripts/ops_manager.py info`
  - `python3 scripts/ops_manager.py status all`
  - `python3 scripts/ops_manager.py ports all`

### 验证
- 本轮已执行基础命令验证脚本可用

### 风险
- 某些历史 bridge 相关日志分支仍偏旧实现语境

---

## 5. 故障自诊断

### 当前状态
- **本轮补了最小规则化版本；底层能力依赖现有巡检与日志体系**

### 本轮新增
- 本地 skill：`/root/.openclaw/workspace/skills/fault-self-diagnosis/SKILL.md`

### 依赖基础
- `scripts/ops_manager.py`
- `qq-bot/bot/ops_patrol.py`
- 现有部署文档与 manifest

### 验证
- 已验证诊断链路所需的状态/端口检查命令存在
- 未单独构建自动根因分析引擎

### 风险
- 目前更像“规则化诊断 SOP + 证据化检查”，不是自动专家系统

---

## 6. 子 agent 协调增强

### 当前状态
- **已有基础，本轮补本地 skill 收敛规则**

### 已有基础
- `CLAUDE.md` / `HANDOVER.md` 已明确：
  - `qq-main` 负责协调
  - `brain-secretary-dev` / `agent-hub-dev` 负责工程实施
- `qq-bot/bot/task_sync.py` 已有任务清单/能力清单同步逻辑

### 本轮新增
- 本地 skill：`/root/.openclaw/workspace/skills/subagent-coordination/SKILL.md`

### 验证
- 已验证文档和同步代码中存在协调、回推、能力匹配相关实现
- 未在本轮额外发起复杂多子 agent 压测

### 风险
- 真实协同质量仍依赖主 agent 的拆单与验收习惯

---

## 7. 部署变更同步

### 当前状态
- **已有明确规则，本轮补成本地 skill**

### 已有基础
- `AGENTS.md`、`CLAUDE.md` 都明确要求：部署事实变更要同步多个文档与 manifest

### 本轮新增
- 本地 skill：`/root/.openclaw/workspace/skills/deployment-sync/SKILL.md`

### 必同步文件
- `CLAUDE.md`
- `HANDOVER.md`
- `SETUP.md`
- `docs/systemd-ops.md`
- `docs/openclaw-setup.md`
- `ops/deployment_manifest.json`

### 验证
- 已验证上述规则已在仓库文档中存在，并补充了 workspace skill 触发入口

### 风险
- 仍依赖执行者真的按规则同步；暂未做自动 diff 审核器

---

## 8. 内容沉淀 / 归档

### 当前状态
- **已有基础，本轮补了归档 skill 和网页归档最小脚本**

### 已有基础
- `MEMORY.md`
- `memory/`
- `qq-bot/bot/chat_history.py`

### 本轮新增
- 本地 skill：`/root/.openclaw/workspace/skills/content-archive/SKILL.md`
- 归档脚本：`scripts/web_to_markdown.py`
- 归档目录：`archives/web/`

### 触发方式
- 让 agent 把网页/结论写入：
  - `archives/web/`
  - `memory/YYYY-MM-DD.md`
  - `MEMORY.md`

### 验证
- 已验证目录与脚本可本地落地文件

### 风险
- 会话总结/自动归档目前仍偏手动触发，不是完整自动流水线

---

## 总结

### 本轮实际做成的项
- **8/8 都有落地点**，但成熟度不同：
  - **已有较完整基础**：2 / 3 / 4 / 6 / 7 / 8
  - **本轮补了最小可用版本**：1 / 5

### 暂时做不到或未完全闭环的点
- 语音自动转写：当前无本地 ASR 后端
- 视频自动理解：当前无视频理解后端
- 网页转 Markdown 对强 JS 页保真有限
- QQ 媒体发送未在本轮做真实端到端 QQ 实发

### 建议后续优先级
1. 给多模态补一个本地 ASR（Whisper 或 API）
2. 给视频补关键帧提取 + OCR/摘要
3. 给部署同步补自动比对检查器
4. 给归档补“会话结论自动沉淀”流程
