# Skill 范式

业界已普遍接受 Skill 范式。现在的 Agent 框架不再做大量意图识别和 Agent 路由——那些是模型能力不足时期的设计模式。随着模型能力提升，**One ReactLoop Agent × N Skills** 已经能解决很多场景问题，不需要拆分 Agent。

---

## 一、Skill 本质上是 Experience 的编排

### 旧范式：意图识别 + Agent 路由

```
用户: "帮我部署到生产环境"
  → 意图识别: 这是"部署"类任务
    → 路由到 DeployAgent
      → DeployAgent 有自己的 prompt、工具、流程
```

为什么这是模型能力不足时期的产物？因为**单个模型不够聪明，无法在一个通用 prompt 下处理所有场景**，所以必须拆给不同的专用 Agent，每个 Agent 只覆盖一小块。

### 新范式：One ReactLoop + N Skills

```
用户: "帮我部署到生产环境"
  → 同一个 Agent Loop 跑起来
    → LLM 思考: 这是部署任务，看看有没有相关 Skill
      → 加载 deploy-to-prod skill → 里面是部署经验（步骤模板、常见坑、检查清单）
        → Agent 按 Skill 指引执行，具体细节用通用推理能力应变
```

**Skill 不是 Agent，Skill 是"以前做过类似任务积累下来的经验包"。** Agent 拿到 Skill 后还是自己思考、自己调工具、自己应变——Skill 只是给它一个经过验证的模板和注意事项。

---

## 二、渐进式披露（Progressive Disclosure）

不能把 N 个 Skill 全塞进 system prompt。100 个 Skill 每个 2000 字，prompt 直接爆了。正确做法是**按需加载、逐层展开**：

### 加载流程

```
Layer 0（始终在 prompt 里）:
  [可用技能] deploy-to-prod, run-migration, debug-oom, ...  ← 只有名字

Layer 1（Agent 决定加载时）:
  调用 view_skill("deploy-to-prod") → 拿到概览（用途、适用场景、前置条件）
  → Agent 判断: 这个 Skill 确实适用

Layer 2（确认使用后）:
  展开完整内容 → 步骤模板、参数说明、常见坑、回滚方案
  → Agent 按模板执行
```

**类比浏览器加载网页**：
- Layer 0 = 书签栏（只看到标题）
- Layer 1 = 打开页面读摘要
- Layer 2 = 展开全部内容

没被点到的页面不会占用内存。Mini-Agent 已有雏形：system prompt 里只列 skill 名字（Layer 0），LLM 调用 `view_skill` 时展开内容（Layer 1-2）。

### 卸载

用过之后要及时把 Skill 的完整内容从上下文移除，否则马上触发压缩：

```python
# Skill 使用完毕后:
# 1. 保留 Skill 的执行结果（产物）在对话里
# 2. 移除 Skill 的完整步骤模板，不占上下文
# 3. 只在 system prompt 里留一句 "[上次使用了 deploy-to-prod skill]"
```

卸载 ≠ 删除。Skill 定义本身持久化存着，卸载的是**这次对话里注入的 Skill 原文**。

---

## 三、Skill 遇到上下文压缩怎么办

对话长了要压缩，但压缩会把已加载的 Skill 步骤一起消掉。Agent 正执行到第 3 步，第 1-2 步的上下文没了——它可能不知道接下来该做什么。

### 解法：Skill 状态外置

```
不要: 把 Skill 的步骤模板全放在 messages 里让 LLM 自己记
要做: Skill 执行进度存在 harness 层，压缩时不受影响

┌─────────────────────────────────┐
│  Harness 层（不受压缩影响）        │
│  skill_state = {                 │
│    "skill": "deploy-to-prod",    │
│    "current_step": 3,            │
│    "completed": [1, 2],          │
│    "artifacts": {...}            │
│  }                               │
└─────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│  LLM 上下文（会被压缩）            │
│  "当前执行到第 3 步：运行冒烟测试"   │
│  "已完成：1.构建镜像 2.灰度发布"    │
└─────────────────────────────────┘
```

压缩发生时，harness 层把当前进度重新注入为一条简短 system 消息：

```
[Skill deploy-to-prod 进度: 第3/5步，已完成 1-2 步]
```

LLM 丢了具体的步骤描述，但知道"我在哪、下一步是什么"。

---

## 四、Skill 可以嵌套

一个 Skill 在执行中可以引用另一个 Skill——这不是 Agent 路由，被调用的 Skill 仍然在**同一个 Agent Loop** 里执行：

```
deploy-to-prod skill:
  Step 1: 构建镜像
  Step 2: 调用 run-migration skill（数据库迁移）
  Step 3: 调用 smoke-test skill（冒烟测试）
  Step 4: 切换流量
```

与 `delegate_task` 的区别：`delegate_task` 是起一个独立 LLM 调用（子 Agent），Skill 嵌套是**同一个 LLM 在同一次对话里顺序执行多段经验模板**。上下文临时切换到子 Skill，执行完后回到父 Skill 继续。

---

## 五、Skill 不一定要强绑定 Sandbox

"Sandbox"是把 Skill 的执行隔离在受限环境（如 Docker 容器）里，防止破坏系统。但**不是所有 Skill 都需要：**

| Skill 类型 | 需要 Sandbox？ | 原因 |
|-----------|---------------|------|
| 代码生成 Skill（写代码、lint） | 否 | 产物是代码文件，不直接执行 |
| 部署 Skill | 是 | 操作线上基础设施 |
| 数据分析 Skill | 看情况 | 读数据不需要，改数据库需要 |
| 知识问答 Skill | 否 | 纯 prompt 模板 + 查文档 |
| 审批流程 Skill | 否 | 编排人机交互 |

