from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlparse

from src.adapters.base import BaseAdapter, ParseResult
from src.utils.http import HttpClient


class KuaishouAdapter(BaseAdapter):
    """快手适配器"""

    _DOMAINS = {"v.kuaishou.com", "www.kuaishou.com", "www.gifshow.com"}

    @staticmethod
    def match(url: str) -> bool:
        parsed = urlparse(url)
        host = parsed.hostname or ""
        return any(host == d or host.endswith("." + d) for d in KuaishouAdapter._DOMAINS)

    async def parse(self, url: str) -> ParseResult:
        async with HttpClient() as client:
            resp = await client.get(url)
            html = resp.text

            data = self._extract_data(html)

            if data:
                return self._parse_from_data(data)

            return self._parse_from_html(html, url)

    def _extract_data(self, html: str) -> dict[str, Any] | None:
        """从页面提取数据"""
        # 方式 1: window.__APOLLO_STATE__
        m = re.search(r'window\.__APOLLO_STATE__\s*=\s*(\{.*?\})\s*;?\s*</script>', html, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass

        # 方式 2: __NEXT_DATA__ (部分页面使用 Next.js)
        m = re.search(r'__NEXT_DATA__\s*=\s*(\{.*?\})\s*</script>', html, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass

        # 方式 3: window.__data__
        m = re.search(r'window\.__data__\s*=\s*(\{.*?\})\s*;?\s*</script>', html, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass

        return None

    def _parse_from_data(self, data: dict[str, Any]) -> ParseResult:
        """从 JSON 数据解析"""
        # 在 APOLLO_STATE 中查找视频/图文数据
        photo_data = None
        for key, val in data.items():
            if isinstance(val, dict) and ("photoId" in val or "caption" in val or "videoUrl" in val):
                photo_data = val
                break

        if not photo_data:
            # 尝试从 props.pageProps 提取 (Next.js)
            props = data.get("props", {}).get("pageProps", {})
            photo_data = props.get("photo") or props.get("videoInfo", {})

        title = photo_data.get("caption", "") if photo_data else ""
        desc = photo_data.get("caption", "") if photo_data else ""

        author = ""
        author_avatar = ""
        user_info = photo_data.get("user", {}) if photo_data else {}
        if user_info:
            author = user_info.get("name") or user_info.get("user_name") or user_info.get("nickname", "")
            avatar_url = user_info.get("headurl") or user_info.get("avatar", "")
            if avatar_url and not avatar_url.startswith("http"):
                avatar_url = "https://" + avatar_url
            author_avatar = avatar_url

        # 视频
        video_url = None
        if photo_data:
            video_url = (
                photo_data.get("videoUrl")
                or photo_data.get("video_url")
                or photo_data.get("playUrl")
                or photo_data.get("mp4Url")
            )
            if video_url and not video_url.startswith("http"):
                video_url = "https://" + video_url

        # 图片（图集）
        images: list[str] = []
        if photo_data:
            photo_list = photo_data.get("photoList") or photo_data.get("ext_params", {}).get("itemList", [])
            for item in photo_list:
                if isinstance(item, dict):
                    img_url = item.get("url") or item.get("cdnUrl") or item.get("src", "")
                    if img_url:
                        if not img_url.startswith("http"):
                            img_url = "https://" + img_url
                        images.append(img_url)

        # 封面
        cover_url = None
        if photo_data:
            cover = photo_data.get("coverUrl") or photo_data.get("cover", "")
            if cover:
                if not cover.startswith("http"):
                    cover = "https://" + cover
                cover_url = cover

        return ParseResult(
            platform="kuaishou",
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
            platform="kuaishou",
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
