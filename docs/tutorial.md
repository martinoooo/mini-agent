# Mini-Agent 从零构建教程

> 35 步从零构建一个完整的 AI Agent，每一步都是可运行的独立项目。
> 借鉴 [Hermes Agent](https://github.com/NousResearch/hermes-agent) 架构设计。

## 学习路线总览

```
基础认知          工具系统            Agent 能力         工程化
────────────────────────────────────────────────────────────
Step 1  LLM调用   Step 3  注册表    Step 7  流式输出    Step 16 配置
Step 2  工具调用   Step 4  工具集    Step 8  会话持久    Step 17 日志
                  Step 5  循环      Step 9  上下文压缩   Step 19 统计
                  Step 6  搜索      Step 10 代码沙箱    Step 25 测试
                                    Step 11 命令审批    Step 30 标题
                                    Step 12 记忆系统    Step 31 擦除器
                                    Step 13 工具护栏
                                    Step 14 错误重试    安全
                                    Step 15 多模型      ──────────
                                    Step 18 定时任务    Step 23 PII脱敏
                                    Step 20 子Agent     Step 11 审批
                                    Step 21 会话搜索    Step 13 护栏
                                    Step 22 技能系统
                                    Step 26 插件系统    协作
                                    Step 27 TUI界面     ──────────
                                    Step 28 MCP协议     Step 33 多角色
                                    Step 29 自升级      Step 34 @路由
                                    Step 32 并行执行    Step 35 Kanban
```

---

## Step 1: Hello LLM — 最简单的 LLM 调用

**学什么**: 理解 LLM 调用的三个角色 — system（设定行为）、user（用户输入）、assistant（模型回复）

**新增文件**:
```
step-01-hello-llm/
  ├── main.py          # ~40 行，API 调用 + 交互循环
  ├── requirements.txt # openai, python-dotenv
  └── .env.example     # API Key 模板
```

**核心代码**:
```python
from openai import OpenAI
client = OpenAI(api_key="...", base_url="https://api.deepseek.com")

messages = [{"role": "system", "content": "你是一个热心的助手"}]

while True:
    user_input = input("🧑 > ")
    messages.append({"role": "user", "content": user_input})
    response = client.chat.completions.create(model="deepseek-v4-pro", messages=messages)
    answer = response.choices[0].message.content
    messages.append({"role": "assistant", "content": answer})
    print(f"🤖 {answer}")
```

**运行**: `cd step-01-hello-llm && cp .env.example .env && python3 main.py`

---

## Step 2: 第一个工具 — 给 LLM 一把螺丝刀

**学什么**: Function Calling 机制 — LLM 不只返回文本，还可以返回 JSON 说"我想调用这个函数"

**改动**: `main.py` 从 40 行扩展到 ~170 行

**核心代码**:
```python
TOOLS = [{
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "读取指定文件的内容",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
}]

response = client.chat.completions.create(
    model=model, messages=messages,
    tools=TOOLS, tool_choice="auto",  # LLM 自己决定是否调工具
)

if response.choices[0].finish_reason == "tool_calls":
    # LLM 想调工具 → 执行 → 把结果还给 LLM → LLM 继续回复
```

**运行**: `cd step-02-first-tool && python3 main.py`

---

## Step 3: 工具注册表 — 自注册模式

**学什么**: 控制反转（IoC）— 工具自己注册自己，加新工具不用改 main.py

**新增文件**:
```
step-03-registry/tools/
  ├── registry.py       # 全局注册表 _registry = {}
  ├── file_tools.py     # import 时自动调用 register()
  └── terminal_tool.py  # 同上
```

**核心代码**:
```python
# registry.py
_registry = {}
def register(name, handler, ...):
    _registry[name] = {...}

# file_tools.py — import 即注册
from tools.registry import register
register(name="read_file", handler=_read_file, ...)
```

**运行**: `cd step-03-registry && python3 main.py`

---

## Step 4: 工具集系统 — 按场景组合工具

**学什么**: 工具太多时不让 LLM 眼花缭乱，按场景打包

**新增文件**: `toolsets.py`

**核心代码**:
```python
TOOLSETS = {
    "files":    {"tools": ["read_file", "write_file"]},
    "terminal": {"tools": ["run_shell"]},
    "coding":   {"includes": ["files", "terminal"]},  # 递归展开
}
```

**运行**: `cd step-04-toolset && python3 main.py`

---

## Step 5: Agent 循环 — 完整闭环

**学什么**: `AIAgent` 类 — LLM → 工具 → LLM → ... 直到得到最终答案

**新增文件**: `agent.py` + `cli.py`

**核心代码**:
```python
class AIAgent:
    def run(self, user_message: str) -> str:
        self.messages.append({"role": "user", "content": user_message})
        while iteration < self.max_iterations:
            response = self._call_llm()
            if finish_reason == "tool_calls":
                execute_tools()  # 执行完继续循环
            else:
                return msg.content  # LLM 回复了文本，结束
```

**运行**: `cd step-05-agent-loop && python3 cli.py`

---

## Step 6: Web 搜索 — 扩展验证自注册模式

**学什么**: 验证自注册模式 — 加 web_search 工具只需新建一个文件，不改核心代码

**新增文件**: `tools/web_tools.py`

**改动**: `toolsets.py` 加 2 行（新增 "web" 工具集 + MODULE_MAP）

**运行**: `cd step-06-web-search && python3 cli.py`

---

## Step 7: 流式输出 — 逐 token 实时打印

**学什么**: SSE 协议 — `stream=True`，token 级别的增量输出

**改动**: `agent.py` — `_call_llm()` 改为 `_call_llm_stream()`

**核心代码**:
```python
stream = client.chat.completions.create(stream=True, ...)
for chunk in stream:
    if chunk.choices[0].delta.content:
        print(delta.content, end="", flush=True)  # 逐字打印
    if chunk.choices[0].delta.tool_calls:
        # 流式 tool_calls 需要按 index 拼接片段
```

**运行**: `cd step-07-streaming && python3 cli.py`

---

## Step 8: 会话持久化 — 保存和恢复对话

**学什么**: JSON 序列化 — 会话存到文件，下次继续聊

**新增文件**: `session_store.py`

**改动**: `agent.py` 加 `save_session()`/`from_session()`，`cli.py` 加 `/save`/`/load`/`/sessions`

**运行**: `cd step-08-persistence && python3 cli.py`

---

## Step 9: 上下文压缩 — token 窗口管理

**学什么**: 长对话用辅助 LLM 自动摘要，保护头尾，压缩中间

**改动**: `agent.py` 加 `_estimate_tokens()` / `_maybe_compress()` / `_generate_summary()`

**核心代码**:
```python
if estimated_tokens > 4000:
    head = messages[:1]       # system prompt
    tail = messages[-6:]      # 最近 6 条
    middle = messages[1:-6]   # 压缩为摘要
    summary = llm(middle)     # 用 LLM 生成摘要
    messages = head + [summary] + tail
```

**运行**: `cd step-09-compression && python3 cli.py`

---

## Step 10: 代码执行沙箱 — subprocess 隔离

**学什么**: 安全执行 Python 代码 — 临时文件 + 超时 + 输出截断

**新增文件**: `tools/code_tools.py` — `execute_python` 工具

**改动**: `toolsets.py` 加 "exec" / "dev" 工具集

**运行**: `cd step-10-sandbox && TOOLSET=dev python3 cli.py`

---

## Step 11: 命令审批 — 高风险操作需确认

**学什么**: 策略模式 — Agent 不关心怎么审批，只调回调函数

**新增文件**: `tools/approval.py` — ApprovalManager + 风险分级（low/medium/high）

**改动**: `agent.py` 加审批检查，`cli.py` 加 y/n 交互回调

**运行**: `cd step-11-approval && python3 cli.py`

---

## Step 12: 记忆系统 — MEMORY.md 自动读写

**学什么**: RAG 雏形 — 启动时读 MEMORY.md 注入 system prompt，LLM 主动写记忆

**新增文件**: `tools/memory_tools.py` — `read_memory` / `write_memory`

**改动**: `agent.py` 启动时加载 MEMORY.md 到 system prompt

**运行**: `cd step-12-memory && python3 cli.py`

---

## Step 13: 工具护栏 — 循环检测 + 敏感路径 + 超长命令

**学什么**: 安全防线 — 不信任 LLM，系统强制执行规则

**新增文件**: `tools/guardrails.py`

**改动**: `agent.py` — `_execute_tool()` 执行前过护栏

**运行**: `cd step-13-guardrails && python3 cli.py`

---

## Step 14: 错误分类与重试 — 指数退避

**学什么**: 容错设计 — 429/5xx/超时可重试，400/401 不重试

**新增文件**: `tools/retry.py` — `classify_error()` + `retry_call()`

**改动**: `agent.py` — API 调用包一层 `retry_call()`

**运行**: `cd step-14-retry && python3 cli.py`

---

## Step 15: 多模型适配 — Provider 抽象层

**学什么**: 适配器模式 — Agent 不依赖具体 LLM SDK

**新增文件**: `providers/` — `base.py`（抽象基类）+ `openai_compat.py`（实现）+ `__init__.py`（工厂函数）

**改动**: `agent.py` — `self.client` 改为 `self.provider`

**架构**:
```
Agent → BaseProvider (抽象) ← OpenAICompatProvider → OpenAI SDK
```

**运行**: `cd step-15-providers && python3 cli.py`

---

## Step 16: 配置系统 — JSON 配置文件

**学什么**: 配置管理 — config.json + 环境变量覆盖

**新增文件**: `config.py` — `Config.load()`

**改动**: `cli.py` — 用 `Config.load()` 替代散落的 `os.getenv()`

**运行**: `cd step-16-config && python3 cli.py`

---

## Step 17: 日志系统 — 双输出（控制台 + 文件）

**学什么**: 结构化日志 — DEBUG/INFO/WARNING/ERROR 分级

**新增文件**: `logger.py`

**改动**: `agent.py` — `print()` 改 `self.log.info()`，`cli.py` 加 `/log` 命令

**运行**: `cd step-17-logging && python3 cli.py`

---

## Step 18: 定时任务 — Cron 调度

**学什么**: 时间感知 — 后台线程轮询，到期提醒注入对话

**新增文件**: `cron/scheduler.py` + `tools/cron_tools.py`

**改动**: `agent.py` 启动 CronScheduler，`run()` 检查到期提醒

**运行**: `cd step-18-cron && python3 cli.py`

---

## Step 19: 使用统计 — Token 追踪

**学什么**: Token 计费模型 — input/output tokens

**新增文件**: `tools/usage.py` — `UsageTracker` 类

**改动**: `agent.py` 捕获流式 usage，`cli.py` 加 `/stats` 命令

**运行**: `cd step-19-usage && python3 cli.py`

---

## Step 20: 子 Agent 委派 — 任务隔离

**学什么**: Agent 委派模式 — 父 Agent spawn 子 Agent 独立执行

**新增文件**: `tools/delegate_tool.py` — `delegate_task` 工具

**核心代码**:
```python
def _run_delegate(task: str) -> str:
    child = AIAgent(...)     # 独立的消息历史
    result = child.run(task) # 独立执行
    return result            # 返回摘要给父 Agent
```

**运行**: `cd step-20-delegate && python3 cli.py`

---

## Step 21: 会话搜索 — 全文搜索历史

**学什么**: 跨会话知识检索 — 搜索所有已保存的对话

**新增文件**: `tools/search_tools.py` — `search_sessions` 工具

**运行**: `cd step-21-search && python3 cli.py`

---

## Step 22: 技能系统 — 可复用技能文档

**学什么**: 知识外化 — Agent 从对话中学习，保存为 .md 技能文件

**新增文件**: `tools/skill_tools.py` — `create_skill` / `list_skills` / `view_skill`

**改动**: `agent.py` 启动时扫描 skills/ 目录注入 system prompt

**运行**: `cd step-22-skills && python3 cli.py`

---

## Step 23: PII 脱敏 — 敏感信息隐藏

**学什么**: 隐私保护 — 正则匹配手机号/邮箱/API Key 等，存储前脱敏

**新增文件**: `tools/redact.py` — `redact()` 函数

**改动**: `agent.py` — 工具结果和用户输入存储前调 `redact()`

**运行**: `cd step-23-redact && python3 cli.py`

---

## Step 24: 凭证池 — 多 API Key 轮询

**学什么**: 负载均衡 — 多个 Key 轮询 + 限流冷却

**新增文件**: `tools/credential_pool.py` — `CredentialPool` 类

**改动**: `providers/` 支持 credential_pool 参数

**运行**: `cd step-24-credpool && DEEPSEEK_API_KEY=k1,k2,k3 python3 cli.py`

---

## Step 25: 测试套件 — 33 个单元测试

**学什么**: 回归保护 — unittest 覆盖所有核心模块

**新增文件**: `tests/test_core.py` — 33 个测试用例

**运行**: `cd step-25-tests && python3 -m unittest tests.test_core -v`

---

## Step 26: 插件系统 — Hook 生命周期

**学什么**: 可扩展性 — 插件放在目录下自动发现，钩子自动触发

**新增文件**: `plugins/` — `loader.py`（动态 import）+ `hooks.py`（HookManager）

**插件格式**（`~/.mini-agent/plugins/example.py`）:
```python
def on_startup(agent): ...
def on_tool_call(name, args, result): ...
def on_shutdown(agent): ...
```

**运行**: `cd step-26-plugins && python3 cli.py`

---

## Step 27: TUI 高级界面 — Rich 库

**学什么**: 显示层抽象 — 彩色面板、Markdown 渲染、表格

**新增文件**: `tui/display.py` — `Display` 类（基于 Rich）

**改动**: `agent.py` — 所有 `print()` 替换为 `Display.xxx()`

**运行**: `cd step-27-tui && python3 cli.py`

---

## Step 28: MCP 协议集成 — 外部工具生态

**学什么**: JSON-RPC over stdio — 接入 MCP Server 的工具

**新增文件**: `tools/mcp_client.py` + `tools/mcp_bridge.py`

**核心代码**:
```python
client = MCPClient("github", "npx", ["-y", "@modelcontextprotocol/server-github"])
tools = client.list_tools()  # 自动发现 26 个 GitHub 工具
```

**运行**: `cd step-28-mcp && python3 cli.py`

---

## Step 29: 自升级机制 — 技能创建 Nudge

**学什么**: 自动学习 — 工具调用≥3次时自动提示创建技能

**改动**: `agent.py` — `run()` 中加 tool_call_count 计数器 + Nudge 注入

**运行**: `cd step-29-self-upgrade && python3 cli.py`

---

## Step 30: 标题生成器 — 会话自动命名

**学什么**: 辅助 LLM 调用 — 保存会话时用 LLM 生成中文标题

**改动**: `agent.py` 加 `_generate_title()`，`session_store.py` 加 title 字段

**效果**: 会话标题从 `20260509-abc123` 变为 `帮我分析代码结构`

---

## Step 31: 思考擦除器 — 节省存储

**学什么**: 存储优化 — 保存前剥离 reasoning_content

**改动**: `agent.py` — `save_session()` 中 `m.pop("reasoning_content", None)`

**效果**: 保存的会话文件体积减少，reload 不触发 DeepSeek reasoning 校验

---

## Step 32: 并行工具执行 — ThreadPoolExecutor

**学什么**: 并发 — 多个独立工具同时执行，不再串行等待

**改动**: `agent.py` — 工具循环从 `for tc in tool_calls` 改为 `ThreadPoolExecutor`

**效果**: 两个 `read_file` 同一秒触发，总时间减半

---

## Step 33: 多角色 Profile — SOUL.md 定义人格

**学什么**: Agent Profile — 同一个代码，不同的人格和能力

**新增文件**: `tools/profile_manager.py` — 3 个内置角色（coder/researcher/reviewer）

**配置**: `~/.mini-agent/profiles/coder/SOUL.md` — "你是资深软件工程师..."

**改动**: 
- `agent.py` — `profile` 参数，加载 SOUL.md 作为 system prompt
- `delegate_tool.py` — 子 Agent 支持 `profile` 参数
- `cli.py` — `PROFILE=coder` 环境变量，`/profile` 命令

**运行**: `cd step-33-profiles && PROFILE=coder python3 cli.py`

---

## Step 34: @角色 路由 — 群聊式协作

**学什么**: 消息路由 — `@coder` 自动路由到对应角色

**新增文件**: `tools/profile_router.py` — `parse_mention()` + `route()`

**改动**: `cli.py` — 输入 `@xxx` 时拦截并路由

**效果**:
```
🧑 > @coder 写排序函数
  → coder Agent 执行（共享频道上下文）
🤖 [@coder]: 以下是快速排序实现...
```

**运行**: `cd step-34-mentions && python3 cli.py`

---

## Step 35: Kanban 看板 — 异步任务调度

**学什么**: 跨会话任务管理 — JSON 存储 + 后台线程执行

**新增文件**: 
- `tools/kanban_store.py` — 任务存储
- `tools/kanban_tools.py` — LLM 可调用的看板工具  
- `cron/kanban_scheduler.py` — 后台调度器

**改动**: `agent.py` 启动 KanbanScheduler，`cli.py` 加 `/kanban` 命令

**效果**:
```
🧑 > 在看板上创建任务"写API"，分配给 @coder
  → 后台调度器认领 todo 任务 → 用 coder profile 执行 → done
🧑 > /kanban
  📋 Todo:0 | 🔄 Doing:0 | ✅ Done:1
```

**运行**: `cd step-35-kanban && python3 cli.py`

---

## 最终架构

```
mini-agent/
├── agent.py              # AIAgent 核心（500+ 行，35 步迭代）
├── cli.py                # 交互入口（@路由 /kanban /profile 等）
├── config.py             # 配置管理
├── logger.py             # 日志系统
├── session_store.py      # 会话持久化
├── providers/            # LLM Provider 抽象
├── plugins/              # 插件系统
├── cron/                 # 定时任务 + Kanban 调度
├── tui/                  # Rich 显示层
├── tests/                # 单元测试
└── tools/                # 15 个工具（全部自注册）
    ├── registry.py       # 注册表
    ├── file_tools.py     # 文件读写
    ├── terminal_tool.py  # 终端命令
    ├── web_tools.py      # 网页搜索
    ├── code_tools.py     # 代码沙箱
    ├── memory_tools.py   # 长期记忆
    ├── cron_tools.py     # 定时提醒
    ├── delegate_tool.py  # 子Agent委派
    ├── search_tools.py   # 会话搜索
    ├── skill_tools.py    # 技能系统
    ├── redact.py         # PII脱敏
    ├── approval.py       # 命令审批
    ├── guardrails.py     # 工具护栏
    ├── retry.py          # 错误重试
    ├── credential_pool.py# 凭证池
    ├── usage.py          # 使用统计
    ├── mcp_client.py     # MCP客户端
    ├── mcp_bridge.py     # MCP桥接
    ├── profile_manager.py# 角色管理
    ├── profile_router.py # @路由
    ├── kanban_store.py   # 看板存储
    └── kanban_tools.py   # 看板工具
```

---

*最后更新: 2026-05-12 | 35 Steps | 15 Tools | 33 Tests*
