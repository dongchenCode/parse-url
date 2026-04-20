from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ParseResult:
    """解析结果数据类"""

    platform: str  # 'douyin' | 'bilibili' | 'kuaishou' | 'xiaohongshu'
    title: str
    description: str
    author: str
    images: list[str] = field(default_factory=list)
    video_url: Optional[str] = None
    cover_url: Optional[str] = None
    author_avatar: Optional[str] = None


class BaseAdapter(ABC):
    """平台适配器基类"""

    @staticmethod
    @abstractmethod
    def match(url: str) -> bool:
        """检查链接是否匹配该平台"""
        ...

    @abstractmethod
    async def parse(self, url: str) -> ParseResult:
        """解析链接，返回结构化内容"""
        ...
