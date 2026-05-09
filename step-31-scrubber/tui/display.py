"""
TUI 显示层 — Step 27 新增

基于 Rich 库的统一显示接口，替代散落的 print() 调用。

学习目标:
  - 理解显示层抽象：把"怎么显示"从"显示什么"中分离
  - 理解 Rich 的核心组件：Console、Panel、Markdown、Live
"""

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.table import Table
from rich.text import Text
from rich import box

console = Console()


class Display:
    """统一的终端显示接口"""

    # ── 标题和状态 ──────────────────────────────

    @staticmethod
    def header(title: str, model: str, toolset: str, approval: bool,
               tool_count: int, session_id: str = None):
        """打印启动横幅"""
        info = Table.grid(padding=(0, 2))
        info.add_column(style="dim")
        info.add_column()
        info.add_row("模型", f"[cyan]{model}[/]")
        info.add_row("工具集", f"[green]{toolset}[/] ({tool_count} 个工具)")
        info.add_row("审批", "[yellow]开启[/]" if approval else "[dim]关闭[/]")
        if session_id:
            info.add_row("会话", f"[dim]{session_id[:16]}...[/]")

        panel = Panel(info, title=f"[bold]Mini Agent — {title}[/]",
                      border_style="blue", padding=(1, 2))
        console.print(panel)

    @staticmethod
    def help_text():
        """打印帮助信息"""
        console.print("[dim]/save /sessions /load /tools /toolset /config /log /stats /cron /reset /quit[/]")

    # ── 流式输出 ────────────────────────────────

    @staticmethod
    def thinking_start():
        """思考开始"""
        console.print("\n🤖 ", end="")

    @staticmethod
    def thinking_token(text: str):
        """思考内容 token"""
        console.print(f"[dim italic]{text}[/]", end="")

    @staticmethod
    def text_token(text: str):
        """普通文本 token"""
        console.print(text, end="")

    @staticmethod
    def thinking_end():
        """思考结束"""
        console.print()

    # ── 工具调用 ────────────────────────────────

    @staticmethod
    def tool_call(iteration: int, name: str, args: str):
        """工具调用"""
        console.print(f"  [yellow]🔧[/] [dim][{iteration}][/] [cyan]{name}[/]({args})")

    @staticmethod
    def tool_result(iteration: int, result: str):
        """工具结果"""
        # 截断过长结果
        preview = result[:100].replace("\n", " ")
        console.print(f"  [green]✅[/] [dim][{iteration}][/] {preview}")

    @staticmethod
    def tool_blocked(reason: str):
        """工具被护栏拦截"""
        console.print(f"  [red]🛡️[/] {reason[:100]}")

    # ── 提醒 ────────────────────────────────────

    @staticmethod
    def reminder(text: str):
        """定时提醒"""
        console.print(f"\n  [bold yellow]⏰ {text}[/]")

    # ── 静态内容（Markdown） ─────────────────────

    @staticmethod
    def markdown(text: str):
        """渲染 Markdown 内容"""
        md = Markdown(text)
        console.print(md)

    # ── 会话统计 ────────────────────────────────

    @staticmethod
    def stats(usage_dict: dict):
        """显示使用统计"""
        table = Table(box=box.SIMPLE, show_header=False)
        table.add_column(style="dim")
        table.add_column(style="green")
        table.add_row("耗时", f"{usage_dict.get('elapsed_seconds', 0):.0f}秒")
        table.add_row("LLM 调用", f"{usage_dict.get('llm_calls', 0)} 次")
        table.add_row("工具调用", f"{usage_dict.get('tool_calls', 0)} 次")
        table.add_row("input", f"{usage_dict.get('input_tokens', 0):,} tokens")
        table.add_row("output", f"{usage_dict.get('output_tokens', 0):,} tokens")
        total = usage_dict.get('input_tokens', 0) + usage_dict.get('output_tokens', 0)
        table.add_row("合计", f"{total:,} tokens")

        console.print(Panel(table, title="会话统计", border_style="green"))

    # ── 子 Agent ─────────────────────────────────

    @staticmethod
    def subagent_start(task: str):
        """子 Agent 开始"""
        console.print(f"  [bold magenta]👶 [子Agent] 开始:[/] {task[:60]}...")

    @staticmethod
    def subagent_done():
        """子 Agent 完成"""
        console.print(f"  [bold magenta]👶 [子Agent] 完成[/]")

    # ── 简单消息 ────────────────────────────────

    @staticmethod
    def info(text: str):
        console.print(f"[dim]{text}[/]")

    @staticmethod
    def success(text: str):
        console.print(f"[green]✅ {text}[/]")

    @staticmethod
    def error(text: str):
        console.print(f"[red]❌ {text}[/]")
