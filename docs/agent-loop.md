# Agent 架构核心概念：LoopTurn / LoopSession / LoopControl

Agent 的架构可以抽象为三个层次的循环控制。这些概念是面试中衡量候选人是否真正写过 Agent 的分水岭。

---

## 一、LoopTurn：一次"思考→行动"原子轮次

**一个 LoopTurn = 一次 ModelCall + 紧随其后的一批 ToolCall。**

```python
# agent.py run() 的 while 循环，每轮 iteration 就是一个 LoopTurn

while True:
    content, reasoning, tool_calls, finish = self._call_llm_stream()  # ModelCall

    if tool_calls:
        for tc in tool_calls:
            self._execute_tool(name, args)  # ToolCall，可并行
        continue  # 这轮 LoopTurn 结束，进入下一轮

    return content  # 没有 tool_calls，整个 LoopSession 结束
```

### ToolCall 的批处理

ToolCall 可以是**批量调用**的——若干个互不依赖的工具在同一次 ModelCall 后被并行执行，不需要串行等待。

```python
# agent.py:422-449 — 多个 tool_calls 并发执行
with ThreadPoolExecutor(max_workers=min(len(tool_calls), 4)) as executor:
    futures = {}
    for tc in tool_calls:
        futures[executor.submit(self._execute_tool, name, args)] = tc
    for future in as_completed(futures):
        results[tc_id] = future.result()
```

批处理的前提：这批工具之间没有数据依赖（LLM 在同一个 assistant message 里返回了多个 tool_call，说明它认为这些调用可以并发）。

---

## 二、LoopSession：一轮对话的"方向盘"

**一次完整的对话 = 多个 LoopTurn 组成的 LoopSession。** Session 层面要管理三件事：

### 2.1 Steer（转向）

用户在中途改变意图——"别做 A 了，改做 B"。Agent 需要能识别意图变更，而不是继续死磕上一个任务。

```python
# Mini-Agent 中的对应：
# - /reset 命令强行清空对话
# - 用户直接发新指令覆盖当前任务，LLM 自行判断切换
```

更高级的做法：在每次 LoopTurn 之前做一个"意图一致性检查"——当前执行方向是否仍然和用户的最新消息对齐。如果偏离，以用户最新消息为准重新规划。

### 2.2 Followup（追问）

Agent 完成任务后主动推进对话，而不是被动等用户下一句话。

```python
# agent.py:460-469 — 在 LLM 最终回复后，nudge 它主动问
if tool_call_count >= 3:
    self.messages.append({
        "role": "system",
        "content": "[系统提示] 如果过程值得复用，考虑使用 create_skill 保存。",
    })
```

Followup 的典型模式：
- **信息不足时追问**：Agent 发现自己缺关键信息 → 主动提问，而不是瞎猜
- **完成后提议下一步**："X 已修复，要不要我也把 Y 顺便做了？"
- **异常后征求决策**："A 方案行不通，B 和 C 都可以，你选哪个？"

### 2.3 Interrupt（打断）

外部事件中断当前执行，Agent 必须优雅处理而不是崩溃。

```python
# Mini-Agent 中的中断来源：

# 1. 审批拒绝 → 工具返回 "⛔ 用户拒绝了"（agent.py:563-565）
if not approved:
    return f"⛔ 用户拒绝了 '{name}' 的执行"

# 2. 护栏拦截 → 工具返回拦截原因（agent.py:570-573）
block_reason = guardrails.check(name, args)
if block_reason:
    return block_reason

# 3. 超过最大轮次 → 强制终止（agent.py:475）
return f"⚠ 超过最大工具调用轮次 ({self.max_iterations})，已强制停止。"
```

关键原则：**中断消息要可操作**——不只是说"被拦了"，还要让 LLM 知道**为什么被拦**和**可以怎么调整**。只给 `"Error"` 会导致 LLM 反复重试同一个操作。

---

## 三、LoopControl：管两件事

LoopControl 是整个 Agent 循环的"控制面"，分 ContextControl 和 RunControl 两个维度。

```
┌──────────────────────────────────────────┐
│               LoopControl                 │
│                                          │
│  ┌──────────────┐  ┌──────────────┐      │
│  │ContextControl│  │  RunControl   │      │
│  │              │  │              │      │
│  │ 上下文压缩    │  │ StopReason   │      │
│  │ 业务上下文    │  │ 思考模式切换   │      │
│  │ 多模态数据    │  │ 最大轮次控制   │      │
│  │ 内容过滤     │  │ 错误恢复      │      │
│  └──────────────┘  └──────────────┘      │
└──────────────────────────────────────────┘
```

