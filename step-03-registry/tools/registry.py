"""
工具注册表 — 极简版

这就是 Hermes Agent 的核心设计模式：自注册。
每个工具文件在被 import 时，调用 register() 把自己写入全局注册表。
添加新工具 = 新建一个 .py 文件。不需要修改任何现有代码。
"""

from typing import Callable

# 全局注册表。Python 的 import 机制保证它只初始化一次，
# 所有模块共享同一份数据。
_registry: dict[str, dict] = {}


def register(name: str, toolset: str, description: str,
             parameters: dict, handler: Callable):
    """
    注册一个工具。每个工具模块在 import 时调用此函数。

    name        - 工具名称，LLM 用这个名字来调用
    toolset     - 所属工具集，用于分组管理（Step 4 会用到）
    description - 给 LLM 看的描述，LLM 据此判断何时调用
    parameters  - JSON Schema 格式的参数定义
    handler     - 实际执行的 Python 函数
    """
    _registry[name] = {
        "name": name,
        "toolset": toolset,
        "description": description,
        "parameters": parameters,
        "handler": handler,
    }


def get_all() -> dict[str, dict]:
    """返回所有已注册的工具"""
    return dict(_registry)


def get_by_toolset(toolset: str) -> dict[str, dict]:
    """按工具集名称过滤"""
    return {n: t for n, t in _registry.items() if t["toolset"] == toolset}


def get_handler(name: str) -> Callable | None:
    """根据工具名获取 handler 函数"""
    entry = _registry.get(name)
    return entry["handler"] if entry else None


def build_openai_schemas(tool_names: list[str]) -> list[dict]:
    """
    将已注册工具转换为 OpenAI Function Calling 格式。
    这是 registry 和 LLM 之间的桥梁。
    """
    schemas = []
    for name in tool_names:
        t = _registry.get(name)
        if t:
            schemas.append({
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["parameters"],
                },
            })
    return schemas
