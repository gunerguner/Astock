"""A 股代码与各行情源符号转换。"""

import re

_BAOSTOCK_CODE_RE = re.compile(r"^(sh|sz)\.(\d{6})$")


def cn_index_sina_symbol(code: str) -> str:
    code = code.strip()
    prefix = "sz" if code.startswith("399") else "sh"
    return f"{prefix}{code}"


def parse_baostock_code(code: str) -> tuple[str, str] | None:
    """解析 baostock 代码 `sh.600000` → (exchange, digits)。"""
    m = _BAOSTOCK_CODE_RE.match(code)
    if not m:
        return None
    return m.group(1), m.group(2)
