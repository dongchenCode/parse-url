from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.errors import ParseError, error_response, parse_error_handler
from src.api.routes import router

app = FastAPI(
    title="Parse URL",
    description="社交媒体链接解析下载工具 — 输入抖音/哔哩哔哩/快手/小红书等平台的分享链接，自动解析并下载",
    version="0.1.0",
)

# CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(router)


# 全局异常处理
@app.exception_handler(ParseError)
async def _parse_error_handler(request, exc):
    return await parse_error_handler(request, exc)


@app.exception_handler(Exception)
async def _general_error_handler(request, exc):
    return error_response(50001, f"服务内部错误: {exc}")


@app.get("/")
async def root():
    return {"code": 0, "message": "Parse URL API is running", "docs": "/docs"}
