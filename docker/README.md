# Astock Docker 部署

所有 Compose 与镜像定义集中在 **`docker/`** 目录。在仓库根目录执行 Compose 时，请使用 `-f docker/docker-compose.yml` 与 `--env-file docker/.env`（或先 `cd docker` 再 `--env-file .env`）。

## 运行时架构

本编排包含三个服务：**`redis`**（缓存）、**`backend`**（FastAPI + Gunicorn/Uvicorn Worker）、**`frontend`**（Vue3 + Arco 构建产物 + Nginx）。

| 组件 | 说明 |
|------|------|
| Redis | `redis:7-alpine`，持久化卷 `redis_data`；不可用时后端自动降级直连数据源 |
| 后端 | 镜像由 `docker/Dockerfile.backend` 构建；SQLite 挂载至 `SQLITE_HOST_DIR`；启动时 `init_db()` 自动建表（**生产环境可直接替换为预置好的 `astock.db`**） |
| 前端 | 镜像由 `docker/Dockerfile.frontend` 构建：`pnpm build` + Nginx 监听 **8080** |

**前后端分工**：业务 SPA 仅存在于 **frontend** 镜像；axios 基址写死为同源 `/api/v1`，Nginx 将 `/api` 反代至 `backend:8000`。改前端后须 `build frontend`，仅重建 backend **不会**更新页面。

**构建上下文（`build.context`）为仓库根目录**（`docker-compose.yml` 中为 `..`）。仓库根 **`.dockerignore`** 在构建时生效。

## 目录说明

| 文件 | 作用 |
|------|------|
| `docker-compose.yml` | 编排 `redis`、`backend`、`frontend` |
| `Dockerfile.backend` | Python 依赖 + Gunicorn，无前端构建 |
| `Dockerfile.frontend` | pnpm 构建 + Nginx 托管 SPA 并反代 `/api` |
| `gunicorn.docker.conf.py` | 容器内 Gunicorn：`bind 0.0.0.0:8000`，`timeout` 默认 300s |
| `nginx.conf` | 前端容器内监听 **8080**；`/api` 反代至 `http://backend:8000` |
| `.env.example` | 环境变量模板，复制为 `docker/.env` 后按需修改 |
| `sqlite-data/` | SQLite 持久化目录（挂载至容器 `/app/data`） |

## 端口与映射

| 服务 | 容器内端口 | 默认宿主机映射 |
|------|------------|----------------|
| frontend（nginx） | 8080 | `FRONTEND_PUBLISH_PORT`（默认 **8082**） |
| backend（Gunicorn） | 8000 | `BACKEND_PUBLISH_PORT`（默认 **8002**） |
| redis | 6379 | **不映射**（仅容器网络） |

## 与 stockManager / carSales 同机部署

三项目各自独立 Compose 栈，通过 **`COMPOSE_PROJECT_NAME`** 与 **宿主机端口** 隔离，**不共享 Docker 网络**。

| 项目 | COMPOSE_PROJECT_NAME | 前端宿主机端口 | 后端宿主机端口 |
|------|----------------------|----------------|----------------|
| stockManager | `stockmanager` | 8080 | 8000 |
| carSales | `carsales` | 8081 | 8001 |
| **Astock** | **`astock`** | **8082** | **8002** |

同机部署时 **勿删** `COMPOSE_PROJECT_NAME=astock`，否则后启动的栈可能顶替先启动栈的 `backend`/`frontend` 容器。

对外 HTTPS 由 **tencentDocker** 边缘 Nginx 按子域名分流至各项目前端端口（Astock 默认 `host.docker.internal:8082` → `astock.zhangzhicheng.info`）。

## 前置条件

