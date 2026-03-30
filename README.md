# AI 面试助手

一个面向结构化面试练习的全栈项目，支持单题练习、套题练习、题库管理、历史分析、AI 模型配置和语音转写配置。

项目当前由以下部分组成：

- `backend/`：FastAPI 后端，负责题库、练习记录、AI 调用、导入、历史分析等 API
- `frontend/`：Vue 3 + Element Plus 前端，负责练习页面、题库管理、设置页和历史记录
- `data/`：Docker 部署时挂载的 SQLite 数据目录
- `uploads/`：Docker 部署时挂载的上传目录

## 功能总览

### 首页

- 快速进入单题练习或套题练习
- 查看最近 30 天分数趋势
- 查看最近练习记录

### 单题练习

- 随机抽题
- 自定义题目后直接开始练习
- 录音作答与文本转写
- 单题 AI 流式分析
- 支持重新生成分析结果

### 套题练习

- 选择已有试卷开始练习
- 自定义试卷标题、时长和题目
- 支持分页加载试卷列表，降低首屏卡顿
- 支持多词搜索，例如 `2026 天津`
- 选择试卷后会先展示本套题题目和练习时长配置
- 套题练习支持逐题切换、总计时和单题计时
- 结束后生成整套题分析结果
- 支持删除试卷
- 删除试卷时会同步清理该试卷独占题目及相关练习数据

### 题库管理

- 题目分页浏览
- 按关键词搜索
- 按题型筛选
- 新增、查看、编辑、删除题目
- 批量删除题目
- 多选题目后直接发起套题练习
- 支持导入题库
  - 单题导入
  - 套卷导入
  - 文本导入
  - TXT / PDF 文件导入
  - 导入任务进度展示

### 历史记录

- 单题练习历史
- 套题练习历史
- 分数趋势图
- 查看单次练习详情
- 选中多条记录后进行 AI 综合分析

### 系统设置

- 分析模型配置
- 导入模型配置
- 支持从 OpenAI 兼容接口拉取可用模型列表
- 支持设置生成参数
  - `max_output_tokens`
  - `temperature`
  - `top_p`
- 语音转写方式切换
  - 浏览器语音识别
  - Whisper API
- Whisper API URL / Key / Model 配置
- 导入最大字符数配置
- 提示词管理

## 技术栈

### 后端

- FastAPI
- SQLAlchemy 2.x
- SQLite
- httpx
- OpenAI Python SDK

### 前端

- Vue 3
- Vite
- TypeScript
- Element Plus
- ECharts

### 部署

- 本地手动部署
- Docker Compose 一键部署

## 目录结构

```text
ai面试助手/
├── backend/               # FastAPI 后端
│   ├── app/
│   ├── data/              # 本地手动部署时的 SQLite 数据
│   ├── uploads/           # 本地手动部署时的上传目录
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/              # Vue 3 前端
│   ├── src/
│   ├── nginx.conf
│   ├── Dockerfile
│   └── package.json
├── data/                  # Docker 部署时映射出来的 SQLite 数据目录
├── uploads/               # Docker 部署时映射出来的上传目录
├── .env.example           # 后端环境变量示例
├── docker-compose.yml
└── README.md
```

## 方式一：本地部署

本方式适合本机开发调试，也适合不使用 Docker 的手动部署。

### 1. 环境要求

- Python 3.10+
- Node.js 20+
- npm 10+

### 2. 克隆项目

```bash
git clone https://github.com/4a5s5/AI-mianshi.git
cd AI-mianshi
```

### 3. 启动后端

进入后端目录：

```bash
cd backend
```

创建虚拟环境并激活：

```bash
python -m venv venv
```

Windows PowerShell：

```powershell
.\venv\Scripts\Activate.ps1
```

macOS / Linux：

```bash
source venv/bin/activate
```

安装依赖：

```bash
pip install -r requirements.txt
```

可选：创建后端配置文件。

