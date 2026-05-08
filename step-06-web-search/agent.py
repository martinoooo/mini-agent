"""
AIAgent 类 — 与 Step 5 完全相同！

自注册模式的好处：agent.py 不需要任何修改，自动适配新工具。
它只依赖 registry 和 toolsets，不管后面加了多少工具。
"""

import json
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
        self.max_iterations = max_iterations

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

    def run(self, user_message: str) -> str:
        self.messages.append({"role": "user", "content": user_message})

        iteration = 0
        while iteration < self.max_iterations:
            iteration += 1

            response = self._call_llm()
            choice = response.choices[0]
            msg = choice.message

            if choice.finish_reason == "tool_calls" and msg.tool_calls:
                self.messages.append(msg.model_dump())

                for tool_call in msg.tool_calls:
                    name = tool_call.function.name
                    args = json.loads(tool_call.function.arguments)
                    print(f"  🔧 [{iteration}] {name}({json.dumps(args, ensure_ascii=False)})")
                    result = self._execute_tool(name, args)
                    print(f"  ✅ [{iteration}] {result[:120]}")
                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result,
                    })
                continue

            if msg.content:
                self.messages.append({"role": "assistant", "content": msg.content})
                return msg.content

            return f"(LLM 返回了空响应)"

        return f"⚠ 超过最大工具调用轮次 ({self.max_iterations})，已强制停止。"

    def _call_llm(self):
        kwargs = {"model": self.model, "messages": self.messages}
        if self.tools:
            kwargs["tools"] = self.tools
            kwargs["tool_choice"] = "auto"
        return self.client.chat.completions.create(**kwargs)

    def _execute_tool(self, name: str, args: dict) -> str:
        try:
            handler = get_handler(name)
            if handler is None:
                return f"错误: 未知工具 '{name}'"
            return str(handler(**args))
        except Exception as e:
            return f"错误: 工具 '{name}' 执行失败: {e}"
