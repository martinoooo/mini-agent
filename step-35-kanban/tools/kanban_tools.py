"""
Kanban 工具 — Step 35 新增

LLM 可调用的看板管理工具:
  kanban_create  — 在看板上创建新任务
  kanban_list    — 查看看板状态
  kanban_show    — 查看任务详情
"""

import json
from tools.registry import register
from tools.kanban_store import KanbanStore
from tools.profile_manager import ProfileManager


def _kanban_create(title: str, assignee: str, description: str = "") -> str:
    """在看板上创建一个新任务"""
    profiles = ProfileManager.list_profiles()
    if assignee not in profiles:
        return f"未知角色 '{assignee}'。可用: {', '.join(profiles)}"

    task_id = KanbanStore.create(title, assignee, description)
    return (
        f"✅ 任务已创建\n"
        f"   ID: {task_id}\n"
        f"   标题: {title}\n"
        f"   分配给: @{assignee}\n"
        f"   状态: todo"
    )


def _kanban_list(status: str = "") -> str:
    """查看看板状态"""
    tasks = KanbanStore.list_tasks(status or None)

    if not tasks:
        return "看板为空。使用 kanban_create 创建任务。"

    counts = {"todo": 0, "doing": 0, "done": 0}
    for t in tasks:
        counts[t["status"]] = counts.get(t["status"], 0) + 1

    lines = [
        f"看板状态 (共 {len(tasks)} 个任务)",
        f"  📋 Todo: {counts['todo']} | 🔄 Doing: {counts['doing']} | ✅ Done: {counts['done']}",
        "",
    ]

    for t in tasks[-10:]:  # 最近 10 个
        icon = {"todo": "📋", "doing": "🔄", "done": "✅"}.get(t["status"], "❓")
        lines.append(f"  {icon} [{t['status']}] {t['title']} → @{t['assignee']}")

    return "\n".join(lines)


def _kanban_show(task_id: str) -> str:
    """查看任务详情"""
    task = KanbanStore.get(task_id)
    if not task:
        return f"未找到任务 '{task_id}'"

    return (
        f"任务: {task['title']}\n"
        f"ID: {task['id']}\n"
        f"分配给: @{task['assignee']}\n"
        f"状态: {task['status']}\n"
        f"创建: {task.get('created_at', '?')[:16]}\n"
        f"描述: {task.get('description', '(无)')}\n"
        f"结果: {task.get('result', '(暂无)')}"
    )


register(name="kanban_create", toolset="kanban",
    description="在 Kanban 看板上创建一个任务，指定角色执行。适合：创建异步任务、安排工作。",
    parameters={
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "任务标题"},
            "assignee": {"type": "string", "description": "分配给哪个角色（coder/researcher/reviewer）"},
            "description": {"type": "string", "description": "任务描述（可选）"},
        },
        "required": ["title", "assignee"],
    },
    handler=_kanban_create,
)

register(name="kanban_list", toolset="kanban",
    description="查看 Kanban 看板上的所有任务状态",
    parameters={
        "type": "object",
        "properties": {
            "status": {"type": "string", "description": "按状态过滤（todo/doing/done），不传则全部"},
        },
        "required": [],
    },
    handler=_kanban_list,
)

register(name="kanban_show", toolset="kanban",
    description="查看 Kanban 看板上某个任务的详细信息",
    parameters={
        "type": "object",
        "properties": {
            "task_id": {"type": "string", "description": "任务 ID"},
        },
        "required": ["task_id"],
    },
    handler=_kanban_show,
)
