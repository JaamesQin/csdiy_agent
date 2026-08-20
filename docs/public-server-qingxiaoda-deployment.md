# CoursePilot 公网服务器部署与清小搭联通测试

> 适用场景：操作端是 Linux，目标服务器具有公网 IPv4、SSH 用户名、密码和自定义登录端口。
>
> 本文先使用“公网 IP + HTTP”完成短期 API Key 联通测试，再给出域名和 HTTPS 升级步骤。
> HTTP 方案不能作为正式生产配置。

## 1. 部署结构和前提

测试阶段的数据流如下：

```text
清小搭或外部 curl
  -> http://<服务器公网 IP>/v1
  -> Nginx :80
  -> Uvicorn 127.0.0.1:8000
  -> CoursePilot
  -> 账号/会话/画像 SQLite（可写）
  -> StudyKit archive SQLite（只读）
  -> 可选 DeepSeek API
```

本文假设：

- 本地当前目录是完整的 `csdiy_agent` 仓库；
- `data/archive/studykits.sqlite3` 已通过 Git LFS 拉取，不是 LFS 指针；
- 目标服务器使用 Ubuntu 22.04、Ubuntu 24.04 或其他具备 Python 3.12 的 Debian 系发行版；
- SSH 用户可以执行 `sudo`；
- 云厂商安全组可以开放 SSH 端口和 TCP 80；
- 首次测试不配置 DeepSeek，先验证确定性能力、StudyKit、JSON、SSE 和清小搭协议。

本文使用以下约定：

| 名称 | 示例 | 含义 |
| --- | --- | --- |
| `CP_SERVER_IP` | `203.0.113.10` | 服务器公网 IPv4 |
| `CP_SSH_PORT` | `2222` | SSH 登录端口 |
| `CP_SSH_USER` | `ubuntu` | 具有 sudo 权限的 SSH 用户 |
| `coursepilot` | 固定值 | 服务器上的无登录权限运行用户 |
| `/opt/coursepilot` | 固定值 | 应用代码和虚拟环境目录 |
| `/var/lib/coursepilot` | 固定值 | 可写账号数据库目录 |
| `/etc/coursepilot/coursepilot.env` | 固定值 | 生产环境变量文件 |

不要把 SSH 密码、CoursePilot API Key、DeepSeek API Key、Cookie、CSRF token 或数据库内容粘贴到聊天、工单或 Git 中。

## 2. 本地部署前检查

在本地 Linux 的仓库根目录执行：

```bash
pwd
test -f requirements.txt
test -f app/main.py
test -f data/archive/studykits.sqlite3
ls -lh data/archive/studykits.sqlite3
```

当前归档应约为 125 MiB。如果文件只有几百字节，说明它仍是 Git LFS 指针，应先初始化私有数据子模块并拉取 LFS 对象：

```bash
git submodule update --init --recursive
git -C data lfs pull
ls -lh data/archive/studykits.sqlite3
```

可选但推荐：部署前运行完整测试。

```bash
.venv/bin/pytest -q
```

测试不得使用真实生产密钥，也不应依赖外部模型凭据。

## 3. 配置本地连接变量

这些变量只在当前终端生效。替换为真实值：

```bash
export CP_SERVER_IP="203.0.113.10"
export CP_SSH_PORT="2222"
export CP_SSH_USER="ubuntu"
```

检查变量，尤其不要写错 SSH 端口：

```bash
printf 'server=%s user=%s ssh_port=%s\n' \
  "$CP_SERVER_IP" "$CP_SSH_USER" "$CP_SSH_PORT"
```

## 4. 首次 SSH 登录并改用密钥

先用现有用户名、密码和端口验证登录：

```bash
ssh -p "$CP_SSH_PORT" "$CP_SSH_USER@$CP_SERVER_IP"
```

成功后退出服务器：

```bash
exit
```

如果本地尚无专用 SSH 密钥，创建一个：

```bash
ssh-keygen -t ed25519 -f "$HOME/.ssh/coursepilot_deploy" -C "coursepilot-deploy"
```

把公钥安装到服务器。此步骤会最后一次要求输入服务器密码：

```bash
ssh-copy-id \
  -i "$HOME/.ssh/coursepilot_deploy.pub" \
  -p "$CP_SSH_PORT" \
  "$CP_SSH_USER@$CP_SERVER_IP"
```

