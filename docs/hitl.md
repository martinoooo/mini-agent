# Human in The Loop (HITL)

做在线 Agent 绕不过的话题。HITL 的本质是**在人机之间切换控制权**——Agent 不能所有决策都自己做，删文件、发邮件、花钱操作必须让人确认。

---

## 一、Middleware 机制

业界框架（LangGraph、AutoGen、Semantic Kernel）不把 HITL 做在 Agent 核心里，而是做成**中间件链**——在 ModelCall 和 ToolCall 之间插一层可编程的拦截器。

```
                  ┌──────────────────────────────────┐
                  │       Middleware Chain             │
ModelCall ──────▶ │  PreTurn  → MidTurn → PostTurn    │ ──────▶ ToolCall
                  └──────────────────────────────────┘
```

每条中间件可以对每个 LoopTurn 做三件事：

| 操作 | 效果 |
|------|------|
| **放行** | 不做任何事，流转给下一个中间件 |
| **拦截** | 阻止本次操作，返回一个 StopReason |
| **修改** | 改写 tool 参数、替换 prompt、注入上下文 |

所有中间件共享一个能力——**访问当前 LoopTurn 的完整上下文**（messages、tool_calls、iteration 次数、已使用 token 数），以此决定要不要截停。

**具体框架的实现方式：**

- **LangGraph**：`interrupt()` 本质上是一个内置的 PostTurn 中间件——LLM 决策完要调工具了，中间件喊停等人工审批。配合 checkpoint 机制实现状态持久化。
- **AutoGen**：`@hook` 装饰器，在消息处理前后注入自定义逻辑。
- **Semantic Kernel**：显式的 Middleware Pipeline，每个中间件接收 context 决定是否继续传递。

Middleware 不是一个单独的功能，而是一个**可扩展的拦截链**——PreTurn、MidTurn、PostTurn 各是一个挂钩点，业务方按需挂自己的逻辑。

---

## 二、StopReason 如何设计

HITL 引入了一批**人为因素导致的停止**，StopReason 至少要有这些：

```
自然停止（LLM 侧）:
  stop              — LLM 认为任务完成
  tool_calls        — 还需要调工具
  length            — token 不够了

人工干预停止（HITL 侧）:
  approval_denied   — 用户拒绝了工具执行
  guardrail_block   — 安全护栏拦截
  policy_violation  — 企业策略拒绝（如禁止推代码到 main 分支）
  clarification     — 信息不足，需要用户澄清
  timeout           — 用户 N 分钟没回复，自动放弃
  user_cancel       — 用户主动点了取消

系统停止:
  max_iterations    — 超过最大轮次
  budget_exhausted  — token 预算花光了
  error             — 不可恢复的异常
```

### 核心：不同 StopReason 对应不同恢复路径

```python
match stop_reason:
    case "approval_denied":
        # 注入拒绝原因，LLM 换方案继续
        messages.append({"role": "system", "content": f"操作被拒: {reason}，请换方案"})
        continue  # 进入下一轮 LoopTurn

    case "clarification":
        # 暂停，把问题抛给用户，等回复后 resume
        yield AskUser(question)
        messages.append({"role": "user", "content": user_reply})
        continue

    case "budget_exhausted":
        # 不能继续了，保存现场让用户决定
        save_session()
        return "预算耗尽，请充值后恢复会话"

    case "timeout":
        # 用户太久没回，结束 session
        save_session()
        return "超时未响应，会话已保存"

    case "policy_violation":
        # 企业策略禁止，直接终止，不允许重试
        return f"操作违反策略: {reason}"
```

面试官想听的不是你能列出几种 StopReason，而是**每种 StopReason 对应什么样的恢复路径**——这是区分"用过框架"和"真设计过系统"的关键。

---

## 三、干预点设计：PreTurn / MidTurn / PostTurn

HITL 的干预不只在"审批工具调用"那一刻。一个 LoopTurn 有三个可以插手的时间点：

```
┌──────────┐   ┌──────────────┐   ┌──────────┐   ┌──────────┐
│  上一次    │   │   ModelCall  │   │  ToolCall │   │  下一次    │
│  ToolCall │──▶│   (LLM思考)   │──▶│  (执行工具)  │──▶│  ModelCall │
│  结束     │   │              │   │           │   │           │
└──────────┘   └──────────────┘   └──────────┘   └──────────┘
      ▲               ▲                ▲               ▲
      │               │                │               │
   PreTurn         MidTurn          PostTurn         PreTurn
   (动手前)        (决策后)          (执行后)         (下一轮)
```

### PreTurn（动手前）

**在 LLM 调用之前截停。** 场景：系统检测到用户消息里有敏感词、token 预算快用完、定时提醒到期需要先处理。

```python
# Mini-Agent 中：调用 LLM 前先处理定时提醒（agent.py:367-374）
while self._pending_reminders:
    reminder = self._pending_reminders.pop(0)
    self.messages.append({"role": "system", "content": f"[系统提醒] {reminder}"})
```

还可用于：连续 5 轮 tool_call 没进展 → PreTurn 拦截，不调 LLM 了，直接问用户"我卡住了，换个思路？"

### MidTurn（决策后）

**LLM 已经输出了 tool_call，但还没执行。** 最常见的 HITL 干预点。场景：审批——"LLM 说要删文件，这得让你看一眼"。

```python
# Mini-Agent 中：执行前检查审批（agent.py:562-565）
if self.approval.needs_approval(name):
    approved = self.approval.request(name, args)
    if not approved:
        return "⛔ 用户拒绝了"
```

