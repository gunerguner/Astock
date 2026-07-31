"""通用 httpx 请求封装。"""


from typing import Any

import httpx

from astock.config import EM_USER_AGENT
from astock.providers._shared.retry import retry_call

HTTP_TIMEOUT = 30.0
FRED_HTTP_TIMEOUT = 6.0
DEFAULT_HEADERS = {
    "User-Agent": EM_USER_AGENT,
    "Accept": "text/csv,application/json,*/*",
}


def http_get_text(
    url: str,
    *,
    label: str,
    params: dict[str, Any] | None = None,
    timeout: float = HTTP_TIMEOUT,
    headers: dict[str, str] | None = None,
) -> str:
    hdrs = headers or DEFAULT_HEADERS

    def _do() -> str:
        with httpx.Client(timeout=timeout, headers=hdrs, http2=False) as client:
            resp = client.get(url, params=params)
            resp.raise_for_status()
            return resp.text

    return retry_call(label, _do)


def http_get_json(
    url: str,
    *,
    label: str,
    params: dict[str, Any] | None = None,
    timeout: float = HTTP_TIMEOUT,
    headers: dict[str, str] | None = None,
) -> Any:
    hdrs = headers or DEFAULT_HEADERS

    def _do() -> Any:
        with httpx.Client(timeout=timeout, headers=hdrs, http2=False) as client:
            resp = client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()

    return retry_call(label, _do)
