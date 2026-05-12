"""
Kanban 调度器 — Step 35 新增

后台线程扫描看板，自动执行 todo 任务。
每个任务用对应 profile 的 AIAgent 执行。
"""

import threading
import time
from tools.kanban_store import KanbanStore


class KanbanScheduler:
    """
    Kanban 任务调度器。

    每 30 秒扫描一次看板，认领 todo 状态的任务，
    用对应 profile 创建 Agent 执行。
    """

    def __init__(self, api_key: str, base_url: str, model: str,
                 interval: int = 30):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.interval = interval
        self._thread: threading.Thread = None
        self._running = False

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def _loop(self):
        while self._running:
            try:
                self._process_tasks()
            except Exception:
                pass
            time.sleep(self.interval)

    def _process_tasks(self):
        """处理 todos 中的任务"""
        from agent import AIAgent
        from tools.profile_manager import ProfileManager

        # 同时处理最多的任务数
        max_batch = 3
        for _ in range(max_batch):
            task = KanbanStore.claim_next("any")
            if not task:
                break

            profile = task.get("assignee", "")
            if profile not in ProfileManager.list_profiles():
                KanbanStore.update(task["id"], status="done",
                    result=f"未知角色: {profile}")
                continue

            try:
                child = AIAgent(
                    api_key=self.api_key,
                    base_url=self.base_url,
                    model=self.model,
                    toolset="dev",
                    max_iterations=8,
                    profile=profile,
                    approval_callback=None,
                )
                child.cron.stop()

                task_desc = task.get("description") or task.get("title", "")
                print(f"\n  📋 [Kanban] @{profile} 开始: {task_desc[:60]}...")

                result = child.run(f"执行以下任务:\n{task_desc}")

                KanbanStore.update(task["id"], status="done", result=result)
                print(f"  📋 [Kanban] @{profile} 完成: {task['title']}")

            except Exception as e:
                KanbanStore.update(task["id"], status="done",
                    result=f"执行失败: {e}")
