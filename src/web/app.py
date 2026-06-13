"""
FastAPI Web 应用
提供仪表盘页面和 REST API。
"""

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

from src.config import Config
from src.database import Database
from src.web.api import create_api_router

STATIC_DIR = Path(__file__).parent / "static"


def create_app(config: Config, db: Database) -> FastAPI:
    """创建 FastAPI 应用"""
    app = FastAPI(
        title="Model Monitor",
        description="模型 API 监控仪表盘",
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url=None,
    )

    # 注册 API 路由
    api_router = create_api_router(config, db)
    app.include_router(api_router, prefix="/api")

    # 主页
    @app.get("/", response_class=HTMLResponse)
    async def index():
        html_path = STATIC_DIR / "index.html"
        if html_path.exists():
            return HTMLResponse(content=html_path.read_text(encoding="utf-8"))
        return HTMLResponse(content="<h1>Model Monitor</h1><p>仪表盘文件未找到</p>")

    return app
