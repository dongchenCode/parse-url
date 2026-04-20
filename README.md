# Parse URL

社交媒体链接解析下载工具 — 输入抖音 / 哔哩哔哩 / 快手 / 小红书等平台的分享链接，自动解析并下载其中的图片、视频及文案信息，支持视频语音转文字。

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

## 前置条件

- Python >= 3.10
- [uv](https://docs.astral.sh/uv/)（Python 包管理工具）
- ffmpeg（语音转文字功能需要）

```bash
# 安装 uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 安装 ffmpeg
brew install ffmpeg
```

## 快速开始

```bash
# 克隆项目
git clone <repo-url>
cd parse-url

# 安装依赖
uv sync
```

### 命令行使用

```bash
# 解析单个链接（查看信息）
parse-url "https://v.douyin.com/xxx"

# 解析并下载媒体文件
parse-url "https://v.douyin.com/xxx" --download

# 下载并生成语音转文字
parse-url "https://v.douyin.com/xxx" -d --transcribe

# 指定模型和字幕格式
parse-url "https://v.douyin.com/xxx" -d --transcribe --model base --format srt

# 指定输出目录
parse-url "https://v.douyin.com/xxx" -d -o ./downloads

# 批量解析（从文件读取链接）
parse-url --file links.txt -d
```

### API 服务

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

## API 接口

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

所有接口返回统一格式：

```json
{
  "code": 0,
  "message": "success",
  "data": { ... }
}
```

详细接口文档请参见 [ParseURL.md](./ParseURL.md) 中的 API 部分。

## 技术栈

- **语言**: Python >= 3.10
- **Web 框架**: FastAPI + Uvicorn
- **HTTP 客户端**: httpx
- **HTML 解析**: BeautifulSoup4
- **语音转文字**: MLX-Whisper（Apple MLX 框架，Metal GPU 加速）
- **音视频处理**: ffmpeg
- **CLI**: click + rich
- **包管理**: uv

## 项目结构

```
parse-url/
├── pyproject.toml
├── src/
│   ├── cli.py                # CLI 入口
│   ├── server.py             # API 服务入口
│   ├── core/
│   │   ├── parser.py         # 解析调度器
│   │   ├── downloader.py     # 通用下载器
│   │   └── transcriber.py    # 语音转文字
│   ├── adapters/
│   │   ├── base.py           # 适配器基类
│   │   ├── douyin.py         # 抖音
│   │   ├── bilibili.py       # 哔哩哔哩
│   │   ├── kuaishou.py       # 快手
│   │   └── xiaohongshu.py    # 小红书
│   ├── api/
│   │   ├── routes.py         # 路由定义
│   │   ├── schemas.py        # 请求/响应模型
│   │   └── errors.py         # 异常处理
│   └── utils/
│       ├── http.py           # HTTP 请求封装
│       ├── link.py           # 链接处理工具
│       └── file.py           # 文件工具
└── output/                   # 默认下载目录
```

## 注意事项

- 本项目仅供学习交流使用，请勿用于商业用途
- 语音转文字需要 Apple Silicon（M1 及以上）以获得 Metal GPU 加速
- 部分平台可能需要配置 Cookie 才能解析完整内容
- 平台接口可能随时变更，适配器需要持续维护
- 请遵守各平台的内容使用政策

## License

MIT
