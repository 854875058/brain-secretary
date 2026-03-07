import json
import aiosqlite
import logging
from datetime import datetime
from bot.runtime_paths import TASK_DB_PATH

logger = logging.getLogger(__name__)

DB_PATH = str(TASK_DB_PATH)

CAPABILITY_CHECKLIST_ITEMS = [
    {
        "item_key": "cap_send_image",
        "title": "发图片",
        "detail": "QQ 里可直接发送图片，不再只回链接。",
        "status": "done",
        "sort_index": 10,
        "assigned_agent": "brain-secretary-dev",
        "owner_agent": "qq-main",
        "category": "capability",
        "validation": "已通过 QQ 实发测试图验证。",
    },
    {
        "item_key": "cap_send_file",
        "title": "发文件",
        "detail": "打通 QQ 文件消息发送链路，并做真实端到端验证。",
        "status": "implemented_pending_verify",
        "sort_index": 20,
        "assigned_agent": "brain-secretary-dev",
        "owner_agent": "qq-main",
        "category": "capability",
        "validation": "桥接层已支持 file 消息段，待 QQ 端到端验证。",
    },
    {
        "item_key": "cap_send_voice",
        "title": "发语音",
        "detail": "打通 QQ 语音/record 消息发送链路，并做真实端到端验证。",
        "status": "implemented_pending_verify",
        "sort_index": 30,
        "assigned_agent": "brain-secretary-dev",
        "owner_agent": "qq-main",
        "category": "capability",
        "validation": "桥接层已支持 record 消息段，待 QQ 端到端验证。",
    },
    {
        "item_key": "cap_send_video",
        "title": "发视频",
        "detail": "打通 QQ 视频消息发送链路，并做真实端到端验证。",
        "status": "implemented_pending_verify",
        "sort_index": 40,
        "assigned_agent": "brain-secretary-dev",
        "owner_agent": "qq-main",
        "category": "capability",
        "validation": "桥接层已支持 video 消息段，待 QQ 端到端验证。",
    },
    {
        "item_key": "cap_read_multimodal",
        "title": "读图 / 读文件 / 读语音 / 读视频",
        "detail": "支持解析 QQ 多模态输入并路由到合适工具或模型。",
        "status": "pending",
        "sort_index": 50,
        "assigned_agent": "brain-secretary-dev",
        "owner_agent": "qq-main",
        "category": "capability",
        "validation": "暂无稳定解析与验证结果。",
    },
    {
        "item_key": "cap_ops_patrol",
        "title": "运维巡检",
        "detail": "一句话触发 OpenClaw / qq-bot / NapCat / nginx / 端口 / 反代 / 日志巡检。",
        "status": "in_progress",
        "sort_index": 60,
        "assigned_agent": "brain-secretary-dev",
        "owner_agent": "qq-main",
        "category": "capability",
        "validation": "已有 ops_manager.py 与 /report 基础，待整合成稳定 QQ 技能。",
    },
    {
        "item_key": "cap_subagent_coordination",
        "title": "子 Agent 协调增强",
        "detail": "支持可追踪派单、异步完成回推、完成一件汇报一件。",
        "status": "in_progress",
        "sort_index": 70,
        "assigned_agent": "qq-main",
        "owner_agent": "qq-main",
        "category": "capability",
        "validation": "已定位异步回推缺口并开始修复。",
    },
    {
        "item_key": "cap_message_diag_enhancement",
        "title": "其余消息 / 诊断 / 落地增强项",
        "detail": "包括网页转 Markdown、故障自诊断、部署变更同步、QQ 消息增强等。",
        "status": "in_progress",
        "sort_index": 80,
        "assigned_agent": "brain-secretary-dev",
        "owner_agent": "qq-main",
        "category": "capability",
        "validation": "已形成参考调研与部分页面/规则改进，待继续落地。",
    },
]


