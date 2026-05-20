# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概览

AI 面试助手是一个全栈结构化面试练习应用：`frontend/` 是 Vue 3 + Vite + TypeScript + Element Plus 前端，`backend/` 是 FastAPI + SQLAlchemy async + SQLite 后端。后端统一在 `/api/v1` 下暴露题库、套卷、作答、历史、模型配置、提示词、语音转写和导入接口。

本地开发通常前后端分开启动；Docker 部署时前端 Nginx 托管静态资源并把 `/api` 代理到后端；Windows EXE 打包通过 `launcher.py` 启动内置 Uvicorn 服务并打开浏览器。

## 常用命令

### 后端

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Windows PowerShell 虚拟环境激活命令：

```powershell
cd backend
.\venv\Scripts\Activate.ps1
```

### 前端

```bash
cd frontend
npm install
npm run dev
npm run build
npm run preview
```

前端开发服务使用 `frontend/vite.config.ts` 中的固定端口 `3100`，并把 `/api` 代理到 `http://localhost:8000`。`npm run build` 会先运行 `vue-tsc`，再运行 `vite build`。

### Docker 部署

```bash
docker compose up -d --build
docker compose up -d
docker compose logs -f
docker compose ps
docker compose down
```

Docker 部署时前端宿主机端口是 `3100`，后端数据卷映射为 `./data:/app/data`，上传目录映射为 `./uploads:/app/uploads`。

### Windows EXE 打包

```powershell
.\scripts\build_windows_exe.ps1
```

该脚本会在 `frontend/` 下执行 `npm exec vite build`，再在仓库根目录执行 `python -m PyInstaller .\AIInterviewAssistant.spec --noconfirm --clean`，产物路径为 `dist\AIInterviewAssistant.exe`。

### 测试和 lint 状态

当前仓库没有发现已配置的后端测试框架、前端 `test` 脚本或 lint 脚本。单个测试没有既有运行命令；可用的主要校验是 `cd frontend && npm run build`，其中包含 TypeScript/Vue 类型检查。

## 高层架构

### 后端启动与路由

`backend/app/main.py` 创建 FastAPI 应用，lifespan 启动时调用 `init_db()` 和 `init_default_prompts()`。所有业务路由在这里注册到 `/api/v1`，根路径和 catch-all 路由会在 `frontend/dist/index.html` 存在时返回前端构建产物。

`backend/app/core/config.py` 使用 Pydantic Settings 读取 `.env`，并根据运行模式设置 `APP_HOME`、`DATA_DIR`、`UPLOAD_DIR`、`DATABASE_URL` 和 `FRONTEND_DIST_DIR`。非 frozen 模式默认以当前工作目录作为 `APP_HOME`；EXE 模式优先使用可写的 `app_data` 目录。

`backend/app/core/database.py` 创建 async SQLAlchemy engine/session，并在启动时通过 `Base.metadata.create_all` 建表。它还包含少量启动期 schema 补列逻辑，用于给既有 SQLite 表补充新增字段。

### 后端模块划分

- `backend/app/api/v1/routes_*.py`：HTTP API 层，负责请求解析、分页、SSE 响应和数据库会话依赖。
- `backend/app/models/`：SQLAlchemy ORM 模型，核心实体包括 `Question`、`Paper`、`PaperItem`、`Answer`、`AnalysisResult`、`PaperSession`、`ModelConfig`、`Prompt`、`SpeechConfig`、`SystemConfig` 和 `ImportTask`。
- `backend/app/schemas/`：Pydantic 请求/响应 schema。
- `backend/app/services/analyze_service.py`：读取激活的分析模型和提示词，组织单题、套卷、历史分析 prompt，并调用 AI 客户端。
- `backend/app/services/import_service.py`：读取激活的导入模型和导入提示词，把 TXT/PDF/文本内容解析为题目或套卷并写库。
- `backend/app/services/ai_client.py`：OpenAI 兼容接口封装，负责非流式 chat、流式 chat 和模型列表拉取。

### 前端结构与 API 流

`frontend/src/main.ts` 初始化 Vue、Pinia、Vue Router 和 Element Plus。`frontend/src/router/index.ts` 定义主要页面：Dashboard、单题练习、套卷练习、题库、历史和设置。

`frontend/src/api/request.ts` 是 Axios 封装，优先使用 `VITE_API_BASE_URL`，否则默认 `/api/v1`。大多数 API 模块位于 `frontend/src/api/`；单题和套卷的流式分析接口在页面中直接使用 `fetch('/api/v1/...')` 读取 SSE。

练习相关 UI 主要拆在 `frontend/src/components/practice/`，录音和计时逻辑分别在 `frontend/src/composables/useRecorder.ts` 与 `frontend/src/composables/useTimer.ts`。套卷练习状态由 `frontend/src/store/practice.ts` 管理。

### 主要业务数据流

单题练习：前端选择或创建题目，提交作答到 `/api/v1/answers`，再读取 `/api/v1/answers/{answer_id}/analysis/stream` 的 SSE。后端通过 `AnalyzeService.analyze_answer_stream()` 获取 `role="analyze"` 的激活模型和 `single_analyze` 提示词，调用 OpenAI 兼容流式接口，结束后保存分析结果。

套卷练习：前端选择或创建套卷，逐题记录答案，结束后批量创建 `Answer` 并创建 `PaperSession`，再读取 `/api/v1/answers/paper-analyze/stream/{session_id}` 的 SSE。后端汇总同一 session 下的题目、答案和时间明细，使用 `paper_analyze` 提示词生成整套分析并保存到 `PaperSession`。

题库导入：`routes_import.py` 接收 TXT/PDF/文本并创建 `ImportTask`，后台任务调用 `ImportService`。单题导入使用 `import_single` 提示词；套卷导入使用 `import_paper` 提示词，并会同时创建 `Paper`、`PaperItem` 和 `Question`。

设置页：模型配置、提示词、语音转写配置和导入字符数配置都从 `frontend/src/views/SettingsView.vue` 通过 `frontend/src/api/config.ts` 等 API 模块访问后端。模型按 `role` 区分 `analyze` 和 `import`，同一 role 下只应有一个激活配置。

### 部署与打包入口

`frontend/nginx.conf` 为 Docker 前端容器提供 SPA fallback、静态资源缓存、`/api` 反向代理，并对分析 SSE 路径关闭代理缓冲。`docker-compose.yml` 只暴露前端 `3100:80`，后端仅在 compose 网络内被前端代理访问。

`launcher.py` 是 EXE/本地桌面启动器入口：父进程从默认端口 `3100` 开始寻找可用端口，启动子进程运行 Uvicorn `app.main:app`，等待 `/health` 成功后打开浏览器。`AIInterviewAssistant.spec` 以 `launcher.py` 为 PyInstaller 入口，并在 `frontend/dist` 存在时将其打入包内的 `frontend_dist`。

## 配置文件

后端配置示例在根目录 `.env.example`，运行后端时通常复制为 `backend/.env`。常用变量包括 `DATABASE_URL`、`CORS_ORIGINS` 和 `DEBUG`。

前端配置示例在 `frontend/.env.example`。开发环境通常不需要设置 `VITE_API_BASE_URL`，因为 Vite 已代理 `/api`；当部署为跨域 API 地址时再设置完整的 `/api/v1` base URL。
