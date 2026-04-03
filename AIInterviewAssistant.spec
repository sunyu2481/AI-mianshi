# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata


project_root = Path(SPECPATH).resolve()
frontend_dist = project_root / "frontend" / "dist"

datas = collect_data_files("certifi")
datas += copy_metadata("openai")

if frontend_dist.exists():
    datas.append((str(frontend_dist), "frontend_dist"))

hiddenimports: list[str] = []
for package_name in ("uvicorn", "aiosqlite", "openai", "httpx", "h11"):
    hiddenimports.extend(collect_submodules(package_name))

hiddenimports = sorted(set(hiddenimports))


a = Analysis(
    [str(project_root / "launcher.py")],
    pathex=[str(project_root / "backend")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="AIInterviewAssistant",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
