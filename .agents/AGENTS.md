# AGENTS 约定(Astock 仓库)

本文件面向在本仓库工作的 AI 编码助手,与 `.agents/skills/astock/` 一起生效。
完整测试方案见 [`.agents/skills/astock/references/testing.md`](./skills/astock/references/testing.md)。

## 完成标准

- 改动 `backend/astock/**`、`frontend/src/**` 或任一 `tests/` 目录后,**必须真正执行**
  对应测试命令(见下表),不能只提示用户去跑;失败则修到全绿再收工。
- 前后端都改动、或动了 API 契约(字段/信封/枚举/阶段定义)时,必须 `make test` 全量。
- 纯文档、注释、`.agents/` 改动可跳过。
- 新增功能必须随代码补测试;修 bug 先补能复现的回归用例。

## 改动范围 → 命令

| 改动 | 命令 |
|------|------|
| `backend/astock/**` | `make test-backend` |
| `frontend/src/**` | `make test-frontend` |
| 前后端都动 / API 契约 | `make test` |
| 提交前 | `make test` |

## 测试位置(硬性约束)

- 后端测试只允许放 `backend/tests/`(api/、unit/),禁止写进 `astock/` 包内。
- 前端测试只允许放 `frontend/tests/`(镜像 `src/` 结构),禁止写进 `src/` 模块内。
