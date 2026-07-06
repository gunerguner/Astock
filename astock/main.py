from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from astock.config import FASTAPI_PORT
from astock.core.exception_handlers import register_exception_handlers
from astock.core.logging_config import setup_logging

setup_logging()

from astock.core.database import init_db
from astock.routers import admin


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Astock 数据平台", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(admin.router)
register_exception_handlers(app)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("astock.main:app", host="0.0.0.0", port=FASTAPI_PORT, reload=True)
