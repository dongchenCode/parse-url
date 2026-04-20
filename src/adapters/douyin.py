from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlparse

from src.adapters.base import BaseAdapter, ParseResult
from src.utils.http import HttpClient


class DouyinAdapter(BaseAdapter):
    """抖音适配器"""

    # 匹配域名
    _DOMAINS = {"v.douyin.com", "www.douyin.com", "www.iesdouyin.com"}

    @staticmethod
    def match(url: str) -> bool:
        parsed = urlparse(url)
        host = parsed.hostname or ""
        return any(host == d or host.endswith("." + d) for d in DouyinAdapter._DOMAINS)

    async def parse(self, url: str) -> ParseResult:
        async with HttpClient() as client:
            resp = await client.get(url)
            html = resp.text

            # 尝试从 RENDER_DATA 或 SSR 数据中提取 JSON
            data = self._extract_json(html)

            if data:
                return self._parse_from_data(data)

            # 回退：从 meta 标签提取
            return self._parse_from_html(html, url)

    def _extract_json(self, html: str) -> dict[str, Any] | None:
        """从页面中提取 JSON 数据"""
        # 方式 1: RENDER_DATA
        m = re.search(r'id="RENDER_DATA"[^>]*>(.*?)</script>', html)
        if m:
            try:
                from urllib.parse import unquote
                raw = unquote(m.group(1))
                render_data = json.loads(raw)
                # 遍历 key 找到包含视频/图文数据的对象
                for key, val in render_data.items():
                    if isinstance(val, dict):
                        detail = val.get("awemeDetail") or val.get("aweme_detail")
                        if detail:
                            return detail
            except (json.JSONDecodeError, KeyError):
                pass

        # 方式 2: window._ROUTER_DATA
        m = re.search(r'window\._ROUTER_DATA\s*=\s*(\{.*?\})\s*</script>', html, re.DOTALL)
        if m:
            try:
                router_data = json.loads(m.group(1))
                for key, val in router_data.items():
                    if isinstance(val, dict):
                        detail = val.get("awemeDetail") or val.get("aweme_detail")
                        if detail:
                            return detail
            except (json.JSONDecodeError, KeyError):
                pass

        return None

    def _parse_from_data(self, data: dict[str, Any]) -> ParseResult:
        """从 JSON 数据解析"""
        # 基础信息
        author_info = data.get("authorInfo") or data.get("author", {})
        author = author_info.get("nickname", "")
        author_avatar = (
            author_info.get("avatar168x168", {}).get("url_list", [""])[0]
            if isinstance(author_info.get("avatar168x168"), dict)
            else ""
        )

        desc = data.get("desc", "")
        title = desc.split("\n")[0] if desc else ""

        # 图片
        images: list[str] = []
        img_data = data.get("images")
        if img_data:
            for img in img_data:
                url_list = img.get("url_list", [])
                if url_list:
                    # 选择最大分辨率的 URL
                    images.append(url_list[-1])

        # 视频
        video_url = None
        video_data = data.get("video", {})
        play_addr = video_data.get("playAddr") or video_data.get("play_addr", {})
        if isinstance(play_addr, dict):
            url_list = play_addr.get("url_list", [])
            if url_list:
                video_url = url_list[0]

        # 尝试获取无水印视频
        if not video_url:
            play_addr_265 = video_data.get("playAddr265") or video_data.get("play_addr_265", {})
            if isinstance(play_addr_265, dict):
                url_list = play_addr_265.get("url_list", [])
                if url_list:
                    video_url = url_list[0]

        # 封面
        cover_url = None
        cover_data = video_data.get("cover") or video_data.get("originCover") or video_data.get("origin_cover", {})
        if isinstance(cover_data, dict):
            url_list = cover_data.get("url_list", [])
            if url_list:
                cover_url = url_list[-1]

        return ParseResult(
            platform="douyin",
            title=title,
            description=desc,
            author=author,
            images=images,
            video_url=video_url,
            cover_url=cover_url,
            author_avatar=author_avatar,
        )

    def _parse_from_html(self, html: str, url: str) -> ParseResult:
        """从 HTML meta 标签回退解析"""
        title = self._match_meta(html, "og:title") or "未知标题"
        desc = self._match_meta(html, "og:description") or ""
        image = self._match_meta(html, "og:image") or ""

        return ParseResult(
            platform="douyin",
            title=title,
            description=desc,
            author="",
            images=[image] if image else [],
            video_url=None,
            cover_url=image or None,
        )

    @staticmethod
    def _match_meta(html: str, prop: str) -> str | None:
        m = re.search(rf'<meta\s+property="{re.escape(prop)}"\s+content="([^"]*)"', html)
        if not m:
            m = re.search(rf'<meta\s+content="([^"]*)"\s+property="{re.escape(prop)}"', html)
        return m.group(1) if m else None
