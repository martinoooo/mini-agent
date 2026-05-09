"""
配置系统 — Step 16 新增

学习目标:
  - 理解为什么需要配置管理：环境变量太多难以维护
  - 理解配置优先级：命令行 > 环境变量 > 配置文件 > 默认值
  - 理解关注点分离：.env 管密钥，config.json 管行为

配置文件位置（按优先级）:
  1. 项目目录 ./config.json
  2. 用户目录 ~/.mini-agent/config.json

配置优先级（从高到低）:
  环境变量 > config.json > 默认值
"""

import json
import os
from pathlib import Path

# 默认配置
DEFAULTS = {
    "model": "deepseek-v4-pro",
    "base_url": "https://api.deepseek.com",
    "provider_type": "openai_compat",
    "toolset": "full",
    "max_iterations": 10,
    "approval": True,
    "compress_threshold": 4000,
}

# 搜索路径
CONFIG_PATHS = [
    Path.cwd() / "config.json",
    Path.home() / ".mini-agent" / "config.json",
]

# 示例配置模板（首次运行时写入）
CONFIG_TEMPLATE = {
    "_comment": "密钥请放在 .env 文件中，不要写在这里",
    "model": "deepseek-v4-pro",
    "base_url": "https://api.deepseek.com",
    "provider_type": "openai_compat",
    "toolset": "full",
    "max_iterations": 10,
    "approval": True,
    "compress_threshold": 4000,
}


class Config:
    """
    统一配置管理。

    读取顺序: config.json → 环境变量覆盖 → 返回最终值

    用法:
      config = Config.load()
      print(config.model)        # "deepseek-v4-pro"
      print(config.toolset)      # "dev" (来自环境变量 TOOLSET)
    """

    def __init__(self, data: dict = None):
        data = data or {}
        self.model = data.get("model", DEFAULTS["model"])
        self.base_url = data.get("base_url", DEFAULTS["base_url"])
        self.provider_type = data.get("provider_type", DEFAULTS["provider_type"])
        self.toolset = data.get("toolset", DEFAULTS["toolset"])
        self.max_iterations = data.get("max_iterations", DEFAULTS["max_iterations"])
        self.approval = data.get("approval", DEFAULTS["approval"])
        self.compress_threshold = data.get("compress_threshold", DEFAULTS["compress_threshold"])

    @classmethod
    def load(cls) -> "Config":
        """加载配置：config.json + 环境变量覆盖"""
        data = {}

        # 1. 从 config.json 读取
        for path in CONFIG_PATHS:
            if path.exists():
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        json_data = json.load(f)
                        data.update(json_data)
                except Exception:
                    pass

        # 2. 环境变量覆盖
        env_map = {
            "MODEL": "model",
            "DEEPSEEK_BASE_URL": "base_url",
            "PROVIDER_TYPE": "provider_type",
            "TOOLSET": "toolset",
            "MAX_ITERATIONS": "max_iterations",
            "APPROVAL": "approval",
            "COMPRESS_THRESHOLD": "compress_threshold",
        }
        for env_key, config_key in env_map.items():
            val = os.getenv(env_key)
            if val is not None:
                if config_key in ("max_iterations", "compress_threshold"):
                    try:
                        data[config_key] = int(val)
                    except ValueError:
                        pass
                elif config_key == "approval":
                    data[config_key] = val.lower() not in ("off", "false", "0")
                else:
                    data[config_key] = val

        return cls(data)

    @staticmethod
    def init_config(path: Path = None):
        """创建默认配置文件"""
        path = path or CONFIG_PATHS[0]
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(CONFIG_TEMPLATE, f, ensure_ascii=False, indent=2)
            return True
        return False

    def to_dict(self) -> dict:
        """导出为字典（用于显示和保存）"""
        return {
            "model": self.model,
            "base_url": self.base_url,
            "provider_type": self.provider_type,
            "toolset": self.toolset,
            "max_iterations": self.max_iterations,
            "approval": self.approval,
            "compress_threshold": self.compress_threshold,
        }