---

### 3.1 ContextControl：上下文控制

#### 3.1.1 上下文压缩

**触发时机的计算**

不是拍脑袋设一个阈值，而是按模型上下文窗口的比例：

```
实际触发 = min(模型上下文窗口 × 70%, compress_threshold)
```

因为在 100K 窗口的模型上 4K 就压缩太浪费；在 8K 窗口的模型上 4K 又太晚——LLM 的输出还需要空间，拖到 4K 才压，模型可能已经没余量生成 tool_call 了。

**压缩策略**

Mini-Agent 用的是经典方案——保留头尾 + 摘要中间（[agent.py:295-313](../demo/agent.py#L295-L313)）：

```python
# 保留 system prompt（head） + 最近 KEEP_TAIL 条（tail）
# 中间的 [1:-KEEP_TAIL] 部分 → 调用 LLM 生成摘要 → 作为 system 消息插入
self.messages = head + [
    {"role": "system", "content": f"[对话历史摘要]\n{summary}"},
] + list(tail)
```

**摘要生成的两种路线：**

| 方案 | 做法 | 优劣 |
|------|------|------|
| 用主模型 | 同一个 `_call_llm()` 不带 tools | 质量高，多一次 LLM 调用 |
| 用小模型 | 另起便宜模型（如 GPT-4o-mini）专门做压缩 | 便宜，模型不同可能丢信息 |

一次摘要调用的开销 vs 不压缩后续每轮都带全量历史的累积浪费——前者远小于后者。

**压缩会丢什么？什么时候丢不得？**

- **工具调用的精确参数和 tool_call_id**——正常情况下无所谓，但如果压缩后 LLM 想引用之前的 tool 返回值，会因为 tool_call_id 在消息列表里已经不存在而幻觉。
- **渐进式决策的推理链条**——"读 A → 根据 A 找到 B → 改 B"，压缩后中间推理丢了，LLM 可能忘了为什么要改 B。

解法：压缩时做**结构化提取**而非纯文本摘要——不只是"用户改了 B 配置"，而是存成 `{"action": "file_edit", "path": "B", "reason": "A 文件引用了 B"}`。

**压缩时机**

必须在调用 LLM 之前做，不能在之后做。调用之后再压 = 那次调用已经带着全量历史发出去了，token 已经花了，压了个寂寞。你的代码（[agent.py:377](../demo/agent.py#L377)）`_maybe_compress()` 放在 `append(user_message)` 之后、`_call_llm_stream()` 之前——是正确的。

#### 3.1.2 业务上下文加载/卸载

Agent 切换任务时，怎么让 LLM 忘掉上一个任务的知识、加载新任务的知识。

**简单方案——暴力切 system prompt**

```python
def switch_context(self, new_profile: str):
    self.messages = [{"role": "system", "content": build_prompt_for(new_profile)}]
    # 旧对话完全丢弃
```

问题：丢失了用户在整个 session 里积累的偏好和记忆。

**进阶方案——分层上下文**

```
┌─────────────────────────────────┐
│ Layer 1: 持久层（不随任务切换）      │  用户偏好、长期记忆、使用习惯
├─────────────────────────────────┤
│ Layer 2: 任务层（切换任务时整个替换）   │  当前任务的 domain knowledge、工具集
├─────────────────────────────────┤
│ Layer 3: 对话层（正常增长，会被压缩）   │  当前对话的具体消息
└─────────────────────────────────┘
```

切任务时：Layer 1 不动，Layer 2 换掉，Layer 3 保留最近几轮。

**完整方案——上下文槽位（Context Slots）**

给每个业务领域维护独立的上下文槽位，切换时保存/恢复：

```python
class ContextSlotManager:
    def __init__(self):
        self._slots: dict[str, dict] = {}

    def save(self, name: str, messages: list):
        self._slots[name] = {"messages": messages, "saved_at": time.time()}

    def restore(self, name: str) -> list:
        return self._slots.get(name, {}).get("messages", [])
```

跟操作系统进程切换一样——保存上下文 → 切换上下文 → 恢复现场。Mini-Agent 里 `session_store.py` 的会话保存/恢复就是上下文槽位的持久化版本。

#### 3.1.3 多模态数据处理

**输入多模态**

| 类型 | 做法 |
|------|------|
| 图片 | 直接 Base64 编码放入 `messages[].content[]` 作为 `image_url`（需多模态模型）；或先用视觉模型生成描述再用文本模型处理 |
| PDF | PyMuPDF / marker 转为 Markdown，保留表格结构 |
| 音频 | Whisper 转文字，再走文本链路 |

```python
# 直接发给多模态模型
messages.append({
    "role": "user",
    "content": [
        {"type": "text", "text": "这个截图里的报错是什么？"},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_data}"}},
    ],
})
```

**关键设计点：**
- 多模态内容不进压缩——摘要只能处理文本，压缩时要保留图片的引用和文字描述
- Token 计数要区分模态——图片的 token 计算和文本完全不同（GPT-4V 按图片分辨率算），`4字符≈1 token` 的估算对多模态不适用

**输出多模态**

Agent 输出图片（图表等）通常是 LLM 生成代码（matplotlib、Mermaid），由 harness 层渲染后展示——不是 LLM 直接生成像素。

#### 3.1.4 内容过滤和安全审查

Mini-Agent 有工具层面的 guardrails（敏感路径、循环检测、超长命令），这是**行为层**安全。**内容层**安全分三道防线：

**三层防御体系：**

```
用户输入 → 防线1（输入过滤）
    → LLM 决策（system prompt 里的安全指引）
        → 防线3（工具护栏，guardrails.check）
            → 工具执行
    → LLM 生成输出
        → 防线2（输出过滤，防泄露）
            → 展示给用户
```

**防线 1：输入过滤**

```python
def input_guard(user_message: str) -> str | None:
    # 提示注入检测
    injection_patterns = [
        r"ignore (all |your )?(previous |above )?instructions?",
        r"you are now",
        r"system:\s*",
    ]
    for pattern in injection_patterns:
        if re.search(pattern, user_message, re.IGNORECASE):
            return "⛔ 检测到提示注入攻击"

    # 调外部 moderation API
    if moderation_api.check(user_message).flagged:
        return "⛔ 内容违反安全策略"

    return None
```

**防线 2：输出过滤**

```python
def output_guard(response: str) -> str:
    # 敏感信息泄露检测：API Key、JWT Token、密码
    leak_patterns = [
        r'sk-[a-zA-Z0-9]{20,}',
        r'Bearer [a-zA-Z0-9_-]+\.',
    ]
    for pattern in leak_patterns:
        response = re.sub(pattern, '[已隐藏]', response)
    return response
```

如果要在生成过程中过滤（而不是事后），需要在流式输出的同时做关键字扫描，命中敏感词立即截断流——这需要 harness 层的流式输出回调。

**防线 3：工具护栏（Mini-Agent 已有）**

[guardrails.py](../demo/tools/guardrails.py) ——循环检测、敏感路径、超长命令。

**面试时的核心论点：**
1. **分层防御** — 输入侧、输出侧、行为侧各管各的
2. **fail-safe** — 拦截后给 LLM 可操作的反馈（不是只给 "Error"，要说明为什么和怎么做）
3. **不依赖 LLM 自律** — 内容过滤在 harness 层做，不在 system prompt 里让 LLM "自己看着办"

---

### 3.2 RunControl：运行控制

#### 3.2.1 StopReason：为什么停了

Agent 停止有六种原因，每种的处理逻辑不同：

| StopReason | 含义 | 处理方式 |
|-----------|------|---------|
| `stop` | LLM 认为说完了 | 正常返回 |
| `tool_calls` | 还要继续调工具 | 执行工具，进入下一轮 LoopTurn |
| `length` | Token 不够了 | 提示用户精简输入 / 自动压缩 |
| **审批拒绝** | 用户拒绝了工具调用 | 把拒绝原因注入消息，让 LLM 换方案 |
| **护栏拦截** | guardrails 拦了工具 | 同上，LLM 收到拦截原因后调整 |
| **max_iterations** | 超过最大轮次 | 强制终止并恢复现场（[agent.py:475](../demo/agent.py#L475)） |

```python
# Mini-Agent 中的 StopReason 处理
if finish_reason == "tool_calls" and tool_calls:
    # 执行工具，继续循环
    continue

if finish_reason == "stop" and content:
    return content  # 正常终止

return f"⚠ 超过最大工具调用轮次 ({self.max_iterations})，已强制停止。"
```

#### 3.2.2 思考模式切换

不同任务需要不同的推理深度——快任务关掉深度推理省 token，复杂任务开启并多花钱。

```python
# 通过 provider 层传不同参数控制
def _call_llm_stream(self, thinking_mode: str = "auto"):
    kwargs = {"model": self.model, "messages": self.messages, "tools": self.tools}
    if thinking_mode == "deep":
        kwargs["reasoning_effort"] = "high"    # 深思模式
    elif thinking_mode == "fast":
        kwargs["reasoning_effort"] = "minimal"  # 快速模式
    return self.provider.create_stream(**kwargs)
```

也可以在 LoopSession 中途根据任务复杂度自动切换：连续 3 轮 tool_call 没进展 → 自动开启深度推理；简单问答 → 关掉省 token。

#### 3.2.3 最大轮次控制

`max_iterations` 不是随便设个 10 就完了：

- 设太低 → 复杂任务半途而废
- 设太高 → Agent 陷入死循环浪费大量 token
- 合理的值取决于工具数量：工具越多、越复杂的 Agent，需要更多轮次探索

Mini-Agent 的做法（[agent.py:384](../demo/agent.py#L384)）是保守的：`while iteration < self.max_iterations`，超过就强制终止并告知用户——保证不会无限烧钱。

#### 3.2.4 错误恢复

Agent 执行过程中任何环节都可能出错——LLM 返回了不合法的 JSON 参数、工具执行超时、API 挂了。每一层的错误都要有恢复策略：

| 错误类型 | 恢复策略 |
|---------|---------|
| LLM 返回了不合法 JSON 参数 | 把错误信息注入消息，让 LLM 重试（而不是崩溃） |
| 工具执行超时 | 返回超时信息给 LLM，让它决定是否换方案 |
| API 调用失败 | `retry_call()` 自动重试（[agent.py:338-343](../demo/agent.py#L338-L343)） |
| 循环检测触发 | 注入护栏消息，引导 LLM 换思路 |

关键原则：**控制面不崩溃**——任何错误都不应该让整个 Agent 进程挂掉，而是以消息的形式回传给 LLM，让它自己纠错。

---

## 四、面试高频考点

| 考点 | 表面回答 | 真写过的人会补充 |
|------|---------|----------------|
| 怎么做上下文压缩？ | 用 LLM 生成摘要 | 压缩时机要在调用 LLM 之前；摘要有损，可能丢掉 tool_call_id 引用链；结构化提取优于纯文本摘要 |
| 怎么做内容过滤？ | 加敏感词列表 | 分层做：输入侧防注入、输出侧防泄露、行为侧防滥用；拦截后要给 LLM 可操作的反馈 |
| 怎么做安全审查？ | 审批机制 | 分风险等级区别对待（读低风险、写中风险、执行高风险）；不能只拦不教 |
| StopReason 有哪些？ | stop / tool_calls / length | 还有审批拒绝、护栏拦截、max_iterations 强制截断——每种恢复策略不同 |
| 怎么处理多模态？ | Base64 编码 | 多模态不进压缩、token 计数方式完全不同、可以先用小模型做预处理再交给主模型 |
| 上下文怎么切任务？ | 重建 system prompt | 分层上下文（持久层/任务层/对话层）、上下文槽位保存恢复 |
| 长任务怎么管理？ | max_iterations 截断 | 截断之前先自动保存现场（save_session），用户可以恢复继续；配合压缩减少每轮开销 |

---

## 五、与 Mini-Agent 代码的对应

| 概念 | Mini-Agent 对应位置 |
|------|-------------------|
| LoopTurn | `agent.py:384-450` — while 循环中每轮 iteration |
| ModelCall | `agent.py:477-558` — `_call_llm_stream()` |
| ToolCall（批量） | `agent.py:422-449` — `ThreadPoolExecutor` 并行执行 |
| Steer | `cli.py` — `/reset` 命令；用户新指令覆盖 |
| Followup | `agent.py:460-469` — skill 创建 nudge |
| Interrupt | `agent.py:562-573` — 审批拒绝 + 护栏拦截 |
| 上下文压缩 | `agent.py:278-313` — `_maybe_compress()` |
| 业务上下文切换 | `agent.py:175-200` — `_refresh_profiles()` |
| 内容过滤 | `tools/guardrails.py` — 循环检测 + 敏感路径 + 超长命令 |
| StopReason | `agent.py:384-475` — finish_reason + max_iterations 分支 |
| 错误恢复 | `tools/retry.py` — `retry_call()` + 工具错误消息回传 |
