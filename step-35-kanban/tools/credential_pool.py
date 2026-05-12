"""
凭证池 — Step 24 新增

学习目标:
  - 理解为什么需要凭证池: 单个 API Key 有限流、配额和故障风险
  - 理解轮询策略: 多个 Key 轮流使用，分散负载
  - 理解故障转移: Key A 挂了自动切 Key B

配置:
  环境变量 DEEPSEEK_API_KEY 支持逗号分隔多个 Key:
    DEEPSEEK_API_KEY=sk-key1,sk-key2,sk-key3

  或在 config.json 中:
    {"api_keys": ["sk-key1", "sk-key2", "sk-key3"]}
"""

import os
import random
import threading
import time
from typing import Optional


class CredentialPool:
    """
    多 API Key 管理。

    策略:
      - 轮询（round-robin）分配
      - Key 遇到 429 后冷却 60 秒
      - 所有 Key 都被冷却时，选冷却时间最短的
    """

    def __init__(self, keys: list[str] = None):
        self._keys = keys or self._load_keys()
        self._index = 0
        self._cooldowns: dict[int, float] = {}  # {index: cooldown_until_timestamp}
        self._lock = threading.Lock()

    def _load_keys(self) -> list[str]:
        """从环境变量加载多个 Key（逗号分隔）"""
        raw = os.getenv("DEEPSEEK_API_KEY", "")
        keys = [k.strip() for k in raw.split(",") if k.strip()]
        return keys or [raw] if raw else []

    @property
    def key_count(self) -> int:
        return len(self._keys)

    def get_key(self) -> Optional[str]:
        """获取一个可用的 API Key"""
        if not self._keys:
            return None

        with self._lock:
            now = time.time()

            # 尝试找到未冷却的 Key
            for _ in range(len(self._keys)):
                idx = self._index % len(self._keys)
                self._index += 1

                cooldown = self._cooldowns.get(idx, 0)
                if now >= cooldown:
                    return self._keys[idx]

            # 全部冷却中，选最快恢复的
            best_idx = min(self._cooldowns, key=self._cooldowns.get)
            return self._keys[best_idx]

    def mark_rate_limited(self, key: str):
        """标记某个 Key 被限流，冷却 60 秒"""
        with self._lock:
            for idx, k in enumerate(self._keys):
                if k == key:
                    self._cooldowns[idx] = time.time() + 60
                    break

    @classmethod
    def from_config(cls, config_keys: list[str] = None) -> "CredentialPool":
        """从配置创建（优先 config.json，回退环境变量）"""
        if config_keys:
            return cls(config_keys)
        return cls()
