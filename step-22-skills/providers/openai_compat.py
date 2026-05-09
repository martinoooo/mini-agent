"""
OpenAI 兼容协议 Provider

支持所有 OpenAI Chat Completions 兼容的 API:
  - DeepSeek (api.deepseek.com)
  - OpenAI (api.openai.com)
  - OpenRouter (openrouter.ai)
  - 任何兼容 /v1/chat/completions 的服务

SDK: openai (官方 Python SDK)
"""

from openai import OpenAI

from providers.base import BaseProvider


class OpenAICompatProvider(BaseProvider):
    """封装 OpenAI Python SDK，统一到 BaseProvider 接口"""

    def __init__(self, api_key: str, base_url: str = ""):
        super().__init__(api_key, base_url)
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url if base_url else "https://api.openai.com/v1",
        )

    def create_stream(self, model: str, messages: list[dict],
                      tools: list[dict] = None):
        """流式调用。返回 OpenAI SDK 原生的流式迭代器。"""
        kwargs = {
            "model": model, "messages": messages,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        return self.client.chat.completions.create(**kwargs)

    def create(self, model: str, messages: list[dict],
               max_tokens: int = 512):
        """非流式调用。返回 OpenAI SDK 原生的完整响应。"""
        return self.client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
        )
