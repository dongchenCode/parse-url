# Parse URL

社交媒体链接解析下载工具 — 输入抖音 / 哔哩哔哩 / 快手 / 小红书等平台的分享链接，自动解析并下载其中的图片、视频及文案信息，支持视频语音转文字。

## 支持平台

| 平台 | 分享链接格式 | 解析内容 |
|------|-------------|---------|
| 抖音 | `https://v.douyin.com/xxx` | 视频 / 图文笔记 |
| 哔哩哔哩 | `https://b23.tv/xxx` 或 `https://www.bilibili.com/video/BVxxx` | 视频 |
| 快手 | `https://v.kuaishou.com/xxx` | 视频 / 图集 |
| 小红书 | `https://www.xiaohongshu.com/discovery/item/xxx` | 图文笔记 / 视频 |

## 安装

```bash
# 前置条件：Python >= 3.10, uv, ffmpeg（语音转文字需要）
brew install ffmpeg
curl -LsSf https://astral.sh/uv/install.sh | sh

# 克隆并安装依赖
git clone <repo-url> && cd parse-url
uv sync
```

## 使用

### 命令行

```bash
# 解析链接（查看信息）
parse-url "https://v.douyin.com/xxx"

# 解析并下载
parse-url "https://v.douyin.com/xxx" --download

# 下载并语音转文字
parse-url "https://v.douyin.com/xxx" -d --transcribe

# 指定模型和输出格式
parse-url "https://v.douyin.com/xxx" -d --transcribe --model base --format srt

# 批量解析（从文件读取链接）
parse-url --file links.txt -d
```

### API 服务

```bash
uv run uvicorn src.server:app --reload --port 8000
```

启动后访问 `http://localhost:8000/docs` 查看交互式 API 文档。

## API 概览

所有接口返回统一格式 `{"code": 0, "message": "success", "data": {...}}`。

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/parse` | 解析单个链接 |
| POST | `/api/parse/batch` | 批量解析（最多 20 条） |
| POST | `/api/download` | 解析并下载（异步） |
| POST | `/api/transcribe` | 视频语音转文字（异步） |
| GET | `/api/task/{task_id}` | 查询任务状态 |
| GET | `/api/task/{task_id}/files` | 获取文件列表 |
| GET | `/api/task/{task_id}/files/{filename}` | 下载单个文件 |
| GET | `/api/platforms` | 查询支持的平台 |
| GET | `/api/models` | 查询可用的语音模型 |

### 错误码

| 错误码 | 含义 |
|-------|------|
| 0 | 成功 |
| 40001 | 链接格式无效 |
| 40002 | 平台暂不支持 |
| 40003 | 解析失败 |
| 40004 | 语音转写失败 |
| 40401 | 任务不存在 |
| 50001 | 服务内部错误 |

## 语音转文字模型

| 模型 | 内存占用 | 速度 | 适用场景 |
|------|---------|------|---------|
| `tiny` | ~150MB | 最快 | 快速预览 |
| `base` | ~210MB | 快 | 日常使用（默认） |
| `small` | ~540MB | 中等 | 精度与速度平衡 |
| `medium` | ~1.5GB | 慢 | 高精度需求 |
| `large-v3` | ~2.9GB | 最慢 | 最高精度 |
| `large-v3-turbo` | ~1.5GB | 较快 | 大模型精度 + 更快速度 |

> 首次使用时模型会自动从 HuggingFace 下载，需要 Apple Silicon (M1+) 以获得 Metal GPU 加速。

## 项目结构

```
src/
├── cli.py                 # CLI 入口（click + rich）
├── server.py              # FastAPI 服务入口
├── core/
│   ├── parser.py          # 解析调度器
│   ├── downloader.py      # 通用下载器（支持 DASH 音视频合并）
│   └── transcriber.py     # 语音转文字（ffmpeg + MLX-Whisper）
├── adapters/
│   ├── base.py            # 适配器基类（ParseResult + BaseAdapter）
│   ├── douyin.py          # 抖音
│   ├── bilibili.py        # 哔哩哔哩
│   ├── kuaishou.py        # 快手
│   └── xiaohongshu.py     # 小红书
├── api/
│   ├── routes.py          # 路由定义
│   ├── schemas.py         # 请求/响应模型
│   └── errors.py          # 异常处理
└── utils/
    ├── http.py             # HTTP 客户端封装（重试、UA）
    ├── link.py             # 链接处理（短链解析、平台识别）
    └── file.py             # 文件工具（命名、去重）
```

## 注意事项

- 仅供学习交流使用，请勿用于商业用途
- 部分平台可能需要配置 Cookie 才能解析完整内容
- 平台接口可能随时变更，适配器需要持续维护
- 请遵守各平台的内容使用政策

## License

MIT
