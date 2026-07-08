from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from astock.config import (
    APP_TITLE,
    APP_VERSION,
    CORS_HEADERS,
    CORS_METHODS,
    CORS_ORIGINS,
    FASTAPI_PORT,
    HOST,
)
from astock.core.database import init_db
from astock.core.exception_handlers import register_exception_handlers
from astock.core.logging_config import setup_logging
from astock.routers import admin, analysis

setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title=APP_TITLE, version=APP_VERSION, lifespan=lifespan)

allow_credentials = "*" not in CORS_ORIGINS
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=allow_credentials,
    allow_methods=CORS_METHODS,
    allow_headers=CORS_HEADERS,
)

app.include_router(admin.router)
app.include_router(analysis.router)
register_exception_handlers(app)

if __name__ == "__main__":
    # 本地开发启动入口；生产环境使用 gunicorn astock.main:app
    uvicorn.run("astock.main:app", host=HOST, port=FASTAPI_PORT, reload=True)
