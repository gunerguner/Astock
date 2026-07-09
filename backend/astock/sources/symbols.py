"""A 股代码与各行情源符号转换。"""

import re

from astock.config import STOCK_CODE_PREFIXES

_CODE_DIGITS_RE = re.compile(r"^\d{6}$")
_BAOSTOCK_CODE_RE = re.compile(r"^(sh|sz)\.(\d{6})$")


def is_a_share_code(code: str) -> bool:
    if not _CODE_DIGITS_RE.match(code):
        return False
    exchange = "sh" if code.startswith("6") else "sz"
    prefixes = tuple(STOCK_CODE_PREFIXES.get(exchange, ()))
    return bool(prefixes) and code.startswith(prefixes)


def cn_index_sina_symbol(code: str) -> str:
    code = code.strip()
    prefix = "sz" if code.startswith("399") else "sh"
    return f"{prefix}{code}"


def to_baostock_code(code: str) -> str:
    prefix = "sh" if code.startswith("6") else "sz"
    return f"{prefix}.{code}"


def to_tencent_code(code: str) -> str:
    prefix = "sh" if code.startswith("6") else "sz"
    return f"{prefix}{code}"


def parse_baostock_code(code: str) -> tuple[str, str] | None:
    """解析 baostock 代码 `sh.600000` → (exchange, digits)。"""
    m = _BAOSTOCK_CODE_RE.match(code)
    if not m:
        return None
    return m.group(1), m.group(2)
