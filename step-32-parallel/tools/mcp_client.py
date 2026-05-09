"""
MCP 协议客户端 — Step 28 新增

学习目标:
  - 理解 MCP (Model Context Protocol): LLM 连接外部工具的标准协议
  - 理解 JSON-RPC: 请求/响应的简单协议格式
  - 理解 stdio transport: 通过标准输入输出与子进程通信

MCP 协议:
  请求:  {"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}
  响应:  {"jsonrpc":"2.0","id":1,"result":{"tools":[...]}}

可用 MCP Server (需先安装):
  - @modelcontextprotocol/server-filesystem  → 安全文件操作
  - @modelcontextprotocol/server-github      → GitHub API
  - @modelcontextprotocol/server-sqlite      → SQLite 数据库
  - @modelcontextprotocol/server-brave-search → 网页搜索
  - @modelcontextprotocol/server-fetch       → HTTP 请求
  - @modelcontextprotocol/server-memory      → 知识图谱记忆
"""

import json
import subprocess
import threading
import time


class MCPClient:
    """
    最小 MCP JSON-RPC 客户端。

    通过子进程 + stdio 与 MCP Server 通信。
    不需要官方 SDK，只依赖 subprocess 和 json。

    用法:
      client = MCPClient("my-server", "npx", ["-y", "@scope/server-name"])
      tools = client.list_tools()
      result = client.call_tool("tool_name", {"arg": "value"})
    """

    def __init__(self, name: str, command: str, args: list[str],
                 env: dict = None, timeout: int = 30):
        self.name = name
        self._timeout = timeout
        self._request_id = 0
        self._lock = threading.Lock()

        # 启动 MCP Server 进程（继承父进程环境变量 + 额外 env）
        proc_env = os.environ.copy()
        if env:
            proc_env.update(env)

        try:
            self._process = subprocess.Popen(
                [command] + args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=proc_env,
            )
        except FileNotFoundError:
            raise RuntimeError(
                f"命令 '{command}' 未找到。请先安装 MCP Server:\n"
                f"  npm install -g {args[0] if args else command}"
            )
        except Exception as e:
            raise RuntimeError(f"启动 MCP Server 失败: {e}")

        # 发送初始化请求
        self._send("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "mini-agent", "version": "1.0"},
        })
        self._read_response()  # 忽略初始化响应

    # ── 公开 API ──────────────────────────────────

    def list_tools(self) -> list[dict]:
        """获取 MCP Server 提供的工具列表"""
        resp = self._send_and_receive("tools/list", {})
        return resp.get("result", {}).get("tools", [])

    def call_tool(self, tool_name: str, arguments: dict) -> str:
        """调用 MCP Server 的工具"""
        resp = self._send_and_receive("tools/call", {
            "name": tool_name,
            "arguments": arguments,
        })
        result = resp.get("result", {})
        content = result.get("content", [])
        if isinstance(content, list):
            texts = [c.get("text", str(c)) for c in content]
            return "\n".join(texts)
        return str(result)

    def close(self):
        """关闭连接"""
        try:
            self._process.stdin.close()
            self._process.terminate()
            self._process.wait(timeout=5)
        except Exception:
            pass

    # ── JSON-RPC 通信 ─────────────────────────────

    def _send(self, method: str, params: dict):
        self._request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params,
        }
        payload = json.dumps(request) + "\n"
        self._process.stdin.write(payload)
        self._process.stdin.flush()

    def _read_response(self) -> dict:
        line = self._process.stdout.readline()
        if not line:
            raise RuntimeError(f"MCP Server '{self.name}' 已断开")
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            return {"error": f"解析失败: {line[:200]}"}

    def _send_and_receive(self, method: str, params: dict,
                          timeout: int = None) -> dict:
        timeout = timeout or self._timeout
        with self._lock:
            self._send(method, params)
            start = time.time()
            while time.time() - start < timeout:
                resp = self._read_response()
                if resp.get("id") == self._request_id:
                    return resp

        raise TimeoutError(f"MCP 调用 '{method}' 超时 ({timeout}s)")
