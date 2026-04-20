from __future__ import annotations

import asyncio
import shutil
import subprocess
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


async def _download_file(url: str, path: Path, headers: dict[str, str] | None = None) -> int:
    """下载单个文件，返回文件大小"""
    async with httpx.AsyncClient(
        follow_redirects=True, timeout=120.0, headers=headers
    ) as client:
        async with client.stream("GET", url) as resp:
            resp.raise_for_status()
            with open(path, "wb") as f:
                async for chunk in resp.aiter_bytes(_CHUNK_SIZE):
                    f.write(chunk)
            return path.stat().st_size


async def _merge_av(video_path: Path, audio_path: Path, output_path: Path) -> None:
    """用 ffmpeg 合并视频和音频轨道"""
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-i", str(audio_path),
        "-c", "copy",
        str(output_path),
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        error_msg = stderr.decode("utf-8", errors="replace")
        raise RuntimeError(f"ffmpeg 合并失败: {error_msg[:300]}")


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

    has_dash_audio = result.video_url and result.audio_url

    # DASH 模式：分别下载视频轨和音频轨，再合并
    if has_dash_audio:
        video_item = DownloadItem(
            url=result.video_url, filename="video.mp4", path=save_dir / "video.mp4"
        )
        audio_item = DownloadItem(
            url=result.audio_url, filename="audio.m4s", path=save_dir / "audio.m4s"
        )
        merged_item = DownloadItem(
            url=result.video_url, filename="video.mp4", path=save_dir / "video_merged.mp4"
        )
        items = [video_item, audio_item]
        download_result = DownloadResult(output_dir=save_dir, items=items)

        semaphore = asyncio.Semaphore(max_concurrency)

        async def _download_one(item: DownloadItem) -> None:
            async with semaphore:
                for attempt in range(_MAX_RETRIES):
                    try:
                        item.status = "downloading"
                        if progress:
                            progress(download_result.completed, download_result.total, item)
                        item.size = await _download_file(item.url, item.path)
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

        # 合并音视频
        if video_item.status == "done" and audio_item.status == "done" and shutil.which("ffmpeg"):
            try:
                await _merge_av(video_item.path, audio_item.path, merged_item.path)
                # 用合并后的文件替换原始视频
                video_item.path.unlink(missing_ok=True)
                merged_item.path.rename(video_item.path)
                video_item.size = video_item.path.stat().st_size
            except Exception:
                # 合并失败，保留仅视频的文件
                merged_item.path.unlink(missing_ok=True)
        # 清理音频临时文件
        audio_item.path.unlink(missing_ok=True)

        # 最终只保留视频和图片
        final_items = [video_item]
        final_items.extend(_build_image_items(result, save_dir))
        download_result.items = final_items
        return download_result

    # 非 DASH 模式：直接下载
    urls: list[str] = []
    if result.video_url:
        urls.append(result.video_url)
    urls.extend(result.images)

    items: list[DownloadItem] = []
    for i, url in enumerate(urls):
        ext = get_extension(url)
        is_video = result.video_url and url == result.video_url
        if is_video and ext not in (".mp4", ".mov", ".avi", ".mkv", ".webm", ".flv"):
            ext = ".mp4"
        if is_video:
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
                    item.size = await _download_file(item.url, item.path)
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


def _build_image_items(result: ParseResult, save_dir: Path) -> list[DownloadItem]:
    """构建图片下载项"""
    items = []
    for i, url in enumerate(result.images):
        ext = get_extension(url)
        items.append(
            DownloadItem(url=url, filename=f"{i:03d}{ext}", path=save_dir / f"{i:03d}{ext}")
        )
    return items
