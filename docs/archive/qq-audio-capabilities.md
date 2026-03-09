# QQ Bridge 音频能力说明

更新时间：2026-03-07

## 1. 当前语音发送链路

现有链路：

```text
OpenClaw / 主 agent 输出指令
  -> qq-bot/main.py 提取媒体指令
  -> bot/qq_sender.py 组装 NapCat OneBot 消息段
  -> record 段发送给 NapCat
  -> QQ 展示为语音消息
```

已支持的原始语音指令：

```text
[[send_voice]] file:///绝对路径/xxx.wav
```

桥接内部会转成：

```json
{"type": "record", "data": {"file": "file:///..."}}
```

### 为什么之前测试音频可能“有发送但无声”

已检查仓库里的测试素材：`qq-bot/data/openclaw-test-voice.wav`

- 格式：WAV / PCM s16le
- 声道：mono
- 采样率：16000 Hz
- 时长：约 1.2 秒
- 音量：`mean_volume -9.2 dB`，不属于静音文件

结论：**仓库里的测试 WAV 本身不是静音**。

更可能的原因有三类：

1. **NapCat / QQ 对本地 `record` 文件兼容性问题**
   - 某些格式虽然能发出，但 QQ 端转码或播放异常
2. **语音过短，听感像“没声”**
   - 1.2 秒的测试音频太短，且内容不明显时，容易误判
3. **QQ 客户端侧缓存 / 播放异常**
   - 消息能到达，但终端未正常解码或未自动下载

所以这次我补了第二层：**桥接层现合成 TTS**，方便用“明显有内容的语音”验证整条链路。

---

## 2. 已落地：`[[send_tts]]`

现在主 agent 可以直接输出：

```text
[[send_tts]] 你好，我是大脑秘书
```

桥接会自动：

1. 用本机 `ffmpeg + flite` 合成语音
2. 生成到目录：`qq-bot/data/generated_tts/`
3. 输出为 `16k / mono / pcm_s16le wav`
4. 再按现有 `record` 语音链路发送到 QQ

### 触发格式

推荐：

```text
[[send_tts]] 你好，我是大脑秘书
```

也支持行内形式：

```text
[[send_tts:你好，我是大脑秘书]]
```

### 何时用 `send_tts`，何时用 `send_voice`

- 已有现成音频文件：用 `[[send_voice]]`
- 只有一段文字，想直接发语音：用 `[[send_tts]]`

---

## 3. 本地依赖

当前最小可用实现依赖：

- `ffmpeg`
- `ffmpeg` 已编入 `flite` filter（本机已确认存在）

优点：

- 不新增 Python 三方依赖
- 不需要外部 API key
- 可在当前 Linux 环境直接落地

限制：

- `flite` 英文效果最好，中文可用性有限
- 对中文文本，实际发音质量不如 Edge TTS / 商业 TTS

因此当前实现定位是：**最小可用、真实可发、便于联调验证**。

---

## 4. 建议主 agent 用法

如果用户明确要“给我发一段语音”，主 agent 可以直接输出：

```text
[[send_tts]] 你好，我是大脑秘书，现在帮你测试 QQ 语音链路。
```

如果用户要发已有文件语音：

```text
[[send_voice]] file:///root/brain-secretary/qq-bot/data/openclaw-test-voice.wav
```

---

## 5. 唱歌 / 音乐生成结论

当前状态：**暂不建议直接在本项目里硬接正式版唱歌能力**。

原因：

1. **当前环境没有低成本本地音乐生成依赖**
   - 无现成 Bark / AudioCraft / SoVITS / RVC / DiffSinger 等模型环境
   - 也没有 torch / numpy / scipy 这类常见音频生成栈
2. **生成质量与资源需求不匹配当前桥接层定位**
   - `qq-bot` 当前主要职责是桥接，不适合直接背大型生成模型
3. **“唱歌”比 TTS 多一层旋律、伴奏、人声风格与时长控制**
   - 要真落地，至少要补模型、推理资源、缓存策略、输出格式治理
4. **无外部 API 的前提下，很难低成本做出稳定可用结果**

### 目前务实建议

分两步：

#### 路线 A：先不做真正唱歌，只做“朗读/拟播报”

- 先靠 `[[send_tts]]` 覆盖“发有声内容”诉求
- 对很多“来段语音”场景已经够用

#### 路线 B：后续如要真做唱歌，建议独立成外部音频服务

建议不要塞进 `qq-bot` 主进程，而是单独做一个：

- 输入：歌词 / 风格 / 时长 / 是否清唱
- 输出：可下载 WAV/MP3 文件
- 再由 `qq-bot` 用 `[[send_voice]]` 或 `[[send_file]]` 转发

这样更稳，也更容易替换底层模型。

### 最小实验入口（当前不建议默认开启）

如果后续一定要先做实验版，建议只做下面这种轻量接口：

```text
[[send_voice]] file:///path/to/generated-song-demo.wav
```

也就是：

- 音乐生成交给外部脚本 / 独立服务
- 桥接层只负责发送结果

这比把音乐生成直接塞进 `qq-bot` 更现实。
