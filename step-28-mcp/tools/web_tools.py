"""
Web 搜索工具 — Step 6 新增！

重点：这个文件是 Step 6 唯一新增的代码。
因为我们用了自注册模式，加一个全新的工具只需要:
  1. 创建这个文件（定义 handler + 调用 register()）
  2. 在 toolsets.py 的 MODULE_MAP 里加一行
  3. 在 TOOLSETS 里加一个 "web" 工具集

不需要修改 registry.py、agent.py、cli.py 中的任何代码！
这就是 Hermes Agent 自注册模式的威力。
"""

import urllib.request
import urllib.parse
import re
from tools.registry import register


def _web_search(query: str) -> str:
    """
    通过 DuckDuckGo HTML 搜索（免费，无需 API Key）。

    生产环境中应使用 SerpAPI、Google Custom Search 等服务。
    这里用 DuckDuckGo 是为了零配置即可运行。
    """
    url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
    req = urllib.request.Request(url, headers={"User-Agent": "MiniAgent/1.0"})

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8")
    except Exception as e:
        return f"搜索失败: {e}"

    # 解析搜索结果
    links = re.findall(
        r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
        html, re.DOTALL,
    )
    snippets = re.findall(
        r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>',
        html, re.DOTALL,
    )

    results = []
    for i, (raw_url, raw_title) in enumerate(links[:5]):
        title = re.sub(r'<.*?>', '', raw_title).strip()
        decoded_url = urllib.parse.unquote(raw_url)
        snippet = re.sub(r'<.*?>', '', snippets[i]).strip() if i < len(snippets) else ""
        results.append(f"- [{title}]({decoded_url})")
        if snippet:
            results.append(f"  {snippet}")

    return "\n".join(results) if results else "未找到相关结果"


# ── 自注册 ── 和 file_tools.py、terminal_tool.py 完全一样的模式
register(
    name="web_search",
    toolset="web",
    description="搜索互联网。传入关键词，返回前 5 条结果的标题、链接和摘要。",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "搜索关键词"},
        },
        "required": ["query"],
    },
    handler=_web_search,
)
