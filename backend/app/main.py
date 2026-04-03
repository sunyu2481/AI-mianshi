from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from .core.config import settings
from .core.database import init_db
from .init_data import init_default_prompts

# 导入所有模型以确保它们被注册
from .models.question import Question
from .models.paper import Paper, PaperItem
from .models.answer import Answer
from .models.analysis import AnalysisResult
from .models.config import ModelConfig, Prompt, SpeechConfig, SystemConfig
from .models.import_task import ImportTask
from .models.paper_session import PaperSession

# 导入路由
from .api.v1.routes_questions import router as questions_router
from .api.v1.routes_papers import router as papers_router
from .api.v1.routes_answers import router as answers_router
from .api.v1.routes_models import router as models_router
from .api.v1.routes_prompts import router as prompts_router
from .api.v1.routes_history import router as history_router
from .api.v1.routes_speech import router as speech_router
from .api.v1.routes_import import router as import_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时
    await init_db()
    await init_default_prompts()
    yield
    # 关闭时
    pass


app = FastAPI(
    title=settings.APP_NAME,
    description="天津公务员省考结构化面试 AI 练习助手",
    version="1.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(questions_router, prefix="/api/v1")
app.include_router(papers_router, prefix="/api/v1")
app.include_router(answers_router, prefix="/api/v1")
app.include_router(models_router, prefix="/api/v1")
app.include_router(prompts_router, prefix="/api/v1")
app.include_router(history_router, prefix="/api/v1")
app.include_router(speech_router, prefix="/api/v1")
app.include_router(import_router, prefix="/api/v1")


def _frontend_index_file() -> Path:
    return settings.FRONTEND_DIST_DIR / "index.html"


def _frontend_ready() -> bool:
    return _frontend_index_file().exists()


def _resolve_frontend_file(relative_path: str) -> Path | None:
    if not relative_path:
        return None

    frontend_root = settings.FRONTEND_DIST_DIR.resolve()
    candidate = (frontend_root / relative_path).resolve()

    try:
        candidate.relative_to(frontend_root)
    except ValueError:
        return None

    if candidate.is_file():
        return candidate

    return None


@app.get("/")
async def root():
    if _frontend_ready():
        return FileResponse(_frontend_index_file())
    return {"message": "AI面试助手 API", "version": "1.0.0"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/{full_path:path}")
async def frontend_entry(full_path: str):
    if not _frontend_ready():
        raise HTTPException(status_code=404, detail="Frontend build files not found")

    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="API route not found")

    file_path = _resolve_frontend_file(full_path)
    if file_path is not None:
        return FileResponse(file_path)

    return FileResponse(_frontend_index_file())