async def init_db():
    """初始化数据库"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project TEXT NOT NULL,
                prompt TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                result TEXT,
                created_at TEXT,
                finished_at TEXT,
                user_qq INTEGER
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS projects (
                name TEXT PRIMARY KEY,
                path TEXT NOT NULL,
                description TEXT
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS checklist_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_key TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                detail TEXT,
                status TEXT DEFAULT 'pending',
                sort_index INTEGER DEFAULT 0,
                assigned_agent TEXT,
                owner_agent TEXT,
                category TEXT,
                source TEXT,
                user_qq INTEGER,
                group_id INTEGER,
                chat_type TEXT DEFAULT 'private',
                notes TEXT,
                validation TEXT,
                created_at TEXT,
                updated_at TEXT,
                finished_at TEXT
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS bridge_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS async_deliveries (
                delivery_key TEXT PRIMARY KEY,
                transcript_message_id TEXT,
                transcript_path TEXT,
                target_chat_type TEXT,
                target_user_qq INTEGER,
                target_group_id INTEGER,
                content TEXT,
                delivered_at TEXT
            )
            """
        )
        await db.commit()
    logger.info("数据库初始化完成")


async def add_task(project: str, prompt: str, user_qq: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO tasks (project, prompt, status, created_at, user_qq) VALUES (?, ?, 'pending', ?, ?)",
            (project, prompt, datetime.now().isoformat(), user_qq),
        )
        await db.commit()
        return cursor.lastrowid


async def update_task(task_id: int, status: str, result: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        if result is not None:
            await db.execute(
                "UPDATE tasks SET status=?, result=?, finished_at=? WHERE id=?",
                (status, result, datetime.now().isoformat(), task_id),
            )
        else:
            await db.execute("UPDATE tasks SET status=? WHERE id=?", (status, task_id))
        await db.commit()


async def get_task(task_id: int) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM tasks WHERE id=?", (task_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_recent_tasks(limit: int = 10) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM tasks ORDER BY id DESC LIMIT ?", (limit,))
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def register_project(name: str, path: str, description: str = ""):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO projects (name, path, description) VALUES (?, ?, ?)",
            (name, path, description),
        )
        await db.commit()


