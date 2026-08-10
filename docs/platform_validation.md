# 清小搭平台与本地协议验证记录

> 更新日期：2026-08-10
> 当前结论：本地协议验证通过，清小搭生产平台验证待执行

## 1. 验证范围

本轮只验证阶段 1 中可以在本地独立完成的部分：

- FastAPI 服务启动与健康检查；
- `Authorization: Bearer <credential>` 鉴权；
- `GET /v1/models`；
- `POST /v1/chat/completions` 非流式 JSON；
- `POST /v1/chat/completions` 流式 SSE；
- `model` 缺失、空字符串或 `null`；
- `max_tokens: 1`；
- `stream` 严格 JSON 布尔校验；
- 流式中途错误的 stop 帧、独立 `error` 字段和 `[DONE]`；
- 密钥缺失或过短时拒绝启动；
- 密钥不出现在正常或错误响应中；
- 本地聊天界面和静态资源；
- 独立 Uvicorn 进程上的真实 HTTP、SSE 和轻量并发请求。

本轮没有验证清小搭账号侧能力、生产网络、文件 URL 或长期状态。

## 2. 本地环境

| 项目 | 值 |
| --- | --- |
| Python | 3.12.3 |
| FastAPI | 0.141.1 |
| Uvicorn | 0.52.0 |
| HTTP 客户端 | HTTPX 0.28.1 |
| 测试框架 | pytest 9.1.1 |
| 服务地址 | `http://127.0.0.1:<临时端口>` |
| 模型调用 | 无，使用固定回显 |

## 3. 自动化结果

执行命令：

```bash
source .venv/bin/activate
pytest -q
```

结果：

```text
36 passed in 2.27s
```

依赖检查：

```text
No broken requirements found.
```

真实 HTTP 测试会启动独立 Uvicorn 子进程，并覆盖：

- 100 次 `/v1/models` 请求；
- 100 次非流式对话请求；
- 20 次流式对话请求；
- SSE 实际增量到达；
- 每个流式响应以 `data: [DONE]` 结束。

上述请求成功率为 100%。

## 4. 能力结论

| 能力 | 状态 | 证据或说明 |
| --- | --- | --- |
| Bearer 鉴权 | 支持 | 正确密钥 200，错误或缺失密钥 401 |
| `/v1/models` | 支持 | 返回 OpenAI 风格模型列表 |
| 非流式 JSON | 支持 | `choices[0].message.content` 与 `usage` 完整 |
| 流式 SSE | 支持 | role、content、stop、`[DONE]` 顺序和唯一性通过 |
| 流式错误收尾 | 支持 | stop + 独立 `error` + `[DONE]` |
| 严格 `stream` | 支持 | 字符串、数字、`null` 等返回 422 |
| 探测字段兼容 | 支持 | `max_tokens: 1` 和空模型通过 |
| 多轮消息输入 | 支持 | 接受 system、user、assistant，使用最后一条用户消息 |
| 本地聊天界面 | 支持 | 流式切换、停止、清空、多轮和会话级密钥 |
| 真实模型生成 | 尚未实现 | 阶段 1 使用固定回显 |
| 清小搭四项探测 | 待验证 | 需要生产部署地址 |
| 清小搭真实试聊 | 待验证 | 需要账号侧操作 |
| `file.url` | 待验证 | 需要平台实际发送文件请求 |
| 用户或会话标识 | 待验证 | 标准协议文档未作确定保证 |
| 长期状态 | 待验证 | 需要平台账号实测 |
| 平台日志 | 待验证 | 需要生产部署与清小搭后台 |

## 5. 待执行的平台验收

生产部署完成后依次执行：

1. 验证生产域名的 `/health`、`/v1/models` 和 `/v1/chat/completions`；
2. 等待实例闲置后再次验证冷启动；
3. 在清小搭接入向导完成连通性、凭证、最小对话和响应格式四项探测；
4. 从清小搭页面完成一轮真实输入和输出；
5. 验证系统提示和多轮历史；
6. 验证文件 URL、域名、类型、大小和 120 秒总超时；
7. 记录会话标识、状态保存、日志和平台版本；
8. 将每项 P0 平台依赖标记为支持、降级或阻塞。

## 6. 当前判定

本地协议实现满足进入生产部署和清小搭接入探测的条件。由于清小搭账号侧探测与真实试聊尚未完成，阶段 1 暂不能标记为全部完成。

## 7. 2026-08-09 多用户安全验证

本节是新增验证记录，不替代上面的 2026-07-31 协议记录。

实现新增了账号注册/登录/注销、SQLite Schema v2、Argon2id、服务端会话、
CSRF、同源校验、限流和账号画像隔离，同时保留原有 API Key 接口。