后端默认即能启动。如果你需要自定义数据库路径、CORS 或调试开关，可以把根目录的 `.env.example` 复制为 `backend/.env`，然后按需修改。

默认配置示例：

```env
DATABASE_URL=sqlite+aiosqlite:///./data/interview.db
CORS_ORIGINS=*
DEBUG=False
```

启动后端：

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

启动后可访问：

- API 根地址：`http://localhost:8000`
- 健康检查：`http://localhost:8000/health`
- Swagger 文档：`http://localhost:8000/docs`

### 4. 启动前端

打开新的终端，进入前端目录：

```bash
cd frontend
```

安装依赖：

```bash
npm install
```

前端开发模式默认已经配置好了 `/api` 反向代理到 `http://localhost:8000`，本地联调通常不需要额外配置 API 地址。

直接启动：

```bash
npm run dev
```

前端默认访问地址：

- `http://localhost:3100`

### 5. 本地手动部署说明

如果你不是用于开发，而是希望手动部署到本机或服务器上，可以这样做：

先构建前端：

```bash
cd frontend
npm run build
```

构建产物在：

- `frontend/dist/`

然后你可以：

- 用 Nginx 托管 `frontend/dist`
- 将 `/api` 反向代理到后端 `8000` 端口

如果前端不是通过同域 `/api` 访问后端，而是直接访问单独的后端域名或端口，可以参考 `frontend/.env.example` 配置 `VITE_API_BASE_URL`。

如果你是部署到公网服务器，建议这里也优先使用域名并启用 HTTPS，而不是直接写服务器 IP。

## 方式二：Docker 部署

本方式适合本机快速体验或服务器一键部署。

### 1. 环境要求

- Docker
- Docker Compose Plugin

### 2. 启动服务

在项目根目录执行：

```bash
docker compose up -d --build
```

启动后访问：

- 前端：`http://localhost:3100`
- 后端 API：`http://localhost:3100/api/v1`

说明：

- 前端容器内部使用 Nginx
- Nginx 会把 `/api` 自动代理到后端容器
- 流式分析接口已经在 `frontend/nginx.conf` 中做了 SSE 相关反向代理设置

### 3. 数据持久化

Docker 部署会把数据映射到项目根目录下：

- `./data`：SQLite 数据库
- `./uploads`：上传文件

默认数据库文件为：

- `./data/interview.db`

### 4. 常用命令

启动：

```bash
docker compose up -d
```

停止：

```bash
docker compose down
```

重新构建并启动：

```bash
docker compose up -d --build
```

查看日志：

```bash
docker compose logs -f
```

查看容器状态：

```bash
docker compose ps
```

### 5. 修改端口

当前 `docker-compose.yml` 中前端默认暴露的是宿主机 `3100` 端口：

```yaml
frontend:
  ports:
    - "3100:80"
```

如果你要改成 `8080`，修改为：

```yaml
frontend:
  ports:
    - "8080:80"
```

然后重新启动：

```bash
docker compose up -d --build
```

### 6. HTTPS 建议

如果你要在公网使用，建议在 Docker 外层再加一个 Nginx / Traefik / Caddy 做 HTTPS。

原因：

- 浏览器录音能力在公网环境下通常要求 HTTPS
- HTTPS 终止交给宿主机反向代理更容易管理证书

### 7. 服务器部署时建议绑定域名

如果你把项目部署到云服务器或物理服务器上，建议通过域名访问，例如：

- `https://interview.example.com`

不建议长期直接使用：

- `http://服务器IP:3100`
- `http://服务器IP:8000`

原因：

- 浏览器麦克风能力依赖安全上下文，公网环境通常需要 `HTTPS`
- `localhost` 在本机调试时是例外，但远程服务器的 `IP:端口` 不属于这个例外
- 直接暴露后端端口也不利于统一做反向代理、证书续期和安全控制

推荐做法：

