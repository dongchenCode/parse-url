from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

_MODEL_SIZES = {
    "tiny": "150MB",
    "base": "210MB",
    "small": "540MB",
    "medium": "1.5GB",
    "large-v3": "2.9GB",
    "large-v3-turbo": "1.5GB",
}


@dataclass
class Segment:
    """转写片段"""

    start: float
    end: float
    text: str


@dataclass
class TranscribeResult:
    """转写结果"""

    text: str
    segments: list[Segment]
    language: str
    duration: float


def check_ffmpeg() -> bool:
    """检查 ffmpeg 是否已安装"""
    return shutil.which("ffmpeg") is not None


async def extract_audio(video_path: str, output_path: str | None = None) -> str:
    """使用 ffmpeg 从视频中提取音轨为 16kHz WAV"""
    if not check_ffmpeg():
        raise RuntimeError("ffmpeg 未安装，请先执行: brew install ffmpeg")

    video = Path(video_path)
    if not video.exists():
        raise FileNotFoundError(f"视频文件不存在: {video_path}")

    if output_path is None:
        output_path = str(video.with_suffix(".wav"))

    cmd = [
        "ffmpeg",
        "-i", str(video),
        "-vn",  # 不包含视频
        "-acodec", "pcm_s16le",  # 16-bit PCM
        "-ar", "16000",  # 16kHz 采样率
        "-ac", "1",  # 单声道
        "-y",  # 覆盖输出
        output_path,
    ]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        error_msg = stderr.decode("utf-8", errors="replace")
        raise RuntimeError(f"ffmpeg 音频提取失败: {error_msg[:500]}")

    return output_path


def _load_model(model: str):
    """加载 MLX-Whisper 模型"""
    try:
        import mlx_whisper
    except ImportError:
        raise RuntimeError(
            "mlx-whisper 未安装，请执行: uv add mlx-whisper\n"
            "注意: MLX-Whisper 需要 Apple Silicon (M1+) 才能使用 Metal GPU 加速"
        )
    return mlx_whisper


async def transcribe(
    video_path: str,
    model: str = "base",
    output_format: str = "text",
    language: Optional[str] = "zh",
) -> str:
    """
    对视频文件进行语音转写

    Args:
        video_path: 视频文件路径
        model: MLX-Whisper 模型名
        output_format: 输出格式 (text/srt/vtt/json)
        language: 语言提示 (zh/en/ja 等，None 则自动检测)

    Returns:
        转写结果字符串
    """
    # 1. 提取音频
    audio_path = await extract_audio(video_path)

    try:
        # 2. MLX-Whisper 推理 (在线程中运行以避免阻塞事件循环)
        result = await asyncio.to_thread(_run_whisper, audio_path, model, language)
    finally:
        # 清理临时音频文件
        Path(audio_path).unlink(missing_ok=True)

    # 3. 格式化输出
    return format_output(result, output_format)


def _run_whisper(audio_path: str, model: str, language: Optional[str]) -> dict:
    """同步执行 Whisper 推理"""
    mlx_whisper = _load_model(model)

    model_path = f"mlx-community/whisper-{model}"

    result = mlx_whisper.transcribe(
        audio_path,
        path_or_hf_repo=model_path,
        language=language,
        word_timestamps=True,
    )
    return result


def format_output(result: dict, output_format: str) -> str:
    """将 Whisper 结果格式化为指定格式"""
    segments = result.get("segments", [])
    text = result.get("text", "").strip()

    if output_format == "text":
        return text

    if output_format == "srt":
        return _format_srt(segments)

    if output_format == "vtt":
        return _format_vtt(segments)

    if output_format == "json":
        return _format_json(result)

    return text


def _format_srt(segments: list[dict]) -> str:
    """生成 SRT 字幕格式"""
    lines: list[str] = []
    for i, seg in enumerate(segments, 1):
        start = _format_timestamp_srt(seg["start"])
        end = _format_timestamp_srt(seg["end"])
        lines.append(f"{i}")
        lines.append(f"{start} --> {end}")
        lines.append(seg["text"].strip())
        lines.append("")
    return "\n".join(lines)


def _format_vtt(segments: list[dict]) -> str:
    """生成 WebVTT 格式"""
    lines = ["WEBVTT", ""]
    for seg in segments:
        start = _format_timestamp_vtt(seg["start"])
        end = _format_timestamp_vtt(seg["end"])
        lines.append(f"{start} --> {end}")
        lines.append(seg["text"].strip())
        lines.append("")
    return "\n".join(lines)


def _format_json(result: dict) -> str:
    """生成 JSON 格式"""
    output = {
        "text": result.get("text", "").strip(),
        "language": result.get("language", ""),
        "segments": [
            {
                "start": seg["start"],
                "end": seg["end"],
                "text": seg["text"].strip(),
            }
            for seg in result.get("segments", [])
        ],
    }
    return json.dumps(output, ensure_ascii=False, indent=2)


def _format_timestamp_srt(seconds: float) -> str:
    """格式化为 SRT 时间戳: HH:MM:SS,mmm"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _format_timestamp_vtt(seconds: float) -> str:
    """格式化为 VTT 时间戳: HH:MM:SS.mmm"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def get_available_models() -> list[dict]:
    """查询可用的 MLX-Whisper 模型列表"""
    models = []
    cache_dir = Path.home() / ".cache" / "huggingface" / "hub"

    for model_id, size in _MODEL_SIZES.items():
        repo_name = f"models--mlx-community--whisper-{model_id}"
        cached = (cache_dir / repo_name).exists() if cache_dir.exists() else False
        models.append({
            "id": model_id,
            "size": size,
            "cached": cached,
        })
    return models
