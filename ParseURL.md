# Parse URL - 社交媒体链接解析下载工具

输入抖音 / 哔哩哔哩 / 快手 / 小红书等平台的分享链接，自动解析并下载其中的图片、视频及文案信息，支持视频语音转文字。

## 支持平台

| 平台 | 分享链接格式 | 解析内容 |
|------|-------------|---------|
| 抖音 | `https://v.douyin.com/xxx` | 视频 / 图文笔记 |
| 哔哩哔哩 | `https://b23.tv/xxx` 或 `https://www.bilibili.com/video/BVxxx` | 视频 |
| 快手 | `https://v.kuaishou.com/xxx` | 视频 / 图集 |
| 小红书 | `https://www.xiaohongshu.com/discovery/item/xxx` | 图文笔记 / 视频 |

## 功能特性

- 粘贴分享链接，自动识别平台并解析
- 提取标题、作者、描述等文案信息
- 下载无水印图片（小红书图集、抖音图文等）
- 下载视频文件（抖音、快手、B站等）
- 视频语音转文字（基于 MLX-Whisper，Apple Silicon Metal 加速）
- 支持批量解析（多个链接一次处理）
- 提供命令行工具 & RESTful API 服务

## 技术栈

- **语言**: Python >= 3.10
- **Web 框架**: FastAPI + Uvicorn
- **HTTP 客户端**: httpx（支持异步）
- **HTML 解析**: BeautifulSoup4
- **语音转文字**: MLX-Whisper（基于 Apple MLX 框架，Metal GPU 加速，本地运行）
- **音视频处理**: ffmpeg（提取音频供 MLX-Whisper 识别）
- **CLI 框架**: click
- **CLI 美化**: rich（进度条、表格、高亮输出）
- **并发控制**: asyncio + asyncio.Semaphore
- **包管理**: uv

## 项目结构

```
parse-url/
├── README.md
├── pyproject.toml
├── src/
│   ├── __init__.py
│   ├── cli.py                # CLI 入口（click）
│   ├── server.py             # API 服务入口（FastAPI app）
│   ├── core/
│   │   ├── __init__.py
│   │   ├── parser.py         # 解析调度器：识别平台 → 分发到对应适配器
│   │   ├── downloader.py     # 通用下载器：图片/视频批量下载、重试、进度
│   │   └── transcriber.py    # 语音转文字：ffmpeg 提取音频 → MLX-Whisper 识别
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── base.py           # 适配器基类（定义统一接口）
│   │   ├── douyin.py         # 抖音适配器
│   │   ├── bilibili.py       # 哔哩哔哩适配器
│   │   ├── kuaishou.py       # 快手适配器
│   │   └── xiaohongshu.py    # 小红书适配器
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes.py         # 路由定义
│   │   ├── schemas.py        # 请求/响应模型（Pydantic）
│   │   └── errors.py         # 统一异常处理
│   └── utils/
│       ├── __init__.py
│       ├── http.py           # HTTP 请求封装（UA、Cookie、重定向跟随）
│       ├── link.py           # 链接处理：提取短链、解析重定向、识别平台
│       └── file.py           # 文件工具：命名、去重、目录创建
└── output/                   # 默认下载目录
```

## 核心流程

```
用户输入分享链接
       │
       ▼
  链接预处理（提取 URL、跟随重定向获取真实链接）
       │
       ▼
  识别平台（根据域名匹配对应适配器）
       │
       ▼
  平台适配器解析
  ┌──────────────────────────────────┐
  │ 1. 请求页面 / API 获取数据       │
  │ 2. 提取结构化信息：              │
  │    - 标题、描述、作者            │
  │    - 图片 URL 列表（无水印）     │
  │    - 视频 URL                   │
  │ 3. 返回解析结果                  │
  └──────────────────────────────────┘
       │
       ▼
  下载媒体文件到本地
       │
       ▼（若为视频且需要转写）
  ffmpeg 提取音轨 → MLX-Whisper 语音识别 → 输出文字 / 字幕
```

