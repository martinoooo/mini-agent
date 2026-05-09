"""
MCP 桥接层 — 自动发现并注册 MCP Server 工具

学习目标:
  - 理解桥接模式：把外部工具协议翻译为内部注册表格式
  - 理解工具代理：调用代理函数转发到 MCP Server

配置 (config.json):
  {
    "mcp_servers": [
      {
        "name": "filesystem",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
      }
    ]
  }
"""

import os
from tools.registry import register
from tools.mcp_client import MCPClient

# 已连接的 MCP Server 列表
_clients: list[MCPClient] = []
_tool_to_client: dict[str, MCPClient] = {}  # tool_name → client


def connect_servers(config: dict = None):
    """
    连接所有配置的 MCP Server，将其工具注册到 registry。

    在 agent.__init__() 中调用。
    """
    servers = config.get("mcp_servers", []) if config else []
    servers = servers or _env_servers()

    for srv in servers:
        name = srv.get("name", "unknown")
        command = srv.get("command", "")
        args = srv.get("args", [])

        try:
            client = MCPClient(name, command, args)
            _clients.append(client)

            tools = client.list_tools()
            for tool in tools:
                _register_mcp_tool(client, tool)

            print(f"  🔌 MCP [{name}]: {len(tools)} 个工具")
        except Exception as e:
            print(f"  ⚠ MCP [{name}]: 连接失败 - {e}")


def _register_mcp_tool(client: MCPClient, tool: dict):
    """
    将一个 MCP 工具注册到 Agent 的 registry。

    MCP 工具格式:
      {"name": "read_file", "description": "...",
       "inputSchema": {"type": "object", "properties": {...}}}
    """
    tool_name = f"mcp_{tool['name']}"  # 加 mcp_ 前缀避免与内置工具冲突
    description = tool.get("description", "")
    schema = tool.get("inputSchema", {"type": "object", "properties": {}})

    # 创建代理函数（闭包捕获 client 和原始工具名）
    def make_handler(c, t_name):
        def handler(**kwargs):
            return c.call_tool(t_name, kwargs)
        return handler

    register(
        name=tool_name,
        toolset="mcp",
        description=f"[MCP] {description}",
        parameters=schema,
        handler=make_handler(client, tool["name"]),
    )
    _tool_to_client[tool_name] = client


def disconnect_all():
    """断开所有 MCP 连接"""
    for client in _clients:
        try:
            client.close()
        except Exception:
            pass
    _clients.clear()
    _tool_to_client.clear()


def get_connected_count() -> int:
    return len(_clients)


def _env_servers() -> list[dict]:
    """从环境变量读取 MCP Server 配置（简化场景）"""
    raw = os.getenv("MCP_SERVER")
    if not raw:
        return []
    # 格式: MCP_SERVER="name:command:arg1,arg2"
    # 例如: MCP_SERVER="fs:npx:-y @modelcontextprotocol/server-filesystem /tmp"
    parts = raw.split(":", 2)
    if len(parts) >= 3:
        return [{
            "name": parts[0].strip(),
            "command": parts[1].strip(),
            "args": [a.strip() for a in parts[2].split(",")],
        }]
    return []
