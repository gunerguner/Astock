"""Astock FastAPI 服务启动入口。"""

from astock.config import FASTAPI_PORT

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("astock.main:app", host="0.0.0.0", port=FASTAPI_PORT, reload=True)
