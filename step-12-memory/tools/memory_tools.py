"""
记忆工具 — Step 12 新增

学习目标:
  - 理解 Agent 的长期记忆：跨会话记住用户偏好和信息
  - 理解 MEMORY.md 模式：一个简单的知识库文件
  - 理解 RAG 雏形：读取记忆 → 注入上下文 → LLM 利用

与 Hermes Agent 的关系:
  Hermes 有完整的 MemoryManager, 支持多种后端（Honcho, Mem0）。
  这里是极简版——就是读写一个 Markdown 文件。

两个工具:
  read_memory  — 读取 MEMORY.md（LLM 主动查询记忆）
  write_memory — 追加到 MEMORY.md（LLM 主动记录信息）
"""

import os
from datetime import datetime
from pathlib import Path
from tools.registry import register

MEMORY_FILE = Path.home() / ".mini-agent" / "MEMORY.md"


def _ensure_file():
    """确保 MEMORY.md 存在，不存在则创建空文件"""
    MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not MEMORY_FILE.exists():
        MEMORY_FILE.write_text("<!-- Mini Agent Memory -->\n", encoding="utf-8")


def _read_memory() -> str:
    """读取整个 MEMORY.md"""
    _ensure_file()
    try:
        content = MEMORY_FILE.read_text(encoding="utf-8")
        return content if content.strip() else "(记忆为空)"
    except Exception as e:
        return f"错误: 读取记忆失败 - {e}"


def _write_memory(content: str) -> str:
    """
    追加一段新记忆到 MEMORY.md。

    格式: 带时间戳的条目，方便阅读。
    """
    _ensure_file()
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        entry = f"\n## {now}\n\n{content.strip()}\n"

        with open(MEMORY_FILE, "a", encoding="utf-8") as f:
            f.write(entry)

        return f"已记录到记忆: {content[:100]}..."
    except Exception as e:
        return f"错误: 写入记忆失败 - {e}"


register(
    name="read_memory",
    toolset="memory",
    description=(
        "读取 Agent 的长期记忆文件（MEMORY.md）。"
        "包含之前记录的用户偏好、重要信息和项目上下文。"
        "在需要回忆之前的对话内容时使用。"
    ),
    parameters={
        "type": "object",
        "properties": {},
        "required": [],
    },
    handler=_read_memory,
)

register(
    name="write_memory",
    toolset="memory",
    description=(
        "将重要信息写入长期记忆文件（MEMORY.md）。"
        "适合记录: 用户偏好、重要决策、项目背景、待办事项等。"
        "每条记忆会自动加上时间戳。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "要记录的信息内容",
            },
        },
        "required": ["content"],
    },
    handler=_write_memory,
)
