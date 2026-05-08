"""
工具集系统 — 按场景组合工具

学习目标:
  - 理解为什么需要工具集：不同场景需要不同工具，全给 LLM 反而容易选错
  - 理解 includes 递归展开：工具集可以引用其他工具集（组合模式）
  - 理解关注点分离：registry 管"工具有什么"，toolset 管"工具怎么组合"

新增概念（相比 Step 3）:
  一个全局的 TOOLSETS 字典，定义了基础工具集（files/terminal）和
  组合工具集（coding = files + terminal）。
  resolve_toolset() 函数递归展开 includes 引用。

为什么 TOOLSETS 要放在单独的文件而不是 registry.py 里？
  关注点分离。Registry 管"工具是什么"，Toolset 管"工具怎么组合"。
  两个职责，两个模块。
"""

from tools.registry import get_all

# ── 工具集定义 ────────────────────────────────────────
# 每个工具集可以包含 tools（直接指定工具名）和 includes（引用其他工具集）
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
    # 组合：coding = files + terminal
    "coding": {
        "description": "编程开发—文件操作 + 终端",
        "tools": [],
        "includes": ["files", "terminal"],
    },
    # 全部
    "full": {
        "description": "所有可用工具",
        "tools": [],
        "includes": ["files", "terminal"],
    },
}


def resolve_toolset(name: str) -> list[str]:
    """
    递归展开工具集。

    "coding" → ["read_file", "write_file", "run_shell"]
    "files"  → ["read_file", "write_file"]
    """
    if name not in TOOLSETS:
        raise ValueError(f"未知工具集: {name}")

    ts = TOOLSETS[name]
    result = list(ts["tools"])

    for included in ts.get("includes", []):
        result.extend(resolve_toolset(included))  # 递归

    # 去重但保持顺序
    seen = set()
    deduped = []
    for n in result:
        if n not in seen:
            seen.add(n)
            deduped.append(n)
    return deduped


def get_toolset(name: str) -> list[str]:
    """解析工具集，并校验工具都在 registry 中已注册"""
    names = resolve_toolset(name)
    registered = set(get_all().keys())
    valid = [n for n in names if n in registered]
    missing = set(names) - registered
    if missing:
        print(f"⚠ 工具集 '{name}' 中有未注册的工具: {missing}")
    return valid


def get_all_toolsets() -> dict:
    """返回所有工具集的名称和描述（用于 CLI 展示）"""
    return {n: t["description"] for n, t in TOOLSETS.items()}


def discover_tools():
    """
    导入工具模块 → 触发 registry.register()。

    MODULE_MAP 显式声明了每个模块和它所属工具集的对应关系。
    生产环境中（如 Hermes Agent）这一步是通过 AST 分析自动完成的——
    扫描 tools/*.py 文件中是否有 registry.register() 调用来决定是否加载。
    """
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
