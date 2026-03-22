#!/usr/bin/env python3
"""
PyInstaller build script for packaging Python backend.
"""

import os
import sys
import shutil
from pathlib import Path
from PyInstaller.__main__ import run


def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.absolute()


def clean_dist():
    """Clean previous build artifacts."""
    project_root = get_project_root()
    dist_dir = project_root / "python-dist"
    build_dir = dist_dir / "build"

    if dist_dir.exists():
        print(f"Cleaning existing directory: {dist_dir}")
        shutil.rmtree(dist_dir)

    dist_dir.mkdir(parents=True, exist_ok=True)


def build_backend():
    """Build Python backend with PyInstaller."""
    project_root = get_project_root()

    backend_dir = project_root / "backend"
    dist_dir = project_root / "python-dist"

    pyinstaller_args = [
        str(backend_dir / "__main__.py"),
        "--name=octopus-server",
        "--onefile",
        "--console",
        f"--distpath={dist_dir}",
        f"--workpath={dist_dir / 'build'}",
        "--clean",
        "--noconfirm",
    ]

    hidden_imports = [
        "uvicorn",
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        "uvicorn.config",
        "fastapi",
        "starlette",
        "starlette.middleware",
        "starlette.middleware.cors",
        "starlette.staticfiles",
        "pydantic",
        "pydantic_settings",
        "httpx",
        "aiohttp",
        "aiohttp.client",
        "requests",
        "websockets",
        "openai",
        "anthropic",
        "apscheduler",
        "apscheduler.schedulers",
        "apscheduler.triggers",
        "sqlalchemy",
        "sqlalchemy.orm",
        "sqlalchemy.ext",
        "sqlalchemy.ext.asyncio",
        "playwright",
        "bs4",
        "lark_oapi",
        "yaml",
        "loguru",
    ]

    for imp in hidden_imports:
        pyinstaller_args.append(f"--hidden-import={imp}")

    print("=" * 60)
    print("Building Python Backend with PyInstaller")
    print("=" * 60)
    print(f"Arguments: {' '.join(pyinstaller_args)}")
    print()

    run(pyinstaller_args)


def main():
    try:
        clean_dist()
        build_backend()
        print("\n✅ Build completed successfully!")
        print(f"   Output: {get_project_root() / 'python-dist' / 'octopus-server'}")
    except Exception as e:
        print(f"\n❌ Build failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()