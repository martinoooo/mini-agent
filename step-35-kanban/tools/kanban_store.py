"""
Kanban 任务存储 — Step 35 新增

存储格式: ~/.mini-agent/kanban.json
每个任务: {id, title, description, assignee, status, created_at, result}
"""

from __future__ import annotations
import json
import os
import time
from datetime import datetime
from pathlib import Path

KANBAN_FILE = Path.home() / ".mini-agent" / "kanban.json"


class KanbanStore:
    """JSON 文件持久化的看板任务管理"""

    @staticmethod
    def create(title: str, assignee: str, description: str = "") -> str:
        """创建新任务，返回 task_id"""
        tasks = KanbanStore._load()
        task_id = datetime.now().strftime("%Y%m%d%H%M%S") + "-" + os.urandom(3).hex()
        task = {
            "id": task_id,
            "title": title,
            "description": description,
            "assignee": assignee,
            "status": "todo",
            "created_at": datetime.now().isoformat(),
            "result": None,
        }
        tasks.append(task)
        KanbanStore._save(tasks)
        return task_id

    @staticmethod
    def list_tasks(status: str = None) -> list[dict]:
        """列出任务，可按状态过滤"""
        tasks = KanbanStore._load()
        if status:
            return [t for t in tasks if t.get("status") == status]
        return tasks

    @staticmethod
    def get(task_id: str) -> dict | None:
        for t in KanbanStore._load():
            if t["id"] == task_id:
                return t
        return None

    @staticmethod
    def update(task_id: str, **kwargs):
        tasks = KanbanStore._load()
        for t in tasks:
            if t["id"] == task_id:
                t.update(kwargs)
                KanbanStore._save(tasks)
                return True
        return False

    @staticmethod
    def claim_next(assignee: str) -> dict | None:
        """认领下一个 todo 任务（原子操作）"""
        tasks = KanbanStore._load()
        for t in tasks:
            if t["status"] == "todo":
                t["status"] = "doing"
                t["started_at"] = datetime.now().isoformat()
                KanbanStore._save(tasks)
                return t
        return None

    @staticmethod
    def _load() -> list[dict]:
        KANBAN_FILE.parent.mkdir(parents=True, exist_ok=True)
        if not KANBAN_FILE.exists():
            return []
        try:
            return json.loads(KANBAN_FILE.read_text()) or []
        except Exception:
            return []

    @staticmethod
    def _save(tasks: list[dict]):
        KANBAN_FILE.parent.mkdir(parents=True, exist_ok=True)
        KANBAN_FILE.write_text(json.dumps(tasks, ensure_ascii=False, indent=2))
