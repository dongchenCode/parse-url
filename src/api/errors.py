from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse


# 错误码定义
class ErrorCode:
    SUCCESS = 0
    INVALID_URL = 40001
    PLATFORM_UNSUPPORTED = 40002
    PARSE_FAILED = 40003
    TRANSCRIBE_FAILED = 40004
    TASK_NOT_FOUND = 40401
    INTERNAL_ERROR = 50001


_ERROR_MESSAGES = {
    ErrorCode.INVALID_URL: "无法识别的链接格式",
    ErrorCode.PLATFORM_UNSUPPORTED: "平台暂不支持",
    ErrorCode.PARSE_FAILED: "解析失败",
    ErrorCode.TRANSCRIBE_FAILED: "语音转写失败",
    ErrorCode.TASK_NOT_FOUND: "任务不存在",
    ErrorCode.INTERNAL_ERROR: "服务内部错误",
}


def error_response(
    code: int,
    message: str | None = None,
    data: Any = None,
) -> JSONResponse:
    """生成统一错误响应"""
    msg = message or _ERROR_MESSAGES.get(code, "未知错误")
    return JSONResponse(
        status_code=200,
        content={"code": code, "message": msg, "data": data},
    )


def success_response(data: Any = None, message: str = "success") -> JSONResponse:
    """生成统一成功响应"""
    return JSONResponse(
        status_code=200,
        content={"code": 0, "message": message, "data": data},
    )


class ParseError(Exception):
    """解析异常"""

    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


async def parse_error_handler(request: Request, exc: ParseError) -> JSONResponse:
    """全局解析异常处理"""
    return error_response(exc.code, exc.message)
