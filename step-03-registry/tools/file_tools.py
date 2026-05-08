"""
文件操作工具

每个工具文件 = handler 函数 + register() 调用。
import 即注册，无需在别处声明。
"""
from tools.registry import register


def _read_file(path: str) -> str:
    """读取文件内容"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return f"错误: 文件 '{path}' 不存在"
    except Exception as e:
        return f"错误: {e}"


register(
    name="read_file",
    toolset="files",
    description="读取指定文件的内容。传入文件路径，返回文件文本。",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "文件路径"},
        },
        "required": ["path"],
    },
    handler=_read_file,
)
