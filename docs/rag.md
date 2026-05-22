# RAG 与 Agent 结合

## RAG 是什么

**RAG（Retrieval-Augmented Generation，检索增强生成）**——从知识库检索相关文档，塞进 prompt，让 LLM 基于这些文档生成答案。

```
用户问题 → 检索相关片段 → 把片段注入 prompt → LLM 生成答案
```

用到代码场景：把整个代码库切成小段，每段存成向量，提问时先检索最相关的代码片段，再让 LLM 基于这些片段回答。这是 CodeGraph、Sourcegraph、GitHub Copilot 背后在做的事。

---

## Embedding 是什么

**Embedding（向量嵌入）** 就是把一段文本转换为一组数字（向量）。语义相近的文本，向量在数学空间里也挨得近。

```
"猫是一种动物" → [0.12, -0.34, 0.78, ..., 0.05]
"狗是一种动物" → [0.11, -0.31, 0.75, ..., 0.04]  ← 很接近
"快速排序算法" → [-0.45, 0.67, -0.12, ..., 0.88]  ← 差很远
```

这是通过 embedding 模型（如 OpenAI `text-embedding-3-small`）算出来的。同样的模型 + 同样的文本，每次算出的向量一样。

---

## 向量数据库是什么

普通数据库存的是"字段=值"，向量数据库存的是"向量+元数据"，核心能力是**相似度检索**——给你一个向量，找出库里最接近的 K 个向量。

```
查询: "怎么处理用户登录" → embedding → [0.23, -0.56, ...]
                                            ↓
                              向量数据库做余弦相似度计算
                                            ↓
              返回 Top 5: auth.py:45-60, login_handler.ts:120-135, ...
```

常用向量数据库：Pinecone（云服务）、Qdrant、Milvus、Chroma（轻量）、pgvector（PostgreSQL 插件）。

---

## RAG vs grep vs CodeGraph

| | grep | RAG（向量检索） | CodeGraph（AST 图谱） |
|---|---|---|---|
| **原理** | 字面匹配 | 语义向量相似度 | AST 解析 + 图遍历 |
| "这个函数被谁调了？" | ❌ 只能搜名字 | ❌ 猜不准 | ✅ 100% 精确 |
| "认证相关的代码在哪？" | ❌ 不会联想 | ✅ 语义理解 | ❌ 函数名不匹配就找不到 |
| "改了 X 会影响谁？" | ❌ | ❌ 做不到 | ✅ `codegraph_impact` 直接算 |
| 索引方式 | 无需索引 | 调 embedding API | 本地 tree-sitter 解析 |
| 特点 | 精确字面匹配 | 模糊但语义强 | 精确结构查询 |

三者互补，不是谁替代谁。真正的"升级"是三者结合。

---

## RAG 如何与 Agent 结合

按深入程度分四层：

### 第一层：RAG 作为工具

把 RAG 封装成一个 tool，Agent 在需要时主动调用。调用链路：

```
用户: "我们项目的认证方案是什么？"
  → Agent 思考: 应该查知识库
    → LLM 输出 tool_call: search_knowledge_base("认证方案")
      → _execute_tool → guardrails → handler → 查向量库 → 返回文档
        → LLM 基于文档生成回答
```

### 第二层：自动注入上下文（Agent 无感知）

每次对话前自动检索并注入 system prompt，Agent 不知道有检索发生。

```
用户输入 → 本地代码调 embedding 模型 → 向量数据库查 Top K → 结果塞进 messages → 发给 LLM
```

LLM 全程不知道"有检索发生过"，它只是看到了更多的上下文。这就是 `_load_memory_context()` 的思路——把静态读文件换成动态查向量库。

### 第三层：长期经验记忆

```
每次工具调用成功 → 自动生成经验笔记 → embedding → 存入向量库
每次新任务 → 自动检索相关历史经验 → 注入上下文
```

Agent 做的越多，知识库越丰富，下次越聪明。

### 第四层：工具路由

不用把 50 个工具的 schema 全塞进 system prompt。根据用户意图先检索出最相关的 5 个工具，只发送这些工具的 schema。省 token + 提高工具选择准确率。

---

## 检索是谁做的？

**完全是本地代码做的，LLM 在整个检索过程中不参与。** 流程：

```
用户输入 → 本地代码调 embedding 模型 → 本地代码查向量库 → 本地代码拼进 messages → 发给 LLM
                                              ↑
                                    这整段属于 harness 层
```

LLM 只是看到了拼好的完整上下文，直接生成回答。这跟 `_load_memory_context()`（[agent.py:139](../demo/agent.py#L139)）做的事完全一样：本地代码读文件、拼接进 system prompt，LLM 无感知。RAG 只是把"读文件"换成了"查向量库"。

检索属于 **harness 层**的职责——在 LLM 被调用之前自动完成，不是 LLM 控制的行为。

---

## 与 Mini-Agent 现有架构的对应

| 现有的 | RAG 化后 |
|--------|---------|
| `_load_memory_context()` 读 `MEMORY.md` | 查向量库，返回语义相关的记忆片段 |
| `create_skill` 存成文件 | embedding 后存向量库 |
| Agent 主动搜代码用 grep | Agent 主动搜代码用语义检索 tool |
| 50 个工具 schema 全发 | 检索出 Top 5 相关工具再发 |