操作层面不只是 y/n——可以是：

- **修改参数**："命令太长只跑前半段"
- **替换工具**："别用 rm，用 trash"
- **补充信息**："执行前先把环境变量设成 X"

### PostTurn（执行后）

**工具已经执行完了，结果在手里。** 场景：结果审计——"LLM 读取了一个文件，内容是敏感文档，要不要展示给 LLM？"

```python
# Mini-Agent 中：工具执行后通过 hooks 审查结果（agent.py:581-583）
result = self.hooks.invoke(
    "on_tool_call", name=name, args=args, result=result,
)
```

PostTurn 可做：结果脱敏、结果截断（太长只给摘要）、结果标记（标注哪些内容来自不可信源）。

### 三种干预点对比

| | PreTurn | MidTurn | PostTurn |
|---|---|---|---|
| **时机** | LLM 调用前 | LLM 输出后、执行前 | 执行后 |
| **能做什么** | 注入上下文、拦截不安全意图 | 审批、修改参数、替换工具 | 脱敏结果、审计日志、截断 |
| **Mini-Agent 对应** | `_pending_reminders` 注入 | `approval.request()` | `hooks.invoke("on_tool_call")` |
| **典型场景** | "你已调了 20 个工具，确定继续？" | "要执行 `rm -rf`，你确认吗？" | "文件太大，只给 LLM 前 500 行" |

---

## 四、两种 HITL 模式

### Stop and Resume（停止-恢复）

整个 Agent 进程**完全暂停**，状态序列化到磁盘，用户处理好之后重新拉起进程继续跑。

```
Agent 执行中 → 触发 HITL → 完整保存状态 → Agent 进程退出
                                                     ↓
                                         用户处理（可能几小时/几天后）
                                                     ↓
                                        启动新进程 → 加载状态 → 从断点继续跑
```

**优点**：可以关闭终端，横跨数小时甚至数天。适合同步 HITL——审批人不一定在线。
**代价**：要序列化完整的 Agent 状态（`self.messages`、流式状态、进行中的 LLM 调用、还没执行的 tool_call 队列），然后在新进程里完整恢复。**不能有任何内存状态丢失。**

LangGraph 的 checkpoint 机制做的就是这个——每次 `interrupt()` 时把 StateGraph 的完整状态存下来，之后用同一个 thread_id 和 checkpoint_id 恢复。

**Mini-Agent 的现有基础**：`save_session()` 把 messages 存盘，`from_session()` 恢复。但缺少一个关键东西——**断点上下文**。现在的实现是"下次用户说句话才恢复对话"，真正的 Stop and Resume 是"下次启动时，不需要用户输入，Agent 自己接着被拦截的那个 tool 继续跑"。

### Hang & Wait for Decision（挂起等待）

Agent 进程**不退出**，阻塞在某个 IO 上，等用户给了回复后原地继续。

```
Agent 执行中 → 触发 HITL → 阻塞（进程不退出）
                                ↓
                         用户输入 y/n / 修改参数
                                ↓
                         拿到决策结果 → 原地继续下一行代码
```

**优点**：实现简单——不需要序列化/反序列化，内存状态天然保留。适合同步 HITL——用户在终端前看着。
**代价**：进程不能退出，不能关终端，审批人必须在同一时间同一台机器上。需要额外设计超时机制。

**Mini-Agent 的对应**：`input("批准执行? [y/N] > ")`（[cli.py:38](../demo/cli.py#L38)）。这行代码卡在标准输入上等用户打字——就是 Hang & Wait 的最简实现。

### 对比

| | Stop and Resume | Hang & Wait |
|---|---|---|
| **进程状态** | 退出，状态存盘 | 阻塞，进程不退出 |
| **恢复方式** | 新进程加载状态 | 原地继续 |
| **实现复杂度** | 高（序列化所有状态） | 低（一个 input() 就够） |
| **适用场景** | 异步审批、长耗时等待 | 终端前实时交互 |
| **超时处理** | 天然支持（进程不在运行） | 需要额外超时机制 |
| **成本** | 无（进程不存在，不占资源） | 进程占据内存等待 |
| **Mini-Agent 对应** | `save_session()` + `from_session()` | `input("批准执行?")` |

### 工程上通常两套都做

同一套系统，两种模式根据场景切换：

- **高风险操作**（删库、发布到生产）→ Stop and Resume，强制人确认后再跑
- **低风险澄清**（"文件名打错了，你是要 config.yaml 还是 config.json？"）→ Hang & Wait，用户秒回后继续
- **审批人不在线** → 自动降级为 Stop and Resume，发通知 + 存盘退出

---

## 五、与 Mini-Agent 代码的对应

| 概念 | 一句话 | Mini-Agent 对应 |
|------|--------|----------------|
| HITL | 人机间切换控制权 | `approval.request()` |
| Middleware 链 | PreTurn/MidTurn/PostTurn 可编程拦截 | hooks + guardrails + approval 拼起来 |
| StopReason | 每种停止原因对应不同恢复路径 | 还缺 HITL 侧的，目前只有 `max_iterations` |
| PreTurn | LLM 调用前截停 | `_pending_reminders` 注入 |
| MidTurn | LLM 输出后、执行前截停 | `approval.needs_approval()` |
| PostTurn | 执行后审查结果 | `hooks.invoke("on_tool_call")` |
| Stop and Resume | 退出进程，恢复时继续 | `save_session()` — 雏形已有 |
| Hang & Wait | 阻塞等回复 | `input("批准执行?")` |
