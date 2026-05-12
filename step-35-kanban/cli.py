"""
CLI 入口 — Step 35: Kanban 看板

相比 Step 18 新增:
  - UsageTracker 追踪 token 消耗和工具调用次数
  - /stats 命令查看实时统计
  - 退出时自动显示会话统计摘要
  - /log 命令查看日志文件路径和最近日志
  - LOG_LEVEL 环境变量控制日志等级 (DEBUG/INFO/WARNING/ERROR)
"""

import os
from dotenv import load_dotenv
from agent import AIAgent
from session_store import SessionStore
from tools.approval import TOOL_RISK
from config import Config
from logger import setup as setup_logging, LOG_FILE

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))


def _make_approval_callback():
    """创建交互式审批回调：用户输入 y/n 决定是否放行"""

    def ask(tool_name: str, args: dict, risk: str) -> bool:
        risk_label = {"low": "🟢", "medium": "🟡", "high": "🔴"}
        print(f"\n  {risk_label.get(risk, '')} [{risk.upper()}] 工具调用需要审批:")
        print(f"    工具: {tool_name}")
        key_args = {k: v for k, v in args.items()}
        if "code" in key_args:
            key_args["code"] = key_args["code"][:100] + "..." if len(key_args.get("code", "")) > 100 else key_args["code"]
        if "command" in key_args:
            key_args["command"] = key_args["command"][:100]
        for k, v in key_args.items():
            print(f"    {k}: {v}")
        try:
            answer = input("  批准执行? [y/N] > ").strip().lower()
            return answer in ("y", "yes")
        except (EOFError, KeyboardInterrupt):
            return False

    return ask


