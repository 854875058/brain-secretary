# 子 Agent 模块

> 说明：2026-03-07 起，现网已经落地 `qq-main` 协调大脑 + `brain-secretary-dev` 真实子 agent。具体以 `README.md`、`docs/openclaw-setup.md`、`HANDOVER.md` 为准。


> 目录: agents/
> 状态: 规划中

---

## 现有项目 → Agent 映射

| Agent 名称 | 负责任务 | 对应现有目录 | 状态 |
|-----------|---------|------------|------|
| dataset-agent | PDF/Word/PPT 转换 | PDF-Excel, PDF-PPT, PDF转md, Word-Excel 等 | 待封装 |
| crawler-agent | 数据爬取、Token统计 | 现有爬虫脚本 | 待封装 |
| doc-agent | 文档读写处理 | 读取doc文件, Word、PDF、PPT-TXT | 待封装 |
| ragflow-agent | RAG 知识库操作 | ragflow/ | 待封装 |

---

## Agent 接口规范

每个 Agent 需要实现以下接口：

### 接收任务

```
POST /task
{
  "task_id": "uuid",
  "type": "任务类型",
  "params": {},
  "callback_url": "大脑回调地址"
}
```

### 汇报结果

```
POST <callback_url>
{
  "task_id": "uuid",
  "status": "success" | "failed",
  "result": {},
  "error": "错误信息（如果失败）"
}
```

---

## 待开发

- [ ] 为每个现有项目封装统一接口
- [ ] 编写各 Agent 的启动脚本
- [ ] 定义每类任务的输入/输出规范
