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

    # 只列 backend/ 真正用到的隐藏导入。PyInstaller 的静态分析能覆盖其余直接
    # import 的模块，hidden-import 只用于：
    #   * uvicorn 启动时的子模块（uvicorn 内部用 importlib 动态加载）
    #   * 顶层包名（fastapi / httpx / openai / anthropic 等），避免 PyInstaller
    #     在某些 hook 下误判找不到
    # 不要把 aiohttp / apscheduler / sqlalchemy / playwright / bs4 / lark_oapi
    # 等"为将来可能用到而防御性预留"的包加进 hidden-imports —— 它们会在打包
    # 时触发 PyInstaller 去分析对应的 hooks，进而把 torch/scipy/sklearn/pandas
    # /matplotlib/PyQt5/PySide6 这些根本不存在的依赖拽进 onefile。
        # 把 backend 里真实 import 到的所有第三方库都列进 hidden-imports。
    # PyInstaller 的静态分析对"顶层 import"很可靠，但对以下情况会丢：
    #   1) 函数内 lazy import（cron/service.py 里 apscheduler 就是这么栽的）
    #   2) try/except 包起来的可选依赖（local_playwright.py 里 playwright）
    #   3) importlib.import_module("...") 动态加载
    #   4) 通过 entry_points / metadata 注册的插件
    #
    # 这个列表是基于 backend/**/*.py 的真实 import 扫描结果维护的。
    # 新增模块时如果忘了加，PyInstaller 打包后会在 import 时报 ModuleNotFoundError。
    hidden_imports = [
        # ---- Web framework ----
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
        "pydantic",
        "pydantic_settings",
        "starlette",
        "starlette.middleware",
        "starlette.middleware.cors",
        "starlette.staticfiles",
        "python_multipart",  # fastapi 文件上传
        # ---- HTTP clients / websocket ----
        "httpx",
        "aiohttp",
        "aiohttp.client",
        "requests",
        "websockets",
        # ---- LLM providers ----
        "openai",
        "anthropic",
        # ---- DB / scheduling ----
        "aiosqlite",
        "apscheduler",
        "apscheduler.schedulers",
        "apscheduler.triggers",
        "apscheduler.jobstores",
        "apscheduler.jobstores.sqlalchemy",
        # yoyo migrations
        "yoyo",
        # ---- 渠道 / 第三方 SDK ----
        "lark_oapi",
        "slack_bolt",
        "discord",
        "telegram",
        "dingtalk_stream",
        # ---- 文档/媒体解析 ----
        "bs4",
        "docx",  # python-docx
        "openpyxl",
        "pypdf",
        "fitz",  # PyMuPDF
        "qrcode",
        "tiktoken",
        # ---- 浏览器自动化 ----
        # local_playwright.py 在 class 注解上直接引用 Page 类，import 时一旦缺失就 NameError
        "playwright",
        "playwright.async_api",
        # ---- 其他 ----
        "cryptography",
        "yaml",
        "loguru",
    ]

    for imp in hidden_imports:
        pyinstaller_args.append(f"--hidden-import={imp}")

    # 打包机可能装了 PyQt5（被 PySide6 之外的某个依赖间接引入），PyInstaller
    # 不允许同时冻结两套 Qt binding。Octopus 项目使用 PySide6，所以强制排除
    # PyQt5 相关模块。
    for qt_binding in ("PyQt5", "PyQt5.sip", "PyQt5.QtCore", "PyQt5.QtWidgets", "PyQt5.QtGui"):
        pyinstaller_args.append(f"--exclude-module={qt_binding}")

    # 进一步剔除 backend 完全不引用的重型库 —— 它们多数是被其它包的 hook
    # 当"可选依赖"探测到后强行 collect 进来的，不属于 runtime 需要。
    # 别在这里 exclude playwright/apscheduler/aiohttp/requests/bs4/lark_oapi 等
    # backend 真实用到的库（即使是函数内 lazy import）。
    for dead in (
        # 真正的 ML / 科学计算 / GUI 库，backend 0 处使用
        "torch", "torch.utils", "torch.nn",
        "scipy", "scipy.stats",
        "sklearn", "sklearn.metrics",
        "matplotlib", "matplotlib.pyplot",
        "IPython", "pygments",
        "altair",
        "pandas", "numpy",  # 真的用到再加回
        # 数据库 ORM（backend 用原生 sqlite3 + aiosqlite + yoyo，不用 SQLAlchemy ORM）
        "sqlalchemy.orm", "sqlalchemy.ext", "sqlalchemy.ext.asyncio",
        "psycopg2",  # PostgreSQL 驱动，不用
        # Google API / RPC 框架
        "grpc", "google.api_core",
        # 音频处理
        "pydub", "audioop",
        # 其他独立打包工具
        "patchright",
    ):
        pyinstaller_args.append(f"--exclude-module={dead}")

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
