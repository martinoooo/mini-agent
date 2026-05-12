"""
多角色 Profile 管理 — Step 33 新增

学习目标:
  - 理解 Agent Profile：同一个代码，不同的人格和能力
  - 理解 SOUL.md 模式：用文件定义 Agent 的行为风格
  - 理解多角色协作：主 Agent 把任务分给不同角色的子 Agent

Profile 目录: ~/.mini-agent/profiles/<name>/
  ├── SOUL.md        ← 系统提示词（定义人格）
  └── config.json    ← 配置覆盖（可选，工具集/模型等）
"""

import json
from pathlib import Path

PROFILES_DIR = Path.home() / ".mini-agent" / "profiles"

# 内置角色模板
BUILTIN_PROFILES = {
    "coder": (
        "# 资深软件工程师\n\n"
        "你是一位资深软件工程师，擅长 Python 和系统设计。\n"
        "你注重代码质量、可维护性和最佳实践。\n"
        "写代码前先思考架构，完成任务后主动提出改进建议。\n"
        "用中文回复，代码块标注语言。"
    ),
    "researcher": (
        "# 技术研究员\n\n"
        "你是一位技术研究员，擅长搜索和分析技术信息。\n"
        "你会全面调查问题，对比不同方案，给出有深度的分析报告。\n"
        "做研究时使用 web_search 工具，用 delegate_task 分解复杂研究。\n"
        "用中文回复，结论要有依据。"
    ),
    "reviewer": (
        "# 代码审查员\n\n"
        "你是一位代码审查员，专注发现代码中的问题和改进点。\n"
        "你会检查: 安全性、性能、可读性、错误处理、架构设计。\n"
        "每个问题都要指出具体位置和改进建议。\n"
        "用中文回复，使用 constructive feedback 风格。"
    ),
}


class Profile:
    """一个 Agent 角色的配置"""

    def __init__(self, name: str, soul: str, toolset: str = None):
        self.name = name
        self.soul = soul
        self.toolset = toolset  # None = 使用默认

    @property
    def system_prompt(self) -> str:
        return self.soul


class ProfileManager:
    """管理多个 Profile"""

    @staticmethod
    def list_profiles() -> list[str]:
        """列出所有可用 Profile"""
        PROFILES_DIR.mkdir(parents=True, exist_ok=True)
        builtin = set(BUILTIN_PROFILES.keys())
        custom = {d.name for d in PROFILES_DIR.iterdir() if d.is_dir()}
        return sorted(builtin | custom)

    @staticmethod
    def load(name: str) -> Profile:
        """加载指定 Profile"""
        # 1. 尝试从文件系统加载
        profile_dir = PROFILES_DIR / name
        if profile_dir.exists():
            soul_file = profile_dir / "SOUL.md"
            if soul_file.exists():
                soul = soul_file.read_text(encoding="utf-8")

                # 读取可选的 config.json
                toolset = None
                config_file = profile_dir / "config.json"
                if config_file.exists():
                    try:
                        cfg = json.loads(config_file.read_text())
                        toolset = cfg.get("toolset")
                    except Exception:
                        pass

                return Profile(name, soul, toolset)

        # 2. 回退到内置模板
        if name in BUILTIN_PROFILES:
            return Profile(name, BUILTIN_PROFILES[name])

        # 3. 不存在
        raise ValueError(
            f"Profile '{name}' 不存在。可用: {', '.join(ProfileManager.list_profiles())}"
        )

    @staticmethod
    def create(name: str, soul: str = None):
        """创建一个新的 Profile"""
        profile_dir = PROFILES_DIR / name
        profile_dir.mkdir(parents=True, exist_ok=True)

        soul = soul or BUILTIN_PROFILES.get(
            name,
            f"# {name}\n\n你是一个 {name} 角色。用中文回复。",
        )
        (profile_dir / "SOUL.md").write_text(soul, encoding="utf-8")

    @staticmethod
    def init_builtins():
        """初始化内置角色到文件系统（方便用户编辑）"""
        for name, soul in BUILTIN_PROFILES.items():
            profile_dir = PROFILES_DIR / name
            if not profile_dir.exists():
                ProfileManager.create(name, soul)
