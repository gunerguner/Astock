---
name: code-style
description: Astock 仓库的代码风格规范，约束重复代码、现代语言用法、简练优雅、文件/函数规模与测试代码质量。在编写、修改或评审 backend/astock、frontend/src 及任一 tests/ 目录时遵循。
---

# 代码风格规范

在 Astock 仓库内写代码时遵循以下规范。仓库架构与分层约定见 [astock skill](../astock/SKILL.md)；本文件只管"代码长什么样"。

## 1. 不重复、不冗余

- **单一实现**：同一逻辑只允许存在一份。写新功能前先搜项目里是否已有等价实现（后端 `core/`、`services/`；前端 `utils/`、`hooks/`、`components/`），有则直接复用或小改扩展，不要复制粘贴后再改。
- **相似代码超过 3 处才抽象**；2 处相似允许重复，宁要两段直白代码也不要一个牵强的抽象。
- **不留临时代码**：调试用 `print` / `console.log`、注释掉的旧代码、`TODO`/`FIXME` 残留、只为"先跑通"的绕路逻辑，提交前必须清掉或转成正式实现。
- **不留死代码**：未被引用的函数、类型、常量、路由、CSS 一并删除；"以后可能用"不是保留理由，需要时从 git 历史找回。
- **不加无用防御**：不为"不可能发生"的情况写分支；信任项目内的类型契约与调用约定。

## 2. 现代语言风格

**Python（后端 3.12+）**

- f-string 格式化；`pathlib.Path` 而非 `os.path`；`dict`/`set` 字面量与推导式。
- 类型注解完整（函数签名必写，Pydantic/SQLModel 字段自带）；用 `X | None` 而非 `Optional[X]`。
- 优先 dataclass / Pydantic model 而非裸 dict 传递结构化数据；返回 `TypedDict` 时须有明确形状。
- `match` 适合分支分派时用；`enumerate`/`zip` 优于手动下标；`functools.cache`/`lru_cache` 处理纯函数缓存。
- 上下文管理器（`with`）管理资源；不用裸 `except:`，异常要具体。
- **数据处理优先用内置聚合，而不是手写循环累加**：
  - 聚合用 `sum()`/`max()`/`min()`/`any()`/`all()`/`len()`，配 `key=` 排序取极值：`max(rows, key=lambda r: r.turnover)`，不要手写 `best = None; if x > best...`。
  - 归并/分组用 `functools.reduce`、`itertools.groupby`（先 `sorted` 再 group）、`collections.Counter`/`defaultdict`，如 `Counter(r.code for r in rows).most_common(n)` 代替手动 dict 计数。
  - 一对多展开用嵌套推导式或 `itertools.chain.from_iterable`，不写双重循环 append。
  - 生成器表达式惰性求值，传给聚合函数时省去中间列表：`sum(r.amount for r in rows if r.active)`。
  - 排序统一 `sorted(key=...)`，不用 `cmp`；多级排序用元组 key。

**TypeScript / Vue3（前端）**

- `const` 优先、箭头函数、模板字符串、可选链 `?.` 与空值合并 `??`；`async/await` 而非 `.then` 链。
- 类型从使用处推导，避免冗余显式标注；导出接口优先 `interface`，联合字面量类型优于 `enum`。
- 组件一律 `<script setup lang="ts">` + Composition API；可复用逻辑抽成 `hooks/use-*.ts`。
- 不用 `any`；确需逃逸时用 `unknown` + 收窄。不写 `!` 非空断言，除非紧邻的代码已证明非空。
- **数组/集合处理用高阶函数链，而不是命令式循环**：
  - 变换过滤用 `map`/`filter`/`flatMap`（代替 `map` + `flat`）；查找判断用 `find`/`some`/`every`/`includes`，不要用 `filter(...)[0]`。
  - 多对一聚合（分组、求和、建索引）用 `reduce`，或更直白的 `Object.groupBy`/`Map.groupBy`；累加数字优先 `reduce((a, b) => a + b, 0)` 以外的具名意图（如 `sum` 小工具函数），避免 reduce 里塞复杂逻辑。
  - 构建 key→value 映射用 `Object.fromEntries(items.map(...))` / `new Map(items.map(...))`，不要手写 for 循环往对象里塞。
  - 去重用 `new Set` + 展开或 `[...new Set(xs)]`；不可变更新用 `toSorted`/`toReversed`/`with`/`at`，不直接 mutate 入参。
  - `computed` 内保持纯函数式的数据管道（filter → map → sort），副作用（发请求、改 ref）不混进管道中间步骤。

