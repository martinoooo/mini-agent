"""
Hook 管理器 — 管理所有已注册的生命周期钩子

学习目标:
  - 理解 Hook 模式：在关键节点插入自定义逻辑
  - 理解为什么 Agent 需要扩展点：不修改核心代码就能添加行为

Hook 类型:
  on_startup(agent)    — Agent 初始化完成时
  on_shutdown(agent)   — Agent 关闭时
  on_tool_call(name, args, result) — 工具调用后（可修改 result）
"""


class HookManager:
    """收集并调用插件钩子"""

    def __init__(self):
        self._hooks: dict[str, list] = {
            "on_startup": [],
            "on_shutdown": [],
            "on_tool_call": [],
        }

    def register(self, hook_name: str, func):
        """注册一个钩子函数"""
        if hook_name in self._hooks:
            self._hooks[hook_name].append(func)

    def invoke(self, hook_name: str, *args, **kwargs):
        """
        调用所有注册的钩子。

        对于 on_tool_call: hook(name, args, result) -> result
          钩子可以修改返回值
        """
        if hook_name not in self._hooks:
            return kwargs.get("result")

        result = kwargs.get("result")
        for fn in self._hooks[hook_name]:
            try:
                if hook_name == "on_tool_call":
                    new_result = fn(
                        kwargs.get("name", ""),
                        kwargs.get("args", {}),
                        result,
                    )
                    if new_result is not None:
                        result = new_result
                else:
                    fn(*args)
            except Exception:
                pass  # 插件出错不影响主流程
        return result

    @property
    def count(self) -> int:
        return sum(len(v) for v in self._hooks.values())
