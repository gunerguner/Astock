# Astock 自动化回归测试

统一入口:仓库根 `make test`(等价于先后端后前端全量跑一遍)。

## 测试位置约定(硬性)

| 端 | 框架 | 唯一允许的位置 | 禁止 |
|----|------|----------------|------|
| 后端 | pytest(venv: `backend/.venv`) | `backend/tests/`(api/ = HTTP 集成,unit/ = 纯计算) | 任何 `astock/**/test_*.py`、`conftest.py` 进业务包 |
| 前端 | vitest + happy-dom | `frontend/tests/`(目录镜像 `src/`:utils/、api/、hooks/…) | 任何 `src/**/*.test.ts`、`__tests__/` 进业务模块 |

## 常用命令

```bash
make test            # 前后端全量(首选回归命令)
make test-backend    # 仅后端 pytest
make test-frontend   # 仅前端 vitest run
make test-cov        # 带覆盖率(不设门槛,仅出报告)
make check           # test + 前端 lint/type:check
```

单独跑(绕过 make):

```bash
cd backend && .venv/bin/python -m pytest tests/ -v
cd frontend && pnpm test          # vitest run
cd frontend && pnpm test:watch    # watch 模式
```

## 改动范围 → 必跑命令

| 改动 | 命令 |
|------|------|
| `backend/astock/**`(路由/服务/模型/配置/导入) | `make test-backend` |
| `frontend/src/**` | `make test-frontend` |
| 前后端都动 / API 契约(字段、信封、枚举) | `make test` |
| 只动 `backend/tests/` 或 `frontend/tests/` | 对应单端命令 |
| 纯文档 / 注释 / `.agents/` | 可跳过 |
| 提交前 / AI 改完收工 | `make test` |

## 测试基建约定(改 conftest/vitest.config 前必读)

- **隔离**:后端测试用内存 SQLite(`StaticPool` + `dependency_overrides[get_db]`),
  `conftest.py` 在 import astock 前设置 `DB_PATH/LOG_DIR` 环境变量(config.py 在
  import 时固化常量);TestClient 不进入 `with` 上下文,不触发 lifespan。
  任何测试不得触碰 `backend/db/astock.db`。
- **零出网**:providers/datasets(baostock、akshare、BLS、FRED、东财、新浪)一律
  monkeypatch;`redis_gateway` 是绑定引用,必须逐使用方模块 patch
  (conftest 的 autouse `fake_redis` 已覆盖,新增使用方须同步登记)。
- **契约断言**:API 测试统一断言 `{code, message, data}` 信封;错误场景断言
  `ErrorCode`(1001 校验/1003 不存在/2001 外部源/3001 数据库/9000 内部)。
- **前端**:纯函数/组合式函数优先;`@/locale`、`@/api/request`、`@arco-design/web-vue`
  的 Message 均在测试内 mock;SSE 用 `streamPost` + stub fetch 测帧解析。
- **状态泄漏**:内存库跨测试共享连接,`db_session` fixture 已在测试后清表;
  新 fixture 若落库须挂到该 fixture 之下。

## 明确不测(依赖外网/时钟/耗时)

- baostock / akshare / BLS / FRED / 东财 / 新浪真实网络调用
- Redis TTL 真实过期、`import/stream?dataset=all` 全量真实导入耗时
- 「今日是否已过宏观刷新日」「最近结算日」等时钟相关断言
  (涉及 `last_settled_date` 的用例用区间外/兜底值断言,不锚定今天)

## 新增功能的测试义务

- 新增/修改 API:补 `tests/api/` 用例(成功信封 + 至少一个错误信封),
  前端新增接口函数补 `tests/api/` URL/参数构造断言
- 新增服务层计算逻辑:补 `tests/unit/`
- 修复 bug:先补一个能复现的回归用例再修
