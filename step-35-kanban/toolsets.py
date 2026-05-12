"""
工具集系统 — Step 22 版本

相比 Step 21 的变化：加了 "skill" 工具集（技能系统）
"""

from tools.registry import get_all

TOOLSETS = {
    "files": {
        "description": "文件读写",
        "tools": ["read_file", "write_file"],
        "includes": [],
    },
    "terminal": {
        "description": "终端命令",
        "tools": ["run_shell"],
        "includes": [],
    },
    "web": {
        "description": "互联网搜索",
        "tools": ["web_search"],
        "includes": [],
    },
    "exec": {
        "description": "代码执行沙箱",
        "tools": ["execute_python"],
        "includes": [],
    },
    "memory": {
        "description": "长期记忆",
        "tools": ["read_memory", "write_memory"],
        "includes": [],
    },
    "cron": {
        "description": "定时任务",
        "tools": ["add_reminder", "list_reminders", "delete_reminder"],
        "includes": [],
    },
    "delegate": {
        "description": "子 Agent 委派",
        "tools": ["delegate_task"],
        "includes": [],
    },
    "kanban": {                                       # ← Step 35 新增
        "description": "Kanban 看板",
        "tools": ["kanban_create", "kanban_list", "kanban_show"],
        "includes": [],
    },
    "search": {
        "description": "会话搜索",
        "tools": ["search_sessions"],
        "includes": [],
    },
    "mcp": {                                          # ← Step 28 新增
        "description": "MCP 外部工具",
        "tools": [],
        "includes": [],
    },
    "skill": {
        "description": "技能系统",
        "tools": ["create_skill", "list_skills", "view_skill"],
        "includes": [],
    },
    "coding": {
        "description": "编程开发 — 文件 + 终端",
        "tools": [],
        "includes": ["files", "terminal"],
    },
    "dev": {                                          # ← Step 10 新增
        "description": "开发模式 — coding + 代码执行",
        "tools": [],
        "includes": ["coding", "exec"],
    },
    "research": {
        "description": "研究分析 — 文件 + 搜索",
        "tools": [],
        "includes": ["files", "web"],
    },
    "full": {
        "description": "全部工具",
        "tools": [],
        "includes": ["files", "terminal", "web", "exec", "memory", "cron", "delegate", "search", "skill", "mcp", "kanban"],
    },
}


def resolve_toolset(name: str) -> list[str]:
    if name not in TOOLSETS:
        raise ValueError(f"未知工具集: {name}")
    ts = TOOLSETS[name]
    result = list(ts["tools"])
    for included in ts.get("includes", []):
        result.extend(resolve_toolset(included))
    seen = set()
    deduped = []
    for n in result:
        if n not in seen:
            seen.add(n)
            deduped.append(n)
    return deduped


def get_toolset(name: str) -> list[str]:
    names = resolve_toolset(name)
    registered = set(get_all().keys())
    return [n for n in names if n in registered]


def get_all_toolsets() -> dict:
    return {n: t["description"] for n, t in TOOLSETS.items()}


def discover_tools():
    import importlib
    MODULE_MAP = {
        "tools.file_tools":     ["files"],
        "tools.terminal_tool":  ["terminal"],
        "tools.web_tools":      ["web"],
        "tools.code_tools":     ["exec"],
        "tools.memory_tools":   ["memory"],
        "tools.cron_tools":     ["cron"],
        "tools.delegate_tool":  ["delegate"],
        "tools.search_tools":   ["search"],
        "tools.kanban_tools":   ["kanban"],
        "tools.mcp_bridge":     ["mcp"],
        "tools.skill_tools":    ["skill"],          # ← Step 22 新增
    }
    for mod_name in MODULE_MAP:
        try:
            importlib.import_module(mod_name)
        except Exception as e:
            print(f"⚠ 无法加载 {mod_name}: {e}")
