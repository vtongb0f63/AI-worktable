# 日课 · 个人学习规划工作台

Next.js / React + FastAPI + SQLite。面向单一所有者，统一北京时间。

- 今天：待办、完成/撤销、课程、词汇复习与跑步入口。
- 周日程：单双周课程、停课日期、截图/PDF 识别草稿、AI 周计划核对后采用。
- 每日新闻：国内、国际、AI、中长跑四类 RSS，保留来源和发布日期，生成中英文摘要，可收藏、收录生词。
- 词汇：手动/CSV 导入、释义补全、默写、句子翻译、词义辨析、间隔复习及人工更正判分。
- 跑步：训练档案、计划草稿、距离/用时/心率/分段/身体反馈、与当天训练任务同步。
- 日志：记录真实操作与每日复盘。旧目标树保留只读历史。

## 运行

1. Python 3.12+：`pip install -r api/requirements-dev.txt`。
2. 设置 `DATABASE_PATH`、`OWNER_EMAIL`、`APP_ORIGIN`；生产环境保留原 `ENCRYPTION_KEY`。现有所有者账号继续使用，公开注册关闭。
3. `PYTHONPATH=api uvicorn app.main:app --host 127.0.0.1 --port 8000`。
4. `cd web`，`npm ci`，`npm run dev`；默认访问 `http://localhost:3000`。
5. AI 单独启动 `app.planner.gateway:app`（8091）及 `python -m app.planner.worker`，设置相同 `AI_GATEWAY_TOKEN`，worker 的 `AI_GATEWAY_URL` 指向网关。

Windows PowerShell 使用 `$env:PYTHONPATH='api'` 等语法设置环境变量。首次独立安装需要通过受信管理脚本创建所有者账号；不要临时在公网开放注册。开发验收使用独立 `.local/e2e.db`，不得替换生产数据库。

## AI 接入

网关使用 Codex app-server 与 ChatGPT 登录授权。没有 OpenAI/DeepSeek 付费 API 回退。`CODEX_HOME` 必须为专用目录，只存订阅授权；不要挂载应用数据、SSH 密钥或 Docker socket。仅 worker 能调用内部网关；所有请求串行，推理禁止工具与网页搜索。容器以非 root 运行，根文件系统只读。

需在专用网关中使用官方 `codex login --device-auth` 完成授权，或按官方认证说明迁移已有授权文件。不要把授权粘贴到网站或提交到 Git。额度/授权不可用时任务显示“等待恢复”，最多自动尝试 3 次；仍可手动操作和默写，已有题目可在额度不足时复用。翻译待批改不会计为错误。

默认每日 07:00 抓取新闻、周日 20:00 生成下周草稿，时间可在设置中调整。worker 必须持续运行。课表和计划均需本人确认后入库，采用前检查版本、课表冲突和重复执行。

官方参考：[Codex 认证](https://learn.chatgpt.com/docs/auth)、[app-server](https://learn.chatgpt.com/docs/app-server)。这是一条自托管 Codex 集成路径，实际可用模型和额度由订阅账户决定。

## 验证

```sh
PYTHONPATH=api pytest -q api/tests
cd web
npm run lint
npm run build
npm audit
```

`scripts/e2e.py` 使用 Playwright，在 localhost 和隔离测试数据库验证登录、待办持久化/撤销、默写、计划采用、训练、日志及手机布局。先安装 `pip install playwright`、`python -m playwright install chromium` 并准备隔离测试账号，详见 [验收记录](docs/改版验收记录.md)。

## 结构与部署

`api/app/planner/domain.py` 为纯规则；`services.py` 为用例；`repository.py` 为作用域隔离与乐观锁；`ai_port.py` 隔离模型接口；`worker.py` 管理队列、计划与内容整理；`gateway.py` 仅负责推理。前端页面按模块拆分，独立数据并发加载，服务端验证登录，表单使用语义标签和原生 dialog。

部署见 [个人学习站运行手册](docs/个人学习站运行手册.md)。历史部署资料已归档在 [部署与改版参照](docs/部署与改版参照.md) 与 `docs/reference/`。**线上 Caddy 同时承载其他服务，不覆盖 Caddyfile，不删除 Caddy 数据卷。**