## 适配器接口设计

每个平台适配器继承基类，实现统一接口：

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class ParseResult:
    platform: str          # 'douyin' | 'bilibili' | 'kuaishou' | 'xiaohongshu'
    title: str
    description: str
    author: str
    images: list[str]      # 图片 URL 列表
    video_url: Optional[str] = None  # 视频 URL（无则为 None）


class BaseAdapter:
    """适配器基类"""

    @staticmethod
    def match(url: str) -> bool:
        """检查链接是否匹配该平台"""
        ...

    async def parse(self, url: str) -> ParseResult:
        """解析链接，返回结构化内容"""
        ...
```

## 语音转文字模块

转写流程由 `transcriber.py` 统一处理，不侵入适配器逻辑：

```
视频文件（本地）
     │
     ▼
ffmpeg 提取音轨 → 16kHz WAV
     │
     ▼
MLX-Whisper 模型推理（Metal GPU 加速）
     │
     ▼
输出结果：
  - 纯文本（全段合并）
  - 带时间戳的字幕（SRT / VTT 格式）
```

**支持的 MLX-Whisper 模型**

| 模型 | 参数量 | 内存占用 | 速度 | 适用场景 |
|------|-------|---------|------|---------|
| `tiny` | 39M | ~150MB | 最快 | 快速预览，精度一般 |
| `base` | 74M | ~210MB | 快 | 日常使用（默认） |
| `small` | 244M | ~540MB | 中等 | 精度与速度平衡 |
| `medium` | 769M | ~1.5GB | 慢 | 高精度需求 |
| `large-v3` | 1550M | ~2.9GB | 最慢 | 最高精度 |
| `large-v3-turbo` | 809M | ~1.5GB | 较快 | 大模型精度 + 更快速度 |

> 首次使用时模型会自动从 HuggingFace 下载到本地缓存，后续直接加载。

---

## RESTful API 文档

### 启动服务

```bash
# 开发模式（热重载）
uv run uvicorn src.server:app --reload --port 8000

# 生产模式
uv run uvicorn src.server:app --host 0.0.0.0 --port 8000 --workers 4
```

启动后访问：
- API 服务: `http://localhost:8000`
- 交互式文档 (Swagger): `http://localhost:8000/docs`
- 备用文档 (ReDoc): `http://localhost:8000/redoc`

### 统一响应格式

所有接口遵循统一的 JSON 响应结构：

**成功响应**

```json
{
  "code": 0,
  "message": "success",
  "data": { ... }
}
```

**错误响应**

```json
{
  "code": 40001,
  "message": "无法识别的链接格式",
  "data": null
}
```

**错误码一览**

| 错误码 | 含义 |
|-------|------|
| `0` | 成功 |
| `40001` | 链接格式无效 / 无法识别平台 |
| `40002` | 平台暂不支持 |
| `40003` | 解析失败（平台接口变更或页面不可访问） |
| `40004` | 语音转写失败（ffmpeg 未安装 / 视频无音轨 / MLX-Whisper 推理异常） |
| `40401` | 任务不存在 |
| `50001` | 服务内部错误 |

---

### 接口列表

#### 1. 解析链接

解析分享链接，返回结构化内容信息（图片/视频 URL、标题、作者等），不触发下载。

```
POST /api/parse
```

**请求体**

```json
{
  "url": "https://v.douyin.com/iRNBho5m/"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `url` | string | 是 | 社交媒体分享链接（支持短链） |

**响应示例**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "platform": "douyin",
    "title": "春日露营Vlog",
    "description": "周末和朋友去了山里露营...",
    "author": "小明同学",
    "author_avatar": "https://example.com/avatar.jpg",
    "images": [
      "https://example.com/img1.jpg",
      "https://example.com/img2.jpg"
    ],
    "video_url": null,
    "cover_url": "https://example.com/cover.jpg"
  }
}
```

