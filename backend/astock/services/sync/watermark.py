"""同步水位：只推进到缺口前的最后一个完整日，且不回退。"""


def prefix_before_gap(
    expected: list[str], present: set[str]
) -> tuple[str | None, bool]:
    """返回 (连续覆盖的最后一日, 是否覆盖全部期望日)。

    期望序列为空视为没有需要同步的交易日。第一个期望日就缺失时，
    连续末尾为 None，调用方应保留旧水位。
    """
    if not expected:
        return None, True
    covered: str | None = None
    for day in expected:
        if day not in present:
            return covered, False
        covered = day
    return covered, True


def forward_date(old: str | None, new: str | None) -> str | None:
    """水位只允许保持或向前。"""
    if new is None:
        return old
    if old is None or new >= old:
        return new
    return old