**通用**

- 使用语言/生态当前的主流写法，不用上一代惯例（如 Python 的 `%` 格式化、`typing.List`；JS 的 `var`、`function` 回调）。
- 升级依赖带来的新 API 优先采用，但一次改动内保持风格统一。

## 3. 简练、优雅

- **先想清楚再写**：能用一段直白代码解决的，不引入设计模式、基类、回调参数或配置项。
- **禁止过度设计（YAGNI）**：不为"以后可能"预留参数、钩子、泛型化；抽象只服务当前需求。
- **早返回（early return）**：先处理边界与错误，主逻辑不留缩进金字塔；嵌套不超过 2–3 层。
- **声明式优于命令式**：让数据"变形"（map/filter/推导式/SQL 聚合）而不是手动循环拼装，除非有性能理由。
- **命名表意**：名字说清"是什么/做什么"，避免 `data2`、`handleClick1`、`tmp`、`flag` 这类名字；函数名用动词，布尔用 `is_/has_/should_` 或 `isXxx`。
- **注释只写"为什么"**：代码已表达的"做什么"不重复注释；解释业务背景、坑、外部数据源行为的注释才值得留。
- **删比加好**：修改时优先考虑能否删掉代码达到目的；一行能表达清楚的不要拆成五行。

## 4. 规模控制

| 对象 | 上限 | 超限处理 |
|------|------|----------|
| 单文件 | 约 300 行 | 按职责拆分为同目录子模块（本仓库惯例：领域文件优先扁平，复杂了再建子包） |
| 单函数 | 约 50 行 | 抽出内聚的私有函数/子步骤，命名即注释 |
| 单个 Vue 组件 `<script>` | 约 250 行 | 图表逻辑抽 `use-*.ts`，表格/筛选拆子组件 |
| 函数参数 | ≤ 4 个 | 更多则收拢为参数对象/TypedDict |
| 嵌套深度 | ≤ 3 层 | 用早返回、提取函数、卫语句压平 |

- 拆分标准是**职责单一**而非机械行数：一个函数做一件事，一个文件管一个领域。
- 新增代码使文件明显超出惯例规模时，应主动提议拆分，而不是继续追加。

## 5. 改动边界

- 只改与任务相关的代码；发现邻近问题可以修，但保持 diff 聚焦，不做无谓的顺手重排、重命名、重格式化。
- 触碰到的旧代码若违反本规范，鼓励顺手修正（小范围），但不发起大规模重写——那应当是独立任务。
- 新增功能先遵循项目现有结构（见 astock skill 的「修改导航」），风格规范不override分层约定。

## 6. 测试代码

测试与业务代码遵守同一套规范（重复、现代风格、简练、规模），另有：

- **不留过时测试**：功能删除/重命名/行为变更时，对应测试同步删除或改写；测"已不存在的行为"的测试是负债，不是安全网。API 契约（字段/信封/枚举/阶段）变更时，断言一并更新，不允许改生产代码迁就旧断言。
- **不留僵尸用例**：`skip`/`xfail` 必须带原因注释并有明确复活条件；注释掉的断言、永远为真的断言（如只断言 `is not None` 掩盖真实契约）视为死代码清除。
- **不镜像实现**：测试断言行为与契约，不把生产实现的算法复述一遍再比对结果（改实现就得改断言的测试没有回归价值）。
- **复用测试基建**：种子数据走 `conftest.py` 的 SeedFactory/现有 fixture，不在每个测试里自建一套建库造数；同一文件内相似的造数抽模块级 helper，不复制粘贴。
- **命名表意**：测试名说清"场景 + 期望"（`test_macro_missing_cpi_keeps_watermark`），避免 `test_1`、`test_new`。
- **位置与命令硬约束**见 [testing.md](../astock/references/testing.md)：后端只放 `backend/tests/`，前端只放 `frontend/tests/`（镜像 `src/` 结构）。

## 7. 提交前自检

- [ ] 没有复制出来的第二份实现；`console.log` / `print` 调试残留已清除
- [ ] 没有注释掉的代码块、未引用的死代码
- [ ] 没有为假设性需求预留的参数、分支、抽象
- [ ] 新代码用的是项目当前的风格，不是从旧代码继承的过时写法
- [ ] 文件/函数规模在限额内，超限已有拆分方案或已拆分
- [ ] 测试与本次改动同步：无过时/僵尸用例，新功能随代码补了测试
- [ ] 测试已按 [AGENTS.md](../../AGENTS.md) 的「改动范围 → 命令」真正执行并通过
