"""Provider 抽象层 — 多模型适配"""

from providers.base import BaseProvider
from providers.openai_compat import OpenAICompatProvider


def create_provider(
    provider_type: str,
    api_key: str,
    base_url: str = "",
    model: str = "",
    credential_pool=None,
) -> BaseProvider:
    if provider_type == "openai_compat":
        return OpenAICompatProvider(
            api_key=api_key, base_url=base_url,
            credential_pool=credential_pool,
        )
    else:
        raise ValueError(
            f"未知的 provider 类型: '{provider_type}'。"
            f"当前支持: openai_compat"
        )
