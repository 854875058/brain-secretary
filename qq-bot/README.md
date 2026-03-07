# QQ Bridge（OpenClaw）

基于 NapCat + FastAPI + **OpenClaw** 的 QQ Bridge：

- NapCat 负责把 QQ 消息推送出来（OneBot 11）
- 本服务负责把消息转发给 `openclaw agent --session-id ...`（具备会话/记忆）
- 再把回复通过 NapCat API 发回 QQ

## 功能

1. **AI 对话**
   - 私聊直接对话
   - 群聊 @bot 触发对话
   - 默认走 OpenClaw（推荐），具备 session 级记忆

2. **远程指令执行**
   - `/status` - 查看服务器 CPU 状态
   - `/disk` - 查看磁盘使用情况
   - `/crawl` - 启动爬虫脚本
   - `/logs` - 查看最近日志
   - `/help` - 显示帮助信息

3. **定时推送**
   - 每天 9:00 推送爬虫统计

## 部署步骤

### 1. 安装依赖

```bash
cd qq-bot
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 2. 配置 NapCat

1. 下载 NapCat Windows 版本
2. 解压并运行 `napcat.exe`
3. 扫码登录 QQ
4. 编辑 `config/onebot11.json`：

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
  }
}
```

### 3. 修改配置

编辑 `config.yaml`，将 `admin.qq_number` 改为你的 QQ 号

### 4. 启动服务

```bash
python main.py
```

## 测试

- 私聊 bot："你好"
- 群聊 @bot："介绍一下你自己"
- 发送指令："/help"

## 目录结构

```
qq-bot/
├── main.py                 # 主程序
├── config.yaml             # 配置文件
├── requirements.txt        # 依赖
├── bot/
│   ├── ai_client.py        # AI 对话
│   ├── qq_sender.py        # QQ 消息发送
│   ├── command_handler.py  # 指令执行
│   └── scheduler.py        # 定时任务
└── logs/                   # 日志目录
```
