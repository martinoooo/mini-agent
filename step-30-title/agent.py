"""
AIAgent 类 — Step 30: 标题生成器

相比 Step 18 的变化:
  - UsageTracker 追踪每次 API 调用的 token 消耗
  - 会话结束时展示统计摘要
  - /stats 命令实时查看用量

学习目标:
  - 理解 token 计费模型：input vs output tokens
  - 理解流式 API 中 token 数据的获取时机（最后一个 chunk）
  - 理解为什么需要统计：控制成本、优化 prompt
"""

import json
import sys
from pathlib import Path
from providers import create_provider
from tools.registry import get_handler, build_openai_schemas
from tools.approval import ApprovalManager, RISK_MEDIUM
from tools import guardrails
from tools.retry import retry_call
from toolsets import get_toolset, discover_tools
from logger import get as get_logger
from cron.scheduler import CronScheduler
from tools.usage import UsageTracker
from tools.redact import redact
from plugins import HookManager, discover_plugins
from tui import Display
from rich.console import Console
console = Console()

KEEP_TAIL = 6
TOKEN_ESTIMATE_RATIO = 4

MEMORY_FILE = Path.home() / ".mini-agent" / "MEMORY.md"


def _load_memory_context() -> str:
    """读取 MEMORY.md，返回注入 system prompt 的上下文"""
    try:
        if MEMORY_FILE.exists():
            content = MEMORY_FILE.read_text(encoding="utf-8").strip()
            # 去掉 HTML 注释行，提取实际内容
            lines = [l for l in content.split("\n") if not l.strip().startswith("<!--")]
            text = "\n".join(lines).strip()
            if text and text != "(记忆为空)":
                return text
    except Exception:
        pass
    return ""


