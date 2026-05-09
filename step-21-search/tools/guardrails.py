"""
工具护栏 — Step 13 新增

学习目标:
  - 理解 Agent 安全的三道防线：审批（事前）→ 护栏（事中）→ 日志（事后）
  - 理解护栏的设计原则：不依赖 LLM 自律，由系统强制执行
  - 理解拦截后的反馈机制：返回错误消息让 LLM 调整行为

检测规则:
  1. 循环检测 — 同一工具+参数在最近 N 轮重复调用
  2. 敏感路径 — 禁止读写系统敏感目录
  3. 超长命令 — shell 命令过长可能是注入攻击
"""

from __future__ import annotations
import json
import os

# 调用历史记录: (tool_name, args_signature)
_call_history: list[tuple[str, str]] = []

# 敏感路径前缀
_SENSITIVE_PATHS = [
    "/etc/passwd", "/etc/shadow", "/etc/hosts",
    "~/.ssh/", "~/.aws/", "~/.gnupg/",
    "/root/", "/var/log/", "/proc/", "/sys/",
    ".env", "credentials", "secret", ".pem",
]

# 循环检测参数
LOOP_WINDOW = 5       # 检查最近 N 次调用
LOOP_THRESHOLD = 3    # 同一工具+参数出现 N 次视为循环

# 命令行最大长度
MAX_COMMAND_LENGTH = 500


def _normalize_path(path: str) -> str:
    """规范化路径用于比较"""
    return os.path.expanduser(path)


def _check_loop(tool_name: str, args: dict) -> str | None:
    """
    循环检测: 如果同一工具 + 相同参数在最近 N 次调用中反复出现，拦截。
    """
    args_sig = json.dumps(args, sort_keys=True, ensure_ascii=False)
    call_key = (tool_name, args_sig)

    _call_history.append(call_key)
    # 只保留最近 N 条
    if len(_call_history) > LOOP_WINDOW * 2:
        _call_history[:] = _call_history[-LOOP_WINDOW * 2:]

    # 统计最近 LOOP_WINDOW 条中的重复次数
    recent = _call_history[-LOOP_WINDOW:]
    count = recent.count(call_key)
    if count >= LOOP_THRESHOLD:
        return (
            f"⛔ [护栏] 检测到工具循环: '{tool_name}' 在最近 {LOOP_WINDOW} 次调用中重复了 {count} 次。\n"
            f"    参数: {args_sig[:200]}\n"
            f"    请换一种方式完成任务，或向用户寻求帮助。"
        )
    return None


def _check_sensitive_path(tool_name: str, args: dict) -> str | None:
    """敏感路径检测: 禁止读写系统敏感文件"""
    path = args.get("path") or args.get("file_path") or ""
    if not path:
        return None

    path = _normalize_path(path)
    for sensitive in _SENSITIVE_PATHS:
        if sensitive in path or path.startswith(sensitive.replace("~", os.path.expanduser("~"))):
            return (
                f"⛔ [护栏] 禁止访问敏感路径: '{path}'\n"
                f"    匹配规则: {sensitive}\n"
                f"    如需访问，请用户手动操作。"
            )
    return None


def _check_command_length(tool_name: str, args: dict) -> str | None:
    """超长命令检测: 可能是注入攻击"""
    if tool_name != "run_shell":
        return None
    command = args.get("command", "")
    if len(command) > MAX_COMMAND_LENGTH:
        return (
            f"⛔ [护栏] 命令过长 ({len(command)} 字符，上限 {MAX_COMMAND_LENGTH})\n"
            f"    请拆分命令或使用文件工具完成。"
        )
    return None


def check(tool_name: str, args: dict) -> str | None:
    """
    执行所有护栏检查。返回 None 表示通过，返回字符串表示拦截。

    检查顺序（短路）:
      循环检测 → 敏感路径 → 超长命令
    """
    for check_fn in [_check_loop, _check_sensitive_path, _check_command_length]:
        error = check_fn(tool_name, args)
        if error:
            return error
    return None


def reset():
    """重置调用历史（/reset 时调用）"""
    _call_history.clear()
