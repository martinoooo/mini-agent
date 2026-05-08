"""
CLI 入口 — 交互式命令行

学习目标:
  - 理解 CLI 的职责：只负责输入/输出，把所有逻辑委托给 AIAgent
  - 理解 agent.py 和 cli.py 的分工：agent 管循环，cli 管交互

与 Step 4 的区别:
  Step 4 及之前所有逻辑都在 main.py 里。现在拆成了：
    agent.py → 只管 Agent Loop
    cli.py   → 只管输入输出
    两个文件，职责清晰。

运行:
  cp .env.example .env
  python cli.py
"""

import os
from dotenv import load_dotenv
from agent import AIAgent

load_dotenv()


def main():
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        print("❌ 请设置 DEEPSEEK_API_KEY 环境变量（在 .env 文件中）")
        return

    # 初始化 Agent — 一行代码
    agent = AIAgent(
        api_key=api_key,
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        model=os.getenv("MODEL", "deepseek-v4-pro"),
        toolset="full",
        max_iterations=10,
    )

    print("=" * 50)
    print("  Mini Agent Step 5 — 完整 Agent")
    print(f"  模型: {agent.model} | 工具: {len(agent.tools)} 个")
    print("  输入消息开始对话，/quit 退出，/tools 查看工具")
    print("=" * 50)

    user_count = 0
    while True:
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
        if user_input == "/tools":
            from tools.registry import get_all
            for name, info in get_all().items():
                print(f"  🔧 {name} — {info['description'][:80]}")
            continue
        if user_input == "/reset":
            agent.messages = [
                {"role": "system", "content": agent.system_prompt},
            ]
            print("🔄 对话已重置")
            continue

        user_count += 1
        result = agent.run(user_input)
        print(f"\n🤖 {result}")


if __name__ == "__main__":
    main()
