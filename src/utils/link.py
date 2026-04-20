from __future__ import annotations

import re
from typing import Optional

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

_URL_PATTERN = re.compile(r"https?://[^\s<>\"]+")


def extract_urls(text: str) -> list[str]:
    """从文本中提取所有 URL"""
    return _URL_PATTERN.findall(text)


async def follow_redirect(url: str) -> str:
    """跟随短链重定向，获取真实 URL"""
    async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
        resp = await client.get(url)
        return str(resp.url)


def identify_platform(url: str) -> Optional[str]:
    """根据 URL 域名识别平台"""
    from urllib.parse import urlparse

    parsed = urlparse(url)
    host = parsed.hostname or ""
    for domain, platform in _PLATFORM_MAP.items():
        if host == domain or host.endswith("." + domain):
            return platform
    return None