async def get_project(name: str) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM projects WHERE name=?", (name,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_all_projects() -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM projects")
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def upsert_checklist_item(
    item_key: str,
    title: str,
    detail: str = "",
    status: str = "pending",
    sort_index: int = 0,
    assigned_agent: str | None = None,
    owner_agent: str | None = None,
    category: str | None = None,
    source: str | None = None,
    user_qq: int | None = None,
    group_id: int | None = None,
    chat_type: str = "private",
    notes: str | None = None,
    validation: str | None = None,
):
    now = datetime.now().isoformat()
    finished_at = now if status in {"done", "completed"} else None
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO checklist_items (
                item_key, title, detail, status, sort_index, assigned_agent, owner_agent,
                category, source, user_qq, group_id, chat_type, notes, validation,
                created_at, updated_at, finished_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(item_key) DO UPDATE SET
                title=excluded.title,
                detail=excluded.detail,
                sort_index=excluded.sort_index,
                assigned_agent=excluded.assigned_agent,
                owner_agent=excluded.owner_agent,
                category=excluded.category,
                source=COALESCE(excluded.source, checklist_items.source),
                user_qq=COALESCE(excluded.user_qq, checklist_items.user_qq),
                group_id=excluded.group_id,
                chat_type=excluded.chat_type,
                status=CASE WHEN checklist_items.status IN ('done','completed') AND excluded.status NOT IN ('done','completed') THEN checklist_items.status ELSE excluded.status END,
                notes=COALESCE(excluded.notes, checklist_items.notes),
                validation=COALESCE(excluded.validation, checklist_items.validation),
                updated_at=excluded.updated_at,
                finished_at=CASE WHEN excluded.status IN ('done','completed') THEN excluded.updated_at ELSE checklist_items.finished_at END
            """,
            (
                item_key,
                title,
                detail,
                status,
                sort_index,
                assigned_agent,
                owner_agent,
                category,
                source,
                user_qq,
                group_id,
                chat_type,
                notes,
                validation,
                now,
                now,
                finished_at,
            ),
        )
        await db.commit()


async def seed_capability_checklist(user_qq: int, chat_type: str = "private", group_id: int | None = None):
    for item in CAPABILITY_CHECKLIST_ITEMS:
        item_key = f"{user_qq}:{item['item_key']}"
        existing = await get_checklist_item(item_key)
        if existing is not None:
            continue
        await upsert_checklist_item(
            item_key=item_key,
            title=item["title"],
            detail=item.get("detail") or "",
            status=item.get("status") or "pending",
            sort_index=item.get("sort_index") or 0,
            assigned_agent=item.get("assigned_agent"),
            owner_agent=item.get("owner_agent"),
            category=item.get("category") or "capability",
            source="capability_seed",
            user_qq=user_qq,
            group_id=group_id,
            chat_type=chat_type,
            validation=item.get("validation"),
        )


async def set_bridge_state_value(key: str, value, updated_at: str | None = None):
    now = updated_at or datetime.now().isoformat()
    raw_value = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO bridge_state (key, value, updated_at) VALUES (?, ?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
            (key, raw_value, now),
        )
        await db.commit()


async def get_bridge_state_value(key: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT value, updated_at FROM bridge_state WHERE key=?", (key,))
        row = await cursor.fetchone()
        if not row:
            return None
        raw_value = row["value"]
        try:
            parsed = json.loads(raw_value)
        except Exception:
            parsed = raw_value
        if isinstance(parsed, dict) and row["updated_at"] and "_db_updated_at" not in parsed:
            parsed["_db_updated_at"] = row["updated_at"]
        return parsed


async def set_bridge_route_state(route: dict):
    await set_bridge_state_value('active_chat_route', route)


async def get_bridge_route_state() -> dict | None:
    value = await get_bridge_state_value('active_chat_route')
    return value if isinstance(value, dict) else None


async def async_delivery_exists(delivery_key: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT 1 FROM async_deliveries WHERE delivery_key=?", (delivery_key,))
        row = await cursor.fetchone()
        return row is not None


async def record_async_delivery(
    delivery_key: str,
    transcript_message_id: str,
    transcript_path: str,
    target_chat_type: str,
    target_user_qq: int | None,
    target_group_id: int | None,
    content: str,
):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO async_deliveries (delivery_key, transcript_message_id, transcript_path, target_chat_type, target_user_qq, target_group_id, content, delivered_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                delivery_key,
                transcript_message_id,
                transcript_path,
                target_chat_type,
                target_user_qq,
                target_group_id,
                content,
                datetime.now().isoformat(),
            ),
        )
        await db.commit()



async def get_checklist_item(item_key: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM checklist_items WHERE item_key=?", (item_key,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_checklist_items(user_qq: int | None = None, chat_type: str | None = None, group_id: int | None = None) -> list[dict]:
    sql = "SELECT * FROM checklist_items WHERE 1=1"
    params = []
    if user_qq is not None:
        sql += " AND user_qq=?"
        params.append(int(user_qq))
    if chat_type:
        sql += " AND chat_type=?"
        params.append(str(chat_type))
    if group_id is not None:
        sql += " AND group_id=?"
        params.append(int(group_id))
    sql += " ORDER BY sort_index ASC, id ASC"

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(sql, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def update_checklist_item(
    item_key: str,
    *,
    status: str | None = None,
    notes: str | None = None,
    validation: str | None = None,
    assigned_agent: str | None = None,
    owner_agent: str | None = None,
    source: str | None = None,
):
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            UPDATE checklist_items
            SET
                status=CASE
                    WHEN ? IS NULL THEN status
                    WHEN status IN ('done','completed') AND ? NOT IN ('done','completed') THEN status
                    ELSE ?
                END,
                notes=COALESCE(?, notes),
                validation=COALESCE(?, validation),
                assigned_agent=COALESCE(?, assigned_agent),
                owner_agent=COALESCE(?, owner_agent),
                source=COALESCE(?, source),
                updated_at=?,
                finished_at=CASE
                    WHEN ? IN ('done','completed') THEN ?
                    ELSE finished_at
                END
            WHERE item_key=?
            """,
            (
                status,
                status,
                status,
                notes,
                validation,
                assigned_agent,
                owner_agent,
                source,
                now,
                status,
                now,
                item_key,
            ),
        )
        await db.commit()