验证密钥登录：

```bash
ssh \
  -i "$HOME/.ssh/coursepilot_deploy" \
  -p "$CP_SSH_PORT" \
  "$CP_SSH_USER@$CP_SERVER_IP"
```

在部署和回滚均验证成功前，不要关闭密码登录，也不要修改服务器 SSH 端口。

## 5. 打包最小在线运行文件

不要上传整个约 5 GiB 的工作区。在线服务不需要 `data/raw/`、旧备份、测试输出、离线生成 checkpoint 或本地 `.venv`。

在本地仓库根目录执行：

```bash
CP_PACKAGE="/tmp/coursepilot-runtime.tar.gz"

tar \
  --exclude='*/__pycache__' \
  --exclude='*.pyc' \
  --exclude='*.pyo' \
  -czf "$CP_PACKAGE" \
  app \
  schemas \
  requirements.txt \
  data/archive/studykits.sqlite3 \
  data/catalog \
  data/manifests \
  data/golden

ls -lh "$CP_PACKAGE"
tar -tzf "$CP_PACKAGE" | head -n 30
```

确认压缩包没有携带本机 Python 缓存，并且包含 StudyKit 归档：

```bash
if tar -tzf "$CP_PACKAGE" | grep -E '(__pycache__/|\.py[co]$)'; then
  echo '错误：运行包包含 Python 缓存，请检查 tar exclude 参数。'
else
  echo 'Python 缓存检查通过。'
fi

tar -tvzf "$CP_PACKAGE" \
  | grep 'data/archive/studykits.sqlite3$'
```

归档列表中 `studykits.sqlite3` 的原始大小应约为 125 MiB。运行包经过 gzip 压缩后明显小于 125 MiB 属于正常现象。

运行包包含：

- FastAPI、协议、Agent、认证、画像和静态代码辅导代码；
- portable StudyKit Schema；
- 只读的 approved StudyKit archive；
- Catalog、Manifest 和两份人工批准的 golden fallback；
- Python 运行依赖清单。

## 6. 上传运行包

```bash
scp \
  -i "$HOME/.ssh/coursepilot_deploy" \
  -P "$CP_SSH_PORT" \
  "$CP_PACKAGE" \
  "$CP_SSH_USER@$CP_SERVER_IP:coursepilot-runtime.tar.gz"
```

验证服务器收到文件：

```bash
ssh \
  -i "$HOME/.ssh/coursepilot_deploy" \
  -p "$CP_SSH_PORT" \
  "$CP_SSH_USER@$CP_SERVER_IP" \
  'ls -lh "$HOME/coursepilot-runtime.tar.gz"'
```

## 7. 安装服务器依赖

登录服务器：

```bash
ssh \
  -i "$HOME/.ssh/coursepilot_deploy" \
  -p "$CP_SSH_PORT" \
  "$CP_SSH_USER@$CP_SERVER_IP"
```

以下命令均在服务器上执行。

确认操作系统、架构和 Python 版本：

```bash
cat /etc/os-release
uname -m
python3 --version || true
```

安装所需软件：

```bash
sudo apt-get update
sudo apt-get install -y \
  python3 \
  python3-venv \
  python3-pip \
  nginx \
  sqlite3 \
  openssl \
  curl \
  ca-certificates
```

再次确认 Python：

```bash
python3 --version
```

仓库以 Python 3.12 测试。Ubuntu 24.04 默认提供 Python 3.12；Ubuntu 22.04 默认显示 Python 3.10，这是正常现象，但不能用它创建 CoursePilot 的生产虚拟环境。

### 7.1 Ubuntu 22.04：并行安装 Python 3.12

先确认确实是 Ubuntu 22.04：

```bash
. /etc/os-release
printf 'distribution=%s version=%s codename=%s\n' \
  "$ID" "$VERSION_ID" "$VERSION_CODENAME"
```

如果输出为 `ubuntu`、`22.04`、`jammy`，执行：

```bash
sudo apt-get install -y software-properties-common
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt-get update
sudo apt-get install -y python3.12 python3.12-venv
python3.12 --version
```

应看到 `Python 3.12.x`。不要执行以下操作：

