"""终端命令工具"""
import subprocess
from tools.registry import register


def _run_shell(command: str, timeout: int = 30) -> str:
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=timeout,
        )
        output = result.stdout.strip()
        if result.returncode != 0:
            err = result.stderr.strip()
            return f"[退出码: {result.returncode}]\n{output}\n{err}"
        return output or "(命令成功，无输出)"
    except subprocess.TimeoutExpired:
        return f"错误: 命令超时 (>{timeout}秒)"
    except Exception as e:
        return f"错误: {e}"


register(name="run_shell", toolset="terminal",
         description="执行 shell 命令并返回输出。", parameters={
             "type": "object",
             "properties": {
                 "command": {"type": "string", "description": "要执行的命令"},
                 "timeout": {"type": "integer", "description": "超时秒数"},
             },
             "required": ["command"],
         }, handler=_run_shell)
