# Agent Framework 理解

面试考察重点不是你用了什么框架，而是你**是否了解不同框架的底层设计与优缺点**。

---

## 一、SSE 原理与 Stream 实现

### SSE 是什么

SSE（Server-Sent Events）是最简单的服务端推送协议——HTTP 长连接 + 单向推送：

```
普通 HTTP:
  客户端请求 → 服务端返回完整响应 → 连接关闭

SSE:
  客户端请求 → 服务端保持连接 → 逐块推送数据 → 推完关闭
```

数据格式极其简单，每行以 `data:` 开头，空行分割事件：

```
data: {"choices":[{"delta":{"content":"你"}}]}

data: {"choices":[{"delta":{"content":"好"}}]}

data: {"choices":[{"delta":{"content":"。"}}]}

data: [DONE]
```

### 为什么用 SSE 而不是 WebSocket

| | SSE | WebSocket |
|---|---|---|
| **方向** | 服务端→客户端（单向） | 双向 |
| **协议** | 纯 HTTP，防火墙友好 | 独立协议，可能被代理拦截 |
| **重连** | 浏览器 `EventSource` 自动重连 | 需手动实现 |
| **复杂度** | 极低 | 需要帧协议、心跳 |

LLM 流式调用的场景是"客户端发一次请求，服务端持续推结果"——**天然就是 SSE 的使用场景**，不需要 WebSocket 的双向能力。

### Mini-Agent 里怎么接 SSE

