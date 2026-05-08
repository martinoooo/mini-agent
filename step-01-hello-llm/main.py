"""
Step 1: Hello LLM — 最简单的 LLM 调用

学习目标:
  - 理解 LLM 是如何被调用的（API 调用 = 发送消息列表 → 获取回复）
  - 理解三个核心角色: system（设定行为）、user（用户输入）、assistant（模型回复）

运行:
  # 先在项目根目录 cp .env.example .env 并填入 API Key
  pip3 install openai python-dotenv
  python3 main.py

延伸思考:
  LLM 只能生成文本。它不能读你的文件、不能执行命令、不能上网搜索。
  如果我问它 "我桌面上有什么文件？"，它只能编造一个答案。
  这就是为什么我们需要 Step 2——给它工具。
"""

import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))


def main():
    # ── 初始化 OpenAI 客户端 ──────────────────────────
    client = OpenAI(
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    )
    model = os.getenv("MODEL", "deepseek-v4-pro")

    # ── 构建消息列表 ──────────────────────────────────
    # LLM 的输入是一个消息列表，每条消息有 role 和 content。
    # role=system    → 设定模型的行为和角色
    # role=user      → 用户说的话
    # role=assistant → 模型之前的回复（多轮对话时使用）
    messages = [
        {"role": "system", "content": "你是一个热心的助手，用中文回复。"},
        {"role": "user", "content": "用一句话介绍什么是 LLM"},
    ]

    # ── 调用 API ──────────────────────────────────────
    print("正在调用 LLM...")
    response = client.chat.completions.create(
        model=model,
        messages=messages,
    )

    # ── 获取回复 ──────────────────────────────────────
    answer = response.choices[0].message.content
    print(f"\n🤖 LLM 回复:\n{answer}")


if __name__ == "__main__":
    main()
