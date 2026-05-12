"""
使用统计 — Step 19 新增

学习目标:
  - 理解 token 计费：input tokens + output tokens = 总成本
  - 理解为什么需要统计：控制成本、优化 prompt、选择模型
  - 理解流式 API 的 token 获取时机：最后一个 chunk 才有 usage

估算价格 (2026 参考):
  deepseek-v4-pro: input ¥0.0014/1K, output ¥0.0056/1K (假设)
  gpt-4o-mini:     input $0.00015/1K, output $0.0006/1K
"""

from datetime import datetime


class UsageTracker:
    """追踪单次会话的 token 使用和工具调用"""

    def __init__(self):
        self.input_tokens = 0
        self.output_tokens = 0
        self.reasoning_tokens = 0
        self.tool_calls = 0
        self.llm_calls = 0
        self.start_time = datetime.now()

    def add_llm_call(self, usage=None):
        """记录一次 LLM 调用"""
        self.llm_calls += 1
        if usage:
            self.input_tokens += getattr(usage, "prompt_tokens", 0)
            self.output_tokens += getattr(usage, "completion_tokens", 0)
            # reasoning_tokens 是某些模型的额外字段
            details = getattr(usage, "completion_tokens_details", None)
            if details:
                self.reasoning_tokens += getattr(details, "reasoning_tokens", 0)

    def add_tool_call(self):
        """记录一次工具调用"""
        self.tool_calls += 1

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def elapsed_seconds(self) -> float:
        return (datetime.now() - self.start_time).total_seconds()

    def summary(self) -> str:
        """生成统计摘要"""
        elapsed = self.elapsed_seconds
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)

        lines = [
            "═" * 36,
            "  会话统计",
            "═" * 36,
            f"  耗时:       {minutes}分{seconds}秒",
            f"  LLM 调用:   {self.llm_calls} 次",
            f"  工具调用:   {self.tool_calls} 次",
            f"  input:      {self.input_tokens:,} tokens",
            f"  output:     {self.output_tokens:,} tokens",
            f"  合计:       {self.total_tokens:,} tokens",
            "═" * 36,
        ]
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "reasoning_tokens": self.reasoning_tokens,
            "tool_calls": self.tool_calls,
            "llm_calls": self.llm_calls,
            "elapsed_seconds": self.elapsed_seconds,
        }
