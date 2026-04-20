from __future__ import annotations

import asyncio
from typing import Any, Optional

import httpx

_DEFAULT_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/17.0 Mobile/15E148 Safari/604.1"
)

_DEFAULT_HEADERS = {
    "User-Agent": _DEFAULT_UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

_TIMEOUT = 30.0
_MAX_RETRIES = 3
_RETRY_DELAY = 1.0


class HttpClient:
    """异步 HTTP 客户端封装"""

    def __init__(
        self,
        headers: Optional[dict[str, str]] = None,
        cookies: Optional[dict[str, str]] = None,
        timeout: float = _TIMEOUT,
        max_retries: int = _MAX_RETRIES,
        follow_redirects: bool = True,
    ) -> None:
        merged_headers = {**_DEFAULT_HEADERS, **(headers or {})}
        self._client = httpx.AsyncClient(
            headers=merged_headers,
            cookies=cookies,
            timeout=timeout,
            follow_redirects=follow_redirects,
        )
        self._max_retries = max_retries

    async def get(
        self,
        url: str,
        *,
        headers: Optional[dict[str, str]] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> httpx.Response:
        return await self._request("GET", url, headers=headers, params=params)

    async def post(
        self,
        url: str,
        *,
        headers: Optional[dict[str, str]] = None,
        json: Optional[Any] = None,
        data: Optional[Any] = None,
    ) -> httpx.Response:
        return await self._request("POST", url, headers=headers, json=json, data=data)

    async def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        last_exc: Optional[Exception] = None
        for attempt in range(self._max_retries):
            try:
                resp = await self._client.request(method, url, **kwargs)
                resp.raise_for_status()
                return resp
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code < 500:
                    raise
                last_exc = exc
            except (httpx.ConnectError, httpx.ReadTimeout, httpx.PoolTimeout) as exc:
                last_exc = exc
            if attempt < self._max_retries - 1:
                delay = _RETRY_DELAY * (2 ** attempt)
                await asyncio.sleep(delay)
        raise last_exc  # type: ignore[misc]

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> HttpClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
