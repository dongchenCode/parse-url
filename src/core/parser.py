from __future__ import annotations

import asyncio
from typing import Optional

from src.adapters.base import BaseAdapter, ParseResult
from src.utils.link import extract_urls, follow_redirect, identify_platform


class Parser:
    """解析调度器：识别平台 → 分发到对应适配器"""

    def __init__(self) -> None:
        self._adapters: list[BaseAdapter] = []

    def register(self, adapter: BaseAdapter) -> None:
        self._adapters.append(adapter)

    def _find_adapter(self, url: str) -> Optional[BaseAdapter]:
        for adapter in self._adapters:
            if adapter.match(url):
                return adapter
        return None

    async def parse(self, url: str) -> ParseResult:
        """解析单个链接"""
        # 预处理：跟随重定向
        real_url = await follow_redirect(url)
        adapter = self._find_adapter(real_url)
        if adapter is None:
            raise ValueError(f"无法识别的链接格式: {url}")
        return await adapter.parse(real_url)

    async def parse_batch(
        self, urls: list[str], max_concurrency: int = 5
    ) -> list[ParseResult | Exception]:
        """批量解析，返回结果列表（成功为 ParseResult，失败为 Exception）"""
        semaphore = asyncio.Semaphore(max_concurrency)

        async def _parse_one(u: str) -> ParseResult | Exception:
            async with semaphore:
                try:
                    return await self.parse(u)
                except Exception as exc:
                    return exc

        return await asyncio.gather(*[_parse_one(u) for u in urls])

    async def parse_text(self, text: str) -> ParseResult:
        """从文本中提取 URL 并解析第一个"""
        urls = extract_urls(text)
        if not urls:
            raise ValueError("文本中未找到有效链接")
        return await self.parse(urls[0])


def create_parser() -> Parser:
    """创建并注册所有适配器的 Parser 实例"""
    from src.adapters.douyin import DouyinAdapter
    from src.adapters.bilibili import BilibiliAdapter
    from src.adapters.kuaishou import KuaishouAdapter
    from src.adapters.xiaohongshu import XiaohongshuAdapter

    parser = Parser()
    parser.register(DouyinAdapter())
    parser.register(BilibiliAdapter())
    parser.register(KuaishouAdapter())
    parser.register(XiaohongshuAdapter())
    return parser
