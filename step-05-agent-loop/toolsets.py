"""工具集系统"""
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
    "coding": {
        "description": "编程开发 — 文件 + 终端",
        "tools": [],
        "includes": ["files", "terminal"],
    },
    "full": {
        "description": "全部工具",
        "tools": [],
        "includes": ["files", "terminal"],
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
        "tools.file_tools":    ["files"],
        "tools.terminal_tool": ["terminal"],
    }
    for mod_name in MODULE_MAP:
        try:
            importlib.import_module(mod_name)
        except Exception as e:
            print(f"⚠ 无法加载 {mod_name}: {e}")
