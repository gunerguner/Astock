"""增量同步状态字符串枚举。"""

from enum import StrEnum


class SyncStatus(StrEnum):
    SUCCESS = "success"
    PARTIAL_FAILURE = "partial_failure"
    FAILED = "failed"
