# Tools / MCP / Skills 概念辨析

## 一句话区分

| 概念 | 本质 | 一句话 |
|------|------|--------|
| **Tools** | 可调用的函数 | Agent 的**手**——执行操作 |
| **MCP** | 外部进程提供的工具 | Agent 的**外接手臂**——跟 Tools 一样，只是实现在外面 |
| **Skills** | 知识文档 | Agent 的**笔记本**——记录"怎么做"，需要时翻看 |

## 对 LLM 来说

```
                    ┌─────────────────────────────┐
                    │      LLM 的视角              │
                    │                             │
                    │  Tools（API 的 tools 参数）   │
                    │  ├─ read_file               │
                    │  ├─ run_shell               │
                    │  ├─ mcp_search_repos  ← MCP │
                    │  ├─ mcp_create_issue  ← MCP │
                    │  └─ view_skill        ← 加载 Skill 也是 Tool │
                    │                             │
                    │  Skills（system prompt 文本） │
                    │  "[可用技能] deploy-guide,   │
                    │   python-patterns"          │
                    └─────────────────────────────┘
```

**Tools 和 MCP 对 LLM 来说完全一样**——都是 `tools` 参数里的函数，LLM 不知道也不关心这个函数是在 `tools/` 目录里还是外部进程里。

**Skills 不同**——只存在于 system prompt 里作为一段文本提示。LLM 想加载具体内容，还是要调用 `view_skill` 这个 Tool。

## 传递方式

| 概念 | 传给 LLM 的方式 | 代码位置 |
|------|----------------|---------|
| Tools | `tools` 参数（Function Calling） | `client.chat.completions.create(tools=self.tools)` |
| MCP | 同上，工具名加 `mcp_` 前缀 | 同上 |
| Skills | system prompt 文本 | `self.messages[0] = {"role":"system", "content":"[可用技能] ..."}` |

## 注册方式

| 概念 | 注册方式 | 存储位置 |
|------|---------|---------|
| Tools | `register()` 自注册 | `tools/*.py` 文件 |
| MCP | `MCPClient` 自动发现 + `register()` | 外部 MCP Server 进程 |
| Skills | 文件扫描，注入 prompt | `~/.mini-agent/skills/*.md` |

## 来源与协议

| 概念 | 来源 | 通信协议 |
|------|------|---------|
| Tools | 项目内 Python 文件 | Python 函数调用 |
| MCP | 外部进程（npm 包 / 任意语言） | JSON-RPC over stdio/HTTP |
| Skills | 本地 Markdown 文件 | 文件读写 |

## 具体交互示例

```
用户: "帮我搜 GitHub 上 pytorch 的 issues，用之前的调试经验分析"

1. LLM 看到 system prompt: "[可用技能] cuda-debug"
2. LLM 调用 mcp_search_issues("pytorch", "bug")    ← MCP 工具
3. 系统执行 → 返回 issue 列表
4. LLM 调用 view_skill("cuda-debug")                ← 内置 Tool（加载 Skill 也是 Tool）
5. 系统返回技能文档内容
6. LLM 结合 issue 列表 + cuda-debug 经验 → 给出分析
```

## 为什么需要三种

| 概念 | 解决什么问题 |
|------|------------|
| Tools | Agent 的基本能力——读写文件、执行命令 |
| MCP | 能力扩展不依赖代码修改——接入新服务只需改配置 |
| Skills | 知识积累——从对话中学习，下次直接复用 |

## 加入新能力的成本

| 概念 | 操作 |
|------|------|
| 新 Tool | 写一个 `tools/xxx.py` + `toolsets.py` 加一行 |
| 新 MCP | `config.json` 加 3 行配置 + `.env` 加 Token |
| 新 Skill | LLM 对话中说"把刚才的步骤保存为技能" |
