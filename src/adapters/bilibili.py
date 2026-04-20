from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlparse

from src.adapters.base import BaseAdapter, ParseResult
from src.utils.http import HttpClient


class BilibiliAdapter(BaseAdapter):
    """哔哩哔哩适配器"""

    _DOMAINS = {"b23.tv", "www.bilibili.com", "bilibili.com"}
    _BV_PATTERN = re.compile(r"/(BV[\w]+)")

    @staticmethod
    def match(url: str) -> bool:
        parsed = urlparse(url)
        host = parsed.hostname or ""
        return any(host == d or host.endswith("." + d) for d in BilibiliAdapter._DOMAINS)

    _DESKTOP_UA = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )

    @staticmethod
    def _to_desktop_url(url: str) -> str:
        """将移动端 URL 转为桌面端"""
        parsed = urlparse(url)
        if parsed.hostname == "m.bilibili.com":
            return url.replace("m.bilibili.com", "www.bilibili.com", 1)
        return url

    async def parse(self, url: str) -> ParseResult:
        url = self._to_desktop_url(url)
        async with HttpClient(headers={"User-Agent": self._DESKTOP_UA}) as client:
            resp = await client.get(url)
            html = resp.text

            # 从页面提取视频信息
            data = self._extract_video_data(html)

            if data:
                return self._parse_from_data(data, url)

            return self._parse_from_html(html, url)

    def _extract_video_data(self, html: str) -> dict[str, Any] | None:
        """从页面提取视频数据 JSON，合并 __playinfo__ 和 __INITIAL_STATE__"""
        playinfo = None
        initial_state = None

        m = re.search(r'window\.__playinfo__\s*=\s*(\{.*?\})\s*</script>', html, re.DOTALL)
        if m:
            try:
                playinfo = json.loads(m.group(1))
            except json.JSONDecodeError:
                pass

        m = re.search(r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\});', html, re.DOTALL)
        if m:
            try:
                initial_state = json.loads(m.group(1))
            except json.JSONDecodeError:
                pass

        if not playinfo and not initial_state:
            return None

        # 合并：playinfo 提供视频流 (dash/durl)，INITIAL_STATE 提供元数据 (videoData)
        merged: dict[str, Any] = {}
        if initial_state:
            merged.update(initial_state)
        if playinfo:
            merged["playinfo"] = playinfo
        return merged

    def _parse_from_data(self, data: dict[str, Any], url: str) -> ParseResult:
        """从 JSON 数据解析"""
        # 从 INITIAL_STATE 提取
        video_data = data.get("videoData") or data.get("view", {}).get("data", {})

        title = video_data.get("title", "")
        desc = video_data.get("desc", "")
        owner = video_data.get("owner", {}) or video_data.get("ownerInfo", {})
        author = owner.get("name", "")
        author_avatar = owner.get("face", "")
        pic = video_data.get("pic", "")

        # 视频流 URL（从 playinfo 提取）
        video_url = None
        audio_url = None
        playinfo_data = data.get("playinfo", data)
        dash = playinfo_data.get("data", {}).get("dash", {})
        if dash:
            # 优先取视频轨道
            video_info = dash.get("video", [])
            if video_info:
                video_url = video_info[0].get("baseUrl") or video_info[0].get("base_url")
            # 取音频轨道
            audio_info = dash.get("audio", [])
            if audio_info:
                audio_url = audio_info[0].get("baseUrl") or audio_info[0].get("base_url")

        # 如果有 durl 格式
        if not video_url:
            durl = playinfo_data.get("data", {}).get("durl", [])
            if durl:
                video_url = durl[0].get("url")

        return ParseResult(
            platform="bilibili",
            title=title,
            description=desc,
            author=author,
            images=[],
            video_url=video_url,
            audio_url=audio_url,
            cover_url=pic if pic else None,
            author_avatar=author_avatar,
        )

    def _parse_from_html(self, html: str, url: str) -> ParseResult:
        """从 HTML meta 标签回退解析"""
        title = self._match_meta(html, "og:title") or "未知标题"
        desc = self._match_meta(html, "og:description") or ""
        image = self._match_meta(html, "og:image") or ""

        return ParseResult(
            platform="bilibili",
            title=title,
            description=desc,
            author="",
            images=[],
            video_url=None,
            cover_url=image or None,
        )

    @staticmethod
    def _match_meta(html: str, prop: str) -> str | None:
        m = re.search(rf'<meta\s+property="{re.escape(prop)}"\s+content="([^"]*)"', html)
        if not m:
            m = re.search(rf'<meta\s+content="([^"]*)"\s+property="{re.escape(prop)}"', html)
        return m.group(1) if m else None
