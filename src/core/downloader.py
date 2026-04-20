from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

import httpx

from src.adapters.base import ParseResult
from src.utils.file import ensure_dir, format_size, get_extension, safe_filename, url_hash

_MAX_CONCURRENCY = 5
_MAX_RETRIES = 3
_CHUNK_SIZE = 65536


@dataclass
class DownloadItem:
    """单个下载项的结果"""

    url: str
    filename: str
    path: Path
    size: int = 0
    status: str = "pending"  # pending | downloading | done | failed
    error: Optional[str] = None

    @property
    def size_display(self) -> str:
        return format_size(self.size)


@dataclass
class DownloadResult:
    """下载任务的总结果"""

    output_dir: Path
    items: list[DownloadItem] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.items)

    @property
    def completed(self) -> int:
        return sum(1 for i in self.items if i.status == "done")

    @property
    def failed(self) -> int:
        return sum(1 for i in self.items if i.status == "failed")


# 进度回调类型：接收 (已完成数, 总数, 当前下载项)
ProgressCallback = Callable[[int, int, DownloadItem], None]


async def download_media(
    result: ParseResult,
    output_dir: Path | str = "output",
    *,
    progress: Optional[ProgressCallback] = None,
    max_concurrency: int = _MAX_CONCURRENCY,
) -> DownloadResult:
    """根据解析结果下载所有媒体文件"""
    output_dir = Path(output_dir)
    # 按平台和标题组织目录
    dir_name = safe_filename(result.title) if result.title else url_hash(str(result.video_url or ""))
    save_dir = output_dir / result.platform / dir_name
    ensure_dir(save_dir)

    # 收集所有需要下载的 URL
    urls: list[str] = []
    if result.video_url:
        urls.append(result.video_url)
    urls.extend(result.images)

    items: list[DownloadItem] = []
    for i, url in enumerate(urls):
        ext = get_extension(url)
        if result.video_url and url == result.video_url:
            filename = f"video{ext}"
        else:
            filename = f"{i:03d}{ext}"
        items.append(
            DownloadItem(url=url, filename=filename, path=save_dir / filename)
        )

    download_result = DownloadResult(output_dir=save_dir, items=items)

    if not items:
        return download_result

    semaphore = asyncio.Semaphore(max_concurrency)

    async def _download_one(item: DownloadItem) -> None:
        async with semaphore:
            for attempt in range(_MAX_RETRIES):
                try:
                    item.status = "downloading"
                    if progress:
                        progress(download_result.completed, download_result.total, item)

                    async with httpx.AsyncClient(
                        follow_redirects=True, timeout=120.0
                    ) as client:
                        async with client.stream("GET", item.url) as resp:
                            resp.raise_for_status()
                            with open(item.path, "wb") as f:
                                async for chunk in resp.aiter_bytes(_CHUNK_SIZE):
                                    f.write(chunk)
                            item.size = item.path.stat().st_size

                    item.status = "done"
                    break
                except Exception as exc:
                    if attempt == _MAX_RETRIES - 1:
                        item.status = "failed"
                        item.error = str(exc)
                    else:
                        await asyncio.sleep(1.0 * (attempt + 1))

            if progress:
                progress(download_result.completed, download_result.total, item)

    await asyncio.gather(*[_download_one(item) for item in items])
    return download_result
