"""
日志系统 — Step 17 新增

学习目标:
  - 理解为什么需要日志：调试、审计、事后排查
  - 理解日志等级：DEBUG < INFO < WARNING < ERROR
  - 理解日志输出目标：控制台（实时） + 文件（持久）

日志格式:
  [2026-05-09 14:30:01] [INFO] [agent] 工具调用: read_file(path='main.py')

日志文件: ~/.mini-agent/agent.log
"""

import logging
import sys
from pathlib import Path
from datetime import datetime

LOG_FILE = Path.home() / ".mini-agent" / "agent.log"

# 日志格式: [时间] [等级] 消息
CONSOLE_FORMAT = "%(asctime)s  %(levelname)-7s  %(message)s"
FILE_FORMAT = "%(asctime)s  %(levelname)-7s  [%(name)s]  %(message)s"
DATE_FORMAT = "%H:%M:%S"


def setup(level: str = "INFO") -> logging.Logger:
    """
    初始化日志系统，返回 root logger。

    level: DEBUG | INFO | WARNING | ERROR

    双输出:
      - 控制台: INFO 及以上，简洁格式
      - 文件:   DEBUG 及以上，完整格式（含模块名）
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    root = logging.getLogger("mini-agent")
    root.setLevel(logging.DEBUG)  # root 设最低，由 handler 控制实际输出等级
    root.handlers.clear()

    # ── 控制台 handler ───────────────────────────
    console = logging.StreamHandler(sys.stderr)
    console.setLevel(log_level)
    console.setFormatter(logging.Formatter(CONSOLE_FORMAT, DATE_FORMAT))
    root.addHandler(console)

    # ── 文件 handler ─────────────────────────────
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(str(LOG_FILE), encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)  # 文件记录所有级别
    file_handler.setFormatter(logging.Formatter(FILE_FORMAT, DATE_FORMAT))
    root.addHandler(file_handler)

    return root


def get(name: str) -> logging.Logger:
    """获取子 logger（按模块名区分）"""
    return logging.getLogger(f"mini-agent.{name}")