---

#### 2. 批量解析

一次提交多个链接，逐个解析并返回结果列表。

```
POST /api/parse/batch
```

**请求体**

```json
{
  "urls": [
    "https://v.douyin.com/iRNBho5m/",
    "https://www.xiaohongshu.com/discovery/item/67da1b2e00000000"
  ]
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `urls` | string[] | 是 | 分享链接列表（最多 20 条） |

**响应示例**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "total": 2,
    "results": [
      {
        "url": "https://v.douyin.com/iRNBho5m/",
        "success": true,
        "data": {
          "platform": "douyin",
          "title": "春日露营Vlog",
          "description": "周末和朋友去了山里露营...",
          "author": "小明同学",
          "images": [],
          "video_url": "https://example.com/video.mp4"
        }
      },
      {
        "url": "https://www.xiaohongshu.com/discovery/item/67da1b2e00000000",
        "success": false,
        "error": "解析失败：页面不可访问"
      }
    ]
  }
}
```

---

#### 3. 解析并下载

解析链接后立即下载所有媒体文件到服务器本地，返回下载任务 ID，可通过轮询查询进度。

```
POST /api/download
```

**请求体**

```json
{
  "url": "https://v.douyin.com/iRNBho5m/",
  "output_dir": "downloads/custom"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `url` | string | 是 | 分享链接 |
| `output_dir` | string | 否 | 自定义下载目录（默认 `output/`） |

**响应示例**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "task_id": "a1b2c3d4",
    "status": "downloading",
    "parse_result": {
      "platform": "douyin",
      "title": "春日露营Vlog",
      "author": "小明同学",
      "images": [],
      "video_url": "https://example.com/video.mp4"
    }
  }
}
```

---

#### 4. 视频语音转文字

对视频内容进行语音识别，返回文字转写结果。支持纯文本和带时间戳字幕两种输出格式。

```
POST /api/transcribe
```

**请求体**

```json
{
  "url": "https://v.douyin.com/iRNBho5m/",
  "model": "base",
  "output_format": "text",
  "language": "zh"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `url` | string | 是 | 含视频的分享链接 |
| `model` | string | 否 | MLX-Whisper 模型：`tiny` / `base` / `small` / `medium` / `large-v3` / `large-v3-turbo`（默认 `base`） |
| `output_format` | string | 否 | 输出格式：`text`（纯文本）/ `srt`（字幕）/ `vtt`（WebVTT）/ `json`（结构化）（默认 `text`） |
| `language` | string | 否 | 语言提示：`zh` / `en` / `ja` 等，传 `null` 则自动检测（默认 `zh`） |

**响应示例 - 纯文本**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "task_id": "e5f6g7h8",
    "video_title": "春日露营Vlog",
    "language": "zh",
    "duration": 125.6,
    "text": "大家好，欢迎来到我的频道。今天想和大家分享一下我们周末去露营的经历。我们选了一个离市区大概两个小时车程的地方，风景特别好。",
    "segments": [
      {
        "start": 0.0,
        "end": 3.5,
        "text": "大家好，欢迎来到我的频道。"
      },
      {
        "start": 3.5,
        "end": 12.8,
        "text": "今天想和大家分享一下我们周末去露营的经历。"
      },
      {
        "start": 12.8,
        "end": 25.0,
        "text": "我们选了一个离市区大概两个小时车程的地方，风景特别好。"
      }
    ]
  }
}
```

