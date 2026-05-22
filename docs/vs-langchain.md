# Mini-Agent vs LangChain/LangGraph

## 一句话总结

LangGraph 把 Agent 循环画成流程图来配置；Mini-Agent 直接写 `while` 循环。**理解了 Mini-Agent，再去看 LangGraph 就是语法糖**。

---

## LangChain 是什么

LangChain 是最早流行的 LLM 应用框架。核心理念是 **Chain（链）**——把 LLM 调用的常见模式封装成可组合的模块。

```python
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate

prompt = PromptTemplate(template="你是一个{role}。用户说：{input}")
chain = LLMChain(llm=model, prompt=prompt)
result = chain.run(role="助手", input="你好")
```

### LangChain 的问题

Chain 是**线性的**——A → B → C，不能循环。Agent 的核心需要"LLM → 工具 → LLM → 工具 → ..."这种动态循环，Chain 体系做不到。

于是有了 LangGraph。

---

## LangGraph 是什么

LangGraph 用**有向图（Graph）**描述 Agent 的决策流程：

- **节点（Node）**：做一件具体的事（调 LLM、执行工具）
- **边（Edge）**：从哪到哪（普通边）或条件判断（条件边）
- **状态（State）**：在整个图中流转的数据

```python
from langgraph.graph import StateGraph, END

# 定义状态
class AgentState(TypedDict):
    messages: list
    next: str

# 定义节点
def call_llm(state):
    response = model.invoke(state["messages"])
    return {"messages": state["messages"] + [response]}

def call_tools(state):
    last_msg = state["messages"][-1]
    for tc in last_msg.tool_calls:
        result = execute_tool(tc.name, tc.args)
        state["messages"].append(ToolMessage(content=result, tool_call_id=tc.id))
    return state

# 定义路由
def should_continue(state):
    last_msg = state["messages"][-1]
    if last_msg.tool_calls:
        return "tools"
    return "end"

# 组装图
graph = StateGraph(AgentState)
graph.add_node("llm", call_llm)
graph.add_node("tools", call_tools)
graph.set_entry_point("llm")
graph.add_conditional_edges("llm", should_continue, {"tools": "tools", "end": END})
graph.add_edge("tools", "llm")  # 工具执行完 → 回到 LLM

app = graph.compile()
result = app.invoke({"messages": [HumanMessage(content="你好")]})
```

### 画出来

```
        ┌─────────┐
        │   LLM   │ ←──────────┐
        └────┬────┘            │
             │                 │
        has_tool_calls?        │
        ┌────┴────┐            │
        │ YES     │ NO         │
        ▼         ▼            │
   ┌────────┐   END           │
   │ TOOLS  │                 │
   └───┬────┘                 │
       │                      │
       └──────────────────────┘
```

---

## 用 Mini-Agent 的方式做同样的事

上面的 LangGraph 代码，用 Mini-Agent 就是一个 `while` 循环：

```python
class AIAgent:
    def run(self, user_message: str) -> str:
        self.messages.append({"role": "user", "content": user_message})

        while True:
            # 对应 LangGraph 的 "llm" 节点
            response = self._call_llm()

            # 对应 LangGraph 的 should_continue 条件边
            if response.has_tool_calls:
                # 对应 LangGraph 的 "tools" 节点
                for tc in response.tool_calls:
                    result = execute_tool(tc.name, tc.args)
                    self.messages.append(ToolMessage(result, tc.id))
                continue  # 对应 tools → llm 的边

            # 对应 END
            return response.content
```

**4 行逻辑 vs 40 行配置**。做的事情完全一样。

---

## 核心对比

| | LangChain/LangGraph | Mini-Agent |
|---|---|---|
| **Agent 循环** | `StateGraph` + 节点 + 边 | `while True` |
| **路由逻辑** | `add_conditional_edges` | `if has_tool_calls: continue` |
| **状态管理** | `TypedDict` + reducer 函数 | `self.messages` 列表 |
| **代码量（核心循环）** | ~40 行 | ~15 行 |
| **学习曲线** | 理解 Graph、State、Node、Edge 概念 | 理解 while/if |
| **可视化** | 可以画流程图 | 需要自己在脑子里画 |
| **复杂流程** | 优势：嵌套、并行、人工审批节点 | 需要手写，但完全可控 |
| **调试** | 黑盒较多 | 直接 print/断点 |

---

## 什么时候用哪个

