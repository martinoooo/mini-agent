# Agent 评测与指标

Agent 是评测驱动的。但 Agent 评测跟传统 ML 评测有本质区别——传统 ML 是"预测值 vs 真值"比大小，Agent 是多步轨迹，没有单一正确答案。

---

## 一、有哪些 Metric

分四个维度：

### 任务级（最终结果）

| 指标 | 衡量什么 | 例子 |
|------|---------|------|
| **Success Rate** | 任务最终完成了没 | 100 个部署任务中成功了多少个 |
| **Efficiency** | 完成得是否高效 | 平均消耗几个 LoopTurn、多少 token、多少秒 |
| **Goal Completion** | 目标达成度（部分完成也算） | 要求改 5 个文件，只改了 4 个 = 0.8 |

### 轨迹级（过程质量）

| 指标 | 衡量什么 | 例子 |
|------|---------|------|
| **Tool Selection Accuracy** | 选的工具对不对 | 要读文件却调了 `run_shell` → 选错了 |
| **Tool Call Correctness** | 参数对不对 | 调了 `read_file` 但路径写错了 |
| **Reasoning Correctness** | 中间推理对不对 | 分析日志时把正常的 WARNING 当成了根因 |
| **Recovery Rate** | 犯错后能不能自己纠回来 | 第一次路径写错，看到错误后能纠正 |

### 安全级

| 指标 | 衡量什么 |
|------|---------|
| **Guardrail Trigger Rate** | 护栏触发频率（过高说明 Agent 行为越界） |
| **Refusal Rate** | 面对有害请求正确拒绝的比例 |
| **Approval Trigger Rate** | 触发人工审批的频率（过高说明自主性不足） |

### 体验级

| 指标 | 衡量什么 |
|------|---------|
| **User Satisfaction** | 用户满意度评分（👍/👎） |
| **Abandonment Rate** | 用户中途放弃的比例 |
| **Regeneration Rate** | 用户要求"重新来"的频率 |

### 面试要点

只提 Success Rate 不够。要说出**效率和安全的权衡**——一个 Agent 100% 成功但每轮要 50 个 LoopTurn（太慢），另一个 80% 成功但 3 轮完成（高效）。**评测不是看单一指标，是看多个指标的 trade-off。**

---

## 二、Offline vs Online 评测流程

### Offline 评测（上线前）

不接触真实用户，用提前准备好的数据集跑批量评测：

```
1. 构建评测数据集（Benchmark）
   └─ N 个典型任务，每个有输入 + 预期输出/预期轨迹

2. 跑 Agent
   └─ 每个任务从头跑一遍，记录完整 Trajectory

3. 自动化评判
   └─ 检查最终结果 → Success Rate
   └─ 检查轨迹每步 → Tool Accuracy
   └─ 检查效率 → Token/Turn 统计

4. 产出评测报告
   └─ 哪些任务过了/挂了
   └─ 挂的原因分类（工具选错 / 参数错 / 推理错 / 护栏误拦）
```

**数据集的来源：**
- 公开 Benchmark（SWE-bench、GAIA、WebArena、τ-bench）
- 内部积累（真实用户历史成功对话脱敏后改为评测用例）
- 对抗用例（专门设计来测边界的坏 case）

### Online 评测（上线后）

在生产环境中用真实用户流量做评测：

```
1. 灰度上线
2. 收集真实使用数据
   └─ Trajectory 记录 + 用户反馈（👍👎）+ 任务完成状态
3. 统计线上指标
   └─ 真实 Success Rate、Abandonment Rate、平均 Token、满意度
4. 对比基线
   └─ 新模型/新策略 vs 旧版本
```

### 对比

| | Offline | Online |
|---|---|---|
| **数据** | 提前准备的标准数据集 | 真实用户的真实请求 |
| **速度** | 快，几小时内出结果 | 慢，需积累足够流量（数天） |
| **可复现** | 完全可复现 | 不可复现（用户行为会变） |
| **覆盖面** | 只覆盖预定义的场景 | 自然覆盖长尾场景 |
| **成本** | 低（批量跑） | 高（可能影响真实用户） |
| **用途** | 开发阶段快速迭代、回归检测 | 最终决策、发现 offline 没覆盖的问题 |

**核心原则：Offline 过了才能上线，Online 才是最终裁判。** Offline 通过了不等于生产没问题——数据集永远不可能覆盖所有真实使用场景。

---

## 三、不同场景用什么评测框架

没有万能框架，不同任务用不同的：

| 场景 | 常用 Benchmark / 框架 | 评什么 |
|------|---------------------|--------|
| **代码生成/修复** | SWE-bench, HumanEval, MBPP | 代码能不能通过单元测试 |
| **Web 操作** | WebArena, MiniWoB++ | Agent 能不能在网页上完成预定操作 |
| **通用 Agent 任务** | GAIA, OSWorld | 端到端任务完成率 |
| **工具调用** | τ-bench, ToolBench, BFCL | 工具选择是否正确、参数对不对 |
| **多轮对话** | MT-Bench, Chatbot Arena | 回答质量的人工/自动化评分 |
| **企业内部任务** | 自建 Eval Harness | 贴合自身业务流程的自定义指标 |

**大部分公司不只用公开 Benchmark——核心用的是自建 Eval Harness。** 公开 Benchmark 证明模型能力，自建 Harness 证明业务价值。

