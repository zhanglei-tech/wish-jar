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
backend/                  FastAPI + SQLAlchemy + Alembic + pytest
frontend/                 Vue 3 + Vite + TypeScript + Naive UI
docs/PRD.md               产品需求
.github/workflows/        CI 与镜像发布
Dockerfile                多阶段构建，前端静态文件由 FastAPI 托管
docker-compose.yml        本地构建运行
docker-compose.nas.yml    群晖直接拉取 GHCR 镜像
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

### 从 GitHub 镜像部署与更新（群晖）

仓库自带两个 GitHub Actions 工作流：

- `.github/workflows/ci.yml`：push 到 `main` 或提 PR 时，自动运行后端 `pytest`、Alembic 迁移验证、前端构建和类型检查。
- `.github/workflows/release-image.yml`：推送 `v*` tag 时，构建镜像并推送到私有 GHCR。

发布一个版本：

```bash
git tag v1.0.0
git push origin v1.0.0
```

构建完成后镜像地址为 `ghcr.io/<GitHub用户名>/wish-jar:1.0.0`，同时会生成 `1.0`、commit sha 和 `latest` 标签。镜像默认私有，首次发布后可在 GitHub 的 Packages 页面确认可见性。

群晖上不需要源码，只需要一个目录放 `docker-compose.nas.yml`、`.env` 和 `data/`：

1. 在 `.env` 中设置 `SECRET_KEY`，以及本次要运行的镜像：

```dotenv
WISH_JAR_IMAGE=ghcr.io/<GitHub用户名>/wish-jar:1.0.0
```

2. 用只读 PAT 登录 GHCR（经典 PAT 勾选 `read:packages`；如果拉取提示 404，再补 `repo` 权限）：

```bash
echo "<PAT>" | docker login ghcr.io -u <GitHub用户名> --password-stdin
```

3. 拉取并启动：

```bash
docker compose -f docker-compose.nas.yml pull
docker compose -f docker-compose.nas.yml up -d
```

更新版本时只改 `.env` 里的 `WISH_JAR_IMAGE`，再执行上面两条命令；回滚就把标签改回上一个版本。

说明：

- 默认只构建 `linux/amd64`，适合大多数群晖型号。ARM 群晖可在仓库 Settings → Secrets and variables → Actions → Variables 新建 `IMAGE_PLATFORMS=linux/amd64,linux/arm64`，或在手动运行工作流时填写。
- GHCR 镜像名必须全小写，工作流会自动转换仓库名。
- 首次发布如果提示没有写包权限，检查 Settings → Actions → General → Workflow permissions，允许 `Read and write permissions`。
- GHCR 私有包会占用免费额度（约 500MB 存储），私有仓库免费版每月约 2,000 分钟 Actions。只保留最近几个版本，旧版本在 GitHub 的 Packages 页面删除。
- 家庭数据始终只在群晖的 `data/` 目录，不要提交到仓库。

Container Manager 里也可以用「项目」选择这个 compose 文件；如果只支持 `docker-compose.yml`，把 `docker-compose.nas.yml` 改名为 `docker-compose.yml` 即可，目录里仍然不需要源码。

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
