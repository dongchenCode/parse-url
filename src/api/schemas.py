from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


# ---- 请求模型 ----


class ParseRequest(BaseModel):
    url: str


class BatchParseRequest(BaseModel):
    urls: list[str] = Field(..., min_length=1, max_length=20)


class DownloadRequest(BaseModel):
    url: str
    output_dir: Optional[str] = None


class TranscribeRequest(BaseModel):
    url: str
    model: str = "base"
    output_format: str = "text"
    language: Optional[str] = "zh"


# ---- 响应模型 ----


class ParseResultData(BaseModel):
    platform: str
    title: str
    description: str
    author: str
    author_avatar: Optional[str] = None
    images: list[str] = []
    video_url: Optional[str] = None
    cover_url: Optional[str] = None


class BatchResultItem(BaseModel):
    url: str
    success: bool
    data: Optional[ParseResultData] = None
    error: Optional[str] = None


class BatchParseData(BaseModel):
    total: int
    results: list[BatchResultItem]


class FileItem(BaseModel):
    name: str
    status: str
    size: str = ""


class TaskFileItem(BaseModel):
    name: str
    path: str
    size: int
    download_url: str


class TaskData(BaseModel):
    task_id: str
    type: str  # "download" | "transcribe"
    status: str  # "pending" | "processing" | "downloading" | "done" | "failed"
    progress: Optional[str] = None
    total: Optional[int] = None
    completed: Optional[int] = None
    output_dir: Optional[str] = None
    video_title: Optional[str] = None
    files: Optional[list[FileItem]] = None
    error: Optional[str] = None


class TranscribeData(BaseModel):
    task_id: str
    video_title: Optional[str] = None
    language: Optional[str] = None
    duration: Optional[float] = None
    text: Optional[str] = None
    segments: Optional[list[dict[str, Any]]] = None
    format: Optional[str] = None
    content: Optional[str] = None


class PlatformInfo(BaseModel):
    id: str
    name: str
    domains: list[str]
    features: list[str]
    status: str = "available"


class ModelInfo(BaseModel):
    id: str
    size: str
    cached: bool


class ApiResponse(BaseModel):
    code: int = 0
    message: str = "success"
    data: Any = None
