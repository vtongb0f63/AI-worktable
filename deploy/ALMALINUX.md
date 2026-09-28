# AlmaLinux 9 上线顺序

本项目的镜像由 GitHub Actions 构建，1 GB VPS 只拉取并运行镜像。执行一项后先检查结果，再继续下一项。正式开放前需具备域名、SMTP 和异地备份。

## 1. GitHub 与域名

将本项目推送到有写入权限的 GitHub 仓库。`main` 分支的 CI 应先通过测试，再发布 API 和 Web 镜像到 GHCR。仓库名含大写字母时，镜像名仍采用小写。

将站点域名的 A 记录指向 VPS 公网 IP。确认 `nslookup 站点域名` 返回该 IP 后再启动 Caddy，让它自动申请 HTTPS 证书。

## 2. 安装 Docker

按 [Docker 官方 CentOS 安装说明](https://docs.docker.com/engine/install/centos/)在 AlmaLinux 9 上安装。执行安装时核对 Docker 仓库 GPG 指纹为 `060A 61C5 1B55 8A7F 742B 77AA C52F EB6B 621E 9F35`。

```sh
dnf -y install dnf-plugins-core
dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
dnf install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable --now docker
docker version
docker compose version
```

安装可能需要数分钟。若 GPG 指纹不符，停止安装并检查仓库来源。不要在 VPS 上构建 Next.js 镜像。

## 3. 目录与配置

以 root 登录，克隆仓库。API 容器使用 UID 10001；宿主机数据和备份目录交给同 UID 的 `growth` 用户。若该 UID 已被占用，应先检查并调整用户与镜像配置。

```sh
dnf -y install git
git clone https://github.com/OWNER/REPO.git /srv/growth-platform
groupadd -g 10001 growth
useradd -u 10001 -g 10001 -M -s /sbin/nologin growth
install -d -o 10001 -g 10001 -m 750 /srv/growth-platform/data /srv/growth-platform/backups
cd /srv/growth-platform
cp .env.example .env
chmod 600 .env
```

将 `.env` 中的域名、镜像地址、管理员邮箱、邀请码和 SMTP 配置改为实际值。`ENCRYPTION_KEY` 由下面的命令生成，并在数据库之外安全保存副本；不要发到聊天或提交到 Git。

```sh
python3 -c 'import base64,os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())'
```

邮箱验证依赖 SMTP。未配置邮件服务时，不要开放注册。GHCR 镜像若为私有，先在 VPS 上以具有 `read:packages` 权限的凭据执行 `docker login ghcr.io`，凭据在终端交互输入。

## 4. 启动与检查

```sh
cd /srv/growth-platform
docker compose pull
docker compose up -d
docker compose ps
docker compose logs --tail=80 api web caddy
```

确认浏览器能通过 HTTPS 访问域名，再检查 `/api/health`、邀请注册、邮箱验证、登录、公开页、举报和管理员隐藏。若任一容器持续重启、内存持续换页或内核终止进程，暂停开放并处理资源问题。VPS 已有约 545 MB swap，先监测使用情况，再决定是否扩容。

## 5. 备份与开放

配置服务器外的 restic 仓库与凭据，安装 `deploy/growth-backup.service` 和 timer。首次运行后在隔离目录恢复快照，执行 `PRAGMA integrity_check` 并启动测试实例验证数据。设置外部 HTTPS 可用性监测。正式发邀请码前，分别用目标用户网络测试登录、今日页和公开主页。

SSH 密码登录和服务器防火墙在站点验收后按逐项确认的加固流程处理。配置前保留 KiwiVM 控制台作为恢复入口，改动后立即验证新的 SSH 连接和网站访问。
