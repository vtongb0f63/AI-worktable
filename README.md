# 生长 · 个人成长平台

邀请制首版：四年目标树、周计划、每日三项主任务、加权进度、成长树与历程、可选择公开主页、DeepSeek 自带密钥 AI 建议。

## 本地运行

需要 Python 3.12+、Node 22+。在项目根目录：

```sh
python -m venv .venv
. .venv/bin/activate
pip install -r api/requirements-dev.txt
export BOOTSTRAP_INVITE=your-first-invite
export ADMIN_EMAIL=you@example.com
export ENCRYPTION_KEY=$(python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')
cd api && uvicorn app.main:app --reload --port 8000
```

在另一个终端：

```sh
cd web
npm ci
npm run dev
```

打开 `http://localhost:3000/register`，使用 `BOOTSTRAP_INVITE` 注册管理员邮箱。未配置 SMTP 的本地模式会返回开发验证链接；非 localhost 环境必须配置邮件服务。首次注册后，由管理员在“管理”页生成后续邀请码。

Windows PowerShell 的变量设置方式为 `$env:BOOTSTRAP_INVITE="..."`。启动 API 前还需设置 `$env:ADMIN_EMAIL` 与 `$env:ENCRYPTION_KEY`。

## 关键约束

- 同级节点默认权重 1。父节点按直接子节点权重加权；没有子节点时，仅在节点明确完成后显示 100%。
- 公开页只包含公开节点，且其所有祖先也必须公开；公开进度只取公开子节点。备注、复盘、密钥及用户邮箱不会出现在公开接口。
- AI 输出必须是合法 JSON 且通过结构验证；页面仅展示草稿。用户点“采纳为任务”或“确认并保存复盘”后才写入。
- 用户密钥用 Fernet 加密。`ENCRYPTION_KEY` 必须备份在数据库之外；丢失后无法解密用户密钥。不要在日志或工单中粘贴密钥。
- `events` 是追加记录。账号删除会删除其全部数据，这是追加规则的隐私删除例外。

## 测试

```sh
PYTHONPATH=api pytest -q api/tests
cd web && npm run lint && npm run build
```

## 1 GB VPS 部署

1. 准备域名、SMTP 账号、异地 restic 存储库和 GitHub 仓库。设置 `.env`，从 `.env.example` 复制并替换所有占位值；用 `python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'` 生成加密主密钥。`.env` 权限设为仅部署用户可读。
2. GitHub Actions 在 `main` 推送后构建并发布 GHCR 镜像。将 `API_IMAGE`、`WEB_IMAGE` 设置为实际仓库的镜像名。私有 GHCR 镜像需在服务器执行一次 `docker login ghcr.io`。
3. 在服务器创建 `data/`，执行 `docker compose pull && docker compose up -d`。只开放 SSH、80、443；SQLite 数据库仅挂载到 API 容器，不开放数据库端口。Caddy 自动签发 TLS 证书。
4. 在外部服务配置 HTTPS 可用性监测；不要在同一 1 GB 主机运行 Uptime Kuma。可以配置 1 GB swap 作为短时缓冲，并监视内存、swap、进程重启与磁盘空间。若持续换页或容器被杀，暂停邀请并升级内存。
5. 配置服务器外的 restic 存储库，参考 `deploy/backup.env.example` 将凭据放到 `/etc/growth-platform/backup.env`（仅部署用户可读）。将 `deploy/growth-backup.service` 和 `deploy/growth-backup.timer` 安装到 systemd，执行 `systemctl enable --now growth-backup.timer`。脚本先用 SQLite backup API 生成一致快照，再上传并保留 7 日、4 周、6 月版本。清理远端无引用数据的 `restic prune` 请在维护窗口单独执行，避免与 1 GB 主机的服务争夺内存。
6. 用中国大陆电信、移动、联通网络分别在普通时段与晚高峰测试登录、今日页和公开主页。确认可用后再发放邀请码。

服务器安全准备：SSH 仅密钥登录，关闭密码登录；防火墙只放行必要端口；保持系统及 Docker 更新。域名和公开内容相关要求应在正式开放前复核。

恢复演练：在隔离目录执行 `restic restore latest --target ./restore-check`，找到恢复的 `growth-*.db` 后运行 `sqlite3 restored.db 'PRAGMA integrity_check;'`，再将其作为测试实例的 `DATABASE_PATH` 启动 API，确认用户和目标数据可读。不要将演练库覆盖生产库。

## 当前首版边界

未包含公告栏、点赞、评论、关注和自动 AI 写入。生产部署需要用户提供域名、服务器、邮件及异地备份目标；仓库本身不会购买主机或创建外部账号。
