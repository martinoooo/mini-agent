"""Provider 抽象层 — 多模型适配"""

from providers.base import BaseProvider
from providers.openai_compat import OpenAICompatProvider


def create_provider(
    provider_type: str,
    api_key: str,
    base_url: str = "",
    model: str = "",
) -> BaseProvider:
    """
    工厂函数：根据 provider_type 创建对应的 Provider 实例。

    provider_type 可选值:
      "openai_compat"  — OpenAI 兼容协议 (DeepSeek / OpenAI / OpenRouter 等)

    扩展:
      添加新 Provider 只需:
      1. 新建 providers/xxx.py 继承 BaseProvider
      2. 在这里加一行 elif
    """
    if provider_type == "openai_compat":
        return OpenAICompatProvider(api_key=api_key, base_url=base_url)
    else:
        raise ValueError(
            f"未知的 provider 类型: '{provider_type}'。"
            f"当前支持: openai_compat"
        )
