"""
代码执行工具 — Step 10 新增

学习目标:
  - 理解沙箱的基本概念：隔离、超时、输出截断
  - 理解 subprocess 的安全性：为什么不直接 eval()
  - 理解临时文件的用途：代码落盘再执行

与 terminal_tool 的区别:
  terminal_tool 执行 shell 命令（通用但危险）
  code_tools 只执行 Python 代码（专用，可控）
"""

import subprocess
import tempfile
import os
from tools.registry import register


def _execute_python(code: str, timeout: int = 30) -> str:
    """
    在临时文件中执行 Python 代码，返回输出。

    为什么用临时文件而不是 eval()？
      - eval() 只能执行单个表达式
      - 临时文件可以执行任意多行代码
      - subprocess 提供了进程隔离（不是真正的沙箱，但是第一步）
    """
    # 写入临时文件
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, encoding="utf-8"
    ) as f:
        f.write(code)
        tmp_path = f.name

    try:
        result = subprocess.run(
            ["python3", tmp_path],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()

        # 截断过长输出
        max_len = 2000
        output = stdout if stdout else ""
        if stderr:
            output += f"\n[stderr]\n{stderr}"
        if len(output) > max_len:
            output = output[:max_len] + f"\n...(输出已截断，超过 {max_len} 字符)"

        if result.returncode != 0:
            return f"[退出码: {result.returncode}]\n{output}"
        return output or "(代码执行成功，无输出)"
    except subprocess.TimeoutExpired:
        return f"错误: 代码执行超时 (>{timeout}秒)"
    except Exception as e:
        return f"错误: {e}"
    finally:
        # 清理临时文件
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


register(
    name="execute_python",
    toolset="exec",
    description=(
        "执行 Python 代码并返回输出。"
        "可以写多行代码，支持 print() 输出。"
        "适合做计算、数据处理、算法验证等。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "要执行的 Python 代码",
            },
            "timeout": {
                "type": "integer",
                "description": "超时秒数，默认 30",
            },
        },
        "required": ["code"],
    },
    handler=_execute_python,
)
