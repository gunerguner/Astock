from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from astock.config import CORS_ORIGINS, FASTAPI_PORT
from astock.core.database import init_db
from astock.core.exception_handlers import register_exception_handlers
from astock.core.logging_config import setup_logging
from astock.routers import admin, analysis

setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Astock 数据平台", version="1.0.0", lifespan=lifespan)

allow_credentials = "*" not in CORS_ORIGINS
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(admin.router)
app.include_router(analysis.router)
register_exception_handlers(app)

if __name__ == "__main__":
    # 本地开发启动入口；生产环境使用 gunicorn astock.main:app
    uvicorn.run("astock.main:app", host="0.0.0.0", port=FASTAPI_PORT, reload=True)
