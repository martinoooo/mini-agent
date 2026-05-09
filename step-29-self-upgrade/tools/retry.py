"""
API 错误分类与重试 — Step 14 新增

学习目标:
  - 理解为什么需要重试：网络不稳、服务暂时过载是常态
  - 理解错误分类：不是所有错误都应该重试（4xx vs 5xx）
  - 理解指数退避：避免重试风暴，给服务端恢复时间

重试策略:
  可重试: 429(限流) / 5xx(服务端错误) / timeout / 网络错误
  不重试: 400(请求错误) / 401(认证失败) / 402(配额不足)

退避公式: delay = base_delay * 2^attempt (1s → 2s → 4s)
"""

import time
from typing import Callable

# 最大重试次数
MAX_RETRIES = 3
# 基础延迟（秒）
BASE_DELAY = 1.0


def classify_error(error: Exception) -> str:
    """
    将异常分类为已知错误类型。

    返回: 'rate_limit' | 'server_error' | 'timeout' | 'network' | 'bad_request' | 'auth_error' | 'unknown'
    """
    error_str = str(error).lower()
    status_code = getattr(error, "status_code", None)

    # HTTP 429 — 限流
    if "429" in error_str or "rate limit" in error_str or status_code == 429:
        return "rate_limit"

    # HTTP 5xx — 服务端临时故障
    if status_code and 500 <= status_code < 600:
        return "server_error"
    if any(f"{c}" in error_str for c in ["500", "502", "503", "504"]):
        return "server_error"
    if "server error" in error_str or "internal error" in error_str:
        return "server_error"

    # HTTP 401/403 — 认证失败，不重试
    if status_code in (401, 403):
        return "auth_error"

    # HTTP 400/402 — 请求错误/配额，不重试
    if status_code in (400, 402):
        return "bad_request"

    # 超时
    if "timeout" in error_str or "timed out" in error_str:
        return "timeout"

    # 网络错误
    if any(k in error_str for k in ["connection", "network", "dns", "refused", "reset"]):
        return "network"

    return "unknown"


def should_retry(error_type: str) -> bool:
    """判断该错误类型是否应该重试"""
    return error_type in ("rate_limit", "server_error", "timeout", "network")


def retry_call(fn: Callable, description: str = "API call"):
    """
    包装一个函数调用，失败时自动重试。

    用法:
      result = retry_call(lambda: client.chat.completions.create(...))

    重试行为:
      - rate_limit: 延迟较久 (base * 2^attempt * 2)，避免继续触发限流
      - server_error: 标准退避 (base * 2^attempt)
      - timeout: 标准退避
      - network: 快速重试
      - 其他错误: 不重试，直接抛出
    """
    last_error = None

    for attempt in range(MAX_RETRIES + 1):  # 0 = 首次, 1-3 = 重试
        try:
            return fn()
        except Exception as e:
            last_error = e
            error_type = classify_error(e)

            if not should_retry(error_type):
                raise  # 不可重试的错误，直接抛出

            if attempt == MAX_RETRIES:
                break  # 已达最大重试次数

            # 计算延迟
            if error_type == "rate_limit":
                delay = BASE_DELAY * (2 ** attempt) * 2  # 限流多等一会
            else:
                delay = BASE_DELAY * (2 ** attempt)

            wait_msg = f"{description} 失败 ({error_type})，第 {attempt+1}/{MAX_RETRIES} 次重试，等待 {delay:.0f}s..."
            print(f"\n  ⏳ {wait_msg}")
            time.sleep(delay)

    # 所有重试都失败了
    raise last_error
