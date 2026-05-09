"""
定时任务工具 — Step 18 新增

给 LLM 用的定时任务管理工具。LLM 可以:
  - 设置提醒: "30 分钟后提醒我开会"
  - 查看待办: "有哪些定时任务?"
  - 删除任务: "取消那个提醒"
"""

import json
from cron.scheduler import CronScheduler
from tools.registry import register


def _add_reminder(description: str, minutes: int) -> str:
    """添加一个定时提醒"""
    if minutes < 1:
        return "错误: 时间必须 >= 1 分钟"
    if minutes > 1440:  # 24 hours
        return "错误: 最长支持 24 小时 (1440 分钟)"
    task_id = CronScheduler.add_task(description, minutes)
    return (
        f"✅ 已设置提醒\n"
        f"   任务: {description}\n"
        f"   将在 {minutes} 分钟后触发\n"
        f"   ID: {task_id}"
    )


def _list_reminders() -> str:
    """列出所有待处理的定时任务"""
    tasks = CronScheduler.list_tasks("pending")
    if not tasks:
        return "(没有待处理的定时任务)"
    lines = ["待处理的定时任务:"]
    for t in tasks:
        remaining = max(0, int(t["trigger_at"] - __import__("time").time()))
        mins = remaining // 60
        secs = remaining % 60
        lines.append(f"  📌 {t['id'][:12]} — {t['description']} ({mins}分{secs}秒后)")
    return "\n".join(lines)


def _delete_reminder(task_id: str) -> str:
    """删除一个定时任务"""
    ok = CronScheduler.delete_task(task_id)
    if ok:
        return f"✅ 已删除任务: {task_id}"
    return f"错误: 未找到任务 '{task_id}'"


register(
    name="add_reminder",
    toolset="cron",
    description=(
        "设置一个定时提醒。"
        "适合: '30分钟后提醒我开会'、'5分钟后提醒我休息'"
    ),
    parameters={
        "type": "object",
        "properties": {
            "description": {"type": "string", "description": "提醒内容"},
            "minutes": {"type": "integer", "description": "多少分钟后触发"},
        },
        "required": ["description", "minutes"],
    },
    handler=_add_reminder,
)

register(
    name="list_reminders",
    toolset="cron",
    description="列出所有待处理的定时提醒",
    parameters={"type": "object", "properties": {}, "required": []},
    handler=_list_reminders,
)

register(
    name="delete_reminder",
    toolset="cron",
    description="删除指定的定时提醒",
    parameters={
        "type": "object",
        "properties": {
            "task_id": {"type": "string", "description": "要删除的任务 ID"},
        },
        "required": ["task_id"],
    },
    handler=_delete_reminder,
)
