# 平台发布记录

> 更新日期：2026-08-08
> 发布状态：本地候选版本已验证，生产发布待执行

## 当前候选版本

当前仓库包含：

- OpenAI 兼容 FastAPI 服务；
- Bearer 密钥鉴权；
- `/v1/models`；
- `/v1/chat/completions` 非流式和 SSE；
- 标准错误响应和流式错误收尾；
- 规则优先的意图路由、主动学习画像和静态代码辅导；
- Lecture 2/8 已审核黄金 StudyKit 只读上下文；
- 本地聊天测试界面；
- 187 项自动化测试。

## 本地启动

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export COURSEPILOT_API_KEY="$(openssl rand -hex 32)"
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

本地聊天地址：

```text
http://127.0.0.1:8000/
```

## 生产环境变量

| 名称 | 必须 | 说明 |
| --- | --- | --- |
| `COURSEPILOT_API_KEY` | 是 | 至少 16 个字符，通过部署平台 Secret 配置 |
| `COURSEPILOT_TEST_MODE` | 否 | 生产环境保持未设置或 `false` |
| `DEEPSEEK_API_KEY` | 否 | 启用低置信路由、画像候选和语义代码建议；未设置时透明降级 |
| `DEEPSEEK_BASE_URL` / `DEEPSEEK_MODEL` | 否 | 复用离线生成器的模型适配配置 |
| `COURSEPILOT_DB_PATH` | 否 | 画像 SQLite 路径；生产必须挂载持久卷 |

禁止将生产密钥写入代码、镜像、日志或 Git。

## 清小搭配置模板

生产域名确认后填写：

```text
baseUrl: https://<production-domain>/v1
credential: <COURSEPILOT_API_KEY 对应值>
```

不得把 `/chat/completions` 重复附加到 `baseUrl`。

## 当前限制

- 当前只执行画像、代码辅导和澄清；其余意图只识别并透明降级；
- 尚未接入正式 Catalog、MaterialSet、SourceChunk 检索或 RAG；
- 课程上下文仅覆盖 Lecture 2/8 人工批准的黄金 StudyKit；
- 代码只做静态分析，始终 `ran_code=false`；
- `user` 是客户端提供的逻辑标识，不是生产授权凭据；
- 尚未完成清小搭生产探测；
- 尚未实测 `file.url`；
- 本地测试不能证明云端代理不会缓冲 SSE；
- 本地测试不能证明云端冷启动满足清小搭超时要求。

## 降级方案

- 流式代理不稳定：保留非流式 JSON；
- 文件输入不可用：使用公开链接、文本粘贴或预上传样板资料；
- 长期状态不可用：输出可复制状态卡；
- DeepSeek 不可用：保留规则路由、显式画像识别和 Python AST 诊断；
- 画像数据库不可用：继续本轮临时画像和代码辅导，并提示未保存；
- 云端候选版本异常：回退到最近一个完整测试通过的提交。

## 发布后检查

- [ ] `/health` 返回 200；
- [ ] 正确密钥访问 `/v1/models` 返回 200；
- [ ] 错误密钥返回 401；
- [ ] 非流式 JSON 正常；
- [ ] SSE 逐帧到达并以 `[DONE]` 结束；
- [ ] 闲置后冷启动正常；
- [ ] 清小搭四项探测全绿；
- [ ] 清小搭真实试聊成功；
- [ ] 平台限制和降级结论已回填到验证记录。