1. 给服务器绑定一个域名，并把 DNS 解析到服务器公网 IP
2. 用 Nginx / Traefik / Caddy 将域名反向代理到本项目前端端口，例如 `127.0.0.1:3100`
3. 为域名配置 HTTPS 证书，例如 Let's Encrypt
4. 最终通过域名访问前端，由前端继续走同域 `/api` 访问后端

## 首次使用配置

无论是本地部署还是 Docker 部署，首次进入系统后建议按下面顺序配置：

### 1. 进入系统设置

路径：

- `/settings`

### 2. 配置 AI 模型

至少建议配置一套：

- 作答分析模型

如果你要使用题库导入中的 AI 解析能力，还需要再配置一套：

- 题库导入模型

配置项包括：

- 配置名称
- 用途（分析 / 导入）
- API Base URL
- API Key
- 模型名称
- 生成参数

支持 OpenAI 兼容接口。

#### Groq API 获取方式

Groq 提供 OpenAI 兼容接口，可以直接接入本项目的模型配置页。

获取步骤：

1. 打开 Groq Console：`https://console.groq.com`
2. 进入 API Keys 页面：`https://console.groq.com/keys`
3. 点击 `Create API Key` 创建并复制密钥
4. 在系统设置中新增模型配置，填写：
   - `API Base URL`：`https://api.groq.com/openai/v1`
   - `API Key`：你刚创建的 Groq API Key
   - `模型名称`：填写 Groq 支持的模型，或先保存后使用页面里的“获取模型”功能拉取

如果你要分别用于作答分析和题库导入，建议各建一套模型配置，方便单独启停和调参。

### 3. 配置语音转写

支持两种方式：

- `web_speech`
- `whisper`

建议：

- 中国大陆环境优先使用 `Whisper API`
- 浏览器语音识别依赖浏览器和网络环境，不够稳定

### 4. 开始导入题库或直接练习

你可以：

- 在题库管理页手动新增题目
- 导入单题 / 套卷
- 直接进入单题练习
- 直接进入套题练习

## 配置说明

### 后端配置

后端读取 `backend/.env`。

常用变量：

| 变量名 | 说明 | 默认值 |
| --- | --- | --- |
| `DATABASE_URL` | 数据库连接串 | `sqlite+aiosqlite:///./data/interview.db` |
| `CORS_ORIGINS` | CORS 来源 | `*` |
| `DEBUG` | 是否开启调试模式 | `True` / 示例文件中为 `False` |

### 前端配置

开发模式默认通过 Vite 代理 `/api` 到 `http://localhost:8000`，见：

- `frontend/vite.config.ts`

如果你需要前端直接请求其他 API 地址，可在前端目录创建环境文件并配置：

```env
VITE_API_BASE_URL=https://api.your-domain.com/api/v1
```

参考：

- `frontend/.env.example`

## 常见问题

### 1. 本地前端端口是多少？

当前开发端口是：

- `3100`

不是 Vite 默认的 `5173`。

### 2. 录音为什么在某些环境下不能用？

常见原因：

- 浏览器未授权麦克风
- 公网环境未启用 HTTPS
- 使用远程服务器时直接通过 `IP:端口` 访问，页面不在安全上下文内
- 使用了 `web_speech`，但当前网络环境无法正常访问其依赖服务

如果你部署在服务器上，建议绑定域名并启用 HTTPS，再通过域名访问前端页面。

### 3. Docker 部署后前端为什么能直接请求 `/api`？

因为前端镜像内置了 Nginx，已经把 `/api` 代理到后端容器。

### 4. 数据库文件在哪？

本地手动部署：

- `backend/data/interview.db`

Docker 部署：

- `data/interview.db`

### 5. 首次启动会自动初始化什么？

后端首次启动时会自动：

- 创建数据库表
- 创建缺失字段
- 初始化默认提示词

## 开发补充

### 前端常用命令

```bash
cd frontend
npm run dev
npm exec vite build
```

### 后端常用命令

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## License

仅供学习、练习和内部部署参考。
