import os
import sys
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


APP_ENV_PREFIX = "AI_INTERVIEW"


def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _bundle_root() -> Path:
    if _is_frozen():
        return Path(getattr(sys, "_MEIPASS"))
    return _project_root()


def _ensure_writable_dir(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def _default_app_home() -> Path:
    configured = os.getenv(f"{APP_ENV_PREFIX}_HOME")
    if configured:
        return Path(configured).expanduser().resolve()

    if _is_frozen():
        exe_dir = Path(sys.executable).resolve().parent
        portable_home = exe_dir / "app_data"
        if _ensure_writable_dir(portable_home):
            return portable_home

        local_appdata = os.getenv("LOCALAPPDATA")
        fallback_root = Path(local_appdata) if local_appdata else Path.home() / "AppData" / "Local"
        fallback_home = fallback_root / "AIInterviewAssistant"
        if _ensure_writable_dir(fallback_home):
            return fallback_home

        return portable_home

    return Path.cwd()


def _default_frontend_dist_dir() -> Path:
    if _is_frozen():
        return _bundle_root() / "frontend_dist"
    return _project_root() / "frontend" / "dist"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "AI面试助手"
    DEBUG: bool = False
    APP_HOME: Path = _default_app_home()
    DATA_DIR: Path | None = None
    UPLOAD_DIR: Path | None = None
    FRONTEND_DIST_DIR: Path = _default_frontend_dist_dir()
    DATABASE_URL: str | None = None
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB
    CORS_ORIGINS: list[str] = ["*"]
    DEFAULT_PORT: int = 3100

    @model_validator(mode="after")
    def apply_runtime_defaults(self) -> "Settings":
        if self.DATA_DIR is None:
            self.DATA_DIR = self.APP_HOME / "data"

        if self.UPLOAD_DIR is None:
            self.UPLOAD_DIR = self.APP_HOME / "uploads"

        if self.DATABASE_URL is None:
            db_path = (self.DATA_DIR / "interview.db").resolve()
            self.DATABASE_URL = f"sqlite+aiosqlite:///{db_path.as_posix()}"

        return self


settings = Settings()

settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
