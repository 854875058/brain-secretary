# NapCat 配置与问题排查

> 文档: docs/napcat-setup.md
> 更新: 2026-03-06

---

## NapCat 基本信息

| 项目 | 说明 |
|------|------|
| 安装路径 | D:\NapCat\ |
| QQ 路径 | D:\QQ\QQ.exe |
| 启动方式 | Hook 注入模式 |
| 协议 | OneBot 11 |

---

## 当前 Linux 无头运行方式（2026-03-06）

当前在线环境采用：

- 启动脚本：`/root/Napcat/start-qq.sh`
- `systemd` Unit：`napcat-qq.service`
- 管理命令：`systemctl --user start|stop|restart napcat-qq.service`

关键文件：

- 日志：`/root/Napcat/qq.log`
- 二维码：`/root/Napcat/opt/QQ/resources/app/app_launcher/napcat/cache/qrcode.png`

如果是在 Linux 服务器上维护，请优先阅读：`docs/systemd-ops.md`

---

## 启动命令

```bash
D:\NapCat\NapCatWinBootMain.exe D:\QQ\QQ.exe D:\NapCat\NapCatWinBootHook.dll
```

或者在 NapCat 目录下：

```bash
NapCatWinBootMain.exe "D:\QQ\QQ.exe" --enable-logging
```

---

## 已知问题：QQ 登录提示"文件损坏，请重新安装"

### 症状

NapCat 启动后 QQ 登录界面显示：
**"文件损坏，请重新安装QQ"**

### 原因

NapCat 通过 Hook DLL 注入 QQ 进程，QQ 的文件完整性校验检测到文件被修改，触发此提示。

### 解决方法（按顺序尝试）

**方法一：清理进程后重启（最常用）**

```bash
# 在管理员 CMD 中运行
taskkill /f /im QQ.exe
taskkill /f /im NapCatWinBootMain.exe
# 等待 5 秒后重新启动
```

**方法二：清理 QQ 缓存**

删除以下文件（不影响聊天记录）：
- `C:\Users\Administrator\AppData\Roaming\Tencent\QQ\` 下的 `Misc.db`
- `D:\QQ\` 下的 `crashes\` 文件夹
- `D:\QQ\` 下的 `logs\` 文件夹

**方法三：使用 NapCat 推荐的 QQ 版本**

NapCat 只支持特定版本的 QQ，版本不匹配会导致此问题。
检查 NapCat 官方文档确认兼容的 QQ 版本：
https://napcat.napneko.icu/

**方法四：修复 QQ 安装**

用 QQ 官方安装包执行"修复安装"（不是完全重装）。

### 注意

- **不要完全重装 QQ**，修复安装即可
- 重装后还需确认 NapCat 版本与 QQ 版本匹配

---

## NapCat 配置 OneBot 11（推送到 QQ Bridge → OpenClaw）

配置文件路径：`D:\NapCat\config\onebot11_<QQ号>.json`

```json
{
  "http": {
    "enable": true,
    "host": "0.0.0.0",
    "port": 3000,
    "post": [
      {
        "url": "http://127.0.0.1:8000/qq/message",
        "secret": ""
      }
    ]
  },
  "ws": {
    "enable": false
  }
}
```

---

## NapCat 日志位置

```
D:\NapCat\logs\
```

Linux 当前实际位置：

```bash
/root/Napcat/qq.log
```

---

## Linux 常见排查

### `qq-bot` 报 `All connection attempts failed`

优先检查：

- QQ 是否已经扫码登录完成
- `napcat-qq.service` 是否在运行
- `qq-bot/config.yaml` 里的 `napcat.url` 是否仍指向 `http://127.0.0.1:3000`

排查命令：

```bash
systemctl --user status napcat-qq.service
tail -f /root/Napcat/qq.log
ss -lntp | rg ':3000 |:6099 '
```

### 没法直接看终端二维码

直接打开二维码图片：

```bash
/root/Napcat/opt/QQ/resources/app/app_launcher/napcat/cache/qrcode.png
```
