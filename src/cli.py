from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

from src.core.parser import create_parser
from src.core.downloader import download_media

console = Console()


def _run(coro):
    """在事件循环中运行协程"""
    return asyncio.run(coro)


@click.command()
@click.argument("url", required=False)
@click.option("--download", "-d", is_flag=True, help="下载媒体文件")
@click.option("--output", "-o", default="output", help="输出目录")
@click.option("--transcribe", "-t", is_flag=True, help="启用语音转文字")
@click.option("--model", default="base", help="MLX-Whisper 模型 (tiny/base/small/medium/large-v3/large-v3-turbo)")
@click.option("--format", "fmt", default="text", type=click.Choice(["text", "srt", "vtt", "json"]), help="转写输出格式")
@click.option("--file", "-f", type=click.Path(exists=True), help="从文件读取链接批量处理")
def cli(url: str | None, download: bool, output: str, transcribe: bool, model: str, fmt: str, file: str | None):
    """社交媒体链接解析下载工具

    示例:
      parse-url "https://v.douyin.com/xxx"
      parse-url "https://v.douyin.com/xxx" --download
      parse-url "https://v.douyin.com/xxx" -d --transcribe
      parse-url --file links.txt -d
    """
    if not url and not file:
        click.echo("错误: 请提供链接或使用 --file 指定链接文件")
        sys.exit(1)

    urls: list[str] = []
    if file:
        urls = [line.strip() for line in Path(file).read_text().splitlines() if line.strip()]
    elif url:
        urls = [url]

    parser = create_parser()

    for i, u in enumerate(urls, 1):
        if len(urls) > 1:
            console.rule(f"[bold blue][{i}/{len(urls)}]")

        _process_one(parser, u, download, output, transcribe, model, fmt)


def _process_one(
    parser,
    url: str,
    do_download: bool,
    output: str,
    do_transcribe: bool,
    whisper_model: str,
    fmt: str,
):
    """处理单个链接"""
    # 解析
    with console.status("[bold green]正在解析链接..."):
        try:
            result = _run(parser.parse(url))
        except ValueError as exc:
            console.print(f"[bold red]解析失败: {exc}")
            return
        except Exception as exc:
            console.print(f"[bold red]解析出错: {exc}")
            return

    # 展示解析结果
    _display_result(result)

    # 下载
    if do_download:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task_id = progress.add_task("下载中", total=len(result.images) + (1 if result.video_url else 0))

            def on_progress(completed: int, total: int, item):
                progress.update(task_id, completed=completed, total=total)

            dl_result = _run(download_media(result, output_dir=output, progress=on_progress))

        _display_download_result(dl_result)

        # 语音转文字
        if do_transcribe and result.video_url:
            _do_transcribe(dl_result, whisper_model, fmt)


def _display_result(result):
    """展示解析结果"""
    table = Table(title="解析结果", show_header=False)
    table.add_column("字段", style="bold cyan")
    table.add_column("值")

    table.add_row("平台", result.platform)
    table.add_row("标题", result.title)
    table.add_row("作者", result.author)
    if result.description:
        table.add_row("描述", result.description[:200])
    table.add_row("图片数", str(len(result.images)))
    table.add_row("视频", result.video_url or "无")

    console.print(table)


def _display_download_result(dl_result):
    """展示下载结果"""
    table = Table(title="下载结果")
    table.add_column("文件名", style="cyan")
    table.add_column("大小")
    table.add_column("状态")

    for item in dl_result.items:
        status_style = "green" if item.status == "done" else "red"
        table.add_row(item.filename, item.size_display, f"[{status_style}]{item.status}")

    console.print(table)
    console.print(f"输出目录: [bold]{dl_result.output_dir}")


def _do_transcribe(dl_result, whisper_model: str, fmt: str):
    """执行语音转文字"""
    video_file = None
    for item in dl_result.items:
        if item.filename.startswith("video") and item.status == "done":
            video_file = item.path
            break

    if not video_file:
        console.print("[bold red]未找到视频文件，无法转写")
        return

    with console.status(f"[bold green]正在使用 {whisper_model} 模型进行语音转文字..."):
        from src.core.transcriber import transcribe

        try:
            transcript = _run(transcribe(str(video_file), model=whisper_model, output_format=fmt))
        except Exception as exc:
            console.print(f"[bold red]转写失败: {exc}")
            return

    # 保存转写结果
    output_path = video_file.parent / f"transcript.{fmt}"
    output_path.write_text(transcript, encoding="utf-8")

    console.print(Panel(transcript[:500] + ("..." if len(transcript) > 500 else ""), title="转写结果", border_style="green"))
    console.print(f"已保存至: [bold]{output_path}")
