"""
会话搜索工具 — Step 21 新增

学习目标:
  - 理解跨会话知识检索：不是只能记住当前对话
  - 理解全文搜索的基本实现：遍历文件 + 字符串匹配
  - 理解为什么 Hermes 用 SQLite FTS5：大规模数据需要索引

搜索范围: ~/.mini-agent/sessions/ 下的所有 JSON 会话文件
"""

import json
from pathlib import Path
from tools.registry import register

SESSIONS_DIR = Path.home() / ".mini-agent" / "sessions"


def _search_sessions(query: str) -> str:
    """
    在所有已保存的会话中搜索关键词。

    返回: 匹配的会话摘要列表，包含时间、关键词上下文片段。
    """
    if not SESSIONS_DIR.exists():
        return "(没有已保存的会话)"

    results = []
    for f in sorted(SESSIONS_DIR.glob("*.json"), reverse=True):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue

        messages = data.get("messages", [])
        matches = []

        # 搜索每条消息的 content
        for i, msg in enumerate(messages):
            content = msg.get("content", "") or ""
            if query.lower() in content.lower():
                # 提取匹配片段的上下文（前后各 40 字符）
                idx = content.lower().find(query.lower())
                start = max(0, idx - 40)
                end = min(len(content), idx + len(query) + 40)
                snippet = content[start:end]
                if start > 0:
                    snippet = "..." + snippet
                if end < len(content):
                    snippet = snippet + "..."

                matches.append({
                    "msg_index": i,
                    "role": msg.get("role", "?"),
                    "snippet": snippet,
                })

        if matches:
            results.append({
                "id": data.get("id", f.stem),
                "updated_at": data.get("updated_at", "")[:16],
                "matches": matches[:3],  # 最多 3 条匹配
                "total_matches": len(matches),
            })

    if not results:
        return f"未找到与 '{query}' 相关的历史会话"

    lines = [f"搜索 '{query}' — 找到 {len(results)} 个相关会话:"]
    for r in results[:10]:  # 最多 10 个会话
        lines.append(f"\n📝 {r['id']} ({r['updated_at']}) — {r['total_matches']} 处匹配:")
        for m in r["matches"]:
            role_icon = {"user": "🧑", "assistant": "🤖", "system": "⚙️", "tool": "🔧"}.get(m["role"], "  ")
            lines.append(f"   {role_icon} {m['snippet'][:120]}")

    return "\n".join(lines)


register(
    name="search_sessions",
    toolset="search",
    description=(
        "在所有历史会话中搜索关键词，返回匹配的会话摘要和上下文片段。"
        "适合: '我之前问过什么问题？'、'之前讨论过 asyncio 吗？'"
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "搜索关键词",
            },
        },
        "required": ["query"],
    },
    handler=_search_sessions,
)