执行：

```bash
.venv/bin/pytest -q
```

结果：

```text
163 passed
```

其中 159 项不需要网络或外部模型凭据；4 项真实 HTTP 测试绑定
`127.0.0.1` 临时端口并启动独立 Uvicorn，覆盖：

- API Key 非流式、SSE 顺序和轻量并发兼容；
- 浏览器账号注册和 Cookie 会话；
- CSRF header 下的画像写入与读取；
- 画像数据不依赖客户端 `user` 字段。

安全测试另行确认：

- 密码只以 Argon2id 格式存储；原始会话令牌不出现在 SQLite 文件；
- 账号会话过期、撤销和用户级联删除后不可恢复；
- v1 画像迁移到 `legacy:`，未知数据库版本被拒绝；
- 用户名大小写唯一，并发重复注册只有一个成功；
- 错误用户和错误密码使用相同响应；登录失败触发限流；
- Cookie 包含 HttpOnly、SameSite=Strict、Path=/，无 Domain 和持久 Max-Age；
- Cookie 写请求缺少 CSRF 时拒绝，非 allowlist Origin 被拒绝；
- 账号 A、账号 B、legacy API Key 三者的画像空间互不相交；
- API Key 客户端仍通过原 `/v1/models`、`/v1/chat/completions` 和 SSE 测试。

尚未完成生产 HTTPS、Secure Cookie、共享限流、备份恢复、日志脱敏和清小搭账号侧实测，因此本记录只证明本地候选版本。

另使用真实浏览器完成桌面与 `390×844` 移动视口检查，验证登录门禁、注册后自动
进入聊天、刷新恢复会话、画像写入/读取、用户名展示和注销返回登录页；最终浏览器
控制台无 error。首次交互测试发现异步 submit 后使用失效 `event.currentTarget` 的
前端问题，已改为稳定表单引用并增加静态回归断言。

## 8. 2026-08-10 账号与在线 Agent 合并验证

本节追加记录账号分支与在线 Agent 分支合并后的兼容性验证，不替代前述历史结果。
合并后的请求链路先由 API 层校验 API Key 或 Cookie 会话与 CSRF，再把
`account:<uuid>` 或 `legacy:<user>` 可信 subject 交给 Agent；Agent 执行意图路由、
主动画像和静态代码辅导。账号请求体中的 `user` 仍被忽略。

执行结果：

```text
.venv/bin/pytest -q --ignore=tests/integration/test_local_http.py
206 passed

.venv/bin/pytest -q tests/integration/test_local_http.py
4 passed
```

合计 `210 passed`。新增合并验证确认：

- SQLite Schema v2 同时由账号、会话和增强画像事实使用，不再存在独立 schema version 竞争；
- Cookie 账号、不同账号和 API Key legacy 用户的画像保持隔离；
- OpenAI `user`、模型 ID、非流式 envelope、usage 与 SSE role/content/stop/`[DONE]` 顺序保持兼容；
- 登录后的 Web UI 保留画像查看/删除、意图路由和 Python 静态代码辅导入口，不保存匿名 ID 或 API Key；
- 未配置 DeepSeek 时仍可使用规则路由、明确画像识别和 Python AST 诊断；
- 4 项真实 HTTP/SSE 测试在 `127.0.0.1` 临时端口全部通过。

## 9. 2026-08-10 多语言辅导与能力帮助验证

本节记录当前候选版本的最新验证，前述 36/210 项结果保留为历史基线。新增验证覆盖
能力目录、Help 路由优先级、CSDIY 多语言别名、所有保证的 Tree-sitter grammar、
Python/Triton AST、解析器失败降级和未标语言边界。

```text
.venv/bin/pytest -q --ignore=tests/integration/test_local_http.py
250 passed

.venv/bin/pytest -q tests/integration/test_local_http.py
4 passed
```

合计 `254 passed`。验证确认：

- `/help` 和“你目前有哪些功能”只列学习画像与多语言静态代码辅导；
- `/help code`、“代码辅导支持什么语言”和“课程导航是什么”返回目录中的对应帮助/状态；
- Help 在画像观察前返回，不写入学习画像；“C++ 中什么是 virtual”不会误路由到 Help；
- C/C++、CUDA、ISPC、LaTeX 等错误代码返回结构位置，Triton 使用 Python 宿主语法；
- 所有保证的 grammar 从安装包离线加载，测试过程不需要外部模型或网络；
- 未标语言不会默认按 Python 解析，课程专用 DSL 和解析器异常会透明降级；
- 所有代码辅导路径仍为 `ran_code=false`，OpenAI JSON/SSE 顺序和真实 loopback HTTP 保持兼容。
