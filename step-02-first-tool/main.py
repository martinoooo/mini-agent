"""
Step 2: 第一个工具 — 给 LLM 一把 "螺丝刀"

学习目标:
  - 理解 Function Calling 机制：LLM 不只是返回文本，还可以返回一个 JSON 说 "我想调用这个函数"
  - 理解工具的组成部分：名称、描述、参数定义（JSON Schema）、实际执行函数
  - 理解工具调用的完整流程：
      用户问问题 → LLM 说"我要调用工具" → 我们执行工具 → 把结果告诉 LLM → LLM 回复用户

运行:
  cp .env.example .env   # 编辑填入你的 API Key
  python main.py

与 Step 1 的区别:
  多传了一个 tools 参数给 API。LLM 收到 tools 后，会自己判断是否需要调用工具。
  如果 LLM 觉得不需要，它就直接回复文本；如果需要，它返回 tool_calls。

延伸思考:
  现在只有一个工具 read_file，工具定义直接写在 main.py 里。
  如果加 10 个工具，main.py 会变得多大？每次加工具都要回来改 main.py 是不是很麻烦？
  这就是 Step 3 要解决的问题——自注册模式。
"""

import os
from dotenv import load_dotenv
from openai import OpenAI
import json

load_dotenv()


# ── 工具定义 ──────────────────────────────────────────
# 一个工具 = 描述（给 LLM 看）+ 实际函数（我们执行）
# 描述用 JSON Schema 格式，告诉 LLM 这个工具叫什么、做什么、需要什么参数

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "读取指定文件的内容。返回文件文本。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "要读取的文件路径",
                    },
                },
                "required": ["path"],
            },
        },
    },
]


# ── 工具的实际执行函数 ────────────────────────────────
# LLM 只负责"决定调用哪个工具、传什么参数"
# 真正干活的是这个函数

def read_file(path: str) -> str:
    """读取文件内容并返回"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        return f"[文件内容] {path}:\n{content}"
    except FileNotFoundError:
        return f"错误: 文件 '{path}' 不存在"
    except Exception as e:
        return f"错误: 无法读取文件 - {e}"


# ── 工具名 → 执行函数的映射 ──────────────────────────
TOOL_HANDLERS = {
    "read_file": read_file,
}


def main():
    client = OpenAI(
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    )
    model = os.getenv("MODEL", "deepseek-v4-pro")

    messages = [
        {"role": "system", "content": "你是一个有用的助手，可以使用工具来帮助用户。用中文回复。"},
    ]

    print("=" * 50)
    print("  Mini Agent Step 2 — 带一个工具的 LLM")
    print("  试试输入: 读取 main.py 的内容")
    print("  试试输入: 读取 /tmp/不存在的文件.txt")
    print("  试试输入: 你好，你叫什么名字？")
    print("=" * 50)

    while True:
        # ── 用户输入 ───────────────────────────────────
        try:
            user_input = input("\n🧑 > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 再见！")
            break

        if not user_input:
            continue
        if user_input in ("/quit", "/exit"):
            print("👋 再见！")
            break

        messages.append({"role": "user", "content": user_input})

        # ── 调用 LLM（带着 tool 列表）─────────────────
        # tool_choice="auto" 表示 LLM 自己决定要不要调用工具
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
        )

        choice = response.choices[0]
        msg = choice.message

        # ── 关键逻辑：检查 LLM 是否要调用工具 ──────────
        if choice.finish_reason == "tool_calls" and msg.tool_calls:
            # LLM 想要调用工具！
            print(f"\n🔧 LLM 请求调用工具:")

            # 先把 LLM 的工具调用请求加入对话历史
            messages.append(msg.model_dump())

            for tool_call in msg.tool_calls:
                name = tool_call.function.name
                args = json.loads(tool_call.function.arguments)

                print(f"   → {name}({json.dumps(args, ensure_ascii=False)})")

                # 执行真正的工具函数
                handler = TOOL_HANDLERS.get(name)
                if handler:
                    result = handler(**args)
                else:
                    result = f"未知工具: {name}"

                print(f"   ← 结果: {result[:100]}...")

                # 把工具执行结果加入对话历史
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                })

            # ── 再次调用 LLM，让它看到工具结果后继续 ────
            print("\n🔄 把结果还给 LLM，等待最终回复...")
            response2 = client.chat.completions.create(
                model=model,
                messages=messages,
            )
            answer = response2.choices[0].message.content
            messages.append({"role": "assistant", "content": answer})
            print(f"\n🤖 {answer}")

        else:
            # LLM 直接回复文本，没调用工具
            answer = msg.content or "(空响应)"
            messages.append({"role": "assistant", "content": answer})
            print(f"\n🤖 {answer}")


if __name__ == "__main__":
    main()
