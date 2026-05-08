"""
Step 4: 工具集系统 — 按场景组合工具

学习目标:
  - 理解工具集的作用：不让 LLM 面对一大堆无关工具
  - 理解 includes 递归展开：coding 工具集 = files + terminal
  - 理解关注点分离：registry 管注册，toolset 管编组，main 只管调用

运行:
  # 先在项目根目录 cp .env.example .env 并填入 API Key
  python main.py

与 Step 3 的区别:
  - 新增 toolsets.py，定义了 TOOLSETS 字典 + resolve_toolset() 递归展开
  - main.py 通过 get_toolset("coding") 获取工具列表，而不是直接用 get_all()
  - 用户可以通过修改 TOOLSET 变量来切换场景
"""

import os
import json
from dotenv import load_dotenv
from openai import OpenAI

from toolsets import get_toolset, get_all_toolsets, discover_tools
from tools.registry import get_handler, build_openai_schemas

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# ── 场景切换：修改这个变量即可启用不同的工具组合 ──────
# 试试改成 "files" 或 "terminal" 看看区别
TOOLSET = "coding"


def main():
    # 1. 导入工具模块 → 自注册
    discover_tools()

    # 2. 展示可用的工具集
    print("=" * 50)
    print("  Mini Agent Step 4 — 工具集系统")
    print("\n  可用的工具集:")
    for name, desc in get_all_toolsets().items():
        marker = " ← 当前" if name == TOOLSET else ""
        print(f"    📦 {name}: {desc}{marker}")
    print("=" * 50)

    # 3. 根据当前工具集获取工具
    tool_names = get_toolset(TOOLSET)
    tool_schemas = build_openai_schemas(tool_names)
    print(f"\n  当前启用的工具 ({TOOLSET}): {tool_names}\n")

    client = OpenAI(
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    )
    model = os.getenv("MODEL", "deepseek-v4-pro")

    messages = [
        {"role": "system", "content": "你是一个有用的助手，用中文回复。"},
    ]

    print("试试看:")
    print("  - 在终端中列出当前目录文件，然后读取 readme 文件的内容")
    print("  - 写一个 hello.py 输出 Hello World，然后运行它\n")

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

        max_turns = 5
        for turn in range(max_turns):
            response = client.chat.completions.create(
                model=model, messages=messages,
                tools=tool_schemas, tool_choice="auto",
            )
            choice = response.choices[0]
            msg = choice.message

            if choice.finish_reason == "tool_calls" and msg.tool_calls:
                messages.append(msg.model_dump())
                for tc in msg.tool_calls:
                    name = tc.function.name
                    args = json.loads(tc.function.arguments)
                    print(f"  🔧 [{turn+1}] {name}({json.dumps(args, ensure_ascii=False)})")
                    handler = get_handler(name)
                    result = str(handler(**args)) if handler else f"未知工具: {name}"
                    print(f"  ✅ [{turn+1}] {result[:120]}")
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    })
            else:
                answer = msg.content or "(空响应)"
                messages.append({"role": "assistant", "content": answer})
                print(f"\n🤖 {answer}\n")
                break
        else:
            print(f"\n⚠ 达到最大轮次 ({max_turns})")


if __name__ == "__main__":
    main()