| 场景 | 推荐 |
|------|------|
| **学习 Agent 原理** | Mini-Agent — 裸写循环，每个细节都清楚 |
| **快速原型** | Mini-Agent — 零依赖，一个文件跑起来 |
| **简单 Agent** | Mini-Agent — LLM + 几个工具，够用 |
| **复杂多 Agent 协作** | LangGraph — 状态管理、人工审批、并行分支 |
| **团队协作** | LangGraph — 流程图可视化，方便沟通 |
| **生产部署** | LangGraph — 有 LangSmith 监控、错误追踪 |

---

## 对应关系速查

| Mini-Agent 概念 | LangGraph 等价 |
|----------------|---------------|
| `AIAgent` 类 | `StateGraph` + compile |
| `self.messages` | `AgentState` |
| `while True` | `add_edge("tools", "llm")` |
| `if has_tool_calls: continue` | `add_conditional_edges` |
| `return content` | `END` |
| `_execute_tool()` | `ToolNode` |
| `_call_llm_stream()` | `ChatModel.bind_tools()` |
| `ApprovalManager` | `interrupt()` / 人工审批节点 |
| `_maybe_compress()` | State reducer（自定义状态压缩） |
| `delegate_task` | Subgraph / `Send()` API |
| `KanbanScheduler` | `Command()` + 后台进程 |

---

## 总结

> 框架是帮你做事的，但理解了底层原理，你才不会被框架限制。

Mini-Agent 500 行代码把 LangGraph 的核心概念全部走了一遍：Agent 循环、工具调用、状态管理、子 Agent、人工审批、定时调度、插件钩子。看完 Mini-Agent，再看 LangGraph 文档就是"哦，这个 Node 就是我的函数，这个 Edge 就是我的 while continue"。

---

## 补充：这些框架还值得学吗？

JD 里常见的"熟悉 LangGraph / AutoGen / CrewAI 等主流智能体框架"，本质是**招聘惯性**——HR 和技术经理互相抄模板，不代表团队真在用。但背后想筛的东西是有道理的：有状态图、角色分工、工具调用、人机协同这套思维范式。

### 行业正在发生的三个变化

**1. 模型厂商在"往上吃"**

以前做 agent 需要三方框架帮你管 prompt、调 API、处理 tool calling。现在各模型厂商在自家 SDK 里直接把这些做了：

| 厂商 | SDK / 方案 | 能力 |
|------|-----------|------|
| OpenAI | Python/Node SDK、Assistants API、Agents SDK | 内置 agent loop、handoff、guardrails、服务端托管 agent 状态 |
| Anthropic | Python/TypeScript SDK、Claude Agent SDK、MCP | 原生 tool use、thinking、prompt caching、工具插拔协议 |
| Google | Gemini SDK、A2A 协议 | 多模态、function calling、grounding（联网检索）、agent 间通信协议 |

打个比方：以前手机需要装第三方输入法和相机 app，现在系统自带足够好了，第三方只能做小众差异化。框架的价值从"封装 API + 管状态"收缩成"把几个 agent 串成流程图的胶水层"。

**2. MCP 和 A2A 在标准化协议**

- **MCP**（Anthropic 主导）：定义"工具怎么描述自己、agent 怎么调用工具"的统一格式。普及后，不同家的 agent 和工具即插即用——像 USB-C 统一了充电线。
- **A2A**（Google 主导）：定义"agent A 怎么跟 agent B 对话通信"的统一格式，让不同模型搭的 agent 能互操作。

趋势就是：那些框架里"封装 tool 调用"的代码会越来越多余——当协议标准化后，你不需要每换一个框架就重新写集成代码。

**3. Agent 在分化为两个赛道**

| 赛道 | 代表产品 | 特点 | 热度 |
|------|---------|------|------|
| **代码生成型 agent** | Claude Code、Cursor、Devin | 一句话→写代码、调 bug、跑测试。单一 agent，强工具执行能力 | 🔥 爆发中 |
| **对话式多 agent** | LangGraph、CrewAI、AutoGen | 定义多个 AI 角色互相对话协作（PM agent + 架构师 agent + 测试 agent...） | 📉 hype 在降温 |

多 agent 对话在企业内部 RPA / 流程自动化里还有空间（审批流、合同审核），但实际落地成本高很多——多 agent 之间沟通的不确定性大，调试困难。

### 结论

- **简历上写掌握了 LangGraph 的 graph/state/checkpoint 思想，依然有价值**——招聘方要找的是理解这套范式的人，不是绑定某个框架
- **真正的核心竞争力**：理解模型能力边界、评估体系、MCP 协议、把 agent 拆成可测试的模块——比会调某个框架的 API 强得多
- **学思想 > 学框架，看协议 > 看封装，跟模型能力前沿走 > 跟多 agent 角色扮演走**
