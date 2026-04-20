# Parse URL - 开发计划

> 将 ParseURL.md 中的设计拆解为可逐步执行的开发任务清单。
> 每个任务粒度为"一个可独立完成、可测试的交付单元"。

---

## Phase 1: 项目初始化与基础框架

### 1.1 初始化项目结构
- [ ] 创建 `pyproject.toml`（依赖：fastapi, uvicorn, httpx, beautifulsoup4, click, rich, mlx-whisper, pydantic）
- [ ] 创建目录结构：`src/`, `src/core/`, `src/adapters/`, `src/api/`, `src/utils/`, `output/`
- [ ] 创建所有 `__init__.py` 文件
- [ ] 运行 `uv sync` 确认依赖安装成功

### 1.2 实现数据模型与基类
- [ ] 在 `src/adapters/base.py` 中定义 `ParseResult` dataclass
  - 字段：platform, title, description, author, author_avatar, images, video_url, cover_url
- [ ] 在 `src/adapters/base.py` 中定义 `BaseAdapter` 抽象基类
  - `match(url: str) -> bool` 静态方法
  - `async parse(url: str) -> ParseResult` 抽象方法

### 1.3 实现工具模块
- [ ] `src/utils/http.py`：HTTP 请求封装
  - 使用 httpx.AsyncClient 封装 GET/POST
  - 统一 User-Agent、Cookie 管理
  - 支持跟随重定向
  - 超时与重试机制
- [ ] `src/utils/link.py`：链接处理
  - `extract_urls(text: str) -> list[str]`：从文本中提取 URL
  - `follow_redirect(url: str) -> str`：跟随短链获取真实 URL
  - `identify_platform(url: str) -> str | None`：根据域名识别平台
- [ ] `src/utils/file.py`：文件工具
  - 安全文件名生成（去除特殊字符）
  - 文件去重（基于 URL hash）
  - 目录自动创建
  - 文件大小格式化

### 1.4 实现核心调度器
- [ ] `src/core/parser.py`：解析调度器
  - 注册所有适配器
  - 根据平台自动分发到对应适配器
  - 批量解析支持（asyncio.gather + Semaphore 并发控制）
- [ ] `src/core/downloader.py`：通用下载器
  - 支持图片/视频批量下载
  - 并发下载（asyncio.Semaphore 控制并发数）
  - 单文件重试（失败最多重试 3 次）
  - 进度回调（供 CLI 和 API 使用）
  - 返回下载结果（文件路径、大小、状态）

### 1.5 实现 CLI 入口
- [ ] `src/cli.py`：命令行工具（click）
  - `parse-url <url>` 基本解析命令
  - `--download / -d` 下载媒体文件
  - `--output / -o` 指定输出目录
  - `--transcribe` 启用语音转文字
  - `--model` 指定 MLX-Whisper 模型（默认 base）
  - `--format` 指定转写输出格式（text/srt/vtt/json）
  - `--file / -f` 从文件读取链接批量处理
- [ ] 集成 rich：进度条、表格输出、语法高亮
- [ ] 在 `pyproject.toml` 中注册 `parse-url` 命令入口

---

## Phase 2: 平台适配器（按优先级排序）

### 2.1 抖音适配器
- [ ] `src/adapters/douyin.py`
  - 实现 `match()`：匹配 `v.douyin.com`, `www.douyin.com`, `www.iesdouyin.com`
  - 实现 `parse()`：
    - 跟随短链获取真实 URL
    - 提取视频无水印 URL
    - 提取图文笔记的图片列表
    - 提取标题、描述、作者信息
  - 测试用例：视频链接、图文笔记链接

### 2.2 小红书适配器
- [ ] `src/adapters/xiaohongshu.py`
  - 实现 `match()`：匹配 `www.xiaohongshu.com`, `xhslink.com`
  - 实现 `parse()`：
    - 提取图集无水印图片 URL 列表
    - 提取视频 URL
    - 提取标题、描述、作者信息
  - 测试用例：图文笔记、视频笔记

### 2.3 哔哩哔哩适配器
- [ ] `src/adapters/bilibili.py`
  - 实现 `match()`：匹配 `b23.tv`, `www.bilibili.com`, `bilibili.com`
  - 实现 `parse()`：
    - 跟随短链获取真实 URL
    - 提取视频流 URL
    - 提取标题、描述、UP 主信息
  - 测试用例：BV 号链接、短链

