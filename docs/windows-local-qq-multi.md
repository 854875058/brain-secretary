# Windows 本地三开 QQ / NapCat 对接远端大脑

> 文档: `docs/windows-local-qq-multi.md`
> 更新: 2026-03-07

---

## 适用场景

当云服务器扫码登录 QQ 经常触发“网络环境复杂 / 同一网络后重扫”的风控时，推荐把 **QQ + NapCat** 放回你自己的 Windows 电脑，本地扫码登录；服务器继续跑 OpenClaw 和 3 个远端桥接。

这样做的目标是：

- 扫码发生在你的常用设备上，减少异地风控
- 服务器继续保留 `qq-main / brain-secretary-dev / brain-secretary-review` 三个 agent
- 你既可以直接找 3 个 QQ 号，也可以继续只找大脑号，让它内部委派

---

## 推荐拓扑

```text
Windows 本地:
  QQ(instance) + NapCat(instance)
      -> HTTP POST -> Server Bridge(instance)

服务器:
  QQ Bridge(instance) -> OpenClaw(target agent)
```

默认映射：

- `brain` / 大脑号 -> `qq-main`
- `tech` / 技术号 -> `brain-secretary-dev`
- `review` / 方案验收号 -> `brain-secretary-review`

---

## 前置条件

### Windows 本地

- 已安装 QQ / NapCat
- 已安装 Git
- 建议安装 `Tailscale`
- 本地 AI 能执行 PowerShell 脚本

### 服务器

- 已拉取当前仓库最新代码
- 已安装并运行 OpenClaw / model proxy / gateway
- 能执行 `python3 scripts/qq_bot_multi.py ...`

---

## Windows 侧步骤

### 0) 更省事的入口

如果你懒得敲命令，直接双击：

```bat
scripts\windows_local_qq_quick_setup.bat
```

它会提示你输入服务器地址，并自动调用 `scripts/windows_local_qq_multi.ps1`。

配完 3 个本地 NapCat 之后，再双击：

```bat
scripts\windows_local_qq_doctor.bat
```

或者直接双击输出目录里的 `run-doctor.bat` 做自检。

如果你本机能 SSH 到服务器，后面还可以直接双击输出目录里的 `apply-remote.bat` 自动上传并应用。

### 1) 克隆仓库

```powershell
git clone <你的仓库地址>
cd brain-secretary
```

### 2) 让本地 AI 生成三开配置脚手架

```powershell
powershell -ExecutionPolicy Bypass -File scripts/windows_local_qq_multi.ps1 `
  -ServerBridgeHost <服务器的 Tailscale IP 或可达主机名>
```

如果自动识别不到你本机的 Tailscale IPv4，再手动补：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/windows_local_qq_multi.ps1 `
  -ServerBridgeHost <服务器 Host> `
  -LocalNapCatHost <你电脑的 Tailscale IPv4>
```

脚本会生成：

- `~/brain-secretary-local-qq/instances/brain/onebot11.json`
- `~/brain-secretary-local-qq/instances/tech/onebot11.json`
- `~/brain-secretary-local-qq/instances/review/onebot11.json`
- `~/brain-secretary-local-qq/server-bridge-profile.json`
- `~/brain-secretary-local-qq/README.local.md`
- `~/brain-secretary-local-qq/run-doctor.bat`
- `~/brain-secretary-local-qq/open-output.bat`
- `~/brain-secretary-local-qq/apply-remote.bat`

### 3) 把 3 份 `onebot11.json` 放进本地 3 个 NapCat 实例

你本地 AI 需要做的是：

- `brain` 实例使用 `brain/onebot11.json`
- `tech` 实例使用 `tech/onebot11.json`
- `review` 实例使用 `review/onebot11.json`

这 3 个实例分别登录 3 个不同的 QQ 号。

### 4) 本地登录并确认端口

最省事的方式是直接运行：

```bat
run-doctor.bat
```

或者在仓库里执行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/windows_local_qq_doctor.ps1 `
  -ServerBridgeHost <服务器 Host>
```

本地确认这 3 个 OneBot HTTP 端口可用：

- `3001`
- `3002`
- `3003`

---

## 服务器侧步骤

### 0) 如果你本机能 SSH 到服务器

可以直接运行：

```bat
apply-remote.bat
```

它会调用仓库里的 `scripts/windows_local_qq_remote_apply.ps1`，自动上传 `server-bridge-profile.json` 并在服务器执行导入 / 重启 / 状态检查。

### 1) 把 Windows 生成的 `server-bridge-profile.json` 复制到服务器仓库

建议放到：

- `ops/windows-local-qq-profile.json`

### 2) 导入 profile 并重启 3 条桥接

```bash
cd /root/brain-secretary
python3 scripts/qq_bot_multi.py import-profile --profile ops/windows-local-qq-profile.json --json
python3 scripts/qq_bot_multi.py restart --json
python3 scripts/qq_bot_multi.py status --json
```

导入后，服务器侧桥接会变成：

- 监听 `0.0.0.0:8011/8012/8013`
- 回调本地 Windows 的 `NapCatHost:3001/3002/3003`

---

## 核心脚本

- Windows 一键入口：`scripts/windows_local_qq_quick_setup.bat`
- Windows 脚手架：`scripts/windows_local_qq_multi.ps1`
- Windows 自检脚本：`scripts/windows_local_qq_doctor.ps1`
- Windows 自检批处理：`scripts/windows_local_qq_doctor.bat`
- Windows 远程应用脚本：`scripts/windows_local_qq_remote_apply.ps1`
- 服务器多桥接：`scripts/qq_bot_multi.py`

`qq_bot_multi.py` 现在支持：

- 默认本机模式：`napcat_host=127.0.0.1`
- 远端 Windows 模式：通过 `import-profile` 导入 `bridge_host` / `napcat_host`
- 输出示例 profile：`python3 scripts/qq_bot_multi.py print-example`

---

## 验证方法

### 服务器验证桥接状态

```bash
python3 scripts/qq_bot_multi.py status --json
```

### Windows 本地自检

```powershell
powershell -ExecutionPolicy Bypass -File scripts/windows_local_qq_doctor.ps1 `
  -ServerBridgeHost <服务器 Host>
```

### 主脑验证委派认知

```bash
openclaw agent --agent qq-main --session-id qq-main-routing-check \
  --message '现在只回答这一行：工程实施->哪个agent；方案验收->哪个agent' \
  --thinking minimal --timeout 45 --json
```

预期：

- `工程实施 -> brain-secretary-dev`
- `方案验收 -> brain-secretary-review`

---

## 建议

- 优先用 `Tailscale`，不要直接把本地 NapCat 端口裸露到公网
- 如果你电脑 IP 变了，重新运行 `windows_local_qq_quick_setup.bat` 或 `windows_local_qq_multi.ps1`，再把新 profile 导入服务器
- 配完本地 3 个 NapCat 以后，先跑 `run-doctor.bat` / `windows_local_qq_doctor.bat` 再排障，会省很多事
- 先让本地 AI 起一个 `brain` 实例也行；确认稳定后再补 `tech / review`
