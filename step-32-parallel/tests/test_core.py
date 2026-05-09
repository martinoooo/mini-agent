"""
核心模块单元测试

运行: cd step-25-tests && python3 -m unittest tests/test_core.py -v
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# 确保 step 目录在 path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestRegistry(unittest.TestCase):
    """工具注册表测试"""

    def setUp(self):
        from tools.registry import _registry
        _registry.clear()

    def test_register_and_get(self):
        from tools.registry import register, get_all, get_handler

        def dummy_handler(x: str) -> str:
            return f"got {x}"

        register(
            name="test_tool",
            toolset="test",
            description="测试工具",
            parameters={"type": "object", "properties": {}},
            handler=dummy_handler,
        )

        self.assertEqual(len(get_all()), 1)
        self.assertIs(get_handler("test_tool"), dummy_handler)

    def test_build_openai_schemas(self):
        from tools.registry import register, build_openai_schemas

        register("t1", "ts", "d1", {"type": "object"}, lambda: None)
        register("t2", "ts", "d2", {"type": "object"}, lambda: None)

        schemas = build_openai_schemas(["t1", "t2"])
        self.assertEqual(len(schemas), 2)
        self.assertEqual(schemas[0]["function"]["name"], "t1")

    def test_get_handler_missing(self):
        from tools.registry import get_handler
        self.assertIsNone(get_handler("nonexistent"))


class TestApproval(unittest.TestCase):
    """审批系统测试"""

    def test_risk_levels(self):
        from tools.approval import TOOL_RISK, ApprovalManager
        self.assertEqual(TOOL_RISK["run_shell"], "high")
        self.assertEqual(TOOL_RISK["read_file"], "low")

    def test_needs_approval_default(self):
        from tools.approval import ApprovalManager
        am = ApprovalManager()
        self.assertTrue(am.needs_approval("run_shell"))      # high > medium
        self.assertTrue(am.needs_approval("write_file"))     # medium == medium
        self.assertFalse(am.needs_approval("read_file"))     # low < medium

    def test_auto_approve_without_callback(self):
        from tools.approval import ApprovalManager
        am = ApprovalManager()
        self.assertTrue(am.request("run_shell", {"cmd": "ls"}))


class TestGuardrails(unittest.TestCase):
    """护栏系统测试"""

    def setUp(self):
        from tools.guardrails import _call_history
        _call_history.clear()

    def test_loop_detection(self):
        from tools.guardrails import check
        for _ in range(4):
            result = check("read_file", {"path": "/tmp/test.txt"})
        self.assertIsNotNone(result)
        self.assertIn("循环", result)

    def test_sensitive_path(self):
        from tools.guardrails import check
        self.assertIsNotNone(check("read_file", {"path": "/etc/passwd"}))
        self.assertIsNone(check("read_file", {"path": "normal.txt"}))

    def test_long_command(self):
        from tools.guardrails import check
        self.assertIsNotNone(check("run_shell", {"command": "A" * 600}))
        self.assertIsNone(check("run_shell", {"command": "ls"}))


class TestRetry(unittest.TestCase):
    """重试系统测试"""

    def test_classify_rate_limit(self):
        from tools.retry import classify_error
        e = Exception("Rate limit exceeded")
        e.status_code = 429
        self.assertEqual(classify_error(e), "rate_limit")

    def test_classify_server_error(self):
        from tools.retry import classify_error
        e = Exception("500 Internal Server Error")
        self.assertEqual(classify_error(e), "server_error")

    def test_classify_auth(self):
        from tools.retry import classify_error
        e = Exception("Unauthorized")
        e.status_code = 401
        self.assertEqual(classify_error(e), "auth_error")

    def test_should_retry(self):
        from tools.retry import should_retry
        self.assertTrue(should_retry("rate_limit"))
        self.assertTrue(should_retry("server_error"))
        self.assertFalse(should_retry("bad_request"))
        self.assertFalse(should_retry("auth_error"))


class TestRedact(unittest.TestCase):
    """PII 脱敏测试"""

    def test_phone(self):
        from tools.redact import redact
        result = redact("我的手机是13812345678")
        self.assertNotIn("13812345678", result)
        self.assertIn("****", result)

    def test_email(self):
        from tools.redact import redact
        result = redact("联系xiaoming@qq.com")
        self.assertNotIn("xiaoming@qq.com", result)
        self.assertIn("****", result)

    def test_api_key(self):
        from tools.redact import redact
        result = redact("密钥sk-abc123def456")
        self.assertNotIn("sk-abc123def456", result)
        self.assertIn("sk-abc****", result)

    def test_normal_text_unchanged(self):
        from tools.redact import redact
        text = "今天天气不错"
        self.assertEqual(redact(text), text)


class TestConfig(unittest.TestCase):
    """配置系统测试"""

    def test_defaults(self):
        from config import Config
        c = Config()
        self.assertEqual(c.model, "deepseek-v4-pro")
        self.assertEqual(c.toolset, "full")

    def test_env_override(self):
        from config import Config
        with patch.dict(os.environ, {"TOOLSET": "coding"}):
            c = Config.load()
            self.assertEqual(c.toolset, "coding")

    def test_env_approval_off(self):
        from config import Config
        with patch.dict(os.environ, {"APPROVAL": "off"}):
            c = Config.load()
            self.assertFalse(c.approval)


class TestCredentialPool(unittest.TestCase):
    """凭证池测试"""

    def test_round_robin(self):
        from tools.credential_pool import CredentialPool
        pool = CredentialPool(["k1", "k2", "k3"])
        self.assertEqual(pool.get_key(), "k1")
        self.assertEqual(pool.get_key(), "k2")
        self.assertEqual(pool.get_key(), "k3")
        self.assertEqual(pool.get_key(), "k1")  # wrap

    def test_rate_limit(self):
        from tools.credential_pool import CredentialPool
        pool = CredentialPool(["k1", "k2", "k3"])
        pool.mark_rate_limited("k1")
        # k1 is now on cooldown, should get k2
        self.assertEqual(pool.get_key(), "k2")

    def test_empty(self):
        from tools.credential_pool import CredentialPool
        pool = CredentialPool([])
        self.assertIsNone(pool.get_key())


class TestSessionStore(unittest.TestCase):
    """会话存储测试"""

    def test_save_and_load(self):
        from session_store import SessionStore
        sid = SessionStore.save(
            messages=[{"role": "user", "content": "hello"}],
            model="test-model",
        )
        data = SessionStore.load(sid)
        self.assertEqual(data["model"], "test-model")
        self.assertEqual(len(data["messages"]), 1)

    def test_list_and_delete(self):
        from session_store import SessionStore
        sid = SessionStore.save(
            messages=[{"role": "user", "content": "test"}],
            model="m",
        )
        sessions = SessionStore.list_all()
        self.assertTrue(any(s["id"] == sid for s in sessions))
        SessionStore.delete(sid)
        self.assertIsNone(SessionStore.load(sid))


class TestUsageTracker(unittest.TestCase):
    """使用统计测试"""

    def test_tool_count(self):
        from tools.usage import UsageTracker
        ut = UsageTracker()
        ut.add_tool_call()
        ut.add_tool_call()
        self.assertEqual(ut.tool_calls, 2)

    def test_token_count(self):
        from tools.usage import UsageTracker

        class FakeUsage:
            prompt_tokens = 100
            completion_tokens = 50
            completion_tokens_details = None

        ut = UsageTracker()
        ut.add_llm_call(FakeUsage())
        self.assertEqual(ut.input_tokens, 100)
        self.assertEqual(ut.output_tokens, 50)
        self.assertEqual(ut.total_tokens, 150)


class TestCronScheduler(unittest.TestCase):
    """定时任务测试"""

    def test_add_and_list(self):
        from cron.scheduler import CronScheduler
        CronScheduler.add_task("测试任务", 60)
        tasks = CronScheduler.list_tasks()
        self.assertTrue(any(t["description"] == "测试任务" for t in tasks))
        for t in tasks:
            CronScheduler.delete_task(t["id"])

    def test_delete(self):
        from cron.scheduler import CronScheduler
        tid = CronScheduler.add_task("临时任务", 10)
        self.assertTrue(CronScheduler.delete_task(tid))
        self.assertFalse(CronScheduler.delete_task("nonexistent"))


if __name__ == "__main__":
    unittest.main()

class TestPluginSystem(unittest.TestCase):
    """插件系统测试"""

    def test_hook_registration_and_invoke(self):
        from plugins.hooks import HookManager
        hm = HookManager()
        calls = []

        def my_hook(name, args, result):
            calls.append((name, result))
            return f"[PLUGIN] {result}"

        hm.register("on_tool_call", my_hook)
        result = hm.invoke("on_tool_call", name="test", args={}, result="ok")
        self.assertEqual(result, "[PLUGIN] ok")
        self.assertEqual(len(calls), 1)

    def test_hook_count(self):
        from plugins.hooks import HookManager
        hm = HookManager()
        hm.register("on_startup", lambda x: None)
        hm.register("on_tool_call", lambda n, a, r: None)
        self.assertEqual(hm.count, 2)

    def test_invoke_unknown_hook(self):
        from plugins.hooks import HookManager
        hm = HookManager()
        result = hm.invoke("nonexistent", result="unchanged")
        self.assertEqual(result, "unchanged")

    def test_hook_error_does_not_crash(self):
        from plugins.hooks import HookManager
        hm = HookManager()

        def bad_hook(name, args, result):
            raise RuntimeError("插件崩溃")

        hm.register("on_tool_call", bad_hook)
        result = hm.invoke("on_tool_call", name="t", args={}, result="ok")
        self.assertEqual(result, "ok")  # 插件崩溃不影响主流程
