"""
技能系统 — Step 22 新增

学习目标:
  - 理解 Agent 的"从对话中学习"能力
  - 理解知识外化：把经验存成文件，未来复用
  - 理解技能的生命周期：创建 → 查看 → 应用

与 Hermes 的关系:
  Hermes 有完整的技能系统（skills/ 目录 + skills_tool.py），
  支持技能创建、更新、归档、Skills Hub 社区分享。
  这里是极简版——创建 .md 文件，启动时列名，调用时加载。

技能 vs 记忆:
  记忆 (MEMORY.md):  "用户叫小明，喜欢 Python"（事实）
  技能 (skills/):     "部署 mini-agent 的步骤"（过程知识）
"""

from pathlib import Path
from tools.registry import register

SKILLS_DIR = Path.home() / ".mini-agent" / "skills"


def _ensure_dir():
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)


def _create_skill(name: str, content: str) -> str:
    """创建一个新技能（或覆盖已有技能）"""
    _ensure_dir()
    # 安全文件名：只保留字母数字和下划线
    safe_name = "".join(c if c.isalnum() or c in "_-" else "_" for c in name)
    filepath = SKILLS_DIR / f"{safe_name}.md"

    header = f"# {name}\n\n> 由 Agent 自动创建\n\n"
    filepath.write_text(header + content, encoding="utf-8")
    return f"✅ 技能 '{name}' 已保存 ({len(content)} 字符)"


def _list_skills() -> str:
    """列出所有可用技能"""
    _ensure_dir()
    files = sorted(SKILLS_DIR.glob("*.md"))
    if not files:
        return "(暂无已保存的技能。完成复杂任务后，可以考虑创建技能以便复用。)"
    lines = [f"可用技能 ({len(files)} 个):"]
    for f in files:
        name = f.stem
        # 读取第一行作为简介
        try:
            first_line = f.read_text(encoding="utf-8").split("\n")[0]
            desc = first_line.lstrip("#").strip() or name
        except Exception:
            desc = name
        lines.append(f"  📄 {name} — {desc[:60]}")
    return "\n".join(lines)


def _view_skill(name: str) -> str:
    """查看指定技能的内容"""
    _ensure_dir()
    safe_name = "".join(c if c.isalnum() or c in "_-" else "_" for c in name)
    filepath = SKILLS_DIR / f"{safe_name}.md"
    if not filepath.exists():
        return f"错误: 技能 '{name}' 不存在。使用 list_skills 查看所有可用技能。"
    content = filepath.read_text(encoding="utf-8")
    return content


def _load_skill_names() -> list[str]:
    """启动时调用：返回所有技能名列表"""
    _ensure_dir()
    return sorted([f.stem for f in SKILLS_DIR.glob("*.md")])


register(
    name="create_skill",
    toolset="skill",
    description=(
        "创建一个可复用的技能文档，保存解决某类问题的经验和方法。"
        "适合: 解决复杂问题后，将步骤和方法保存下来供以后复用。"
        "注意: 同名技能会被覆盖。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "技能名称（简洁明了）"},
            "content": {"type": "string", "description": "技能内容（步骤、方法、注意事项等）"},
        },
        "required": ["name", "content"],
    },
    handler=_create_skill,
)

register(
    name="list_skills",
    toolset="skill",
    description="列出所有已保存的技能",
    parameters={"type": "object", "properties": {}, "required": []},
    handler=_list_skills,
)

register(
    name="view_skill",
    toolset="skill",
    description="查看指定技能的完整内容",
    parameters={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "技能名称"},
        },
        "required": ["name"],
    },
    handler=_view_skill,
)
