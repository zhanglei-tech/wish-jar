# AGENTS.md

本文件规范在本仓库中工作的编程智能体。所有代码、文档、测试和提交都应遵守这里的约定。

## 0. 适用范围与优先级

1. 用户的当前明确指令。
2. `docs/PRD.md`：产品需求的唯一事实来源。
3. 本文件：工程约定、技术路线和智能体行为规范。
4. 现有代码与测试：实现现状，不得擅自推翻。

如果需求、PRD 和代码现状冲突，**停止实现并说明冲突**，不要自行猜测。需求变更必须先更新 `docs/PRD.md`，再改代码。

## 1. 项目概览

“心愿罐（Wish Jar）”是家庭内部使用的儿童积分激励应用：家长创建目标、任务和奖励；孩子完成任务获得积分；积分可兑换约定奖励；长期心愿支持进度、预计天数和锁定储蓄。

- 用户：2 位家长 + 1 位 12 岁孩子。
- 主流程：家长代记为主，共用设备上的孩子自助为辅。
- 部署：群晖 NAS 的 Docker 单容器，以内网访问为主，偶尔通过群晖 DDNS 外网访问。
- MVP 范围：以 `docs/PRD.md` 第 4.1 节和第 5 节的 P0 功能为准。

**当前不做**：PWA 离线缓存 / 后台同步 / 推送通知，以及站内通知、任务模板、里程碑 / 分段兑现、多孩子周榜等 P2 功能。P1 已实现，不要重复推翻；P2 不提前实现。

## 2. 技术路线

- 后端：Python 3.12+、FastAPI、SQLAlchemy 2.0、Alembic、SQLite（WAL）、Pydantic v2。
- 前端：Vue 3、Vite、TypeScript、Pinia、Vue Router、Naive UI。
- 部署：多阶段 Dockerfile，前端构建为静态文件由 FastAPI 托管；`docker compose`。
- 测试：pytest + FastAPI TestClient；前端 `npm run build` 和 TypeScript 检查。
- 支持最小 PWA：manifest + 无缓存 Service Worker，仅用于安装到桌面 / 独立窗口；不做离线缓存、后台同步、推送通知。

### 目录约定

```text
backend/
  app/
    main.py          # create_app、lifespan、静态文件挂载
    config.py        # Settings
    db.py            # engine、session、SQLite PRAGMA
    models.py        # SQLAlchemy 模型
    schemas.py       # Pydantic 请求/响应模型
    auth.py          # PIN、会话、权限依赖
    services.py      # 领域计算与业务规则
    routers/         # API 路由，按领域拆分
    backup.py        # SQLite 备份
  alembic/
  tests/
  requirements.txt
frontend/
  src/
    main.ts
    App.vue
    router.ts
    api.ts
    types.ts
    theme.ts
    styles.css
    stores/
    components/
    pages/
  package.json
  vite.config.ts
docs/PRD.md
Dockerfile
docker-compose.yml
.env.example
README.md
AGENTS.md
```

如果实际目录与上面略有差异可以接受，但不要把前后端代码混在根目录。

## 3. 标准命令

项目建立后，以下命令是标准入口；如果脚本尚未存在，应先补齐，而不是让用户手工猜测。

### 后端

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

```bash
cd backend
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

```bash
cd backend
pytest -q
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

```bash
cd frontend
npm run build
npm run typecheck
```

### Docker

```bash
docker compose up --build
```

## 4. 后端规范

- 使用同步 SQLAlchemy Session；FastAPI 依赖注入提供数据库会话。
- 路由保持薄，业务规则放在 `services.py`；不要在路由里复制领域计算。
- 所有 API 统一前缀 `/api`；错误响应使用 `{"detail": "..."}`；区分 400/401/403/404/409。
- 使用 Pydantic v2 响应模型，**绝不返回 `pin_hash`、Cookie、密钥或内部路径**。
- 时间统一存 UTC；面向用户的“今天/本周”按家庭时区计算，默认 `Asia/Shanghai`。
- 每个请求结束时提交或回滚；异常必须回滚。
- 不要引入异步 SQLAlchemy，除非有明确理由并先征求用户同意。
- 新增依赖要克制；能用标准库或现有依赖解决的，不新增包。

## 5. 数据库与迁移

