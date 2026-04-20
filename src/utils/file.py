from __future__ import annotations

import hashlib
import re
import unicodedata
from pathlib import Path


def safe_filename(name: str, max_length: int = 200) -> str:
    """生成安全文件名，去除特殊字符"""
    # Unicode 归一化
    name = unicodedata.normalize("NFKC", name)
    # 移除控制字符
    name = re.sub(r"[\x00-\x1f\x7f]", "", name)
    # 替换不安全字符为下划线
    name = re.sub(r'[\\/*?:"<>|]', "_", name)
    # 压缩连续空格和下划线
    name = re.sub(r"[\s_]+", "_", name).strip("_")
    # 截断
    if len(name) > max_length:
        name = name[:max_length]
    return name or "unnamed"


def url_hash(url: str) -> str:
    """基于 URL 生成哈希值，用于文件去重"""
    return hashlib.md5(url.encode()).hexdigest()[:12]


def ensure_dir(path: Path) -> Path:
    """确保目录存在，不存在则创建"""
    path.mkdir(parents=True, exist_ok=True)
    return path


def format_size(size_bytes: int | float) -> str:
    """将字节数格式化为人类可读的大小"""
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(size_bytes)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(size)}{unit}"
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}{units[-1]}"


def get_extension(url: str) -> str:
    """从 URL 中提取文件扩展名"""
    # 去除查询参数和片段
    path = url.split("?")[0].split("#")[0]
    ext = Path(path).suffix.lower()
    if ext in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"):
        return ext
    if ext in (".mp4", ".mov", ".avi", ".mkv", ".webm"):
        return ext
    return ".jpg"  # 默认扩展名
