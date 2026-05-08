"""
AIAgent 类 — Step 8: 会话持久化

相比 Step 7 的变化:
  - 新增 save_session() / load_session() 方法
  - 会话保存到 ~/.mini-agent/sessions/ 下的 JSON 文件
  - 可随时保存当前对话，下次启动从历史继续

学习目标:
  - 理解会话数据的序列化和反序列化
  - 理解为什么消息历史需要完整的 role + content + tool_calls
  - 理解 JSON 文件作为轻量级存储的优缺点
"""

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

    def run(self, user_message: str) -> str:
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
