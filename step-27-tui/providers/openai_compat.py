"""
OpenAI 兼容协议 Provider — Step 24 更新

相比之前：支持凭证池，多 Key 轮询 + 故障转移
"""

from openai import OpenAI

from providers.base import BaseProvider


class OpenAICompatProvider(BaseProvider):
    """封装 OpenAI Python SDK，支持单 Key 或凭证池"""

    def __init__(self, api_key: str = "", base_url: str = "",
                 credential_pool=None):
        super().__init__(api_key, base_url)
        self._pool = credential_pool
        self._current_key = api_key
        self._rebuild_client()

    def _rebuild_client(self):
        key = self._current_key or self.api_key
        self.client = OpenAI(
            api_key=key,
            base_url=self.base_url if self.base_url else "https://api.openai.com/v1",
        )

    def _rotate_key(self):
        """切换到凭证池中的下一个可用 Key"""
        if not self._pool:
            return False
        new_key = self._pool.get_key()
        if new_key and new_key != self._current_key:
            self._current_key = new_key
            self._rebuild_client()
            return True
        return False

    def create_stream(self, model: str, messages: list[dict],
                      tools: list[dict] = None):
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
        return self.client.chat.completions.create(
            model=model, messages=messages, max_tokens=max_tokens,
        )

    def on_rate_limited(self):
        """限流时：标记当前 Key + 切换到下一个"""
        if self._pool:
            self._pool.mark_rate_limited(self._current_key)
            self._rotate_key()
