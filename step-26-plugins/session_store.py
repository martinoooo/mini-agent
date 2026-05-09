"""
会话持久化存储

学习目标:
  - 理解会话数据的序列化/反序列化
  - 理解为什么需要持久化：重启后继续之前对话
  - 理解 JSON 作为存储格式的优缺点

使用 JSON 文件存储（比 SQLite 直观，可直接打开看结构）:
  ~/.mini-agent/sessions/
    ├── 20260508-abc123.json
    ├── 20260508-def456.json
    └── ...

每个文件结构:
  {
    "id": "20260508-abc123",
    "created_at": "2026-05-08T12:00:00",
    "updated_at": "2026-05-08T12:05:00",
    "model": "deepseek-v4-pro",
    "toolset": "full",
    "messages": [...]
  }
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def _session_dir() -> Path:
    """会话存储目录 ~/.mini-agent/sessions/"""
    path = Path.home() / ".mini-agent" / "sessions"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _generate_id() -> str:
    """生成会话 ID: 日期-随机后缀"""
    now = datetime.now(timezone.utc)
    return now.strftime("%Y%m%d") + "-" + os.urandom(4).hex()


class SessionStore:
    """会话数据的保存和加载"""

    @staticmethod
    def save(
        messages: list[dict],
        model: str = "",
        toolset: str = "",
        session_id: Optional[str] = None,
    ) -> str:
        """
        保存会话到文件。

        参数:
          messages:   完整的消息历史（含 system, user, assistant, tool）
          model:      模型名称（记录用）
          toolset:    工具集名称（记录用）
          session_id: 会话 ID。None 则自动生成。

        返回: session_id
        """
        session_id = session_id or _generate_id()
        now = datetime.now(timezone.utc).isoformat()

        session = {
            "id": session_id,
            "created_at": now,
            "updated_at": now,
            "model": model,
            "toolset": toolset,
            "messages": messages,
        }

        filepath = _session_dir() / f"{session_id}.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(session, f, ensure_ascii=False, indent=2)

        return session_id

    @staticmethod
    def load(session_id: str) -> Optional[dict]:
        """
        加载指定会话，返回完整 session 数据或 None。
        """
        filepath = _session_dir() / f"{session_id}.json"
        if not filepath.exists():
            return None
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def list_all() -> list[dict]:
        """
        列出所有已保存的会话（摘要信息，不含 messages）。
        按更新时间倒序排列。
        """
        sessions = []
        for f in sorted(_session_dir().glob("*.json"), key=os.path.getmtime, reverse=True):
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                sessions.append({
                    "id": data["id"],
                    "created_at": data.get("created_at", ""),
                    "updated_at": data.get("updated_at", ""),
                    "model": data.get("model", ""),
                    "toolset": data.get("toolset", ""),
                    "message_count": len(data.get("messages", [])),
                })
            except Exception:
                continue
        return sessions

    @staticmethod
    def delete(session_id: str) -> bool:
        """删除指定会话"""
        filepath = _session_dir() / f"{session_id}.json"
        if filepath.exists():
            filepath.unlink()
            return True
        return False
