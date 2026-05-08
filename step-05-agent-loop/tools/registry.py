"""工具注册表"""
from typing import Callable

_registry: dict[str, dict] = {}


def register(name: str, toolset: str, description: str,
             parameters: dict, handler: Callable):
    _registry[name] = {
        "name": name, "toolset": toolset,
        "description": description, "parameters": parameters,
        "handler": handler,
    }


def get_all() -> dict[str, dict]:
    return dict(_registry)


def get_handler(name: str) -> Callable | None:
    entry = _registry.get(name)
    return entry["handler"] if entry else None


def build_openai_schemas(tool_names: list[str]) -> list[dict]:
    schemas = []
    for name in tool_names:
        t = _registry.get(name)
        if t:
            schemas.append({
                "type": "function",
                "function": {
                    "name": t["name"], "description": t["description"],
                    "parameters": t["parameters"],
                },
            })
    return schemas