- 不要修改 `/usr/bin/python3` 链接；
- 不要使用 `update-alternatives` 把系统 Python 切换到 3.12；
- 不要卸载 Ubuntu 自带的 Python 3.10；
- 不要用全局 `pip` 向系统 Python 安装项目依赖。

Ubuntu 22.04 的 apt、PackageKit 和其他系统组件仍继续使用 Python 3.10；只有 CoursePilot 的隔离虚拟环境使用 3.12。

Deadsnakes 是 Launchpad 上的第三方 PPA，而不是 Ubuntu 22.04 官方仓库。它目前为 Jammy 发布 Python 3.12，但其维护方明确说明不保证安全更新时效。短期联通测试可以采用该方案；长期生产环境更推荐升级到原生提供 Python 3.12 的 Ubuntu 24.04。来源：[Deadsnakes PPA](https://launchpad.net/~deadsnakes/+archive/ubuntu/ppa?field.series_filter=jammy)。

### 7.2 确定 CoursePilot 使用的解释器

无论是 Ubuntu 22.04 还是 24.04，都执行：

```bash
CP_PYTHON_BIN="$(command -v python3.12)"
test -n "$CP_PYTHON_BIN"
"$CP_PYTHON_BIN" --version
```

后续必须用这个 Python 3.12 路径创建虚拟环境，而不是裸用 `python3`。

## 8. 创建运行用户和持久化目录

创建不能交互登录的专用用户：

```bash
if ! id coursepilot >/dev/null 2>&1; then
  sudo useradd \
    --system \
    --home-dir /var/lib/coursepilot \
    --create-home \
    --shell /usr/sbin/nologin \
    coursepilot
fi
```

创建目录：

```bash
sudo install -d -o root -g coursepilot -m 0750 /opt/coursepilot
sudo install -d -o coursepilot -g coursepilot -m 0700 /var/lib/coursepilot
sudo install -d -o root -g coursepilot -m 0750 /etc/coursepilot
```

代码和 StudyKit 归档是只读部署内容；只有 `/var/lib/coursepilot` 允许应用写入。

## 9. 安装应用和 Python 依赖

首次部署时 `/opt/coursepilot` 应为空。确认目标后展开运行包：

```bash
sudo tar -xzf "$HOME/coursepilot-runtime.tar.gz" -C /opt/coursepilot
CP_PYTHON_BIN="$(command -v python3.12)"
test -n "$CP_PYTHON_BIN"
sudo "$CP_PYTHON_BIN" -m venv /opt/coursepilot/.venv
sudo /opt/coursepilot/.venv/bin/pip install --upgrade pip
sudo /opt/coursepilot/.venv/bin/pip install \
  --retries 15 \
  --timeout 120 \
  -r /opt/coursepilot/requirements.txt
```

设置只读权限：

```bash
sudo chown -R root:coursepilot /opt/coursepilot
sudo chmod -R g+rX,o-rwx /opt/coursepilot
sudo chmod 0640 /opt/coursepilot/data/archive/studykits.sqlite3
```

检查依赖和归档：

```bash
sudo -u coursepilot /opt/coursepilot/.venv/bin/pip check
sudo -u coursepilot sqlite3 \
  /opt/coursepilot/data/archive/studykits.sqlite3 \
  'PRAGMA quick_check;'
```

预期最后一条输出：

```text
ok
```

## 10. 创建生产环境变量

在服务器上生成 CoursePilot API Key。该命令只显示一次，应立即保存到密码管理器：

```bash
openssl rand -hex 32
```

创建 `/etc/coursepilot/coursepilot.env`：

```bash
sudoedit /etc/coursepilot/coursepilot.env
```

写入以下内容，把占位符替换为刚生成的随机值：

```dotenv
COURSEPILOT_API_KEY=REPLACE_WITH_RANDOM_64_HEX_CHARACTERS
COURSEPILOT_DB_PATH=/var/lib/coursepilot/coursepilot.sqlite3
COURSEPILOT_SESSION_TTL_HOURS=12
COURSEPILOT_CONVERSATION_TTL_DAYS=30
COURSEPILOT_COOKIE_SECURE=false
COURSEPILOT_TEST_MODE=false
COURSEPILOT_PRACTICE_REWRITE_ENABLED=true
```

首次连接测试不设置 `DEEPSEEK_API_KEY`。应用会透明降级，课程导航、StudyKit 查询、概念解释、练习选择和静态代码诊断仍可测试。

限制 Secret 文件权限：

```bash
sudo chown root:coursepilot /etc/coursepilot/coursepilot.env
sudo chmod 0640 /etc/coursepilot/coursepilot.env
```

API Key 不应出现在 systemd unit、Nginx 配置、shell history 或 Git 中。

## 11. 创建 systemd 服务

创建 `/etc/systemd/system/coursepilot.service`：

```bash
sudoedit /etc/systemd/system/coursepilot.service
```

写入：

```ini
[Unit]
Description=CoursePilot OpenAI-compatible API
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=coursepilot
Group=coursepilot
WorkingDirectory=/opt/coursepilot
EnvironmentFile=/etc/coursepilot/coursepilot.env
ExecStart=/opt/coursepilot/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1 --no-server-header
Restart=on-failure
RestartSec=5
TimeoutStopSec=30
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/coursepilot
UMask=0077

[Install]
WantedBy=multi-user.target
```

说明：

- 只运行一个 Uvicorn worker，避免为每个进程重复加载全部 StudyKit，并保持当前 SQLite 和进程内状态语义清晰；
- Uvicorn 只监听 `127.0.0.1:8000`，公网不能绕过 Nginx；
- `ProtectSystem=strict` 让代码、配置和归档对应用保持只读；
- 账号、会话和画像只能写入 `/var/lib/coursepilot`。

加载并启动：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now coursepilot
sudo systemctl status coursepilot --no-pager
```

查看最近日志：

```bash
sudo journalctl -u coursepilot -n 100 --no-pager
```

验证本机健康检查：

```bash
curl -i http://127.0.0.1:8000/health
```

预期 HTTP 200 和：

```json
{"status":"ok"}
```

如果服务失败，先不要配置公网入口，执行：

```bash
sudo systemctl status coursepilot --no-pager
sudo journalctl -u coursepilot -n 200 --no-pager
```

## 12. 配置 Nginx 限流和 SSE 转发

创建共享认证限流区：

```bash
sudoedit /etc/nginx/conf.d/coursepilot-limits.conf
```

写入：

```nginx
limit_req_zone $binary_remote_addr zone=coursepilot_auth:10m rate=5r/m;
```

创建站点配置：

```bash
sudoedit /etc/nginx/sites-available/coursepilot
```

写入：

```nginx
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;

    client_max_body_size 2m;

    location = /auth/register {
        limit_req zone=coursepilot_auth burst=5 nodelay;

        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
    }

    location = /auth/login {
        limit_req zone=coursepilot_auth burst=5 nodelay;

        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }
}
```

`proxy_buffering off` 是 SSE 逐帧返回的关键配置。不要在 Cloudflare、Nginx 或其他网关缓存 `/auth/*` 和 `/v1/*`。

启用站点：

```bash
sudo ln -sfn \
  /etc/nginx/sites-available/coursepilot \
  /etc/nginx/sites-enabled/coursepilot
```

如果这是全新服务器，并且只有 Nginx 默认站点，可以移除默认链接：

```bash
if [ -L /etc/nginx/sites-enabled/default ]; then
  sudo unlink /etc/nginx/sites-enabled/default
fi
```

检查并重载：

```bash
sudo nginx -t
sudo systemctl enable --now nginx
sudo systemctl reload nginx
sudo systemctl status nginx --no-pager
```

从服务器本机验证 Nginx：

```bash
curl -i http://127.0.0.1/health
```

## 13. 配置云安全组和主机防火墙

云厂商安全组至少允许：

| 方向 | 协议 | 端口 | 来源 |
| --- | --- | --- | --- |
| 入站 | TCP | 实际 SSH 端口 | 优先限定为管理员公网 IP |
| 入站 | TCP | 80 | `0.0.0.0/0`，仅用于短期 HTTP 测试 |
| 出站 | TCP | 443 | DeepSeek、系统更新和依赖访问 |

不要开放 TCP 8000。Uvicorn 只应由服务器本机 Nginx 访问。

如果服务器启用 UFW，在执行 `enable` 前必须先允许真实 SSH 端口。请使用明确端口，例如：

```bash
sudo ufw allow 2222/tcp
sudo ufw allow 80/tcp
sudo ufw enable
sudo ufw status verbose
```

务必把示例 `2222` 改成真实 SSH 端口。保持当前 SSH 会话不关闭，并从另一个终端验证新连接成功，避免把自己锁在服务器外。

## 14. 从本地 Linux 做外网验收

退出服务器或另开本地终端。重新设置连接变量：

```bash
export CP_SERVER_IP="203.0.113.10"
```

### 14.1 健康检查

```bash
curl --noproxy '*' -i "http://$CP_SERVER_IP/health"
```

预期 HTTP 200。

如果本地配置了 `http_proxy`、`https_proxy` 或桌面代理，普通 curl 可能先连接本机代理端口，而不是直接连接服务器。可以用以下命令确认：

```bash
env | grep -iE '^(http|https|all|no)_proxy='
curl --noproxy '*' -v \
  --connect-timeout 5 \
  --max-time 10 \
  "http://$CP_SERVER_IP/health"
```

`--noproxy '*'` 只对当前 curl 命令绕过所有代理，不会修改桌面或 shell 的全局代理设置。

### 14.2 错误 API Key 必须失败

```bash
curl -i "http://$CP_SERVER_IP/v1/models" \
  -H 'Authorization: Bearer definitely-wrong-key'
```

预期 HTTP 401。若错误 Key 可以访问，立即停止测试并检查配置。

### 14.3 读取真实 API Key

不要把真实 Key 直接写进命令历史。可以交互读取到当前 shell 变量：

```bash
read -rsp 'CoursePilot API Key: ' CP_API_KEY
printf '\n'
export CP_API_KEY
```

### 14.4 模型列表

```bash
curl -i "http://$CP_SERVER_IP/v1/models" \
  -H "Authorization: Bearer $CP_API_KEY"
```

确认响应包含模型 ID：

```text
coursepilot-probe
```

### 14.5 非流式聊天

```bash
curl -sS "http://$CP_SERVER_IP/v1/chat/completions" \
  -H "Authorization: Bearer $CP_API_KEY" \
  -H 'Content-Type: application/json' \
  --data '{
    "model": "coursepilot-probe",
    "user": "external-smoke-test",
    "messages": [
      {"role": "user", "content": "/help"}
    ],
    "stream": false
  }'
```

确认返回 OpenAI 兼容 JSON envelope，且没有隐藏 rubric、模型推理或内部审计字段。

### 14.6 SSE 流式聊天

```bash
curl -N "http://$CP_SERVER_IP/v1/chat/completions" \
  -H "Authorization: Bearer $CP_API_KEY" \
  -H 'Content-Type: application/json' \
  --data '{
    "model": "coursepilot-probe",
    "user": "external-sse-test",
    "messages": [
      {"role": "user", "content": "请介绍当前可以提供的帮助"}
    ],
    "stream": true
  }'
```

确认 SSE 顺序为：

1. role frame；
2. 一个或多个 content frame；
3. 恰好一个 `finish_reason: stop` frame；
4. 最后为 `[DONE]`。

如果所有内容等待很久后一次性出现，检查 Nginx 是否确实加载了 `proxy_buffering off`：

```bash
sudo nginx -T | grep -n 'proxy_buffering'
```

### 14.7 StudyKit 在线归档

继续使用聊天接口测试：

- 请求课程导航；
- 查询一个已批准课程和单元；
- 请求概念解释；
- 请求练习题；
- 请求 `/help` 并确认显示当前 220 份 approved archive StudyKit；
- 请求不存在的课程或页码，确认系统透明失败而不是编造证据。

## 15. 清小搭配置

在清小搭的 OpenAI 兼容模型配置中填写：

```text
baseUrl: http://<服务器公网 IP>/v1
credential: <COURSEPILOT_API_KEY>
model: coursepilot-probe
```

注意：

- `baseUrl` 只写到 `/v1`；
- 不要追加 `/chat/completions`；
- `credential` 使用 CoursePilot API Key，不是 SSH 密码或 DeepSeek Key；
- 模型 ID 必须是 `coursepilot-probe`；
- 清小搭传入的 OpenAI `user` 仅映射到 `legacy:<user>`，不能访问本地 `account:` 用户；
- 清小搭顶层可选 `sessionId` 用于服务端多轮连续状态；同一对话保持相同值，新对话换值，缺失或空值按新会话处理；
- `sessionId` 不是授权凭据，响应无需回传。服务端只保存经 HMAC 索引的最小课程/练习连续状态，默认滑动保留 30 天；
- API Key 请求不使用浏览器 Cookie，因此不需要 CSRF header。

建议依次试聊：

1. `/help`；
2. “列出当前可在线学习的课程”；
3. 指定一个 ready StudyKit 单元请求概念解释；
4. 请求一道练习；
5. 在同一 `sessionId` 中只发送“第七题”等指代，确认继承上轮课程/讲次；换一个 `sessionId` 后确认不串话；
6. 粘贴一小段带语言标记的代码请求静态诊断；
7. 测试流式输出是否连续显示并正常结束。

测试时同时在服务器观察日志：

```bash
sudo journalctl -u coursepilot -f
```

另一个窗口观察 Nginx 错误日志：

```bash
sudo tail -f /var/log/nginx/error.log
```

日志中不得出现 API Key、密码、Cookie、CSRF token、Argon2 hash、完整代码或完整对话。

## 16. 清小搭拒绝 HTTP 时升级为 HTTPS

如果清小搭拒绝 `http://` base URL，或者联通测试已经通过，应立即使用域名和 HTTPS。

### 16.1 DNS

准备域名，例如：

```text
coursepilot.example.com
```

添加 A 记录：

```text
coursepilot.example.com -> <服务器公网 IPv4>
```

等待解析后验证：

```bash
getent ahostsv4 coursepilot.example.com
```

### 16.2 修改 Nginx server_name

在服务器编辑：

```bash
sudoedit /etc/nginx/sites-available/coursepilot
```

把：

```nginx
server_name _;
```

改为：

```nginx
server_name coursepilot.example.com;
```

检查并重载：

```bash
sudo nginx -t
sudo systemctl reload nginx
```

### 16.3 开放 HTTPS 并申请证书

安全组和 UFW 开放 TCP 443：

```bash
sudo ufw allow 443/tcp
```

在 Ubuntu/Debian 安装 Certbot：

```bash
sudo apt-get install -y certbot python3-certbot-nginx
```

申请证书：

```bash
sudo certbot --nginx -d coursepilot.example.com
```

验证自动续期：

```bash
sudo certbot renew --dry-run
```

### 16.4 启用 Secure Cookie 和 Origin allowlist

编辑环境变量：

```bash
sudoedit /etc/coursepilot/coursepilot.env
```

修改或加入：

```dotenv
COURSEPILOT_COOKIE_SECURE=true
COURSEPILOT_ALLOWED_ORIGINS=https://coursepilot.example.com
```

重启应用：

```bash
sudo systemctl restart coursepilot
sudo systemctl status coursepilot --no-pager
```

验证：

```bash
curl -i https://coursepilot.example.com/health
```

最后将清小搭改成：

```text
baseUrl: https://coursepilot.example.com/v1
credential: <原 CoursePilot API Key>
model: coursepilot-probe
```

HTTPS 完成后，应把 TCP 80 保留为到 HTTPS 的重定向，而不是继续提供明文 API。

## 17. 可选启用 DeepSeek

只有无模型路径和清小搭协议均验证通过后，再编辑：

```bash
sudoedit /etc/coursepilot/coursepilot.env
```

加入：

```dotenv
DEEPSEEK_API_KEY=REPLACE_WITH_REAL_DEEPSEEK_KEY
```

如需非默认端点或模型，再增加：

```dotenv
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
```

重启并观察：

```bash
sudo systemctl restart coursepilot
sudo journalctl -u coursepilot -n 100 --no-pager
```

不要把离线 `StudyKitGenerator` 接到 `/v1/chat/completions`。在线每项具体能力最多调用模型一次，不得增加在线生成器到审核器链。

## 18. 数据备份

账号数据库与 StudyKit archive 必须分开处理：

- `/var/lib/coursepilot/coursepilot.sqlite3`：可写账号、会话和画像数据库；
- `/opt/coursepilot/data/archive/studykits.sqlite3`：只读、人工批准的课程归档。

在线备份账号数据库：

```bash
sudo install -d -o root -g root -m 0700 /var/backups/coursepilot
sudo sqlite3 /var/lib/coursepilot/coursepilot.sqlite3 \
  ".backup '/var/backups/coursepilot/coursepilot-$(date +%Y%m%d-%H%M%S).sqlite3'"
```

检查备份：

```bash
sudo sqlite3 /var/backups/coursepilot/<备份文件名> 'PRAGMA quick_check;'
```

不要在服务运行时只复制 SQLite 主文件而忽略 `-wal` 和 `-shm`。应使用 SQLite `.backup`，或者完全停止服务后同时复制三个文件。

StudyKit archive 是不可变部署输入，可以记录 SHA-256：

```bash
sudo sha256sum /opt/coursepilot/data/archive/studykits.sqlite3
```

## 19. 更新和回滚

更新前：

1. 在本地运行测试；
2. 重新生成最小运行包；
3. 备份账号数据库；
4. 保存当前 `/opt/coursepilot` 的版本副本；
5. 停止服务；
6. 展开新包并重建虚拟环境；
7. 启动并完成 `/health`、JSON、SSE 和清小搭验收。

停止服务：

```bash
sudo systemctl stop coursepilot
```

停止后备份账号数据库及 WAL 文件：

```bash
sudo sh -c \
  'cp -a /var/lib/coursepilot/coursepilot.sqlite3* /var/backups/coursepilot/'
```

任何数据库迁移都应先只启动一个实例。未知 SQLite schema version 会让应用启动失败，不得覆盖或强制降级数据库。

如果新版本异常：

1. 停止 CoursePilot；
2. 恢复最近完整测试通过的代码包；
3. 只有发生数据库迁移且确认需要时才恢复数据库备份；
4. 重新启动；
5. 验证健康检查、认证、账号隔离、JSON、SSE 和 ready StudyKit。

## 20. 常见故障

### 外网无法访问，但本机 health 正常

依次检查：

```bash
sudo ss -lntp
sudo systemctl status nginx --no-pager
sudo nginx -t
sudo ufw status verbose
```

同时检查云厂商安全组是否开放 TCP 80/443。不要通过开放 8000 绕过 Nginx。

### HTTP 502 Bad Gateway

```bash
sudo systemctl status coursepilot --no-pager
sudo journalctl -u coursepilot -n 200 --no-pager
curl -i http://127.0.0.1:8000/health
```

通常表示 Uvicorn 没有运行、启动路径错误、依赖未安装或环境变量无效。

### 服务提示 StudyKit archive missing 或只剩 golden fallback

```bash
sudo ls -lh /opt/coursepilot/data/archive/studykits.sqlite3
sudo -u coursepilot sqlite3 \
  /opt/coursepilot/data/archive/studykits.sqlite3 \
  'PRAGMA quick_check;'
```

确认上传的是约 125 MiB 的真实 LFS 文件，而不是 LFS 指针。

### 清小搭返回 401

确认：

- credential 是 `COURSEPILOT_API_KEY`；
- 没有误用 DeepSeek Key、SSH 密码或 Cookie；
- Key 前后没有空格或换行；
- systemd 已在修改环境文件后重启；
- base URL 没有重复追加 `/chat/completions`。

### 清小搭无法保存 HTTP 地址

按第 16 节配置域名和 HTTPS。不要关闭清小搭的 TLS 校验，也不要使用自签名公网证书规避验证。

### SSE 最后一次性显示

确认：

```bash
sudo nginx -T | grep -n -E 'proxy_buffering|proxy_read_timeout'
```

并确认中间没有另一个开启缓存的 CDN 或代理。

### DeepSeek 不可用

先移除 `DEEPSEEK_API_KEY` 并重启，验证确定性降级路径。模型不可用不应影响 `/health`、课程导航、StudyKit 查询、概念解释、练习选择和静态代码诊断。

### 服务器从 PyPI 下载依赖频繁中断

如果 pip 显示 `Connection interrupted` 但随后出现 `Attempting to resume incomplete download`，并且进度仍在增长，可以先等待。若最终失败，重新执行带重试和长超时的安装命令；已完整下载的 wheel 通常会被缓存：

```bash
sudo /opt/coursepilot/.venv/bin/pip install \
  --retries 15 \
  --timeout 120 \
  -r /opt/coursepilot/requirements.txt
```

如果服务器位于中国大陆，访问 `files.pythonhosted.org` 只有几十 KiB/s，可以按 `Ctrl+C` 中止当前 pip，并临时使用清华 TUNA 的 HTTPS PyPI 镜像：

```bash
sudo /opt/coursepilot/.venv/bin/pip install \
  --index-url https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple \
  --retries 15 \
  --timeout 120 \
  -r /opt/coursepilot/requirements.txt
```

这里只对单次命令指定镜像，不修改服务器全局 pip 配置，也不需要设置 `trusted-host`。TUNA 文档说明该镜像通常在成功同步后每隔约 5 分钟再次同步：[TUNA PyPI 使用帮助](https://mirrors.tuna.tsinghua.edu.cn/help/pypi/)。镜像是第三方软件分发渠道；如果希望始终从官方 PyPI 获取 wheel，使用下面的本地 wheelhouse 方案。

如果服务器到 PyPI 的网络持续不稳定，推荐在本地 Linux 下载 wheelhouse，然后上传并在服务器离线安装。先在本地和服务器分别执行 `uname -m`，确认架构一致；本文示例要求两边均为 `x86_64`，并使用 Python 3.12。

在本地仓库根目录执行：

```bash
CP_WHEEL_DIR="$(mktemp -d /tmp/coursepilot-wheelhouse.XXXXXX)"
CP_WHEEL_PACKAGE="/tmp/coursepilot-wheelhouse.tar.gz"

.venv/bin/python -m pip download \
  --only-binary=:all: \
  --dest "$CP_WHEEL_DIR" \
  -r requirements.txt

tar -czf "$CP_WHEEL_PACKAGE" -C "$CP_WHEEL_DIR" .
ls -lh "$CP_WHEEL_PACKAGE"
```

上传到服务器：

```bash
scp \
  -i "$HOME/.ssh/coursepilot_deploy" \
  -P "$CP_SSH_PORT" \
  "$CP_WHEEL_PACKAGE" \
  "$CP_SSH_USER@$CP_SERVER_IP:coursepilot-wheelhouse.tar.gz"
```

在服务器执行：

```bash
sudo install -d -o root -g root -m 0755 /opt/coursepilot-wheelhouse
sudo tar -xzf "$HOME/coursepilot-wheelhouse.tar.gz" \
  -C /opt/coursepilot-wheelhouse

sudo /opt/coursepilot/.venv/bin/pip install \
  --no-index \
  --find-links=/opt/coursepilot-wheelhouse \
  -r /opt/coursepilot/requirements.txt

sudo -u coursepilot /opt/coursepilot/.venv/bin/pip check
```

看到 `No broken requirements found.` 后即可继续。不要直接把本地 `.venv` 复制到服务器；虚拟环境包含绝对路径和平台相关二进制，不是可靠的部署包。离线安装完成后，可以删除上传压缩包和解压 wheelhouse 以节省空间：

```bash
rm -f "$HOME/coursepilot-wheelhouse.tar.gz"
sudo rm -rf /opt/coursepilot-wheelhouse
```

## 21. 测试完成后的安全收尾

完成公网联通测试后至少执行：

- 配置域名和 HTTPS；
- 设置 `COURSEPILOT_COOKIE_SECURE=true`；
- 设置明确的 `COURSEPILOT_ALLOWED_ORIGINS`；
- 保留 Nginx 共享登录/注册限流；
- 确认 TCP 8000 未开放；
- 将 SSH 仅允许密钥登录，并在确认密钥和备用恢复方式可用后禁用密码登录；
- 将 SSH 安全组来源限制到管理员 IP（如果网络条件允许）；
- 配置数据库自动备份和恢复演练；
- 配置磁盘空间、服务存活和证书过期监控；
- 删除服务器 SSH 用户主目录中的临时上传包：`~/coursepilot-runtime.tar.gz`；
- 清除本地 shell 中临时 API Key：`unset CP_API_KEY`；
- 执行发布记录中的账号隔离、Cookie、CSRF、JSON、SSE、课程证据和降级检查。

HTTP 公网 IP 测试只用于确认协议可达。只要服务开始保存真实账号或面向真实学习者，就必须先完成 HTTPS、持久化备份、共享限流和日志脱敏。
