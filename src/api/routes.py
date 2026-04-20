from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from src.api.errors import ErrorCode, ParseError, error_response, success_response
from src.api.schemas import (
    BatchParseRequest,
    DownloadRequest,
    ParseRequest,
    TranscribeRequest,
)
from src.core.downloader import download_media
from src.core.parser import create_parser
from src.core.transcriber import get_available_models

router = APIRouter(prefix="/api")

# ---- 任务存储 (内存) ----

_tasks: dict[str, dict[str, Any]] = {}

# ---- 平台信息 ----

_PLATFORMS = [
    {
        "id": "douyin",
        "name": "抖音",
        "domains": ["v.douyin.com", "www.douyin.com", "www.iesdouyin.com"],
        "features": ["video", "images"],
        "status": "available",
    },
    {
        "id": "bilibili",
        "name": "哔哩哔哩",
        "domains": ["b23.tv", "www.bilibili.com", "bilibili.com"],
        "features": ["video"],
        "status": "available",
    },
    {
        "id": "kuaishou",
        "name": "快手",
        "domains": ["v.kuaishou.com", "www.kuaishou.com"],
        "features": ["video", "images"],
        "status": "available",
    },
    {
        "id": "xiaohongshu",
        "name": "小红书",
        "domains": ["www.xiaohongshu.com", "xhslink.com"],
        "features": ["images", "video"],
        "status": "available",
    },
]


def _get_parser():
    return create_parser()


# ---- 接口 ----


@router.post("/parse")
async def parse(req: ParseRequest):
    """解析单个链接"""
    parser = _get_parser()
    try:
        result = await parser.parse(req.url)
    except ValueError as exc:
        return error_response(ErrorCode.INVALID_URL, str(exc))
    except Exception as exc:
        return error_response(ErrorCode.PARSE_FAILED, str(exc))

    return success_response({
        "platform": result.platform,
        "title": result.title,
        "description": result.description,
        "author": result.author,
        "author_avatar": result.author_avatar,
        "images": result.images,
        "video_url": result.video_url,
        "cover_url": result.cover_url,
    })


@router.post("/parse/batch")
async def parse_batch(req: BatchParseRequest):
    """批量解析"""
    parser = _get_parser()
    results = await parser.parse_batch(req.urls)

    batch_results = []
    for url, r in zip(req.urls, results):
        if isinstance(r, Exception):
            batch_results.append({"url": url, "success": False, "error": str(r)})
        else:
            batch_results.append({
                "url": url,
                "success": True,
                "data": {
                    "platform": r.platform,
                    "title": r.title,
                    "description": r.description,
                    "author": r.author,
                    "author_avatar": r.author_avatar,
                    "images": r.images,
                    "video_url": r.video_url,
                    "cover_url": r.cover_url,
                },
            })

    return success_response({"total": len(req.urls), "results": batch_results})


@router.post("/download")
async def download(req: DownloadRequest):
    """解析并下载（异步任务）"""
    parser = _get_parser()

    try:
        result = await parser.parse(req.url)
    except ValueError as exc:
        return error_response(ErrorCode.INVALID_URL, str(exc))
    except Exception as exc:
        return error_response(ErrorCode.PARSE_FAILED, str(exc))

    task_id = uuid.uuid4().hex[:8]
    output_dir = req.output_dir or "output"

    task_info = {
        "task_id": task_id,
        "type": "download",
        "status": "downloading",
        "parse_result": result,
        "output_dir": output_dir,
        "files": [],
        "error": None,
    }
    _tasks[task_id] = task_info

    # 后台下载
    asyncio.create_task(_run_download(task_id, result, output_dir))

    return success_response({
        "task_id": task_id,
        "status": "downloading",
        "parse_result": {
            "platform": result.platform,
            "title": result.title,
            "author": result.author,
            "images": result.images,
            "video_url": result.video_url,
        },
    })


async def _run_download(task_id: str, result, output_dir: str):
    """后台执行下载任务"""
    task = _tasks[task_id]
    try:
        dl_result = await download_media(result, output_dir=output_dir)

        files = []
        for item in dl_result.items:
            files.append({
                "name": item.filename,
                "status": item.status,
                "size": item.size_display,
                "path": str(item.path),
            })

        task["status"] = "done" if dl_result.failed == 0 else "failed"
        task["output_dir"] = str(dl_result.output_dir)
        task["files"] = files
    except Exception as exc:
        task["status"] = "failed"
        task["error"] = str(exc)