class AIAgent:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.deepseek.com",
        model: str = "deepseek-v4-pro",
        provider_type: str = "openai_compat",  # ← Step 15
        toolset: str = "full",
        max_iterations: int = 10,
        compress_threshold: int = 4000,  # ← Step 16
        approval_callback=None,
        credential_pool=None,       # ← Step 24
    ):
        self.compress_threshold = compress_threshold
        self.log = get_logger("agent")
        self._pending_reminders: list[str] = []
        self.usage = UsageTracker()

        # ── 插件系统 ───────────────────────────────
        self.hooks = HookManager()
        plugin_count = discover_plugins(self.hooks)
        if plugin_count > 0:
            self.hooks.invoke("on_startup", self)
        self.log.info("加载了 %s 个插件", plugin_count)

        # ── Cron 调度器 ─────────────────────────────
        self.cron = CronScheduler(callback=self._on_reminder_due)
        self.cron.start()
        # ── Provider 抽象层 ──────────────────────────
        self.provider = create_provider(
            provider_type=provider_type,
            api_key=api_key,
            base_url=base_url,
            model=model,
            credential_pool=credential_pool,
        )
        self.model = model
        self.provider_type = provider_type
        self.toolset_name = toolset
        self.max_iterations = max_iterations
        self.session_id = None

        self.approval = ApprovalManager(callback=approval_callback)

        discover_tools()

        # ── MCP 集成（Step 28） ──────────────────────
        from tools.mcp_bridge import connect_servers, get_connected_count
        try:
            from config import Config
            connect_servers(Config.load().to_dict())
        except Exception:
            pass  # MCP 连接失败不影响主流程

        tool_names = get_toolset(toolset)
        self.tools = build_openai_schemas(tool_names)

        # ── 构建 system prompt（含记忆上下文 + 技能列表）──
        base_prompt = (
            "你是一个有用的 AI 助手，可以使用工具来完成任务。"
            "当需要读取文件、执行命令或搜索信息时，请使用对应的工具。"
            "每个工具的 description 中说明了什么时候该用、什么时候不该用，请仔细阅读。"
            "完成复杂任务后，考虑使用 create_skill 将经验保存为可复用技能。"
            "用中文回复用户。"
        )

        # 加载技能列表
        from tools.skill_tools import _load_skill_names
        skill_names = _load_skill_names()

        parts = [base_prompt]

        memory_context = _load_memory_context()
        if memory_context:
            parts.append(f"[长期记忆]\n{memory_context}")

        if skill_names:
            parts.append(
                f"[可用技能] {', '.join(skill_names)}\n"
                "使用 view_skill 查看具体技能内容。解决相关问题时优先参考已有技能。"
            )

        self.system_prompt = "\n\n".join(parts)

        self.messages = [
            {"role": "system", "content": self.system_prompt},
        ]

    # ── 会话持久化 ──────────────────────────────────

    def save_session(self, session_id: str = None) -> str:
        """保存当前会话，自动生成标题"""
        from session_store import SessionStore
        title = self._generate_title()
        self.session_id = SessionStore.save(
            messages=self.messages,
            model=self.model,
            toolset=self.toolset_name,
            session_id=session_id or self.session_id,
            title=title,
        )
        return self.session_id

    def _generate_title(self) -> str:
        """用 LLM 从对话中生成简短标题"""
        # 提取前几条用户消息作为上下文
        user_msgs = [m["content"] for m in self.messages
                     if m.get("role") == "user"][:3]
        if not user_msgs:
            return ""
        context = " | ".join(m[:80] for m in user_msgs)

        try:
            response = self.provider.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "给以下对话起一个简短的标题（10字以内），只返回标题文本，不要引号。"},
                    {"role": "user", "content": context},
                ],
            )
            title = response.choices[0].message.content.strip().strip('"').strip("'")
            return title[:20]
        except Exception:
            return ""

    @classmethod
    def from_session(cls, api_key: str, session_id: str,
                     base_url: str = "https://api.deepseek.com",
                     approval_callback=None):
        """从已保存的会话恢复 AIAgent 实例"""
        from session_store import SessionStore
        data = SessionStore.load(session_id)
        if not data:
            raise ValueError(f"会话 '{session_id}' 不存在")

        agent = cls(
            api_key=api_key,
            base_url=base_url,
            model=data.get("model", "deepseek-v4-pro"),
            toolset=data.get("toolset", "full"),
            approval_callback=approval_callback,
        )
        agent.messages = data["messages"]
        agent.session_id = session_id
        return agent

    # ── 上下文压缩 ──────────────────────────────────

    def _estimate_tokens(self) -> int:
        """粗略估算消息列表的总 token 数（4 字符 ≈ 1 token）"""
        total = 0
        for m in self.messages:
            text = json.dumps(m, ensure_ascii=False)
            total += len(text) // TOKEN_ESTIMATE_RATIO
        return total

    def _maybe_compress(self):
        """
        检查是否需要压缩，如需则执行压缩。

        策略:
          保留 self.messages[0]         — system prompt（头部）
          保留 self.messages[-KEEP_TAIL:] — 最近 KEEP_TAIL 条（尾部）
          压缩 self.messages[1:-KEEP_TAIL] — 中间部分 → 摘要
        """
        if len(self.messages) <= KEEP_TAIL + 4:
            return  # 消息太少，不需要压缩

        estimated = self._estimate_tokens()
        if estimated < self.compress_threshold:
            return

        # 分割
        head = self.messages[:1]  # system prompt
        tail = self.messages[-KEEP_TAIL:]  # 最近的消息
        middle = self.messages[1:-KEEP_TAIL]  # 要压缩的部分

        if len(middle) < 4:
            return  # 中间部分太少，不值得压缩

        self.log.info(
            "对话超过 %s tokens (约 %s)，压缩 %s 条中间消息",
            self.compress_threshold, estimated, len(middle),
        )

        summary = self._generate_summary(middle)
        self.log.info("压缩完成，摘要 %s 字符", len(summary))

        # 重建消息列表: system + summary(as system) + tail
        self.messages = head + [
            {"role": "system", "content": f"[对话历史摘要]\n{summary}"},
        ] + list(tail)

    def _generate_summary(self, messages: list[dict]) -> str:
        """
        使用辅助 LLM 调用，将消息列表压缩为一段摘要。
        不使用流式以简化逻辑。
        """
        # 构建压缩用的消息
        compress_messages = [
            {"role": "system", "content": (
                "你是一个对话摘要助手。请将以下对话历史压缩为一段简洁的摘要。\n"
                "保留以下重要信息:\n"
                "- 用户的关键信息和偏好（姓名、需求、决定等）\n"
                "- 已完成的重要操作和结果\n"
                "- 当前正在进行中的任务状态\n"
                "- 未解决的问题或待办事项\n\n"
                "用中文回复，尽量简洁。"
            )},
            {"role": "user", "content": (
                "请摘要以下 JSON 格式的对话历史:\n\n"
                + json.dumps(messages, ensure_ascii=False, indent=2)
            )},
        ]

        try:
            response = retry_call(
                lambda: self.provider.create(
                    model=self.model,
                    messages=compress_messages,
                    max_tokens=512,
                ),
                description="摘要生成",
            )
            if hasattr(response, "usage") and response.usage:
                self.usage.add_llm_call(response.usage)
            return response.choices[0].message.content or "(摘要生成失败)"
        except Exception as e:
            return f"(压缩出错: {e})"

    def _on_reminder_due(self, task: dict):
        """Cron 回调：任务到期时，立即通知 + 存入待注入队列"""
        msg = f"⏰ 定时提醒: {task['description']}"
        # 立即打印到终端（用户不用等下次输入才看到）
        Display.reminder(msg)
        # 同时存入队列，下次 LLM 调用时注入上下文
        self._pending_reminders.append(msg)
        self.log.info("Cron 触发: %s", task["description"])

    def run(self, user_message: str) -> str:
        # ── 定时提醒检查（Step 18） ──────────────────
        while self._pending_reminders:
            reminder = self._pending_reminders.pop(0)
            Display.reminder(reminder)
            # 以 system 消息注入提醒
            self.messages.append({
                "role": "system",
                "content": f"[系统提醒] {reminder}",
            })

        # ── 压缩检查（对话前） ─────────────────────────
        self._maybe_compress()

        self.messages.append({"role": "user", "content": redact(user_message)})

        iteration = 0
        tool_call_count = 0  # ← Step 29: 本轮工具调用计数

        while iteration < self.max_iterations:
            iteration += 1

            content, reasoning, tool_calls, finish_reason = self._call_llm_stream()

            if finish_reason == "tool_calls" and tool_calls:
                tool_call_count += len(tool_calls)
                # 构建 assistant message（包含 tool_calls）存入消息历史
                assistant_msg = {"role": "assistant", "content": content or None}
                if reasoning:
                    assistant_msg["reasoning_content"] = reasoning
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["function"]["name"],
                            "arguments": tc["function"]["arguments"],
                        },
                    }
                    for tc in tool_calls
                ]
                self.messages.append(assistant_msg)

                for tc in tool_calls:
                    name = tc["function"]["name"]
                    args = json.loads(tc["function"]["arguments"])
                    self.log.info("[%s] %s(%s)", iteration, name, redact(json.dumps(args, ensure_ascii=False)))
                    result = self._execute_tool(name, args)
                    self.log.info("[%s] %s → %s", iteration, name, redact(result[:120]))
                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": redact(result),
                    })
                continue

            # finish_reason == "stop": LLM 给出了最终回答（已流式打印）
            if content:
                assistant_msg = {"role": "assistant", "content": content}
                if reasoning:
                    assistant_msg["reasoning_content"] = reasoning
                self.messages.append(assistant_msg)

                # ── 技能创建 Nudge（Step 29: 自升级） ──
                if tool_call_count >= 3:
                    self.log.info("Nudge: %s 次工具调用，注入技能创建提示", tool_call_count)
                    self.messages.append({
                        "role": "system",
                        "content": (
                            "[系统提示] 本轮涉及多轮工具调用。"
                            "如果刚才的解决过程值得复用，"
                            "考虑使用 create_skill 保存为可复用技能。"
                        ),
                    })

                return content

            return "(LLM 返回了空响应)"

        return f"⚠ 超过最大工具调用轮次 ({self.max_iterations})，已强制停止。"

    def _call_llm_stream(self):
        """
        流式调用 LLM，实时打印文本 token，同时拼接 tool_calls。

        流式模式下：
          - 文本内容在 delta.content 中逐 token 到达
          - tool_calls 在 delta.tool_calls 中分段到达，需要按 index 拼接

        返回:
          content:         完整的文本内容（已实时打印）
          reasoning_content: 思考内容（DeepSeek 思考模式）
          tool_calls:      拼接完成的工具调用列表 [{id, function: {name, arguments}}]
          finish_reason:   "stop" | "tool_calls" | None
        """
        stream = retry_call(
            lambda: self.provider.create_stream(
                model=self.model,
                messages=self.messages,
                tools=self.tools,
            ),
            description="LLM 流式调用",
        )

        content = ""
        reasoning_content = ""
        tool_calls = {}  # {index: {id, function: {name, arguments}}}
        finish_reason = None
        printed_reasoning = False

        Display.thinking_start()  # 流式输出前缀
        for chunk in stream:
            if not chunk.choices:
                continue

            delta = chunk.choices[0].delta
            finish_reason = chunk.choices[0].finish_reason
            # ── 捕获 token 用量（流式最后一个 chunk） ──
            if hasattr(chunk, "usage") and chunk.usage:
                self.usage.add_llm_call(chunk.usage)

            # ── 思考内容（DeepSeek 思考模式）────────────
            if getattr(delta, "reasoning_content", None):
                if not printed_reasoning:
                    
                    printed_reasoning = True
                Display.thinking_token(delta.reasoning_content)
                reasoning_content += delta.reasoning_content
                continue  # 思考内容和正式内容是分开的 chunk

            # 思考结束，换行分隔
            if printed_reasoning and (delta.content or delta.tool_calls):
                Display.thinking_end()
                printed_reasoning = False

            # ── 文本内容：逐 token 打印 ────────────────
            if delta.content:
                Display.text_token(delta.content)
                content += delta.content

            # ── 工具调用：按 index 拼接片段 ────────────
            if delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    if idx not in tool_calls:
                        tool_calls[idx] = {
                            "id": "",
                            "function": {"name": "", "arguments": ""},
                        }
                    entry = tool_calls[idx]
                    if tc_delta.id:
                        entry["id"] = tc_delta.id
                    if tc_delta.function and tc_delta.function.name:
                        entry["function"]["name"] += tc_delta.function.name
                    if tc_delta.function and tc_delta.function.arguments:
                        entry["function"]["arguments"] += tc_delta.function.arguments

        console.print()  # 流式结束后换行

        # 按 index 排序
        tool_calls = [tool_calls[i] for i in sorted(tool_calls.keys())]

        return content, reasoning_content, tool_calls, finish_reason

    def _execute_tool(self, name: str, args: dict) -> str:
        # ── 审批检查（Step 11） ───────────────────────
        if self.approval.needs_approval(name):
            approved = self.approval.request(name, args)
            if not approved:
                return f"⛔ 用户拒绝了 '{name}' 的执行"

        self.usage.add_tool_call()  # ← Step 19

        # ── 护栏检查（Step 13） ───────────────────────
        block_reason = guardrails.check(name, args)
        if block_reason:
            self.log.warning("护栏拦截: %s", block_reason[:120])
            return block_reason

        try:
            handler = get_handler(name)
            if handler is None:
                return f"错误: 未知工具 '{name}'"
            result = str(handler(**args))
            # ── 插件钩子（Step 26） ──────────────────
            result = self.hooks.invoke(
                "on_tool_call", name=name, args=args, result=result,
            )
            return result
        except Exception as e:
            return f"错误: 工具 '{name}' 执行失败: {e}"
