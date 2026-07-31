# 平台发布记录

> 更新日期：2026-07-31
> 发布状态：本地候选版本已验证，生产发布待执行

## 当前候选版本

当前仓库包含：

- OpenAI 兼容 FastAPI 服务；
- Bearer 密钥鉴权；
- `/v1/models`；
- `/v1/chat/completions` 非流式和 SSE；
- 标准错误响应和流式错误收尾；
- 本地聊天测试界面；
- 36 项自动化测试。

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

禁止将生产密钥写入代码、镜像、日志或 Git。

## 清小搭配置模板

生产域名确认后填写：

```text
baseUrl: https://<production-domain>/v1
credential: <COURSEPILOT_API_KEY 对应值>
```

不得把 `/chat/completions` 重复附加到 `baseUrl`。

## 当前限制

- 回复内容为固定回显，不调用真实模型；
- 尚未接入 CourseManifest、资料解析、RAG 或 StudyKit；
- 尚未完成清小搭生产探测；
- 尚未实测 `file.url`；
- 本地测试不能证明云端代理不会缓冲 SSE；
- 本地测试不能证明云端冷启动满足清小搭超时要求。

## 降级方案

- 流式代理不稳定：保留非流式 JSON；
- 文件输入不可用：使用公开链接、文本粘贴或预上传样板资料；
- 长期状态不可用：输出可复制状态卡；
- 云端候选版本异常：回退到最近一个 36 项测试通过的提交。

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