Provider 抽象层向 API 发一个 `stream=True` 的请求，服务端返回 SSE 流。`_call_llm_stream()`（[agent.py:491-498](../demo/agent.py#L491-L498)）拿到一个 Python 迭代器：

```python
stream = self.provider.create_stream(
    model=self.model,
    messages=self.messages,
    tools=self.tools,
)

for chunk in stream:  # 每次迭代 = 一个 SSE 事件
    delta = chunk.choices[0].delta
    if delta.content:
        Display.text_token(delta.content)  # 逐 token 打印
        content += delta.content
    if delta.tool_calls:
        # 工具调用 JSON 也是分片段到达的，需要按 index 拼接
        ...
```

### Stream 实现的三个陷阱

**陷阱 1：Tool Call 的拼接**

工具调用的 JSON 参数不是一次性到齐的，也是分 chunk 到达：

```
chunk 1: delta.tool_calls[0] = {index: 0, function: {name: "read"}}
chunk 2: delta.tool_calls[0] = {index: 0, function: {arguments: "{\"file"}}
chunk 3: delta.tool_calls[0] = {index: 0, function: {arguments: "_path\":\"/e"}}
chunk 4: delta.tool_calls[0] = {index: 0, function: {arguments: "tc\"}"}}
```

必须**按 index 分组累加**，所有 chunk 收完后才能 `json.loads()`。代码见 [agent.py:537-553](../demo/agent.py#L537-L553)——维护一个 `tool_calls` 字典按 index 累加 fragments，收齐后 `json.loads(arguments)`。

**陷阱 2：Usage 只在最后一个 chunk 出现**

Token 计数不在每个 chunk 里，只在流结束时出现一次：

```python
# agent.py:514-515
if hasattr(chunk, "usage") and chunk.usage:
    self.usage.add_llm_call(chunk.usage)
```

**陷阱 3：思考内容（reasoning）和正式内容是分开的 SSE 事件**

DeepSeek 思考模式先推一长段 `reasoning_content`（思考过程），再推 `content`（正式回复）。代码见 [agent.py:518-529](../demo/agent.py#L518-L529)——思考内容与正式内容的处理逻辑不同：思考可以展示但不一定存入最终消息。

---

## 二、数据 Rollout / Trajectory

### 是什么

**Trajectory（轨迹）** = 一次 Agent 对话的完整执行记录。不只是"用户说了什么、Agent 回了什么"，而是**每一轮 LoopTurn 的每一步**：

```
Trajectory = [
    {
        "turn": 1,
        "model_input":   [system_prompt, user_message, ...],
        "model_output":  {"content": "...", "tool_calls": [...]},
        "tool_executions": [
            {"name": "read_file", "args": {"path": "x"}, "result": "...", "duration_ms": 42},
            {"name": "run_shell", "args": {"command": "ls"}, "result": "...", "duration_ms": 150},
        ],
        "token_usage":   {"input": 1234, "output": 567},
        "finish_reason": "tool_calls",
    },
    {
        "turn": 2,
        ...
    },
]
```

### 为什么要记录 Trajectory

| 用途 | 说明 |
|------|------|
| **调试** | Agent 做错了，回放轨迹看是 LLM 决策错了还是工具执行错了 |
| **评估** | 同一个任务，对比不同 prompt/model/Skill 的轨迹，看哪个更短更准 |
| **训练** | 好的轨迹可以作为 few-shot 示例或 fine-tune 数据 |
| **审计** | 生产环境中出问题，轨迹就是"黑匣子" |
| **Skill 改进** | 分析轨迹发现"实际执行路径比 Skill 模板更短"→ 触发 Skill Improvement |

### 怎么基于框架做 Rollout

**方案 1：在 Middleware/Hook 层自动记录**

每次 ModelCall 和 ToolCall 时框架自动打快照。Trajectory 记录应该是 Middleware 的事，不是 Agent 核心代码的事：

```python
class TrajectoryRecorder:
    def __init__(self):
        self.turns = []
        self._current_turn = {}

    def on_model_call_start(self, messages):
        self._current_turn["model_input"] = deepcopy(messages)

    def on_model_call_end(self, response, usage):
        self._current_turn["model_output"] = response
        self._current_turn["token_usage"] = usage
        self._current_turn["finish_reason"] = response.get("finish_reason")

    def on_tool_call_start(self, name, args):
        self._current_turn.setdefault("tool_executions", []).append(
            {"name": name, "args": args, "start": time.time()}
        )

    def on_tool_call_end(self, name, result):
        exec = self._current_turn["tool_executions"][-1]
        exec["result"] = result
        exec["duration_ms"] = (time.time() - exec["start"]) * 1000

    def on_turn_end(self):
        self.turns.append(self._current_turn)
        self._current_turn = {}
```

Mini-Agent 里 `hooks.invoke("on_tool_call")` 已经是一个记录点——只差把输入输出持久化。

**方案 2：在 Provider 层拦截**

在 HTTP 请求层记录每条发出的请求体和收到的完整响应。这是 OpenAI 兼容 API 的通用做法，不依赖框架。

### 存储策略

| 策略 | 做法 | 适用场景 |
|------|------|---------|
| **全量存储** | 每轮 Turn 存一行 JSON，推理结束后一起写 | 调试、评估 |
| **流式追加** | 每个 Turn 结束就 append 到文件 | 长任务防止丢失 |
| **采样存储** | 只记录失败的，或者每 N 次记录一次 | 生产环境降低开销 |

---

## 三、Middleware / Hook 的用途

一旦提到 Middleware 或 Hook，面试官大概率追问："你用过 Hook 做什么？除了审批还有什么？"

### 完整用途清单

**1. 日志与审计**

```python
def on_tool_call(name, args, result):
    audit_log.info(f"[{timestamp}] tool={name} args={redact(args)} result_len={len(result)}")
```

不只是记"调了什么"，还要记上下文——第几轮、token 花了多少。生产环境出问题，靠这些日志还原现场。

**2. 安全护栏**

```python
def on_pre_tool(name, args):
    if loop_detected(name, args):
        return "⛔ 检测到循环"
    if sensitive_path(args.get("path", "")):
        return "⛔ 禁止访问"
```

Mini-Agent 的 [guardrails.py](../demo/tools/guardrails.py) 就是这类。

**3. 结果脱敏和截断**

```python
def on_tool_call(name, args, result):
    result = re.sub(r'sk-[a-zA-Z0-9]{20,}', '[REDACTED]', result)
    if len(result) > 8000:
        result = result[:8000] + f"\n...[截断，原长度 {len(result)} 字符]"
    return result
```

这不只是安全——也是成本控制。工具返回 50K 字符，LLM 处理它要花大量 token。

**4. 成本追踪**

```python
def on_turn_end(turn):
    cost = turn["input_tokens"] * IN_PRICE + turn["output_tokens"] * OUT_PRICE
    metrics.inc("agent.cost", cost)
    if cost > BUDGET_ALERT:
        notify(f"单轮花费 ${cost:.2f}，超过阈值")
```

**5. 上下文注入**

```python
def pre_model_call(messages):
    # 自动注入环境信息
    messages.insert(1, {"role": "system", "content": f"[环境] 时区:{tz} 用户:{user}"})
    # 注入 RAG 检索结果
    docs = retrieve_relevant(messages[-1]["content"])
    if docs:
        messages.insert(-1, {"role": "system", "content": f"[参考]\n{docs}"})
```

**6. Trajectory 记录**（见上一节）

**7. 限速和资源管理**

```python
def pre_tool_call(name, args):
    if name == "run_shell":
        rate_limiter.check()
    if name == "read_file" and concurrent_reads > 10:
        return "⛔ 并发读取过多，请排队"
```

**8. 错误恢复和降级**

```python
def on_tool_call_error(name, args, error):
    if isinstance(error, TimeoutError):
        return f"执行超时，建议拆分操作"
    if isinstance(error, PermissionError):
        return f"权限不足: {error}"
    return f"错误: {type(error).__name__}"
```

关键：**返回的消息要让 LLM 能据此调整行为**，不能只给 Error。

### 框架对比

| 框架 | Hook/Middleware 机制 | 特点 |
|------|---------------------|------|
| **LangGraph** | `interrupt()`, `Command()`, 自定义 middleware | 内置在图的节点间，强类型状态 |
| **AutoGen** | `@hook` 装饰器 | 事件驱动，消息处理前后 |
| **Semantic Kernel** | Middleware Pipeline | 显式管道，可短路跳过后续 |
| **Mini-Agent** | `HookManager` + `guardrails.check()` | 轻量，`on_startup/on_shutdown/on_tool_call` 三个点 |
| **Claude Code** | Hook 系统（`settings.json`） | 进程外执行，harness 层触发 |

### 面试应答策略

被问 "Middleware 还能做什么" 时，不要只说"审批和日志"。展开讲两三个：

- **安全护栏**（有 guardrails 代码支撑）
- **Trajectory 记录**（体现对 Agent 可观测性的理解）
- **错误恢复和降级**（体现对生产环境的敬畏）
- **Token 截断**（体现对成本控制的意识）

核心论点：**Middleware 是 Agent 框架和企业级 Agent 的分水岭。** Demo 不需要 Middleware——Agent 直接调工具。但生产环境中，所有横切关注点（安全、审计、成本、可观测性）都靠 Middleware 承载，而不是写在 Agent 核心逻辑里。

---

## 四、与 Mini-Agent 代码的对应

| 概念 | Mini-Agent 对应 |
|------|----------------|
| SSE 流式接收 | `_call_llm_stream()` — `for chunk in stream` |
| Tool Call 拼接 | `tool_calls[idx]` 按 index 累加 fragments |
| Usage 捕获 | 最后一个 chunk 的 `chunk.usage` |
| Reasoning 分离 | `delta.reasoning_content` vs `delta.content` |
| Trajectory 记录 | `hooks.invoke("on_tool_call")` — 雏形已有 |
| Middleware 链 | `HookManager` + `guardrails.check()` + `approval.request()` |
| 错误恢复 | `retry_call()` + 工具错误消息回传 LLM |