**响应示例 - SRT 字幕格式**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "task_id": "e5f6g7h8",
    "video_title": "春日露营Vlog",
    "language": "zh",
    "duration": 125.6,
    "format": "srt",
    "content": "1\n00:00:00,000 --> 00:00:03,500\n大家好，欢迎来到我的频道。\n\n2\n00:00:03,500 --> 00:00:12,800\n今天想和大家分享一下我们周末去露营的经历。\n\n3\n00:00:12,800 --> 00:00:25,000\n我们选了一个离市区大概两个小时车程的地方，风景特别好。"
  }
}
```

> 视频较长时转写耗时较久，接口会异步处理并返回 `task_id`，通过 `GET /api/task/{task_id}` 轮询结果。

---

#### 5. 查询任务状态

根据任务 ID 查询下载 / 转写任务的进度和结果。

```
GET /api/task/{task_id}
```

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| `task_id` | string | 任务 ID（下载或转写任务） |

**响应示例 - 转写进行中**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "task_id": "e5f6g7h8",
    "type": "transcribe",
    "status": "processing",
    "progress": "45%",
    "video_title": "春日露营Vlog"
  }
}
```

**响应示例 - 下载进行中**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "task_id": "a1b2c3d4",
    "type": "download",
    "status": "downloading",
    "total": 4,
    "completed": 2,
    "files": [
      { "name": "img1.jpg", "status": "done", "size": "1.2MB" },
      { "name": "img2.jpg", "status": "done", "size": "980KB" },
      { "name": "video.mp4", "status": "downloading", "progress": "67%" },
      { "name": "img3.jpg", "status": "pending" }
    ]
  }
}
```

**响应示例 - 已完成**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "task_id": "a1b2c3d4",
    "type": "download",
    "status": "done",
    "total": 3,
    "completed": 3,
    "output_dir": "output/douyin/春日露营Vlog",
    "files": [
      { "name": "img1.jpg", "status": "done", "size": "1.2MB" },
      { "name": "img2.jpg", "status": "done", "size": "980KB" },
      { "name": "video.mp4", "status": "done", "size": "25.6MB" }
    ]
  }
}
```

---

#### 6. 获取下载文件列表

查询已完成的下载任务的所有文件。

```
GET /api/task/{task_id}/files
```

**响应示例**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "task_id": "a1b2c3d4",
    "output_dir": "output/douyin/春日露营Vlog",
    "files": [
      {
        "name": "img1.jpg",
        "path": "output/douyin/春日露营Vlog/img1.jpg",
        "size": 1258291,
        "download_url": "/api/task/a1b2c3d4/files/img1.jpg"
      },
      {
        "name": "video.mp4",
        "path": "output/douyin/春日露营Vlog/video.mp4",
        "size": 26843545,
        "download_url": "/api/task/a1b2c3d4/files/video.mp4"
      },
      {
        "name": "transcript.srt",
        "path": "output/douyin/春日露营Vlog/transcript.srt",
        "size": 5823,
        "download_url": "/api/task/a1b2c3d4/files/transcript.srt"
      }
    ]
  }
}
```

---

#### 7. 下载单个文件

获取任务中的某个具体文件（直接返回文件流）。

```
GET /api/task/{task_id}/files/{filename}
```

**响应**: 文件二进制流（`Content-Type` 根据文件类型自动设置）

---

#### 8. 查询支持的平台

返回当前支持的所有平台及其状态。

```
GET /api/platforms
```

**响应示例**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "platforms": [
      {
        "id": "douyin",
        "name": "抖音",
        "domains": ["v.douyin.com", "www.douyin.com", "www.iesdouyin.com"],
        "features": ["video", "images"],
        "status": "available"
      },
      {
        "id": "bilibili",
        "name": "哔哩哔哩",
        "domains": ["b23.tv", "www.bilibili.com", "bilibili.com"],
        "features": ["video"],
        "status": "available"
      },
      {
        "id": "kuaishou",
        "name": "快手",
        "domains": ["v.kuaishou.com", "www.kuaishou.com"],
        "features": ["video", "images"],
        "status": "available"
      },
      {
        "id": "xiaohongshu",
        "name": "小红书",
        "domains": ["www.xiaohongshu.com", "xhslink.com"],
        "features": ["images", "video"],
        "status": "available"
      }
    ]
  }
}
```

---

