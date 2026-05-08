# Hermes Agent 架构分析文档

## 1. 项目概述

Hermes Agent 是由 [Nous Research](https://nousresearch.com) 开发的自改进型 AI 智能体。它是目前唯一拥有内置学习循环的智能体——能够从经验中创建技能、在使用中改进技能、主动维护记忆、搜索历史对话、跨会话建立用户模型。它通过统一的网关进程支持 CLI、Telegram、Discord、Slack、WhatsApp、Signal 等 20+ 平台。

**核心版本**: v0.13.0 | **语言**: Python 3.11+ | **许可证**: MIT

---

## 2. 顶层架构

```
                        ┌──────────────────────────────┐
                        │       用户入口层 (Entry)       │
                        │  CLI · TUI · Messaging · API │
                        └──────────┬───────────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                     ▼
     ┌────────────┐      ┌──────────────┐      ┌──────────────┐
     │   cli.py   │      │ gateway/run  │      │  web 面板     │
     │ (HermesCLI)│      │ (Gateway)    │      │  (SPA+API)   │
     └─────┬──────┘      └──────┬───────┘      └──────────────┘
           │                    │
           └──────────┬─────────┘
                      ▼
          ┌───────────────────────┐
          │    run_agent.py       │
          │    (AIAgent 核心)      │
          │   · 会话循环           │
          │   · 工具调用编排       │
          │   · 上下文压缩         │
          │   · 记忆管理           │
          │   · 凭证池             │
          └───┬───────┬───────────┘
              │       │
    ┌─────────▼─┐  ┌──▼──────────────┐
    │ model_    │  │  tools/         │
    │ tools.py  │  │  工具注册表      │
    │ (编排层)  │  │  70+ 工具实现   │
    └─────┬─────┘  └─────────────────┘
          │
    ┌─────▼────────┐
    │ agent/       │
    │ · 提供者适配  │
    │ · 模型元数据  │
    │ · 上下文压缩  │
    │ · 记忆管理    │
    │ · 技能命令    │
    │ · Shell Hooks │
    │ · 错误分类    │
    │ · 使用计费    │
    └──────────────┘
```

### 关键设计原则

1. **自注册工具系统**: 每个工具文件通过 `tools/registry.py` 自注册 schema，无需修改核心代码即可添加工具
2. **提供者适配器模式**: 所有 LLM 提供者通过 `agent/` 中的适配器统一接入
3. **Hook/插件系统**: 支持 Python 插件和 Shell 脚本 Hook 两种扩展方式
4. **会话持久化**: SQLite + FTS5 全文搜索，替代原有的 JSONL 文件方案
5. **流式消费**: 网关层通过 `GatewayStreamConsumer` 将同步回调桥接到异步平台

---

## 3. 目录结构与职责

```
hermes-agent/
├── run_agent.py              # AIAgent 类 — 核心会话循环 (750k+ LOC)
├── model_tools.py            # 工具编排层 — 工具发现、注册、函数调用处理
├── toolsets.py               # 工具集定义 — ~100 个预定义工具集
├── cli.py                    # HermesCLI 类 — 交互式 CLI 编排器
├── hermes_state.py           # SessionDB — SQLite 会话存储 (FTS5 搜索)
├── hermes_constants.py       # 常量定义，get_hermes_home() 路径
├── hermes_logging.py         # 日志系统
├── hermes_time.py            # 时间工具
├── batch_runner.py           # 并行批量轨迹生成
├── trajectory_compressor.py  # 轨迹压缩器 — 用于训练数据准备
├── mini_swe_runner.py        # SWE-bench 运行器
├── utils.py                  # 通用工具函数
│
├── agent/                    # 智能体内部模块
│   ├── anthropic_adapter.py  # Anthropic Messages API 适配器
│   ├── bedrock_adapter.py    # AWS Bedrock 适配器
│   ├── codex_responses_adapter.py  # OpenAI Codex Responses API 适配器
│   ├── gemini_*.py           # Google Gemini 适配器
│   ├── auxiliary_client.py   # 辅助 LLM 客户端 (用于压缩/摘要)
│   ├── context_compressor.py # 上下文窗口自动压缩
│   ├── context_engine.py     # 可插拔上下文引擎抽象
│   ├── context_references.py # 上下文引用管理
│   ├── credential_pool.py    # 凭证池 — 多 API Key 负载均衡
│   ├── credential_sources.py # 凭证来源发现
│   ├── curator.py            # 后台技能维护编排器
│   ├── curator_backup.py     # 技能备份
│   ├── display.py            # 终端显示/格式化
│   ├── error_classifier.py   # API 错误分类与重试策略
│   ├── insights.py           # 使用统计与分析
│   ├── memory_manager.py     # 记忆管理器 — 编排多个记忆后端
│   ├── memory_provider.py    # 记忆提供者抽象
│   ├── model_metadata.py     # 模型元数据 — 上下文长度/定价
│   ├── prompt_builder.py     # 系统提示词构建
│   ├── prompt_caching.py     # 提示词缓存支持
│   ├── shell_hooks.py        # Shell Hook 桥接
│   ├── skill_commands.py     # 技能命令处理
│   ├── skill_preprocessing.py # 技能预处理
│   ├── skill_utils.py        # 技能工具函数
│   ├── think_scrubber.py     # 推理区块清理
│   ├── title_generator.py    # 会话标题生成
│   ├── tool_guardrails.py    # 工具护栏 — 异常行为检测
│   ├── transports/           # 传输层抽象
│   └── usage_pricing.py      # 使用定价计算
│
├── tools/                    # 工具实现 (70+ 工具)
│   ├── registry.py           # 中央注册表 — 工具自注册机制
│   ├── approval.py           # 命令审批系统
│   ├── browser_tool.py       # 浏览器自动化 (Playwright)
│   ├── web_tools.py          # Web 搜索/提取
│   ├── terminal_tool.py      # 终端执行
│   ├── file_tools.py         # 文件操作
│   ├── file_operations.py    # 底层文件 I/O
│   ├── mcp_tool.py           # MCP 协议集成
│   ├── delegate_tool.py      # 子智能体委托
│   ├── skills_tool.py        # 技能系统工具
│   ├── skills_hub.py         # Skills Hub 客户端
│   ├── memory_tool.py        # 记忆工具
│   ├── tts_tool.py           # 文本转语音
│   ├── vision_tools.py       # 视觉分析
│   ├── image_generation_tool.py # 图像生成
│   ├── code_execution_tool.py   # 代码执行
│   ├── cronjob_tools.py      # Cron 作业管理
│   ├── send_message_tool.py  # 跨平台消息发送
│   ├── session_search_tool.py # 会话历史搜索
│   ├── transcription_tools.py  # 语音转录
│   ├── voice_mode.py         # 语音交互模式
│   ├── checkpoint_manager.py # 文件检查点
│   ├── process_registry.py   # 进程注册表
│   ├── environments/         # 终端后端 (7 种)
│   │   ├── local.py          # 本地终端
│   │   ├── docker.py         # Docker 容器
│   │   ├── ssh.py            # SSH 远程
│   │   ├── modal.py          # Modal 无服务器
│   │   ├── daytona.py        # Daytona 无服务器
│   │   ├── singularity.py    # Singularity 容器
│   │   └── vercel_sandbox.py # Vercel 沙箱
│   ├── web_providers/        # Web 搜索后端
│   └── browser_providers/    # 浏览器后端
│
├── gateway/                  # 消息网关
│   ├── run.py                # 网关主入口 (730k+ LOC)
│   ├── session.py            # 会话管理
│   ├── session_context.py    # 会话上下文
│   ├── config.py             # 网关配置
│   ├── delivery.py           # 消息投递
│   ├── stream_consumer.py    # 流式消息消费
│   ├── hooks.py              # 网关 Hook 管理
│   ├── status.py             # 状态报告
│   ├── pairing.py            # DM 配对
│   ├── mirror.py             # 消息镜像
│   ├── channel_directory.py  # 频道目录
│   ├── platform_registry.py  # 平台注册表
│   ├── platforms/            # 20+ 平台适配器
│   │   ├── base.py           # 平台基类
│   │   ├── telegram.py       # Telegram
│   │   ├── discord.py        # Discord
│   │   ├── slack.py          # Slack
│   │   ├── whatsapp.py       # WhatsApp
│   │   ├── signal.py         # Signal
│   │   ├── matrix.py         # Matrix
│   │   ├── email.py          # Email
│   │   ├── dingtalk.py       # 钉钉
│   │   ├── feishu.py         # 飞书
│   │   ├── wecom.py          # 企业微信
│   │   ├── weixin.py         # 微信
│   │   ├── homeassistant.py  # Home Assistant
│   │   ├── webhook.py        # Webhook
│   │   ├── sms.py            # SMS
│   │   ├── api_server.py     # REST API
│   │   └── ...               # 更多平台
│   └── assets/               # 网关静态资源
│
├── hermes_cli/               # CLI 子系统
│   ├── main.py               # CLI 主入口
│   ├── commands.py           # Slash 命令处理
│   ├── config.py             # 配置管理
│   ├── setup.py              # 设置向导
│   ├── gateway.py            # 网关 CLI 命令
│   ├── models.py             # 模型切换
│   ├── tools_config.py       # 工具配置
│   ├── plugins.py            # 插件加载
│   ├── profiles.py           # 配置文件管理
│   ├── skin_engine.py        # 皮肤主题引擎
│   ├── auth.py               # 认证管理 (OAuth/Captcha)
│   ├── web_server.py         # Web 仪表板
│   ├── doctor.py             # 诊断工具
│   ├── curator.py            # 策展 CLI
│   ├── kanban.py             # 看板多智能体
│   └── mcp_config.py         # MCP 配置
│
├── plugins/                  # 插件系统
│   ├── memory/               # 记忆提供者插件 (Honcho, Mem0 等)
│   ├── model-providers/      # 模型后端插件 (30+ 提供商)
│   ├── context_engine/       # 上下文引擎插件
│   ├── image_gen/            # 图像生成插件
│   ├── kanban/               # 看板插件
│   ├── hermes-achievements/  # 成就系统
│   ├── observability/        # 可观测性
│   └── ...                   # 其他领域插件
│
├── skills/                   # 内置技能 (26 个领域)
│   ├── creative/             # 创意生成
│   ├── research/             # 研究分析
│   ├── software-development/ # 软件开发
│   ├── productivity/         # 生产力
│   ├── github/               # GitHub 操作
│   └── ...                   # 更多领域
│
├── optional-skills/          # 可选技能 (需主动启用)
│   ├── mlops/                # MLOps
│   ├── finance/              # 金融
│   ├── security/             # 安全
│   └── ...                   # 更多领域
│
├── acp_adapter/              # ACP 协议适配 (IDE 集成)
├── mcp_serve.py              # MCP 服务端
├── cron/                     # Cron 调度器
│   ├── scheduler.py          # 调度引擎
│   └── jobs.py               # 作业管理
├── providers/                # 提供者抽象
├── ui-tui/                   # React Ink 终端 UI
├── tui_gateway/              # TUI 后端 (Python JSON-RPC)
├── web/                      # Web 仪表板 (React + Vite)
├── website/                  # Docusaurus 文档站
├── environments/             # RL 训练环境 (Atropos)
└── tests/                    # 测试套件 (~900 测试文件)
```

---

## 4. 核心子系统详解

### 4.1 AIAgent 核心循环 (`run_agent.py`)

`AIAgent` 类是整个系统的核心，包含 ~60 个初始化参数，管理完整的会话生命周期：

```
用户消息 → run_conversation()
   │
   ▼
┌─────────────────────────────────────────────────┐
│ 1. 会话初始化                                    │
│    · 数据库会话确保 (SessionDB)                   │
│    · 中断状态清理                                 │
│    · 记忆预取 (MemoryManager.prefetch_all)        │
│    · Todo 状态恢复                                │
│    · 系统提示词构建 (缓存)  ←───────────────┐     │
├─────────────────────────────────────────────┤     │
│ 2. 工具调用循环 (while iterations < max)     │     │
│    ┌──────────────────────────────────┐      │     │
│    │ a. 上下文压缩检查 (preflight)      │      │     │
│    │ b. Hook: pre_llm_call             │      │     │
│    │ c. API 调用 (流式/非流式)          │      │     │
│    │ d. 响应解析 (tool_calls / text)    │      │     │
│    │ e. 工具执行 (handle_function_call) │      │     │
│    │ f. 记忆/后处理                    │      │     │
│    │ g. 验证 nudge 触发                │      │     │
│    └──────────────────────────────────┘      │     │
│    重复直到: 无 tool_call / 超过迭代次数        │     │
├─────────────────────────────────────────────┤     │
│ 3. 后处理                                      │     │
│    · 上下文压缩 (post-loop) ─────────────────┘     │
│    · 记忆刷新                                      │
│    · 技能创建 nudge                                │
│    · 轨迹保存                                      │
└─────────────────────────────────────────────────┘
```

**关键特性**:
- **迭代预算** (`IterationBudget`): 父子智能体共享，防止无限循环
- **中断系统**: 线程作用域中断信号，支持用户打断
- **Fallback 机制**: 当主模型失败时自动切换到备用模型
- **/steer 支持**: 在 API 调用期间收到的用户引导会在下个迭代注入

### 4.2 工具注册表系统 (`tools/registry.py`)

这是项目最具特色的设计之一——零耦合的自注册模式：

```python
# 工具文件 (如 tools/file_tools.py)
from tools.registry import register

register(
    name="read_file",
    toolset="files",
    schema={...},         # OpenAI 函数调用 schema
    handler=read_file_handler,
    description="Read a file from the local filesystem",
    requires_env=[],      # 所需的 API Key 环境变量
    is_async=False,
    check_fn=...          # 运行时可用性检查
)
```

**发现机制**:
1. `discover_builtin_tools()` 扫描 `tools/*.py`
2. 通过 AST 分析检测顶层 `registry.register()` 调用
3. `importlib.import_module()` 动态加载触发注册
4. `model_tools.py` 查询注册表构建工具定义

**优势**:
- 添加新工具只需新建一个文件，无需修改核心代码
- 依赖关系清晰: `registry.py` ← `tools/*.py` ← `model_tools.py` ← `run_agent.py`
- 支持运行时可用性检查 (`check_fn`)——例如，仅当网关运行时 `send_message` 才可用

### 4.3 工具集系统 (`toolsets.py`)

工具集提供灵活的工具分组机制：

```
Web 工具集:    web_search, web_extract
终端工具集:    terminal, process
浏览器工具集:  browser_navigate, browser_snapshot, browser_click, ...
技能工具集:    skills_list, skill_view, skill_manage
记忆工具集:    memory, session_search
委派工具集:    execute_code, delegate_task
...
```

核心工具集 `_HERMES_CORE_TOOLS` 被 CLI 和所有消息平台共享。工具集支持组合（通过 `includes` 引用其他工具集），通过 `resolve_toolset()` 递归解析。

### 4.4 LLM 提供者适配器 (`agent/`)

```
                   ┌───────────────────┐
                   │   AIAgent         │
                   │   (run_agent.py)  │
                   └────────┬──────────┘
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼              ▼
    ┌─────────────┐ ┌────────────┐ ┌──────────────┐
    │ Anthropic   │ │ OpenAI     │ │ Gemini       │
    │ Adapter     │ │ Compatible │ │ Adapter      │
    │ (Messages)  │ │ (Chat/Resp)│ │ (Native/CC)  │
    └─────────────┘ └────────────┘ └──────────────┘
              │             │              │
              ▼             ▼              ▼
    ┌─────────────┐ ┌────────────┐ ┌──────────────┐
    │ AWS Bedrock │ │ Codex Resp │ │ 更多提供商...  │
    │ Adapter     │ │ Adapter    │ │              │
    └─────────────┘ └────────────┘ └──────────────┘
```

**支持的 API 模式**:
- `anthropic_messages`: Anthropic Messages API
- `chat_completions`: OpenAI Chat Completions (兼容 OpenRouter、MiniMax、等)
- `codex_responses`: OpenAI Codex Responses API (Codex CLI、X.AI)
- `bedrock_converse`: AWS Bedrock

**自动检测**: AIAgent 根据 provider 名称和 base_url 自动选择正确的 API 模式。

### 4.5 会话持久化 (`hermes_state.py`)

```
┌─────────────────────────────────────┐
│        SessionDB (SQLite)           │
│                                     │
│  ┌───────────────────────────────┐  │
│  │ sessions 表                   │  │
│  │ · id (主键), source (来源)     │  │
│  │ · 模型/配置/系统提示词         │  │
│  │ · 令牌统计, 成本估算           │  │
│  │ · parent_session_id (压缩链)   │  │
│  └───────────────────────────────┘  │
│           │                         │
│  ┌────────▼──────────────────────┐  │
│  │ messages 表                   │  │
│  │ · session_id (外键)           │  │
│  │ · role, content, tool_calls   │  │
│  │ · 完整的会话消息历史           │  │
│  └───────────────────────────────┘  │
│           │                         │
│  ┌────────▼──────────────────────┐  │
│  │ messages_fts (FTS5 虚拟表)    │  │
│  │ · 全文搜索消息内容            │  │
│  │ · 支持跨会话搜索              │  │
│  └───────────────────────────────┘  │
└─────────────────────────────────────┘
```

**设计特点**:
- WAL 模式支持并发读写
- FTS5 全文搜索支持跨会话搜索
- 压缩触发会话拆分 (parent_session_id 链)
- Batch runner 和 RL 轨迹使用独立存储

### 4.6 消息网关 (`gateway/`)

```
   Telegram  Discord  Slack  WhatsApp  Signal  Email  ...
       │        │       │       │         │       │
       └────────┴───────┴───────┴─────────┴───────┘
                        │
              ┌─────────▼───────────┐
              │   Platform Base     │
              │   (抽象基类)         │
              │   · send_message    │
              │   · on_message      │
              │   · stream_token    │
              └─────────┬───────────┘
                        │
              ┌─────────▼───────────┐
              │   Gateway Runner    │
              │   (gateway/run.py)  │
              │   · 会话路由         │
              │   · 命令解析         │
              │   · Agent 缓存池     │
              │   · 流式消费         │
              └─────────┬───────────┘
                        │
              ┌─────────▼───────────┐
              │   Gateway Session   │
              │   (session.py)      │
              │   · SessionSource   │
              │   · 重置策略         │
              │   · 系统提示注入     │
              │   · PII 脱敏        │
              └─────────────────────┘
```

**消息流程**:
1. 平台适配器接收用户消息
2. `GatewayRunner._process_message()` 进行配对检查、黑名单过滤、会话查找
3. 消息委托给 AIAgent 进行 LLM 处理
4. `GatewayStreamConsumer` 将同步流式回调桥接到异步平台编辑
5. 响应通过对应平台适配器投递

**Agent 缓存池**: LRU + TTL 驱逐策略（最大 128 个 Agent，空闲 1h 超时），控制长期运行网关的内存增长。

### 4.7 记忆系统 (`agent/memory_manager.py`)

```
┌─────────────────────────────────────┐
│          MemoryManager              │
│                                     │
│  ┌───────────────────────────────┐  │
│  │ 内置提供者                      │  │
│  │ · MEMORY.md (文件系统)         │  │
│  │ · USER.md (用户画像)           │  │
│  │ · 会话历史搜索 (FTS5)          │  │
│  └───────────────────────────────┘  │
│  ┌───────────────────────────────┐  │
│  │ 外部插件 (仅允许 1 个)         │  │
│  │ · Honcho (辨证用户建模)        │  │
│  │ · Mem0, Supermemory 等        │  │
│  └───────────────────────────────┘  │
│                                     │
│  生命周期:                           │
│  prefetch_all() → system_prompt()   │
│  → sync_all() → post_turn()         │
└─────────────────────────────────────┘
```

### 4.8 技能系统 (`skills/` + `tools/skills_tool.py`)

```
        ┌───────────────────┐
        │   技能生命周期      │
        │                   │
        │  draft → active   │
        │            ↓      │
        │         archived  │
        └───────────────────┘

  自动创建: Agent 在复杂任务后使用 skill_manage 创建技能
  自我改进: 技能在使用中更新
  策展 (Curator): 后台审查技能，自动归档不活跃技能
  技能 Hub: 支持从 agentskills.io 社区分享/导入技能
```

**技能创建触发逻辑**:
1. 该次 turn 的工具调用次数超过 `skill_nudge_interval` 阈值
2. Agent 使用 `skill_manage` 工具创建技能文档
3. 技能存储在 `~/.hermes/skills/` 或从 Skills Hub 同步

### 4.9 上下文压缩 (`agent/context_compressor.py`)

```
  消息列表: [sys] [user] [asst] [tool] [asst] ... [tool] [asst] [user]
              ▲                                           ▲
              │ 保护头 (前 N 条)                            │ 保护尾 (后 N 条)
              └────────────────压缩中间─────────────────────┘
                                     │
                          ┌──────────▼──────────┐
                          │ 辅助 LLM (轻量/快速)  │
                          │ 生成结构化摘要:       │
                          │ · 已解决问题          │
                          │ · 未决问题            │
                          │ · 当前状态            │
                          │ · 剩余工作            │
                          └─────────────────────┘
```

### 4.10 Cron 调度器 (`cron/`)

```
  ┌────────────────────────────────┐
  │      Cron Scheduler            │
  │      (每 60s tick)              │
  │                                │
  │  · 文件锁防并发                 │
  │  · 作业到期检查                 │
  │  · 触发 Agent 执行              │
  │  · 结果投递到指定平台           │
  │  · 提示注入防护 (安全扫描)      │
  └────────────────────────────────┘
```

### 4.11 子智能体委派 (`tools/delegate_tool.py`)

- 通过 `delegate_task` 工具生成隔离的子智能体
- 子智能体继承父智能体的凭证池和令牌预算
- 通过 ThreadPoolExecutor 实现并发委派
- 支持文件状态共享（跨智能体文件名避免冲突）
- 通过 `process_registry.py` 管理子进程生命周期

---

## 5. 数据流全景

```
┌─ 用户输入 ───────────────────────────────────────────────────────┐
│                                                                 │
│  CLI:      hermes_cli/main.py → AIAgent.run_conversation()       │
│  Gateway:  gateway/run.py → GatewaySession → AIAgent             │
│  Cron:     cron/scheduler.py → AIAgent (auto-approve)             │
│  Batch:    batch_runner.py → multiprocessing → AIAgent           │
│  TUI:      ui-tui/ → tui_gateway/ → AIAgent                     │
│  Web:      web/ → gateway/platforms/api_server.py → AIAgent      │
│                                                                 │
├─ 会话 ──────────────────────────────────────────────────────────┤
│                                                                 │
│  每次 run_conversation():                                        │
│  ① SessionDB 记录 (会话开始/更新)                                │
│  ② MemoryManager.prefetch_all() 预取上下文                       │
│  ③ 系统提示词构建 (prompt_builder.py)                           │
│  ④ 工具发现 + 可用性检查 (model_tools.py)                       │
│  ⑤ 上下文压缩 preflight 检查                                    │
│                                                                 │
├─ 迭代 ──────────────────────────────────────────────────────────┤
│                                                                 │
│  每个工具调用迭代 (最多 90 次):                                  │
│  ┌──────────────────────────────────────┐                       │
│  │ pre_llm_call Hook                    │                       │
│  │ → /steer 注入                        │                       │
│  │ → 凭证池分配                         │                       │
│  │ → API 调用 (流式)                    │                       │
│  │ → 工具护栏扫描                       │                       │
│  │ → handle_function_call()               │                       │
│  │ → 工具输出截断 (max_result_size)     │                       │
│  │ → SessionDB 写入                     │                       │
│  └──────────────────────────────────────┘                       │
│                                                                 │
├─ 后处理 ───────────────────────────────────────────────────────┤
│                                                                 │
│  · ContextCompressor 压缩 (如需)                                 │
│  · MemoryManager.sync_all() 同步记忆                             │
│  · 技能创建 Nudge 检查                                          │
│  · 轨迹保存 (JSONL, 可选)                                        │
│  · 使用统计更新                                                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 6. 技术栈与依赖

| 类别 | 技术 | 用途 |
|------|------|------|
| 核心框架 | Python 3.11+ | 主语言 |
| LLM SDK | OpenAI, Anthropic, boto3, mistralai | 多提供商支持 |
| 终端 UI | prompt_toolkit, rich, simple-term-menu | CLI 交互 |
| Web 仪表板 | FastAPI, uvicorn, React + Vite | Web 管理面板 |
| TUI | Ink (React), Node.js | 高级终端 UI |
| 消息平台 | python-telegram-bot, discord.py, slack-bolt, mautrix | 20+ 平台接入 |
| 数据库 | SQLite (WAL + FTS5) | 会话持久化 |
| 内存 | Honcho, Mem0 (插件) | 用户建模 |
| 调度 | croniter | Cron 作业 |
| 安全 | Playwright, URL 安全扫描 | 浏览器/链接安全 |
| 语音 | faster-whisper, edge-tts, elevenlabs | TTS/STT |
| 测试 | pytest, pytest-asyncio, pytest-xdist | ~900 测试文件 |
| 包管理 | uv, setuptools | 依赖/构建 |
| 容器 | Docker, Singularity, Modal, Daytona, Vercel | 终端隔离 |

---

## 7. 设计亮点

1. **闭路学习循环**: 是目前唯一从使用中自我改进的 Agent——创建技能、更新记忆、搜索历史，形成完整的学习闭环

2. **自注册工具系统**: 添加新工具只需创建一个文件并调用 `registry.register()`，通过 AST 分析自动发现，零耦合

3. **多 API 模式自动适配**: 根据 provider/base_url 自动选择 Anthropic Messages / OpenAI Chat / Codex Responses / Bedrock API

4. **工具集组合系统**: 通过 `includes` 引用实现工具集的嵌套组合，一处修改全局生效

5. **Hook 系统双模式**: Python 插件（高性能）和 Shell 脚本 Hook（低门槛）并存，通过同一 `invoke_hook()` 调度

6. **流式消费桥接**: GatewayStreamConsumer 将同步回调优雅地桥接到异步消息平台编辑

7. **凭证池**: 支持多 API Key 负载均衡和故障转移

8. **Agent 缓存池**: LRU + TTL 驱逐策略，控制长期运行网关的内存增长

9. **上下文压缩**: 通过辅助 LLM 自动压缩中间对话，保护头尾上下文，支持迭代更新

10. **23 种平台覆盖**: 从 Telegram 到企业微信、钉钉、飞书，全面覆盖 IM 生态

---

## 8. 扩展点

| 扩展类型 | 路径 | 机制 |
|---------|------|------|
| 新工具 | `tools/` | 创建 `.py` 文件 + `registry.register()` |
| 新终端后端 | `tools/environments/` | 继承 `base.py` 抽象类 |
| 新消息平台 | `gateway/platforms/` | 继承 `base.py` 抽象类 |
| 新 LLM 提供者 | `plugins/model-providers/` | 插件发现机制 |
| 新记忆后端 | `plugins/memory/` | 实现 MemoryProvider 接口 |
| 新上下文引擎 | `plugins/context_engine/` | 实现 ContextEngine 接口 |
| 新技能 | `skills/` 或 `~/.hermes/skills/` | SKILL.md 文件格式 |
| Shell Hook | `~/.hermes/cli-config.yaml` | `hooks:` 配置块 |
| Python 插件 | `plugins/<name>/` | 插件发现 + Hook 注册 |

---

*文档生成时间: 2026-05-08 | Hermes Agent v0.13.0*