@router.post("/transcribe")
async def transcribe(req: TranscribeRequest):
    """视频语音转文字（异步任务）"""
    parser = _get_parser()

    try:
        result = await parser.parse(req.url)
    except ValueError as exc:
        return error_response(ErrorCode.INVALID_URL, str(exc))
    except Exception as exc:
        return error_response(ErrorCode.PARSE_FAILED, str(exc))

    if not result.video_url:
        return error_response(ErrorCode.TRANSCRIBE_FAILED, "该链接不包含视频")

    task_id = uuid.uuid4().hex[:8]

    task_info = {
        "task_id": task_id,
        "type": "transcribe",
        "status": "processing",
        "video_title": result.title,
        "output_dir": "output",
        "result": None,
        "error": None,
    }
    _tasks[task_id] = task_info

    # 后台转写
    asyncio.create_task(
        _run_transcribe(task_id, result, req.model, req.output_format, req.language)
    )

    return success_response({
        "task_id": task_id,
        "status": "processing",
        "video_title": result.title,
    })


async def _run_transcribe(
    task_id: str, result, model: str, output_format: str, language: str | None
):
    """后台执行转写任务"""
    task = _tasks[task_id]
    try:
        # 先下载视频
        dl_result = await download_media(result, output_dir="output")

        video_path = None
        for item in dl_result.items:
            if item.filename.startswith("video") and item.status == "done":
                video_path = str(item.path)
                break

        if not video_path:
            task["status"] = "failed"
            task["error"] = "视频下载失败"
            return

        task["output_dir"] = str(dl_result.output_dir)

        # 转写
        from src.core.transcriber import transcribe as do_transcribe

        transcript = await do_transcribe(
            video_path, model=model, output_format=output_format, language=language
        )

        # 保存转写文件
        output_path = Path(video_path).parent / f"transcript.{output_format}"
        output_path.write_text(transcript, encoding="utf-8")

        task["status"] = "done"
        task["result"] = {
            "format": output_format,
            "content": transcript,
            "output_file": str(output_path),
        }
    except Exception as exc:
        task["status"] = "failed"
        task["error"] = str(exc)


@router.get("/task/{task_id}")
async def get_task(task_id: str):
    """查询任务状态"""
    task = _tasks.get(task_id)
    if not task:
        return error_response(ErrorCode.TASK_NOT_FOUND)

    response_data = {
        "task_id": task["task_id"],
        "type": task["type"],
        "status": task["status"],
    }

    if task["type"] == "download":
        files = task.get("files", [])
        response_data["total"] = len(files)
        response_data["completed"] = sum(1 for f in files if f.get("status") == "done")
        response_data["files"] = files
        if task.get("output_dir"):
            response_data["output_dir"] = task["output_dir"]

    if task["type"] == "transcribe":
        response_data["video_title"] = task.get("video_title")
        if task.get("result"):
            response_data.update(task["result"])

    if task.get("error"):
        response_data["error"] = task["error"]

    return success_response(response_data)


@router.get("/task/{task_id}/files")
async def get_task_files(task_id: str):
    """获取下载文件列表"""
    task = _tasks.get(task_id)
    if not task:
        return error_response(ErrorCode.TASK_NOT_FOUND)

    output_dir = task.get("output_dir", "")
    files = task.get("files", [])

    file_list = []
    for f in files:
        file_list.append({
            "name": f["name"],
            "path": f.get("path", ""),
            "size": 0,
            "download_url": f"/api/task/{task_id}/files/{f['name']}",
        })

    return success_response({
        "task_id": task_id,
        "output_dir": output_dir,
        "files": file_list,
    })


@router.get("/task/{task_id}/files/{filename}")
async def download_file(task_id: str, filename: str):
    """下载单个文件"""
    from fastapi.responses import FileResponse

    task = _tasks.get(task_id)
    if not task:
        return error_response(ErrorCode.TASK_NOT_FOUND)

    # 在文件列表中查找文件路径
    for f in task.get("files", []):
        if f["name"] == filename:
            file_path = f.get("path", "")
            if file_path and Path(file_path).exists():
                return FileResponse(
                    file_path,
                    filename=filename,
                    media_type="application/octet-stream",
                )

    # 也检查转写结果文件
    if task.get("result", {}).get("output_file"):
        result_file = task["result"]["output_file"]
        if Path(result_file).name == filename and Path(result_file).exists():
            return FileResponse(
                result_file,
                filename=filename,
                media_type="application/octet-stream",
            )

    return error_response(ErrorCode.TASK_NOT_FOUND, f"文件不存在: {filename}")


@router.get("/platforms")
async def get_platforms():
    """查询支持的平台"""
    return success_response({"platforms": _PLATFORMS})


@router.get("/models")
async def get_models():
    """查询可用的 MLX-Whisper 模型"""
    try:
        models = get_available_models()
        return success_response({"models": models})
    except Exception:
        # 如果 mlx-whisper 未安装，返回静态列表
        return success_response({
            "models": [
                {"id": "tiny", "size": "150MB", "cached": False},
                {"id": "base", "size": "210MB", "cached": False},
                {"id": "small", "size": "540MB", "cached": False},
                {"id": "medium", "size": "1.5GB", "cached": False},
                {"id": "large-v3", "size": "2.9GB", "cached": False},
                {"id": "large-v3-turbo", "size": "1.5GB", "cached": False},
            ]
        })
