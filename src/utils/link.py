from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urlparse

import httpx

# 平台域名 → 平台 ID 映射
_PLATFORM_MAP: dict[str, str] = {
    "v.douyin.com": "douyin",
    "www.douyin.com": "douyin",
    "www.iesdouyin.com": "douyin",
    "b23.tv": "bilibili",
    "www.bilibili.com": "bilibili",
    "bilibili.com": "bilibili",
    "v.kuaishou.com": "kuaishou",
    "www.kuaishou.com": "kuaishou",
    "www.xiaohongshu.com": "xiaohongshu",
    "xhslink.com": "xiaohongshu",
}

# 已知短链域名，这些域名一定需要重定向
_SHORT_LINK_DOMAINS = {"b23.tv", "v.douyin.com", "v.kuaishou.com", "xhslink.com"}

_URL_PATTERN = re.compile(r"https?://[^\s<>\"]+")

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/17.0 Mobile/15E148 Safari/604.1"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

# 匹配 HTML 中的跳转：meta refresh / window.location / location.href
_META_REFRESH_RE = re.compile(
    r'<meta[^>]*http-equiv=["\']?refresh["\']?[^>]*content=["\']?\d+;\s*url=([^"\'>\s]+)',
    re.IGNORECASE,
)
_JS_LOCATION_RE = re.compile(
    r'(?:window\.)?location(?:\.href)?\s*=\s*["\']([^"\']+)["\']',
    re.IGNORECASE,
)


def extract_urls(text: str) -> list[str]:
    """从文本中提取所有 URL"""
    return _URL_PATTERN.findall(text)


def _is_short_link(url: str) -> bool:
    """判断是否为短链"""
    host = urlparse(url).hostname or ""
    return host in _SHORT_LINK_DOMAINS


def _extract_html_redirect(html: str) -> Optional[str]:
    """从 HTML 中提取跳转 URL（meta refresh / JS location）"""
    m = _META_REFRESH_RE.search(html)
    if m:
        return m.group(1)
    m = _JS_LOCATION_RE.search(html)
    if m:
        return m.group(1)
    return None


async def follow_redirect(url: str, max_hops: int = 5) -> str:
    """跟随短链重定向，获取真实 URL

    支持三种跳转方式：
    1. HTTP 3xx 重定向
    2. HTML meta refresh
    3. JS window.location
    """
    current = url
    for _ in range(max_hops):
        if not _is_short_link(current):
            return current

        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=15.0,
            headers=_HEADERS,
        ) as client:
            try:
                resp = await client.get(current)
            except Exception:
                return current

            # HTTP 重定向后的最终 URL
            final_url = str(resp.url)

            # 如果 URL 已经变了且不再是短链，直接返回
            if final_url != current and not _is_short_link(final_url):
                return final_url

            # 检查 HTML 中的跳转
            if resp.status_code == 200 and "text/html" in resp.headers.get("content-type", ""):
                html_redirect = _extract_html_redirect(resp.text)
                if html_redirect and html_redirect != current:
                    current = html_redirect
                    continue

            # 没有更多跳转
            return final_url

    return current


def identify_platform(url: str) -> Optional[str]:
    """根据 URL 域名识别平台"""
    parsed = urlparse(url)
    host = parsed.hostname or ""
    for domain, platform in _PLATFORM_MAP.items():
        if host == domain or host.endswith("." + domain):
            return platform
    return None