- SQLite 连接必须开启：`journal_mode=WAL`、`foreign_keys=ON`、合理的 `busy_timeout`。
- Alembic 是唯一的生产建表/改表方式。**生产环境禁止用 `Base.metadata.create_all()` 代替迁移**；测试环境可以用。
- 迁移文件进 git，保持单线、单 head；已执行过的迁移**不得修改**，只能新增。
- SQLite 的 `env.py` 必须配置 `render_as_batch=True`，并开启 `compare_type=True`。
- 每次模型变更必须同时提供迁移；破坏性变更优先拆成“先加新列/新表 → 回填 → 下版本再删旧列”。
- 迁移前自动备份 SQLite；备份保留 14 份；升级失败时恢复备份并停止启动，不要带着半迁移的库运行。
- `downgrade()` 可逆的认真实现；不可逆的显式 `NotImplementedError`，回滚依靠备份。
- 运行时数据不进 git：`data/`、`uploads/`、`backups/`、`*.db`、`*.sqlite*`。

## 6. 不可破坏的领域规则

这些规则来自 PRD，任何实现都必须保持一致：

- **余额**：`余额 = 所有积分流水 delta 之和`，不单独存余额字段。
- **可用余额**：`可用余额 = 余额 − 当前 active 的心愿锁定积分`。
- **锁定储蓄**：锁定/解锁不改变余额，只改变可用余额；不写入积分流水，写入 `savings_locks`。
- **解锁**：MVP 只允许家长操作；孩子不能自行解锁。
- **奖励倍率（方案 B）**：`所需积分 = ceil(标价 × 倍率)`；`1.0` 为基准，`>1` 更贵，`<1` 更便宜。
- **倍率快照**：兑换申请提交时保存 `cost_points` 和倍率；之后改价不影响已提交申请。
- **兑换流程**：孩子申请（不扣分）→ 家长通过（扣分、减库存）→ 线下兑现 → 标记已兑现。
- **长期心愿 MVP**：只做进度、预计完成天数、锁定储蓄；不做配捐、专属任务、里程碑/分段兑现。
- **锁定积分使用**：兑换长期心愿时优先消耗该心愿的锁定积分，不足部分用可用余额；多余锁定退回可用余额。
- **审核**：孩子提交默认待审核；家长代记立即通过；孩子可单独关闭审核；家长提交始终立即通过。
- **库存**：`-1` 表示不限；审批通过时减 1；库存为 0 不能兑换。
- **手动调整**：备注必填；调整后余额不能为负，也不能低于已锁定积分。
- **等级**：`累计获得 // 100 + 1`；只按任务获得的积分累计；兑换不降级。
- **连续打卡**：只展示，不加成。
- **周期键**：每日 = 本地日期；每周 = ISO 周；一次性 = `once`；同一任务同一周期最多一条有效提交。
- **照片**：JPG/PNG/WebP，单张 ≤ 5MB，仅存 NAS 本地。
- **现金/实物奖励**：只做线下兑现，不做线上支付或真实货币充值。

## 7. 前端规范

- Vue 3 `<script setup lang="ts">` + Composition API；状态用 Pinia；路由用 Vue Router；组件用 Naive UI。
- 移动端优先，重点适配 Android Chrome / Edge；桌面 Chrome/Edge 正常可用；支持安装为 PWA（独立窗口，无离线缓存）。
- PWA 只用于安装：`public/manifest.webmanifest`、192/512/maskable 图标、`public/sw.js`；service worker 不调用 `caches`、不 `respondWith`、不缓存 API / 照片 / HTML。
- service worker 仅在生产构建注册；`manifest.webmanifest`、`sw.js`、`index.html` 必须 `Cache-Control: no-cache`。
- 新版本提醒不依赖缓存：后端 `/api/version` 基于 `index.html` 内容生成构建 ID，响应 `Cache-Control: no-store`；前端启动、回到前台和页面可见期间检查，发现变化时弹对话框提示刷新，不自动刷新，同一版本不重复提示。
- 不引入 Workbox 等服务 worker 框架；不使用线上支付、第三方分析统计。
- 孩子端：温暖、有仪式感、卡片化、少文字；家长端：清晰、高效、以待办和操作为中心。
- API 请求统一走 `src/api.ts`，携带 Cookie；401 时回到登录页。
- 前端路由守卫只做体验层权限；**所有权限必须在后端再次校验**。
- 不要在前端存储 PIN；不要把 PIN、Cookie、会话密钥写入 localStorage 或日志。
- TypeScript 尽量严格；避免无理由的 `any`。
- 必须有加载态、空状态和错误提示；移动端按钮触控区域不小于 44px。
- 颜色、圆角、阴影通过 CSS 变量统一管理；不要堆砌通用 AI 风格渐变和随意字体。
- 用户界面文案用中文；代码标识符、API 字段用英文。