- 已安装 [Docker](https://docs.docker.com/get-docker/) 与 [Docker Compose V2](https://docs.docker.com/compose/)

## 配置

1. 复制环境变量文件：

   ```bash
   cp docker/.env.example docker/.env
   ```

2. 编辑 `docker/.env`，至少修改：

   - **`COMPOSE_PROJECT_NAME`**：默认 `astock`（同机部署时勿删）
   - **`VITE_ADMIN_REFRESH_PASSWORD`**：页面「刷新全部数据」二次确认码（构建时写入前端，**务必改成非默认值**）
   - 若端口冲突，调整 **`FRONTEND_PUBLISH_PORT`** / **`BACKEND_PUBLISH_PORT`**

3. SQLite 数据文件默认位于 `docker/sqlite-data/astock.db`。首次启动会创建空库；**已有数据的库文件可直接拷贝到该目录覆盖**，无需迁移脚本。

## 启动与停止

在**仓库根目录**执行：

```bash
docker compose -f docker/docker-compose.yml --env-file docker/.env build
docker compose -f docker/docker-compose.yml --env-file docker/.env up -d
```

或在 `docker/` 目录下：

```bash
cd docker
docker compose --env-file .env build
docker compose --env-file .env up -d
```

停止并删除容器（保留数据卷与 SQLite 文件）：

```bash
docker compose -f docker/docker-compose.yml --env-file docker/.env down
```

## 更新代码后重新部署

```bash
git pull
docker compose -f docker/docker-compose.yml --env-file docker/.env build
docker compose -f docker/docker-compose.yml --env-file docker/.env up -d
```

仅改了前端或后端时：

```bash
docker compose -f docker/docker-compose.yml --env-file docker/.env build backend frontend
docker compose -f docker/docker-compose.yml --env-file docker/.env up -d
```

修改 `VITE_ADMIN_REFRESH_PASSWORD` 后须 **重建 frontend** 镜像。

## 数据初始化

1. 启动栈后访问前端页面，或通过 Swagger 调用管理接口。
2. 首次使用需执行数据导入（耗时较长，个股阶段最久）：
   - **推荐**：页面右上角「刷新全部数据」→ 输入 `VITE_ADMIN_REFRESH_PASSWORD` → SSE 四阶段进度弹窗（`POST /api/v1/admin/data/import/stream`）
   ```bash
   curl -N -X POST http://127.0.0.1:8002/api/v1/admin/data/import/stream?dataset=all
   ```

3. 导入完成后各业务页会自动 reload 数据；OpenAPI 文档：`http://127.0.0.1:8002/docs`（或通过前端同源 `/api` 访问）。

## 自检

```bash
# 前端静态页
curl -fsS -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8082/

# 后端健康（元数据接口）
curl -fsS http://127.0.0.1:8002/api/v1/admin/data/sync-status
```

## 常见问题

| 症状 | 处理 |
|------|------|
| 改了前端页面线上没变化 | `docker compose build frontend && docker compose up -d frontend` |
| 数据导入超时 | 优先用页面 SSE 流式刷新或 `/data/import/stream`；仍超时则增大 `GUNICORN_TIMEOUT` 后重建 backend |
| 与 carSales/stockManager 端口冲突 | 修改 `FRONTEND_PUBLISH_PORT` / `BACKEND_PUBLISH_PORT`，并同步更新 tencentDocker 的 `ASTOCK_FRONTEND_UPSTREAM` |
| SQLite 需重置 | 停止栈后替换或删除 `docker/sqlite-data/astock.db`，再 `up -d`（会丢数据；也可从本机拷贝预置库） |

## 接入 tencentDocker 边缘网关

1. 确保本栈前端映射至 **8082**（默认已配置）。
2. 在 `tencentDocker/docker/` 配置 `ASTOCK_FRONTEND_UPSTREAM=host.docker.internal:8082`。
3. 放置 `astock.zhangzhicheng.info` TLS 证书至 `tencentDocker/docker/ssl/astock.zhangzhicheng.info/`。
4. DNS 添加 A 记录后重启 edge-nginx：`docker compose --env-file .env up -d --force-recreate edge-nginx`。
5. 浏览器访问 `https://astock.zhangzhicheng.info`。

详见 `tencentDocker/docs/deploy-guide.md`。
