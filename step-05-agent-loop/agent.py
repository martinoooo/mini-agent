"""
AIAgent 类 — Agent 的核心循环

学习目标:
  - 理解 Agent Loop 的完整逻辑：LLM → 工具 → LLM → ... → 最终回复
  - 理解消息历史管理：为什么要把 tool_calls 和 tool 结果都存入 messages
  - 理解怎么用 finish_reason 判断 LLM 是想调工具还是想回复用户

与前面 Step 的区别:
  之前 main.py 里杂糅了循环逻辑和工具调用。现在把它们抽到 AIAgent 类中，
  职责清晰：agent.py 管循环，cli.py 只管输入输出。

这就是 Hermes Agent 里 run_agent.py 的核心思想——AIAgent 类管理整个会话生命周期。
"""

import json
from openai import OpenAI
from tools.registry import get_handler, build_openai_schemas
from toolsets import get_toolset, discover_tools


class AIAgent:
    """
    极简 AI Agent。

    职责:
      1. 管理 LLM 客户端和对话历史
      2. 运行 Agent Loop: 调 LLM → 执行工具 → 继续 → 直到得到最终答案
      3. 处理错误和边界情况
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.deepseek.com",
        model: str = "deepseek-v4-pro",
        toolset: str = "full",
        max_iterations: int = 10,
    ):
        # LLM 客户端
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.max_iterations = max_iterations

        # ── 工具发现 + 注册 + schema 构建 ─────────────
        # import → 触发 register() → 从 registry 获取 → 构建 OpenAI schema
        discover_tools()
        tool_names = get_toolset(toolset)
        self.tools = build_openai_schemas(tool_names)

        # 系统提示词
        self.system_prompt = (
            "你是一个有用的 AI 助手，可以使用工具来完成任务。"
            "当需要读取文件、执行命令时，请使用对应的工具。"
            "用中文回复用户。"
        )

        # 对话历史 — 以 system 消息开头
        self.messages = [
            {"role": "system", "content": self.system_prompt},
        ]

    def run(self, user_message: str) -> str:
        """
        执行一次完整的 Agent 对话。

        流程:
          messages + 用户消息 → [调 LLM → 检查回复 → 执行工具] × N → 返回最终答案
        """
        # 加入用户消息
        self.messages.append({"role": "user", "content": user_message})

        iteration = 0
        while iteration < self.max_iterations:
            iteration += 1

            # ── ① 调用 LLM ────────────────────────────
            response = self._call_llm()
            choice = response.choices[0]
            msg = choice.message

            # ── ② 分支判断 ────────────────────────────
            # finish_reason == "tool_calls" → LLM 想调用工具
            if choice.finish_reason == "tool_calls" and msg.tool_calls:
                # 把 LLM 的工具调用请求存入历史
                self.messages.append(msg.model_dump())

                for tool_call in msg.tool_calls:
                    name = tool_call.function.name
                    args = json.loads(tool_call.function.arguments)

                    print(f"  🔧 [{iteration}] {name}({json.dumps(args, ensure_ascii=False)})")

                    # ③ 执行工具
                    result = self._execute_tool(name, args)
                    print(f"  ✅ [{iteration}] {result[:120]}")

                    # ④ 把工具结果存入历史
                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result,
                    })
                # 回到 while 开头，让 LLM 看到工具结果后继续思考
                continue

            # finish_reason == "stop" → LLM 给出了最终回答
            if msg.content:
                self.messages.append({"role": "assistant", "content": msg.content})
                return msg.content

            # 其他情况（空响应等）
            return f"(LLM 返回了空响应, finish_reason={choice.finish_reason})"

        # 超过最大轮次
        return f"⚠ 超过最大工具调用轮次 ({self.max_iterations})，已强制停止。"

    def _call_llm(self):
        """调用 OpenAI Chat Completions API。tools 非空时启用 function calling 模式。"""
        kwargs = {"model": self.model, "messages": self.messages}
        if self.tools:
            kwargs["tools"] = self.tools
            kwargs["tool_choice"] = "auto"
        return self.client.chat.completions.create(**kwargs)

    def _execute_tool(self, name: str, args: dict) -> str:
        """
        执行一个工具。

        从 registry 获取 handler → 调用 → 用 try/except 保护。
        错误信息作为工具结果返回给 LLM，LLM 可以据此调整策略。
        """
        try:
            handler = get_handler(name)
            if handler is None:
                return f"错误: 未知工具 '{name}'"
            return str(handler(**args))
        except Exception as e:
            return f"错误: 工具 '{name}' 执行失败: {e}"
