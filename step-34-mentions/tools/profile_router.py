"""
@角色 路由 — Step 34 新增

学习目标:
  - 理解消息路由：根据前缀将请求分发到不同处理器
  - 理解 @mention 模式：群聊中通过 @名字 指定接收者

用法:
  @coder 写一个排序函数        → 用 coder profile 的 Agent 执行
  @researcher 研究排序算法      → 用 researcher profile 的 Agent 执行
  @reviewer 审查 agent.py       → 用 reviewer profile 的 Agent 执行
  直接说话                       → 主 Agent 自己处理
"""

from __future__ import annotations
import os
import threading
from tools.profile_manager import ProfileManager


# 正在执行的后台任务
_running_tasks: dict[str, dict] = {}
_lock = threading.Lock()


def is_mention(text: str) -> bool:
    """检查消息是否以 @角色 开头"""
    return text.startswith("@") and not text.startswith("@@")


def parse_mention(text: str) -> tuple[str, str] | None:
    """
    解析 @角色 消息。

    "@coder 写代码" → ("coder", "写代码")
    "@researcher 研究" → ("researcher", "研究")
    非 mention → None
    """
    if not is_mention(text):
        return None
    parts = text.split(maxsplit=1)
    profile = parts[0][1:]  # 去掉 @
    task = parts[1].strip() if len(parts) > 1 else ""
    return profile, task


def route(profile_name: str, task: str,
          api_key: str, base_url: str, model: str,
          shared_messages: list[dict] = None) -> str:
    """
    将任务路由到指定角色的 Agent 执行。

    shared_messages: 频道共享的对话历史。
      子 Agent 启动时会继承这些消息，从而看到之前的上下文。
      模拟群聊中所有人的对话都可见。
    """
    from agent import AIAgent

    if not task:
        return f"请给 @{profile_name} 一个具体的任务，例如: @{profile_name} 写一个排序函数"

    try:
        profile = ProfileManager.load(profile_name)
    except ValueError:
        available = ", ".join(ProfileManager.list_profiles())
        return f"未知角色 '@{profile_name}'。可用: {available}"

    toolset = profile.toolset or "dev"
    child = AIAgent(
        api_key=api_key,
        base_url=base_url,
        model=model,
        toolset=toolset,
        max_iterations=10,
        profile=profile_name,
        approval_callback=None,
    )
    child.cron.stop()

    # ── 共享上下文：注入频道历史 ──────────────
    if shared_messages:
        # 用 system prompt + 历史消息替换默认的 messages
        child.messages = [
            {"role": "system", "content": child.system_prompt},
        ] + list(shared_messages)  # 前面的所有对话

    print(f"  📨 [{profile_name}] 收到任务: {task[:60]}..."
          f"{' (共享上下文)' if shared_messages else ''}")
    result = child.run(task)
    print(f"  📨 [{profile_name}] 完成")
    return result
