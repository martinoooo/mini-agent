"""
插件加载器 — 扫描并加载插件

学习目标:
  - 理解插件发现机制：扫描目录 → 动态 import → 提取钩子
  - 理解热插拔：加插件不需要重启 Agent（下次启动自动发现）

插件目录: ~/.mini-agent/plugins/

插件格式:
  任意 .py 文件，定义以下函数（可选）:
    def on_startup(agent): ...
    def on_shutdown(agent): ...
    def on_tool_call(name, args, result): ...
      - 返回 None 表示不修改结果
      - 返回字符串表示修改工具返回值
"""

import importlib.util
import sys
from pathlib import Path

from plugins.hooks import HookManager

PLUGINS_DIR = Path.home() / ".mini-agent" / "plugins"

# 标准钩子函数名
HOOK_NAMES = ["on_startup", "on_shutdown", "on_tool_call"]


def discover_plugins(hooks: HookManager) -> int:
    """
    扫描 PLUGINS_DIR，加载所有插件，注册钩子。

    返回: 加载的插件数量
    """
    PLUGINS_DIR.mkdir(parents=True, exist_ok=True)
    count = 0

    for f in sorted(PLUGINS_DIR.glob("*.py")):
        if f.name.startswith("_"):
            continue
        try:
            _load_plugin(f, hooks)
            count += 1
        except Exception:
            pass  # 插件加载失败不影响主流程

    return count


def _load_plugin(filepath: Path, hooks: HookManager):
    """加载单个插件文件"""
    module_name = f"plugin_{filepath.stem}"

    # 动态 import
    spec = importlib.util.spec_from_file_location(module_name, filepath)
    if spec is None or spec.loader is None:
        return
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    # 提取钩子函数
    for hook_name in HOOK_NAMES:
        fn = getattr(module, hook_name, None)
        if callable(fn):
            hooks.register(hook_name, fn)