def main():
    # ── 初始化日志 ──────────────────────────────────
    log_level = os.getenv("LOG_LEVEL", "INFO")
    setup_logging(log_level)

    # ── 初始化内置 Profile ──────────────────────────
    from tools.profile_manager import ProfileManager
    ProfileManager.init_builtins()

    # ── 加载配置 ──────────────────────────────────
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        print("❌ 请设置 DEEPSEEK_API_KEY 环境变量（在 .env 文件中）")
        return

    config = Config.load()

    # 审批回调
    approve_callback = _make_approval_callback() if config.approval else None

    # 恢复历史会话
    load_id = os.getenv("LOAD_SESSION", "")
    if load_id:
        try:
            agent = AIAgent.from_session(
                api_key=api_key,
                session_id=load_id,
                base_url=config.base_url,
                approval_callback=approve_callback,
            )
            print(f"📂 已恢复会话: {load_id}")
        except ValueError:
            print(f"⚠ 会话 '{load_id}' 不存在，创建新会话")
            agent = _new_agent(api_key, config, approve_callback)
    else:
        agent = _new_agent(api_key, config, approve_callback)

    print("=" * 50)
    print("  Mini Agent Step 35 — Kanban 看板")
    print(f"  模型: {config.model} | 工具集: {config.toolset}")
    print(f"  审批: {'开启' if config.approval else '关闭'}")
    if agent.session_id:
        print(f"  会话 ID: {agent.session_id}")
    print("=" * 50)
    print("  命令: /config /log /stats /cron /save /sessions /load /tools /toolset /approval /reset /quit")
    print()

    while True:
        try:
            user_input = input("🧑 > ").strip()
        except (EOFError, KeyboardInterrupt):
            agent.save_session()
            print(f"\n{agent.usage.summary()}")
            print("\n👋 再见！")
            agent.hooks.invoke("on_shutdown", agent)
            agent.kanban.stop()
            agent.cron.stop()
            break

        if not user_input:
            continue

        # ── @角色 路由（Step 34） ─────────────────
        if user_input.startswith("@"):
            from tools.profile_router import parse_mention, route
            parsed = parse_mention(user_input)
            if parsed:
                pname, task = parsed
                agent.messages.append({"role": "user", "content": user_input})
                reply = route(pname, task,
                    api_key=api_key,
                    base_url=config.base_url,
                    model=config.model,
                    shared_messages=agent.messages[1:],
                )
                agent.messages.append({"role": "assistant", "content": f"[@{pname}] {reply}"})
                print(f"\n🤖 [@{pname}] {reply}")
                continue
            # @@ 开头是转义，当做普通消息
            user_input = user_input[1:]

        if user_input in ("/quit", "/exit"):
            sid = agent.save_session()  # 自动保存
            print(f"💾 已自动保存: {sid}")
            print(f"\n{agent.usage.summary()}")
            print("👋 再见！")
            agent.hooks.invoke("on_shutdown", agent)
            agent.kanban.stop()
            agent.cron.stop()
            break

        # ── 配置命令 ──────────────────────────────
        if user_input == "/config" or user_input == "/config show":
            print("  当前配置:")
            for k, v in config.to_dict().items():
                print(f"    {k}: {v}")
            print(f"  (密钥 DEEPSEEK_API_KEY: {'已设置' if api_key else '未设置'})")
            print("  修改: 编辑 ./config.json 或用环境变量覆盖")
            continue

        if user_input == "/config init":
            from config import Config as Cfg
            if Cfg.init_config():
                print("✅ 已创建 config.json")
            else:
                print("  config.json 已存在")
            continue

        if user_input == "/kanban":
            from tools.kanban_store import KanbanStore
            tasks = KanbanStore.list_tasks()
            if not tasks:
                print("  看板为空")
            else:
                counts = {"todo": 0, "doing": 0, "done": 0}
                for t in tasks:
                    counts[t["status"]] = counts.get(t["status"], 0) + 1
                print(f"  📋 Todo: {counts['todo']} | 🔄 Doing: {counts['doing']} | ✅ Done: {counts['done']}")
                for t in tasks[-10:]:
                    icon = {"todo": "📋", "doing": "🔄", "done": "✅"}.get(t["status"], "❓")
                    print(f"  {icon} {t['title']} → @{t['assignee']}")
            continue

        if user_input == "/cron":
            from cron.scheduler import CronScheduler
            tasks = CronScheduler.list_tasks()
            if not tasks:
                print("  (暂无定时任务)")
            else:
                print(f"  待处理 {len(tasks)} 个定时任务:")
                for t in tasks:
                    remaining = max(0, int(t["trigger_at"] - __import__("time").time()))
                    print(f"    📌 {t['description']} ({remaining//60}分钟后)")
            continue

        if user_input == "/stats":
            print(f"\n{agent.usage.summary()}")
            continue

        if user_input == "/log":
            print(f"  日志文件: {LOG_FILE}")
            if LOG_FILE.exists():
                # 显示最近 10 行
                lines = LOG_FILE.read_text(encoding="utf-8").strip().split("\n")
                print(f"  最近 {min(10, len(lines))} 条 (共 {len(lines)} 条):")
                for line in lines[-10:]:
                    print(f"    {line}")
            else:
                print("  (暂无日志)")
            print(f"  日志等级: {log_level} (LOG_LEVEL={os.getenv('LOG_LEVEL', 'INFO')})")
            continue

        # ── 会话持久化命令 ──────────────────────────
        if user_input.startswith("/load "):
            session_id = user_input.split(" ", 1)[1].strip()
            try:
                agent = AIAgent.from_session(
                    api_key=api_key,
                    session_id=session_id,
                    base_url=config.base_url,
                    approval_callback=approve_callback,
                )
                print(f"📂 已恢复会话: {session_id}")
            except ValueError:
                print(f"❌ 会话 '{session_id}' 不存在")
            continue

        if user_input == "/save" or user_input.startswith("/save "):
            save_id = user_input.split(" ", 1)[1].strip() if " " in user_input else None
            sid = agent.save_session(save_id)
            print(f"💾 已保存会话: {sid}")
            continue

        if user_input == "/sessions":
            sessions = SessionStore.list_all()
            if not sessions:
                print("  (暂无已保存的会话)")
            else:
                print(f"  已保存 {len(sessions)} 个会话:")
                for s in sessions:
                    marker = " ← 当前" if s["id"] == agent.session_id else ""
                    t = s.get('title', '') or s['id']
                    print(f"    📝 {t[:30]} | {s['message_count']} 条消息 | {s['updated_at'][:16]}{marker}")
            continue

        # ── 工具 / 审批 / 护栏命令 ────────────────────
        if user_input == "/tools":
            from tools.registry import get_all
            for name, info in get_all().items():
                print(f"  🔧 {name} — {info['description'][:80]}")
            continue

        if user_input == "/reset":
            agent.messages = [{"role": "system", "content": agent.system_prompt}]
            agent.session_id = None
            from tools import guardrails
            guardrails.reset()
            print("🔄 对话已重置")
            continue

        if user_input == "/profile" or user_input.startswith("/profile "):
            from tools.profile_manager import ProfileManager
            parts = user_input.split()
            if len(parts) == 1:
                profiles = ProfileManager.list_profiles()
                current = agent.profile_name or "default"
                print(f"  可用角色 ({len(profiles)} 个):")
                for p in profiles:
                    marker = " ← 当前" if p == current else ""
                    print(f"    👤 {p}{marker}")
                print("  使用: /profile <name> 查看详情 | PROFILE=<name> python cli.py 切换角色")
            else:
                pname = parts[1]
                try:
                    p = ProfileManager.load(pname)
                    print(f"  👤 {p.name}")
                    print(f"  工具集: {p.toolset or '继承默认'}")
                    print(f"  SOUL.md 预览:\n{p.soul[:200]}...")
                except ValueError as e:
                    print(f"  ❌ {e}")
            continue

        if user_input == "/approval":
            print("  工具风险等级:")
            for tool, risk in TOOL_RISK.items():
                label = {"low": "🟢 低", "medium": "🟡 中", "high": "🔴 高"}
                print(f"    {label.get(risk, risk)} — {tool}")
            print(f"  审批状态: {'开启' if config.approval else '关闭'}")
            continue

        if user_input == "/toolset":
            from toolsets import get_all_toolsets
            print("  可用工具集:")
            for name, desc in get_all_toolsets().items():
                marker = " ← 当前" if name == config.toolset else ""
                print(f"    📦 {name}: {desc}{marker}")
            continue

        result = agent.run(user_input)
        if result.startswith("⚠") or result.startswith("(LLM"):
            print(f"\n{result}")
        else:
            print()


def _new_agent(api_key: str, config: Config, approval_cb=None) -> AIAgent:
    profile = os.getenv("PROFILE")
    return AIAgent(
        api_key=api_key,
        base_url=config.base_url,
        model=config.model,
        provider_type=config.provider_type,
        toolset=config.toolset,
        max_iterations=config.max_iterations,
        compress_threshold=config.compress_threshold,
        approval_callback=approval_cb,
        profile=profile,
    )


if __name__ == "__main__":
    main()