建议的基础色：

```css
--bg: #fff7ea;
--surface: #ffffff;
--ink: #3b2a20;
--muted: #8a7568;
--accent: #e86a4a;
--amber: #f2b544;
--teal: #2f8f83;
--line: #f0e2d2;
```

## 8. 安全与隐私

- 不提交真实姓名、孩子照片、PIN、NAS 地址、DDNS 域名、密钥、`.env`。
- PIN 使用 scrypt 哈希存储；会话使用签名 HttpOnly Cookie（SameSite=Lax，HTTPS 下 Secure）。
- 所有家庭成员、孩子、目标、任务、奖励、兑换、储蓄的读写都要校验 `family_id` 和当前角色。
- 上传文件必须校验类型和大小；文件名使用随机 ID，避免路径穿越。
- 不接入第三方统计、广告、外部 CDN 或公有云存储。
- 外网访问由群晖 DDNS + 反向代理 + Let's Encrypt 提供；应用自身不做公网暴露方案。
- 不记录 PIN、Cookie、完整请求体中的敏感字段。

## 9. 测试与完成标准

- 后端至少覆盖：首次启动、登录与角色权限、目标/任务 CRUD、打卡与审核、快速代记、积分调整、奖励倍率、兑换审批、长期心愿锁定/解锁。
- 测试使用独立的临时 SQLite 数据库，不碰真实数据。
- 每次改动后运行：

```bash
cd backend && pytest -q
```

```bash
cd frontend && npm run build && npm run typecheck
```

- PWA 至少覆盖：manifest / `sw.js` 返回正确 Content-Type 与 `Cache-Control: no-cache`；SPA fallback 的 `index.html` 不缓存；service worker 不含缓存逻辑；`/api/version` 无缓存且构建 ID 随 `index.html` 变化。
- 迁移至少验证：空库 `upgrade head`；旧版数据库副本升级到 head。
- 没有运行测试/构建，不得声称“完成”或“可用”；失败要如实报告输出。
- MVP 完成标准：PRD 第 4.1 节与第 5 节 P0 功能可用；Docker 能启动；首次向导、登录、任务闭环、奖励兑换、锁定储蓄、备份、PWA 安装均可工作；README 有运行与部署说明。

## 10. Git 与交付

- **没有用户明确要求，不执行 `git commit`、`git push`、`git tag` 或部署。**
- 提交保持聚焦；建议使用 `feat:`、`fix:`、`docs:`、`chore:`、`test:` 前缀。
- 不提交 `.env`、`data/`、`uploads/`、`backups/`、`*.db`、`.idea/`、`node_modules/`、`dist/`。
- 不执行 `git reset --hard`、强制推送、删除历史或覆盖用户未提交的改动。
- 不做破坏性数据库操作；需要清空/重建数据库时必须先征得用户同意并备份。
- 交付时说明：改了什么、运行了什么测试、哪些没验证、如何回滚。

## 11. 智能体工作流程

1. 先读 `docs/PRD.md` 和本文件，再读相关代码。
2. 查看 `git status` 和现有目录，不要假设代码已经存在。
3. 用任务列表规划；先做最小可验证的切片，不要一次性铺开所有页面。
4. 实现时遵守领域规则和数据模型；不要自行增加 P1/P2 功能。
5. 需求有歧义或冲突时，停止并提问；不要用猜测填补产品决策。
6. 改完代码后运行对应测试/构建，修复到通过或如实报告。
7. 结束时简要说明结果、验证情况和剩余风险。

## 12. 必须停下来征得同意的情况

- 要改 PRD 的范围、优先级或关键规则。
- 要删除/重建数据库、迁移可能丢数据、或恢复备份。
- 要提交/推送代码、创建 PR、部署到 NAS。
- 要引入新的核心依赖、改变技术栈、接入外部服务。
- 要实现 P1/P2 功能，或需求与当前实现冲突。
- 任何不可逆、影响真实家庭数据的操作。

## 13. 当前阶段

- 需求版本：v0.18，状态为“已定稿”，见 `docs/PRD.md`。
- MVP 与 P1 已实现；当前支持最小 PWA 安装能力与更新提示（无离线缓存）。
- 新增需求先更新 PRD，再改代码；P2 不提前实现。