```python
# 一个最简单的自建 Eval Harness
class AgentEval:
    def __init__(self, test_cases):
        self.test_cases = test_cases

    def run(self, agent_factory):
        results = []
        for case in self.test_cases:
            agent = agent_factory()
            trajectory = agent.run_with_trajectory(case.input)
            results.append({
                "case_id": case.id,
                "success": self.judge(case.expected, trajectory),
                "turns": len(trajectory),
                "tokens": sum(t["token_usage"]["total"] for t in trajectory),
                "tool_errors": self.count_tool_errors(trajectory),
            })
        return self.summarize(results)
```

---

## 四、Single Turn vs Multi Turn 评测

### Single Turn（一问一答）

```
用户: "Python 里怎么读取 JSON 文件？"
Agent: "用 json.load()，示例: ..."
```

评测方式接近传统 NLP——**看输出质量**：

| 方法 | 做法 | 适用 |
|------|------|------|
| **人工评分** | 人看回答打 1-5 分 | 质量要求高、不能自动化的场景 |
| **LLM-as-Judge** | 用更强的模型打分（如 GPT-4 评 Claude） | 大规模、成本敏感 |
| **N-gram 匹配**（BLEU/ROUGE） | 和参考答案比字面相似度 | 翻译、摘要等有标准答案的任务 |
| **功能验证** | 代码答案直接跑测试用例 | 代码生成 |

### Multi Turn（多步交互）

```
Turn 1: Agent 调 tool run_shell("git tag v1.2.3")
Turn 2: Agent 调 tool run_shell("kubectl apply -f deploy.yaml")
Turn 3: Agent 调 tool run_shell("kubectl rollout status ...")
  → Agent: "部署完成 ✅"
```

评测要**看整条轨迹，不是只看最终回复**：

| 维度 | 怎么评 |
|------|--------|
| **最终结果** | 部署成功了吗？（查版本号、查 Pod 状态） |
| **每一步是否正确** | Tool 选对了吗？参数对吗？顺序对吗？ |
| **有没有多余步骤** | 调了不必要的工具？ |
| **有没有遗漏步骤** | 部署后没做健康检查？ |
| **错误恢复** | 中途遇到错误，Agent 自己纠正了还是放弃了？ |

### Multi Turn 评测的难点：没有标准答案

同一个任务，10 条不同的轨迹都可能成功。三种解法：

1. **结果验证法**：不管中间怎么走，只验证最终结果（文件存在？服务启动了？测试通过了？）。Mini-Agent 能做到——跑完 Agent 后写个验证脚本检查系统状态。

2. **轨迹约束法**：定义"必须经过的关键步骤"（部署任务必须包含 build + push + deploy + healthcheck），检查轨迹是否覆盖。

3. **LLM-as-Judge 轨迹评分**：把整条轨迹丢给强模型，从"是否高效、是否安全、是否合理"三个角度打分。

---

## 五、新特性或新模型上线的评测流程

### 标准流程（四层门禁）

```
Step 1: 离线评测（Offline Eval）
  └─ 新版本在评测数据集上跑一遍
  └─ 对比基线的各项指标
  └─ 如果核心指标下降超过阈值 → 打回

Step 2: 影子模式（Shadow Mode）
  └─ 新模型在线上并行运行，输出不展示给用户
  └─ 对比新旧模型的输出差异
  └─ 积累数据看新模型在真实场景下的表现

Step 3: 灰度发布（Canary）
  └─ 5%-10% 的用户流量切到新版本
  └─ 观察 Online 指标（成功率、弃用率、满意度）
  └─ 如果指标恶化 → 立即回滚

Step 4: 全量上线
  └─ 逐步放量到 100%
  └─ 持续监控
```

### 每一步的门禁标准

```
Offline 评测:
  ✅ 核心 Success Rate 不下降（≤ -3%）
  ✅ 安全指标不恶化（护栏触发率、内容违规率）
  ✅ 平均 Token 不暴增（≤ +10%）

影子模式:
  ✅ 新旧模型输出不一致率在可接受范围
  ✅ 新模型拒绝率不异常偏高

灰度发布:
  ✅ 用户满意度不下降
  ✅ Abandonment Rate 不上升
  ✅ 线上错误率不上升

任何一步没过 → 回滚 → 分析原因 → 修好 → 重走流程
```

### 面试关键话术

被问"新模型怎么上线"，不说"跑一下评测然后上"。要说：

1. **分层门禁** — 每层有量化阈值，不达标就阻断
2. **回归测试集** — 积累历史上所有出过问题的 case，每次上线前必须过
3. **快速回滚** — 灰度发现问题，回滚时间以分钟计，不是天
4. **评测驱动迭代** — 失败 case 自动加入评测集，同一个坑不踩两次

最后一点最重要：**评测集不是静态的，是从线上失败中不断增长的。** 跟 Skill Improvement 同理——经验要积累，评测也要积累。

---

## 六、汇总

| 问题 | 一句话回答 |
|------|-----------|
| 有哪些 Metric？ | 任务级（成功率/效率）、轨迹级（工具准确性）、安全级（护栏触发）、体验级（满意度） |
| Offline vs Online？ | Offline 快速迭代可复现，Online 真实但慢；Offline 过了才上线，Online 是最终裁判 |
| 用什么评测框架？ | 公开 Benchmark 证明模型能力，自建 Harness 证明业务价值；不同任务用不同框架 |
| Single vs Multi Turn？ | Single 看输出质量，Multi 看整条轨迹——结果验证 + 关键步骤覆盖 + LLM-as-Judge |
| 新模型怎么上线？ | 分层门禁（Offline → Shadow → Canary → 全量），每层有量化阈值，失败 case 自动入评测集 |
