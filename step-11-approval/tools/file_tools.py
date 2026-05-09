"""文件操作工具"""
from tools.registry import register


def _read_file(path: str, offset: int = 0, limit: int = 200) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        end = min(offset + limit, len(lines))
        selected = lines[offset:end]
        header = f"[{path} | 行 {offset+1}-{end} / 共 {len(lines)} 行]\n"
        return header + "".join(selected)
    except FileNotFoundError:
        return f"错误: 文件 '{path}' 不存在"
    except Exception as e:
        return f"错误: {e}"


def _write_file(path: str, content: str) -> str:
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"已写入: {path} ({len(content)} 字符)"
    except Exception as e:
        return f"错误: {e}"


register(name="read_file", toolset="files",
         description="读取文件内容。可指定起始行(offset)和行数(limit)。", parameters={
             "type": "object",
             "properties": {
                 "path": {"type": "string", "description": "文件路径"},
                 "offset": {"type": "integer", "description": "起始行号"},
                 "limit": {"type": "integer", "description": "读取行数"},
             },
             "required": ["path"],
         }, handler=_read_file)

register(name="write_file", toolset="files",
         description="写入文件内容（覆盖模式）", parameters={
             "type": "object",
             "properties": {
                 "path": {"type": "string", "description": "文件路径"},
                 "content": {"type": "string", "description": "要写入的内容"},
             },
             "required": ["path", "content"],
         }, handler=_write_file)