**Skill 的安全边界不应该等于 Skill 的边界。** 在一个 Skill 内部，只有真正需要执行代码/命令的步骤才进 Sandbox，其余步骤（推理、分析、决策）跑在正常环境。用 Mini-Agent 的术语——**guardrails 按工具粒度管，不按 Skill 粒度管。**

---

## 六、Skill 的行动能力不只局限于 Scripts

Skill 可以是一段 Python 脚本，但也可以是：

| Skill 形态 | 是什么 | 例子 |
|-----------|--------|------|
| **Prompt 模板** | 一段精心设计的指令 | "你是一个代码审查者，按以下清单检查：..." |
| **SOP** | 步骤清单 + 每步的决策树 | 事故响应手册 |
| **Few-shot 示例** | 几个输入→输出的范例 | 好的 commit message 和坏的对比 |
| **工具组合配置** | 指定"做这类任务时只用这些工具" | 代码生成 skill 禁用 shell 工具 |
| **知识引用** | 指向外部文档/RAG 的索引 | "参考这个页面里的部署手册" |
| **约束规则** | "做 X 的时候绝不能做 Y" | 迁移 skill 规定"迁移前必须先备份" |

**Script 只是 Skill 的最终执行形式之一，不是 Skill 的全部。** 一个 Skill 的核心价值是"把经验结构化"，至于这个经验最终变成脚本、prompt 还是工具配置——是次要的。

---

## 七、可控性：伪代码 + CodeAct

直接让 Agent 自由发挥风险太大，但写死脚本又失去灵活性。**伪代码 + CodeAct** 是折中方案：

### 做法

```
Skill: "分析日志找根因"

伪代码（控制面，约束 Agent 行为）:
  1. 确认时间范围      ← Agent 必须从这一步开始
  2. 获取该时间段的错误日志
  3. 提取 TOP 3 高频错误模式
  4. 对每种错误，追溯最近的代码变更
  5. 给出最可能的根因 + 置信度

CodeAct（执行面，Agent 自由发挥）:
  每一步的具体实现——用什么命令、读什么文件、怎么解析——由 Agent 自己决定。
```

**伪代码管方向，CodeAct 管细节。** Agent 不能跳过步骤，但每步内部可以灵活应变。

---

## 八、Skill 的可评估性

Skill 不能是"用了感觉挺好"的黑盒，得有量化指标：

```python
class SkillEvaluation:
    skill_name: str
    metrics = {
        "success_rate":        "使用该 Skill 的任务成功率",
        "avg_turns":           "平均消耗几个 LoopTurn",
        "avg_tokens":          "平均 token 消耗",
        "approval_triggered":  "触发审批的次数（越少越好）",
        "user_rejection_rate": "用户拒绝 Skill 建议的比例",
        "time_to_complete":    "端到端耗时",
    }
```

每次使用 Skill 后，hook 在 PostTurn 里自动打点。积累到一定量就知道哪个 Skill 好用、哪个该改进、哪个该废弃。

面试时提到这一点，说明你意识到一个关键问题：**Agent 不是 demo，是要能衡量好坏的系统。**

---

## 九、Skill Improvement（自进化）

Skill 不应该是人手写一次就永远不改的。Agent 在执行中发现更好的做法时，应该能改进 Skill。

### 进化路径

```
Skill v1（人手写初版）→ 使用 N 次 → 收集数据 → 发现改进点 → Skill v2
```

### 触发方式

1. **失败驱动改进**：Agent 按 Skill 执行失败 → 分析失败原因 → 如果 Skill 步骤有问题 → 建议修改 → 人审批后更新
2. **效率驱动改进**：Agent 发现某个步骤其实不需要 → "这步每次都白做" → 建议精简
3. **泛化改进**：Agent 发现 Skill 在更多场景下可用 → 扩展适用范围

```python
# 改进 Skill 的 hook
def on_turn_complete(agent, turn_result):
    if agent.active_skill and turn_result == "success":
        # 记录成功路径，与 Skill 模板对比
        # 如果实际路径比模板更短 → 生成改进建议
        suggest_skill_improvement(agent.active_skill, actual_path)
```

---

## 十、Memory 与 Skill 的关系

| | Memory | Skill |
|---|---|---|
| **存什么** | 事实、偏好、上下文 | 流程、方法、经验 |
| **粒度** | 碎片化（"用户偏好 Python"） | 结构化（"部署到 K8s 的标准步骤"） |
| **触发方式** | 自动检索（RAG） | 按需加载（Progressive Disclosure） |
| **生命周期** | 持续积累，很少删 | 有版本，会迭代改进 |
| **类比** | 人的记忆——"我记得你叫 Martin" | 人的技能——"我知道怎么部署一个微服务" |

**它们是互补的：** Memory 回答"关于这件事我知道什么"，Skill 回答"这件事我知道怎么做"。

**联动方式：** Agent 加载一个 Skill 后，Memory 层自动检索出"上次使用这个 Skill 时的偏好和注意事项"，把两者拼在一起——Skill 给流程，Memory 给个性化。

在 Mini-Agent 里：
- `MEMORY.md` 是 Memory（长期记忆事实）
- `create_skill` 产物是 Skill（保存工作流程）

---

## 核心主张

> **"One ReactLoop Agent × N Skills" 替代了"意图识别 + 多 Agent 路由"。Skill 是经验的载体，不是 Agent 的分身。**
