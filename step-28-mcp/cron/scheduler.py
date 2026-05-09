"""
Cron 调度器 — Step 18 新增

学习目标:
  - 理解定时任务的基本原理：轮询 + 到期触发
  - 理解守护线程：后台运行，主程序退出时自动结束
  - 理解 Agent 的"时间感知"能力

任务存储: ~/.mini-agent/cron.json
检查间隔: 30 秒
"""

import json
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

TASK_FILE = Path.home() / ".mini-agent" / "cron.json"


class CronScheduler:
    """
    轻量级定时调度器。

    用法:
      scheduler = CronScheduler(callback=my_handler)
      scheduler.start()   # 启动后台线程
      scheduler.stop()    # 停止
    """

    def __init__(self, callback: Optional[Callable] = None,
                 interval: int = 30):
        self.callback = callback
        self.interval = interval
        self._thread: Optional[threading.Thread] = None
        self._running = False

    def start(self):
        """启动后台调度线程"""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        """停止调度"""
        self._running = False

    def _loop(self):
        """主循环：每 interval 秒检查一次到期任务"""
        while self._running:
            try:
                self._check_due()
            except Exception:
                pass  # 调度器自身静默失败
            time.sleep(self.interval)

    def _check_due(self):
        """检查并触发到期任务"""
        tasks = self._load_tasks()
        now = datetime.now().timestamp()
        changed = False

        for task in tasks:
            if task.get("status") != "pending":
                continue
            if task["trigger_at"] <= now:
                task["status"] = "triggered"
                changed = True
                if self.callback:
                    try:
                        self.callback(task)
                    except Exception:
                        pass

        if changed:
            self._save_tasks(tasks)

    @staticmethod
    def add_task(description: str, delay_minutes: int) -> str:
        """
        添加一个定时任务。

        参数:
          description:   任务描述（到时会作为提醒内容）
          delay_minutes: 多少分钟后触发

        返回: task_id
        """
        task_id = datetime.now().strftime("%Y%m%d%H%M%S") + "-" + os.urandom(3).hex()
        task = {
            "id": task_id,
            "description": description,
            "trigger_at": datetime.now().timestamp() + delay_minutes * 60,
            "created_at": datetime.now().isoformat(),
            "status": "pending",
        }
        tasks = CronScheduler._load_tasks()
        tasks.append(task)
        CronScheduler._save_tasks(tasks)
        return task_id

    @staticmethod
    def list_tasks(status: str = "pending") -> list[dict]:
        """列出指定状态的任务"""
        tasks = CronScheduler._load_tasks()
        if status:
            tasks = [t for t in tasks if t.get("status") == status]
        return tasks

    @staticmethod
    def delete_task(task_id: str) -> bool:
        """删除指定任务"""
        tasks = CronScheduler._load_tasks()
        new_tasks = [t for t in tasks if t["id"] != task_id]
        if len(new_tasks) == len(tasks):
            return False
        CronScheduler._save_tasks(new_tasks)
        return True

    @staticmethod
    def _load_tasks() -> list[dict]:
        TASK_FILE.parent.mkdir(parents=True, exist_ok=True)
        if not TASK_FILE.exists():
            return []
        try:
            with open(TASK_FILE, "r", encoding="utf-8") as f:
                return json.load(f) or []
        except Exception:
            return []

    @staticmethod
    def _save_tasks(tasks: list[dict]):
        TASK_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(TASK_FILE, "w", encoding="utf-8") as f:
            json.dump(tasks, f, ensure_ascii=False, indent=2)
