# Mini Agent — 从零构建 AI Agent（渐进式教程）

> 借鉴 Hermes Agent 架构，分 6 步从零构建一个可运行的 AI Agent。
> 每一步都是完整可运行的项目，只比上一步多引入一个概念。

## 学习路线

```
Step 1: Hello LLM           ← 最简单的 LLM 调用，理解 "模型能干什么"
    │
Step 2: 第一个工具           ← 给 LLM 一把"螺丝刀"：read_file
    │
Step 3: 工具注册表           ← 自注册模式：工具自己管自己，加工具不用改核心代码
    │
Step 4: 工具集系统           ← 按场景打包工具，理解 "关注点分离"
    │
Step 5: Agent 循环 + CLI     ← LLM → 工具 → LLM → ... 的完整循环
    │
Step 6: Web 搜索             ← 扩展能力：加一个新工具只需新建一个文件
```

## 使用方法

每个步骤都是独立目录，进入后：

```bash
cd step-01-hello-llm
cp .env.example .env        # 编辑 .env 填入你的 API Key
pip install -r requirements.txt   # (只需在 step-01 装一次)
python main.py
```

## 你需要准备

- Python 3.10+
- 一个 DeepSeek API Key（也兼容 OpenAI / OpenRouter / 任何兼容接口）

## 每一步学什么

| 步骤 | 目录 | 新增概念 | 新增文件 |
|------|------|---------|---------|
| 1 | `step-01-hello-llm/` | LLM 调用、API Key、环境变量 | `main.py` |
| 2 | `step-02-first-tool/` | Function Calling、工具定义 | `tools/file_tools.py` |
| 3 | `step-03-registry/` | 自注册模式、中央注册表 | `tools/registry.py` |
| 4 | `step-04-toolset/` | 工具集编组、按场景组合 | `toolsets.py` |
| 5 | `step-05-agent-loop/` | Agent 循环、工具调用链、CLI | `agent.py`, `cli.py` |
| 6 | `step-06-web-search/` | 互联网搜索、扩展验证 | `tools/web_tools.py` |
