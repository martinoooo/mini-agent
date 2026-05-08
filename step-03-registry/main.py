"""
Step 3: 工具注册表 — 自注册模式

学习目标:
  - 理解自注册（Self-Registration）模式：工具模块在被 import 时自己写入注册表
  - 理解为什么需要注册表：加工具不修改核心代码，新建一个 .py 文件就行
  - 理解依赖链: registry.py ← tools/*.py ← main.py（单向，无循环）

运行:
  # 先在项目根目录 cp .env.example .env 并填入 API Key
  python main.py

与 Step 2 的区别:
  - 工具的 schema 定义和 handler 函数移到了 tools/ 目录下的独立文件
  - 每个工具文件在 import 时自动注册到 registry
  - main.py 不再直接定义 TOOLS 和 TOOL_HANDLERS，而是从 registry 获取

这就是 Hermes Agent 的核心设计模式：
  tools/registry.py  (无依赖 — 最底层)
       ↑
  tools/*.py  (import 时调用 registry.register())
       ↑
  main.py  (查询 registry 构建 tools 列表)
"""

import os
import json
from dotenv import load_dotenv
from openai import OpenAI

# ── 导入工具模块，触发自注册 ──────────────────────────
# 每个工具文件在 import 时自动调用 registry.register()
# 所以只需 import，不需要手动维护工具列表
import tools.file_tools
import tools.terminal_tool

# registry 是唯一的真相来源
from tools.registry import get_all, get_handler, build_openai_schemas

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))


def main():
    client = OpenAI(
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    )
    model = os.getenv("MODEL", "deepseek-v4-pro")

    # ── 展示已经自动注册的工具 ────────────────────────
    all_tools = get_all()
    print("=" * 50)
    print("  Mini Agent Step 3 — 工具注册表")
    print(f"  已注册 {len(all_tools)} 个工具:")
    for name, info in all_tools.items():
        print(f"    🔧 {name} — {info['description'][:50]}...")
    print("=" * 50)

    # ── 把所有已注册的工具转成 OpenAI schema ──────────
    tool_schemas = build_openai_schemas(list(all_tools.keys()))

    messages = [
        {"role": "system", "content": "你是一个有用的助手，可以使用工具来帮助用户。用中文回复。"},
    ]

    print("\n试试:")
    print("  - 读取 main.py 的内容")
    print("  - 看看当前目录有哪些文件")
    print("  - 列出 /tmp 目录下的文件")
    print("  - 你好\n")

    while True:
        try:
            user_input = input("🧑 > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 再见！")
            break

        if not user_input:
            continue
        if user_input in ("/quit", "/exit"):
            print("👋 再见！")
            break

        messages.append({"role": "user", "content": user_input})

        # ── 循环：处理多轮工具调用 ────────────────────
        # Step 2 中我们只处理了一轮工具调用，这里开始处理多轮：
        # LLM 可能先读文件 A，然后根据内容再执行命令 B...
        max_turns = 5
        for turn in range(max_turns):
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                tools=tool_schemas,
                tool_choice="auto",
            )

            choice = response.choices[0]
            msg = choice.message

            if choice.finish_reason == "tool_calls" and msg.tool_calls:
                messages.append(msg.model_dump())

                for tool_call in msg.tool_calls:
                    name = tool_call.function.name
                    args = json.loads(tool_call.function.arguments)

                    print(f"  🔧 [{turn+1}] {name}({json.dumps(args, ensure_ascii=False)})")

                    handler = get_handler(name)
                    if handler:
                        result = str(handler(**args))
                    else:
                        result = f"未知工具: {name}"
                    print(f"  ✅ [{turn+1}] 结果: {result[:150]}")

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result,
                    })
                # 继续循环，让 LLM 看到结果
            else:
                # LLM 输出文本，结束循环
                answer = msg.content or "(空响应)"
                messages.append({"role": "assistant", "content": answer})
                print(f"\n🤖 {answer}\n")
                break
        else:
            print(f"\n⚠ 达到最大工具调用轮次 ({max_turns})")


if __name__ == "__main__":
    main()