### 2.4 快手适配器
- [ ] `src/adapters/kuaishou.py`
  - 实现 `match()`：匹配 `v.kuaishou.com`, `www.kuaishou.com`
  - 实现 `parse()`：
    - 提取视频 URL
    - 提取图集 URL 列表
    - 提取标题、描述、作者信息
  - 测试用例：视频链接、图集链接

### 2.5 适配器注册与集成测试
- [ ] 在 `parser.py` 中注册所有适配器
- [ ] 编写集成测试：各平台链接 → 解析 → 下载 全流程验证

---

## Phase 3: 语音转文字

### 3.1 ffmpeg 音轨提取
- [ ] `src/core/transcriber.py`：ffmpeg 封装
  - 检查 ffmpeg 是否安装
  - 从视频文件提取音轨为 16kHz WAV
  - 使用 subprocess 异步调用 ffmpeg

### 3.2 MLX-Whisper 推理
- [ ] 模型加载与推理
  - 支持模型：tiny, base, small, medium, large-v3, large-v3-turbo
  - 模型自动下载（首次使用时从 HuggingFace 缓存）
  - 语言提示支持（zh, en, ja 等，支持自动检测）
  - 利用 Apple Silicon Metal GPU 加速

### 3.3 多格式输出
- [ ] 纯文本输出（segments 合并）
- [ ] SRT 字幕格式（带时间戳）
- [ ] VTT (WebVTT) 格式
- [ ] JSON 结构化格式（含 segments 时间戳）
- [ ] 输出文件保存到下载目录

### 3.4 模型管理
- [ ] 查询本地已缓存模型列表
- [ ] 查询模型大小信息
- [ ] 模型状态 API

---

## Phase 4: RESTful API 服务

### 4.1 FastAPI 应用基础
- [ ] `src/server.py`：创建 FastAPI app
- [ ] CORS 中间件配置
- [ ] 统一响应格式封装（code, message, data）
- [ ] `src/api/schemas.py`：Pydantic 请求/响应模型
- [ ] `src/api/errors.py`：统一异常处理与错误码定义

### 4.2 路由实现
- [ ] `POST /api/parse`：解析单个链接
- [ ] `POST /api/parse/batch`：批量解析（最多 20 条）
- [ ] `POST /api/download`：解析并下载（异步任务）
- [ ] `POST /api/transcribe`：视频语音转文字（异步任务）
- [ ] `GET /api/task/{task_id}`：查询任务状态与进度
- [ ] `GET /api/task/{task_id}/files`：获取文件列表
- [ ] `GET /api/task/{task_id}/files/{filename}`：下载单个文件
- [ ] `GET /api/platforms`：查询支持的平台
- [ ] `GET /api/models`：查询可用的 MLX-Whisper 模型

### 4.3 异步任务管理
- [ ] 内存任务队列（dict 存储 task_id → TaskInfo）
- [ ] 后台任务执行（asyncio.create_task）
- [ ] 任务进度追踪（下载进度、转写进度）
- [ ] 任务状态管理（pending → processing → done / failed）

---

## Phase 5: 体验优化

### 5.1 进度展示
- [ ] CLI：rich 进度条（单文件下载进度 + 总体进度）
- [ ] API：任务进度字段（percentage / completed / total）

### 5.2 Cookie 配置
- [ ] 支持从文件加载 Cookie（JSON 格式）
- [ ] 支持通过环境变量传入 Cookie
- [ ] CLI 参数 `--cookie` 指定 Cookie 文件路径

### 5.3 错误处理与重试
- [ ] 网络请求自动重试（指数退避）
- [ ] 友好错误提示（中文描述 + 建议操作）
- [ ] 适配器解析失败时的降级处理

### 5.4 API 限流
- [ ] 基于 IP 的请求频率限制（slowapi 或自实现）
- [ ] 可配置的限流参数

---

## 开发顺序建议

```
1.1 → 1.2 → 1.3 → 1.4 → 1.5  （基础框架，约 1-2 天）
          ↓
   2.1 → 2.2 → 2.3 → 2.4 → 2.5  （平台适配器，每个约半天）
          ↓
          3.1 → 3.2 → 3.3 → 3.4  （语音转文字，约 1 天）
          ↓
          4.1 → 4.2 → 4.3  （API 服务，约 1-2 天）
          ↓
          5.1 → 5.2 → 5.3 → 5.4  （体验优化，约 1 天）
```

每个步骤完成后都应可以独立运行和测试，不依赖后续步骤。
