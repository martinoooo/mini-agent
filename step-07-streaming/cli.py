"""
CLI 入口 — Step 7: 流式输出

相比 Step 6 的变化:
  - LLM 回复逐 token 实时打印，体验更流畅
  - agent.py 中使用 stream=True，理解 SSE 协议

用法:
  python cli.py                    # 使用默认工具集 (full)
  TOOLSET=research python cli.py   # 使用研究工具集
  TOOLSET=coding python cli.py     # 使用编程工具集
"""

import os
from dotenv import load_dotenv
from agent import AIAgent

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))


def main():
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        print("❌ 请设置 DEEPSEEK_API_KEY 环境变量（在 .env 文件中）")
        return

    # 可通过环境变量切换工具集
    current_toolset = os.getenv("TOOLSET", "full")

    agent = AIAgent(
        api_key=api_key,
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        model=os.getenv("MODEL", "deepseek-v4-pro"),
        toolset=current_toolset,
        max_iterations=10,
    )

    print("=" * 50)
    print("  Mini Agent Step 6 — 完整版")
    print(f"  模型: {agent.model}")
    print(f"  工具集: {current_toolset} ({len(agent.tools)} 个工具)")
    print("=" * 50)
    print("  命令: /tools(查看工具) /toolset(切换) /reset(重置) /quit(退出)")
    print("  试试: 搜索 Python asyncio 的最新用法")
    print("  试试: 先搜索 Git 常用命令，然后把这些命令写入 git-cheatsheet.txt\n")

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

        if user_input == "/tools":
            from tools.registry import get_all
            for name, info in get_all().items():
                print(f"  🔧 {name} — {info['description'][:80]}")
            continue

        if user_input == "/reset":
            agent.messages = [{"role": "system", "content": agent.system_prompt}]
            print("🔄 对话已重置")
            continue

        if user_input == "/toolset":
            from toolsets import get_all_toolsets
            print("  可用工具集:")
            for name, desc in get_all_toolsets().items():
                marker = " ← 当前" if name == current_toolset else ""
                print(f"    📦 {name}: {desc}{marker}")
            print("  使用: TOOLSET=research python cli.py 来切换")
            continue

        result = agent.run(user_input)
        # 结果已在 agent 中流式打印了，只有异常情况才额外显示
        if result.startswith("⚠") or result.startswith("(LLM"):
            print(f"\n{result}")
        else:
            print()  # 流式结束后补一个换行


if __name__ == "__main__":
    main()
