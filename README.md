# 心愿罐 Wish Jar

家庭自用的目标与奖励积分应用：家长为孩子设定目标和阶段任务，孩子完成任务攒积分，兑换约定奖励。

- 2 位家长 + 1 位孩子，家庭内使用。
- 家长代记为主，共用设备上的孩子自助为辅。
- 移动端优先的响应式 Web，不做 PWA、通知、线上支付或第三方统计。
- 数据保存在本机 SQLite，照片只存本地，不接外部云存储。

## 功能（MVP）

- 首次向导：创建家庭、家长 PIN、孩子 PIN，可选示例目标和奖励。
- 成员与 PIN 登录，家长 / 孩子角色权限。
- 目标、任务（每天 / 每周 / 一次性）、照片凭证。
- 孩子提交 → 家长审核；家长代记立即通过；孩子可单独关闭审核。
- 积分流水、可用余额、等级、连续打卡。
- 奖励倍率：`所需积分 = ceil(标价 × 倍率)`，兑换时保存倍率快照。
- 兑换申请 → 家长通过（扣分、减库存）→ 线下兑现。
- 长期心愿：进度、预计完成天数、锁定储蓄，家长可释放锁定。
- 家长看板、管理中心、SQLite 手动 / 每日自动备份。

详细需求见 [docs/PRD.md](docs/PRD.md)，工程约定见 [AGENTS.md](AGENTS.md)。

## 目录

```text
backend/        FastAPI + SQLAlchemy + Alembic + pytest
frontend/       Vue 3 + Vite + TypeScript + Naive UI
docs/PRD.md     产品需求
Dockerfile      多阶段构建，前端静态文件由 FastAPI 托管
docker-compose.yml
```

## 本地开发

### 后端

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

- API 前缀：`/api`
- 健康检查：`GET /api/health`
- 开发默认数据库：`backend/data/wishjar.db`
- 可用 `.env` 覆盖 `DATABASE_URL`、`SECRET_KEY`、`TIMEZONE` 等配置。

### 前端

```bash
cd frontend
npm install
npm run dev
```

打开 `http://localhost:5173`。Vite 会把 `/api` 和 `/uploads` 代理到 `http://localhost:8000`。

首次打开会进入 `/setup` 向导。生产构建：

```bash
cd frontend
npm run build
npm run typecheck
```

### 测试

```bash
cd backend
pytest -q
```

测试使用临时 SQLite，不会碰本地真实数据。迁移可用空库验证：

```bash
cd backend
DATABASE_URL=sqlite:///./data/migration_test.db alembic upgrade head
DATABASE_URL=sqlite:///./data/migration_test.db alembic downgrade base
```

## Docker 部署

```bash
cp .env.example .env
```

编辑 `.env`，至少把 `SECRET_KEY` 换成随机长字符串，例如：

```bash
openssl rand -hex 32
```

启动：

```bash
docker compose up -d --build
```

打开 `http://<主机地址>:8000`，按首次向导创建家庭。

- `./data` 挂载到容器 `/data`，包含 `wishjar.db`、`uploads/`、`backups/`。
- 应用启动时自动执行 Alembic 迁移；迁移前会备份现有数据库。
- 每天 03:10（家庭时区）自动备份，保留最近 14 份；管理页也可以立即备份。
- 通过 HTTPS 反向代理访问时，把 `.env` 里的 `COOKIE_SECURE` 改为 `true`。
- 群晖 Container Manager 可直接使用该 `docker-compose.yml`；端口和时区在 `.env` 中调整。

### 备份与恢复

备份文件位于 `data/backups/wishjar-*.db`。恢复时先停止容器，把备份复制为 `data/wishjar.db`，删除同目录的 `wishjar.db-wal` 和 `wishjar.db-shm`，再启动容器。迁移失败时应用会自动尝试恢复启动前备份并停止启动。

### 回滚

代码回滚使用 git 切换到上一个可用版本后重新 `docker compose up -d --build`。数据库回滚依赖备份：恢复对应时间点的 `wishjar.db`。已执行的迁移文件不要修改。

## 安全与隐私

- PIN 使用 scrypt 哈希存储；登录使用签名 HttpOnly Cookie（SameSite=Lax）。
- 不提交 `.env`、`data/`、`uploads/`、`backups/`、SQLite 文件和照片。
- 所有成员、目标、任务、奖励、兑换、储蓄操作都在后端校验家庭成员和角色。
- 照片仅接受 JPG / PNG / WebP，单张不超过 5MB，随机文件名保存在本地。
- 外网访问由用户自己的反向代理和 HTTPS 负责，应用不内置公网暴露方案。
