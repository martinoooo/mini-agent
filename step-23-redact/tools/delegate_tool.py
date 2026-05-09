"""
子 Agent 委派工具 — Step 20 新增

学习目标:
  - 理解 Agent 委派模式：父 Agent 把子任务交给子 Agent
  - 理解任务隔离：子 Agent 有独立的消息历史
  - 理解结果聚合：子 Agent 返回摘要给父 Agent

使用场景:
  "帮我研究 Python asyncio 和 Rust tokio 的对比"
  → 父 Agent 拆成两个子任务并行执行
  → 汇总结果

与 Hermes Agent 的关系:
  Hermes 有完整的 delegate_tool (tools/delegate_tool.py)，
  支持并发委派、文件状态共享、子进程管理。
  这里是极简版——创建独立 AIAgent，运行任务，返回结果。
"""

import os
import threading
from tools.registry import register


def _run_delegate(task: str) -> str:
    """
    创建子 Agent 执行任务，返回结果。

    子 Agent 的配置继承当前环境变量（API Key、Model、Base URL）。
    有独立的消息历史，不会污染父 Agent 的对话。
    """
    # 延迟导入避免循环依赖
    from agent import AIAgent

    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        return "错误: 未设置 DEEPSEEK_API_KEY"

    try:
        child = AIAgent(
            api_key=api_key,
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            model=os.getenv("MODEL", "deepseek-v4-pro"),
            toolset="dev",  # 子 Agent 用 dev 工具集（文件+终端+代码）
            max_iterations=8,
            approval_callback=None,  # 子 Agent 不需要审批
        )
        # 子 Agent 不需要 cron
        child.cron.stop()

        print(f"  👶 [子Agent] 开始: {task[:60]}...")
        result = child.run(task)
        print(f"  👶 [子Agent] 完成")
        return result
    except Exception as e:
        return f"子 Agent 执行失败: {e}"


register(
    name="delegate_task",
    toolset="delegate",
    description=(
        "创建一个独立的子 Agent 来执行任务。"
        "子 Agent 拥有独立的消息历史和工具访问权限，"
        "只返回最终的总结结果，中间过程不会进入你的上下文窗口。\n\n"
        "== 什么时候该用 delegate_task ==\n"
        "- 推理密集型任务（调试、代码审查、技术调研、对比分析）\n"
        "- 任务会产生大量中间数据，会撑爆你的上下文\n"
        "- 需要多轮工具调用的复杂任务（读取文件→分析→写报告）\n\n"
        "== 什么时候不该用（直接用这些替代）==\n"
        "- 简单问题自己知道答案 → 直接回答\n"
        "- 单个工具调用能搞定 → 直接调工具\n"
        "- 只需执行一段代码 → 用 execute_python\n\n"
        "== 重要注意事项 ==\n"
        "- 子 Agent 没有你的对话记忆，所有相关信息必须通过 task 参数传递\n"
        "- 子 Agent 的总结是自述的，涉及文件创建/修改的操作需要你去验证\n"
        "- 子 Agent 不能和用户交互（不能调 approval 相关的功能）"
    ),
    parameters={
        "type": "object",
        "properties": {
            "task": {
                "type": "string",
                "description": (
                    "委派给子 Agent 的任务描述。必须具体明确，包含所有必要信息：\n"
                    "- 文件路径、错误信息、项目结构\n"
                    "- 用户的语言偏好（如：用中文回复）\n"
                    "- 具体的输出要求"
                ),
            },
        },
        "required": ["task"],
    },
    handler=_run_delegate,
)
