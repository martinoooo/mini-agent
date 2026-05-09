"""
PII 脱敏 — Step 23 新增

学习目标:
  - 理解为什么需要脱敏：日志和会话文件是明文，敏感信息需要保护
  - 理解正则表达式在安全场景的应用
  - 理解脱敏的权衡：太激进会误伤正常内容，太保守会漏掉敏感信息

脱敏规则:
  - 手机号: 138****5678
  - 身份证: 110***********1234
  - 邮箱:   xiao****@qq.com
  - API Key: sk-****
  - IP 地址: 192.168.*.*
"""

import re

_PATTERNS = [
    # 手机号 (中国大陆)
    (re.compile(r'(1[3-9]\d)\d{4}(\d{4})'), r'\1****\2'),
    # 身份证号
    (re.compile(r'(\d{3})\d{11}(\d{3}[0-9Xx])'), r'\1***********\2'),
    # 邮箱: 保留前4个字符
    (re.compile(r'([a-zA-Z0-9._%+-]{4})[a-zA-Z0-9._%+-]*(@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'), r'\1****\2'),
    # API Key (sk- 开头)
    (re.compile(r'(sk-[a-zA-Z0-9]{3})[a-zA-Z0-9]+'), r'\1****'),
    # IP 地址
    (re.compile(r'(\d{1,3})\.\d{1,3}\.\d{1,3}\.\d{1,3}'), r'\1.*.*.*'),
    # 身份证号 (18位，纯数字)
    (re.compile(r'\b(\d{6})\d{8}(\d{4})\b'), r'\1********\2'),
]


def redact(text: str) -> str:
    """
    对文本中的敏感信息进行脱敏处理。
    返回脱敏后的文本。
    """
    if not text:
        return text
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text