#### 9. 查询可用的 MLX-Whisper 模型

返回本地已缓存和可用的 MLX-Whisper 模型列表。

```
GET /api/models
```

**响应示例**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "models": [
      { "id": "tiny", "size": "150MB", "cached": true },
      { "id": "base", "size": "210MB", "cached": true },
      { "id": "small", "size": "540MB", "cached": false },
      { "id": "medium", "size": "1.5GB", "cached": false },
      { "id": "large-v3", "size": "2.9GB", "cached": false },
      { "id": "large-v3-turbo", "size": "1.5GB", "cached": false }
    ]
  }
}
```

---

## 使用方式

> 本项目使用 [uv](https://docs.astral.sh/uv/) 管理 Python 环境和依赖，无需手动安装 Python。

### 前置条件

```bash
# 安装 uv（如未安装）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 安装 ffmpeg
brew install ffmpeg
```

### 初始化项目

```bash
# 克隆项目后，一键创建虚拟环境并安装依赖
uv sync
```

### 命令行使用

```bash
# 解析单个链接
parse-url "https://v.douyin.com/xxx"

# 解析并下载
parse-url "https://v.douyin.com/xxx" --download

# 下载并生成语音转文字
parse-url "https://v.douyin.com/xxx" -d --transcribe

# 指定 MLX-Whisper 模型和输出格式
parse-url "https://v.douyin.com/xxx" -d --transcribe --model base --format srt

# 指定输出目录
parse-url "https://v.douyin.com/xxx" -d -o ./downloads

# 批量解析（从文件读取链接）
parse-url --file links.txt -d
```

### API 服务

```bash
# 启动开发服务（热重载）
uv run uvicorn src.server:app --reload

# 启动生产服务
uv run uvicorn src.server:app --host 0.0.0.0 --port 8000 --workers 4
```

## 实施计划

### Phase 1 - 基础框架搭建

- [ ] 初始化项目：pyproject.toml、目录结构
- [ ] 实现 ParseResult 数据类和 BaseAdapter 基类
- [ ] 实现工具模块（http、link、file）
- [ ] 实现解析调度器和下载器
- [ ] 实现 CLI 入口（click）

### Phase 2 - 平台适配器（按优先级排序）

- [ ] 抖音适配器（视频 + 图文）
- [ ] 小红书适配器（图集 + 视频）
- [ ] 哔哩哔哩适配器（视频）
- [ ] 快手适配器（视频 + 图集）

### Phase 3 - 语音转文字

- [ ] ffmpeg 音轨提取封装
- [ ] MLX-Whisper 模型加载与推理（Metal GPU 加速）
- [ ] 多格式输出（text / srt / vtt / json）
- [ ] 模型管理（查询已缓存模型）

### Phase 4 - API 服务

- [ ] FastAPI 应用搭建、CORS 配置
- [ ] 请求/响应模型定义（Pydantic schemas）
- [ ] 路由实现：解析、批量解析、下载、转写、任务查询
- [ ] 统一异常处理
- [ ] 异步任务管理（内存任务队列）

### Phase 5 - 体验优化

- [ ] 下载进度条展示（CLI: rich / API: 轮询进度）
- [ ] Cookie 配置支持（部分平台需要登录态）
- [ ] 错误重试与友好提示
- [ ] API 访问频率限制

## 注意事项

- 本项目仅供学习交流使用，请勿用于商业用途
- 语音转文字功能依赖 **ffmpeg** 和 **MLX-Whisper**：
  - ffmpeg: `brew install ffmpeg`
  - MLX-Whisper 模型首次使用时自动从 HuggingFace 下载，`large-v3` 约 2.9GB
  - 需要 Apple Silicon（M1 及以上）以获得 Metal GPU 加速
- 部分平台可能需要配置 Cookie 才能解析完整内容
- 平台接口可能随时变更，适配器需要持续维护
- 请遵守各平台的内容使用政策

## License

MIT
