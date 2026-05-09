"""
命令审批系统 — Step 11 新增

学习目标:
  - 理解为什么需要审批：危险操作需要人工确认
  - 理解回调模式：将审批逻辑注入 Agent 而不修改核心循环
  - 理解风险分级：不同工具的风险等级不同

设计模式: 策略模式（Strategy Pattern）
  Agent 不关心"怎么审批"，只调用一个回调函数。
  CLI 提供交互式 y/n 审批，未来可以换成别的策略（比如白名单自动放行）。
"""

from typing import Callable, Optional

# 工具风险等级
RISK_LOW = "low"        # 只读操作，无副作用
RISK_MEDIUM = "medium"   # 可写文件，可能有影响
RISK_HIGH = "high"      # 任意命令/代码执行，高风险

TOOL_RISK = {
    "read_file":       RISK_LOW,
    "web_search":      RISK_LOW,
    "write_file":      RISK_MEDIUM,
    "execute_python":  RISK_MEDIUM,
    "run_shell":       RISK_HIGH,
}

# 风险等级数值（用于比较: 数值越大的风险，等级越高）
_RISK_ORDER = {RISK_LOW: 0, RISK_MEDIUM: 1, RISK_HIGH: 2}

# 审批回调类型: (tool_name, args, risk) -> bool
ApprovalCallback = Callable[[str, dict, str], bool]


class ApprovalManager:
    """
    管理工具审批。

    min_risk 决定什么等级开始需要审批:
      "low"    — 所有工具都需要审批（最严格）
      "medium" — write_file、execute_python、run_shell 需要审批
      "high"   — 只有 run_shell 需要审批（最宽松）
    """

    def __init__(self, callback: Optional[ApprovalCallback] = None,
                 min_risk: str = RISK_MEDIUM):
        self.callback = callback
        self.min_risk = min_risk

    def needs_approval(self, tool_name: str) -> bool:
        """该工具是否需要审批"""
        risk = TOOL_RISK.get(tool_name, RISK_LOW)
        return _RISK_ORDER.get(risk, 0) >= _RISK_ORDER.get(self.min_risk, 0)

    def request(self, tool_name: str, args: dict) -> bool:
        """
        请求审批。返回 True 表示批准，False 表示拒绝。

        如果没设置 callback（非交互模式），默认自动批准。
        """
        risk = TOOL_RISK.get(tool_name, RISK_LOW)
        if self.callback:
            return self.callback(tool_name, args, risk)
        return True  # 无回调时自动放行
