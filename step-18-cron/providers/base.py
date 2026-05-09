"""
Provider 抽象基类 — Step 15 新增

学习目标:
  - 理解适配器模式：Agent 不依赖具体的 LLM SDK
  - 理解抽象基类 (ABC)：定义接口规范，强制子类实现
  - 理解为什么需要这层抽象：换模型不换代码

每个 Provider 子类负责:
  1. 创建对应 SDK 的客户端
  2. 实现流式和非流式 API 调用
  3. 统一返回格式（屏蔽不同 SDK 的差异）
"""

from abc import ABC, abstractmethod
from typing import Iterator


class BaseProvider(ABC):
    """LLM 提供者的抽象基类。所有 Provider 必须继承此类。"""

    def __init__(self, api_key: str, base_url: str = ""):
        self.api_key = api_key
        self.base_url = base_url

    @abstractmethod
    def create_stream(self, model: str, messages: list[dict],
                      tools: list[dict] = None) -> Iterator:
        """
        流式调用 LLM，返回 chunk 迭代器。

        每个 chunk 是一个对象，需包含:
          chunk.choices[0].delta.content        — 文本增量
          chunk.choices[0].delta.tool_calls     — 工具调用增量
          chunk.choices[0].delta.reasoning_content — 思考内容 (可选)
          chunk.choices[0].finish_reason        — 结束原因
        """
        ...

    @abstractmethod
    def create(self, model: str, messages: list[dict],
               max_tokens: int = 512) -> object:
        """
        非流式调用 LLM，返回完整响应对象。

        响应需包含:
          response.choices[0].message.content — 完整文本
        """
        ...
