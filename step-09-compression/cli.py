"""
CLI 入口 — Step 8: 会话持久化

相比 Step 7 新增的功能:
  - /save [id]    — 保存当前会话（可选指定 ID）
  - /sessions     — 列出所有已保存的会话
  - /load <id>    — 从历史会话恢复继续对话
  - 启动时可指定 LOAD_SESSION 环境变量自动恢复

用法:
  python cli.py                             # 新建会话
  LOAD_SESSION=20260508-xxx python cli.py   # 恢复历史会话
"""

import os
from dotenv import load_dotenv
from agent import AIAgent
from session_store import SessionStore

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))


def main():
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        print("❌ 请设置 DEEPSEEK_API_KEY 环境变量（在 .env 文件中）")
        return

    current_toolset = os.getenv("TOOLSET", "full")

    # 检查是否要恢复历史会话
    load_id = os.getenv("LOAD_SESSION", "")
    if load_id:
        try:
            agent = AIAgent.from_session(
                api_key=api_key,
                session_id=load_id,
                base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            )
            print(f"📂 已恢复会话: {load_id}")
            print(f"   历史消息: {len(agent.messages)} 条")
        except ValueError:
            print(f"⚠ 会话 '{load_id}' 不存在，创建新会话")
            agent = _new_agent(api_key)
    else:
        agent = _new_agent(api_key)

    print("=" * 50)
    print("  Mini Agent Step 8 — 会话持久化")
    print(f"  模型: {agent.model} | 工具集: {current_toolset}")
    if agent.session_id:
        print(f"  会话 ID: {agent.session_id}")
    print("=" * 50)
    print("  命令: /save /sessions /load /tools /toolset /reset /quit")
    print()

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

        # ── 会话持久化命令 ──────────────────────────
        if user_input.startswith("/load "):
            session_id = user_input.split(" ", 1)[1].strip()
            try:
                agent = AIAgent.from_session(
                    api_key=api_key,
                    session_id=session_id,
                    base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
                )
                current_toolset = agent.toolset_name
                print(f"📂 已恢复会话: {session_id}")
                print(f"   历史消息: {len(agent.messages)} 条")
                print(f"   上次对话内容已加载，可以继续聊天或 /reset 重新开始")
            except ValueError:
                print(f"❌ 会话 '{session_id}' 不存在")
            continue

        if user_input == "/save" or user_input.startswith("/save "):
            save_id = user_input.split(" ", 1)[1].strip() if " " in user_input else None
            sid = agent.save_session(save_id)
            print(f"💾 已保存会话: {sid}")
            print(f"   文件: ~/.mini-agent/sessions/{sid}.json")
            continue

        if user_input == "/sessions":
            sessions = SessionStore.list_all()
            if not sessions:
                print("  (暂无已保存的会话)")
            else:
                print(f"  已保存 {len(sessions)} 个会话:")
                for s in sessions:
                    marker = " ← 当前" if s["id"] == agent.session_id else ""
                    print(f"    📝 {s['id']} | {s['message_count']} 条消息 | {s['updated_at'][:16]}{marker}")
                print("  使用 /load <id> 恢复会话")
            continue

        # ── 原有命令 ────────────────────────────────
        if user_input == "/tools":
            from tools.registry import get_all
            for name, info in get_all().items():
                print(f"  🔧 {name} — {info['description'][:80]}")
            continue

        if user_input == "/reset":
            agent.messages = [{"role": "system", "content": agent.system_prompt}]
            agent.session_id = None
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
        if result.startswith("⚠") or result.startswith("(LLM"):
            print(f"\n{result}")
        else:
            print()


def _new_agent(api_key: str) -> AIAgent:
    return AIAgent(
        api_key=api_key,
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        model=os.getenv("MODEL", "deepseek-v4-pro"),
        toolset=os.getenv("TOOLSET", "full"),
        max_iterations=10,
    )


if __name__ == "__main__":
    main()
