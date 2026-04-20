from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlparse

from src.adapters.base import BaseAdapter, ParseResult
from src.utils.http import HttpClient


class XiaohongshuAdapter(BaseAdapter):
    """小红书适配器"""

    _DOMAINS = {"www.xiaohongshu.com", "xhslink.com"}

    @staticmethod
    def match(url: str) -> bool:
        parsed = urlparse(url)
        host = parsed.hostname or ""
        return any(host == d or host.endswith("." + d) for d in XiaohongshuAdapter._DOMAINS)

    async def parse(self, url: str) -> ParseResult:
        async with HttpClient() as client:
            resp = await client.get(url)
            html = resp.text

            data = self._extract_data(html)

            if data:
                return self._parse_from_data(data)

            return self._parse_from_html(html, url)

    def _extract_data(self, html: str) -> dict[str, Any] | None:
        """从页面提取笔记数据"""
        # 方式 1: window.__INITIAL_STATE__
        m = re.search(r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\})\s*</script>', html, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass

        # 方式 2: <script type="application/ld+json">
        m = re.search(r'<script\s+type="application/ld\+json">\s*(.*?)\s*</script>', html, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass

        return None

    def _parse_from_data(self, data: dict[str, Any]) -> ParseResult:
        """从 JSON 数据解析"""
        # 从 __INITIAL_STATE__ 提取
        note_data = None

        # 尝试从 note.noteDetailMap 提取
        note_detail_map = data.get("note", {}).get("noteDetailMap", {})
        for key, val in note_detail_map.items():
            if isinstance(val, dict) and "note" in val:
                note_data = val["note"]
                break

        if not note_data:
            note_data = data.get("note", {})

        if not note_data:
            # 尝试从 ld+json 提取
            return self._parse_ld_json(data)

        title = note_data.get("title", "")
        desc = note_data.get("desc", "")
        user = note_data.get("user", {})
        author = user.get("nickname", "")
        author_avatar = user.get("avatar", "")
        if author_avatar and not author_avatar.startswith("http"):
            author_avatar = "https://" + author_avatar

        # 图片
        images: list[str] = []
        image_list = note_data.get("imageList") or note_data.get("imageList", [])
        for img in image_list:
            if isinstance(img, dict):
                # 优先使用无水印的大图
                url_default = img.get("urlDefault") or img.get("url", "")
                url_pre = img.get("urlPre") or ""
                img_url = url_pre or url_default
                if img_url:
                    if not img_url.startswith("http"):
                        img_url = "https://" + img_url
                    images.append(img_url)
            elif isinstance(img, str):
                if not img.startswith("http"):
                    img = "https://" + img
                images.append(img)

        # 视频
        video_url = None
        video = note_data.get("video", {})
        if isinstance(video, dict):
            media = video.get("media", {})
            if isinstance(media, dict):
                stream = media.get("stream", {})
                # 优先 h264
                h264 = stream.get("h264", [])
                if h264:
                    video_url = h264[0].get("master_url") or h264[0].get("backup_urls", [""])[0]
                if not video_url:
                    h265 = stream.get("h265", [])
                    if h265:
                        video_url = h265[0].get("master_url") or h265[0].get("backup_urls", [""])[0]
            if not video_url:
                consumer = video.get("consumer", {})
                if isinstance(consumer, dict):
                    origin_video = consumer.get("originVideoKey", "")
                    if origin_video:
                        video_url = f"https://sns-video-bd.xhscdn.com/{origin_video}"

        # 封面
        cover_url = None
        if isinstance(video, dict):
            cover = video.get("cover", {})
            if isinstance(cover, dict):
                cover_url = cover.get("urlDefault") or cover.get("url", "")
                if cover_url and not cover_url.startswith("http"):
                    cover_url = "https://" + cover_url

        return ParseResult(
            platform="xiaohongshu",
            title=title,
            description=desc,
            author=author,
            images=images,
            video_url=video_url,
            cover_url=cover_url,
            author_avatar=author_avatar,
        )

    def _parse_ld_json(self, data: dict[str, Any]) -> ParseResult:
        """从 ld+json 结构解析"""
        title = data.get("title", "未知标题")
        desc = data.get("description", "")
        image = data.get("image", "")
        images = [image] if image else []

        author = ""
        author_data = data.get("author", {})
        if isinstance(author_data, dict):
            author = author_data.get("name", "")

        return ParseResult(
            platform="xiaohongshu",
            title=title,
            description=desc,
            author=author,
            images=images,
            video_url=None,
            cover_url=image or None,
        )

    def _parse_from_html(self, html: str, url: str) -> ParseResult:
        """从 HTML meta 标签回退解析"""
        title = self._match_meta(html, "og:title") or "未知标题"
        desc = self._match_meta(html, "og:description") or ""
        image = self._match_meta(html, "og:image") or ""

        return ParseResult(
            platform="xiaohongshu",
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
