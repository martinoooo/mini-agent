"""
AIAgent 类 — Step 10: 代码执行沙箱

相比 Step 8 的变化:
  - 新增 _maybe_compress(): 当对话历史超过 token 阈值时自动压缩
  - 使用辅助 LLM 调用对中间消息生成摘要
  - 保留头部（system prompt）和尾部（最近对话），压缩中间部分

学习目标:
  - 理解 LLM 的 token 窗口限制（为什么需要压缩）
  - 理解辅助 LLM 调用的模式（用 LLM 帮 LLM）
  - 理解上下文管理策略：头尾保护 + 中间摘要
"""

import json
import sys
from openai import OpenAI
from tools.registry import get_handler, build_openai_schemas
from toolsets import get_toolset, discover_tools

# 压缩参数
TOKEN_THRESHOLD = 4000   # token 数超过此值触发压缩
KEEP_TAIL = 6             # 保留最后 N 条消息不压缩
TOKEN_ESTIMATE_RATIO = 4  # 粗略估算: N 字符 ≈ 1 token

import json
import sys
from openai import OpenAI
from tools.registry import get_handler, build_openai_schemas
from toolsets import get_toolset, discover_tools


class AIAgent:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.deepseek.com",
        model: str = "deepseek-v4-pro",
        toolset: str = "full",
        max_iterations: int = 10,
    ):
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.toolset_name = toolset
        self.max_iterations = max_iterations
        self.session_id = None  # 加载或保存后会有值

        discover_tools()
        tool_names = get_toolset(toolset)
        self.tools = build_openai_schemas(tool_names)

        self.system_prompt = (
            "你是一个有用的 AI 助手，可以使用工具来完成任务。"
            "当需要读取文件、执行命令或搜索信息时，请使用对应的工具。"
            "用中文回复用户。"
        )
        self.messages = [
            {"role": "system", "content": self.system_prompt},
        ]

    # ── 会话持久化 ──────────────────────────────────

    def save_session(self, session_id: str = None) -> str:
        """保存当前会话到 ~/.mini-agent/sessions/"""
        from session_store import SessionStore
        self.session_id = SessionStore.save(
            messages=self.messages,
            model=self.model,
            toolset=self.toolset_name,
            session_id=session_id or self.session_id,
        )
        return self.session_id

    @classmethod
    def from_session(cls, api_key: str, session_id: str,
                     base_url: str = "https://api.deepseek.com"):
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
        if estimated < TOKEN_THRESHOLD:
            return

        # 分割
        head = self.messages[:1]  # system prompt
        tail = self.messages[-KEEP_TAIL:]  # 最近的消息
        middle = self.messages[1:-KEEP_TAIL]  # 要压缩的部分

        if len(middle) < 4:
            return  # 中间部分太少，不值得压缩

        print(f"\n📦 对话已超过 {TOKEN_THRESHOLD} tokens (约 {estimated})，正在压缩中间 {len(middle)} 条消息...")

        summary = self._generate_summary(middle)
        print(f"  ✅ 压缩完成，摘要 {len(summary)} 字符")

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
            response = self.client.chat.completions.create(
                model=self.model,
                messages=compress_messages,
                max_tokens=512,  # 摘要不要超过 512 tokens
            )
            return response.choices[0].message.content or "(摘要生成失败)"
        except Exception as e:
            return f"(压缩出错: {e})"

    def run(self, user_message: str) -> str:
        # ── 压缩检查（对话前） ─────────────────────────
        self._maybe_compress()

        self.messages.append({"role": "user", "content": user_message})

        iteration = 0
        while iteration < self.max_iterations:
            iteration += 1

            content, reasoning, tool_calls, finish_reason = self._call_llm_stream()

            if finish_reason == "tool_calls" and tool_calls:
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
                    print(f"  🔧 [{iteration}] {name}({json.dumps(args, ensure_ascii=False)})")
                    result = self._execute_tool(name, args)
                    print(f"  ✅ [{iteration}] {result[:120]}")
                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": result,
                    })
                continue

            # finish_reason == "stop": LLM 给出了最终回答（已流式打印）
            if content:
                assistant_msg = {"role": "assistant", "content": content}
                if reasoning:
                    assistant_msg["reasoning_content"] = reasoning
                self.messages.append(assistant_msg)
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
        kwargs = {"model": self.model, "messages": self.messages, "stream": True}
        if self.tools:
            kwargs["tools"] = self.tools
            kwargs["tool_choice"] = "auto"

        stream = self.client.chat.completions.create(**kwargs)

        content = ""
        reasoning_content = ""
        tool_calls = {}  # {index: {id, function: {name, arguments}}}
        finish_reason = None
        printed_reasoning = False

        print("\n🤖 ", end="", flush=True)  # 流式输出前缀
        for chunk in stream:
            if not chunk.choices:
                continue

            delta = chunk.choices[0].delta
            finish_reason = chunk.choices[0].finish_reason

            # ── 思考内容（DeepSeek 思考模式）────────────
            if getattr(delta, "reasoning_content", None):
                if not printed_reasoning:
                    print("💭 ", end="", flush=True)
                    printed_reasoning = True
                print(delta.reasoning_content, end="", flush=True)
                reasoning_content += delta.reasoning_content
                continue  # 思考内容和正式内容是分开的 chunk

            # 思考结束，换行分隔
            if printed_reasoning and (delta.content or delta.tool_calls):
                print()
                printed_reasoning = False

            # ── 文本内容：逐 token 打印 ────────────────
            if delta.content:
                print(delta.content, end="", flush=True)
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

        print()  # 流式结束后换行

        # 按 index 排序
        tool_calls = [tool_calls[i] for i in sorted(tool_calls.keys())]

        return content, reasoning_content, tool_calls, finish_reason

    def _execute_tool(self, name: str, args: dict) -> str:
        try:
            handler = get_handler(name)
            if handler is None:
                return f"错误: 未知工具 '{name}'"
            return str(handler(**args))
        except Exception as e:
            return f"错误: 工具 '{name}' 执行失败: {e}"
