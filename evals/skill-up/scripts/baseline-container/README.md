# Luna xhigh 无 Skill 运行容器

此目录只实现原 30 例 without-Skill 对照组的执行隔离，不改变输入、fixture 或判分。
使用 Node 22 和 Codex 0.164.0；构建后以 image ID 冻结，不能以可变 tag 作为运行依据。
镜像包含 git、bash、Python、curl、ripgrep，供案例中的本地工程操作使用。

## 边界

每例新建容器，根文件系统只读，所有 capability 移除，启用 no-new-privileges。
只有 `/workspace`、`/tmp`、`/root/.codex` 为临时可写目录；`/root/.codex/skills`
单独覆盖为空只读 tmpfs，避免内置 Skill 落盘。Agent 不挂载宿主路径、源码、历史结果、
Memory、Docker socket 或凭据。框架只复制当前例 fixture，判分在生成结束后执行。
`/tmp` 必须显式使用 `exec`，以便 chmod 700 后直接执行真实 shell/Python judge；
Docker tmpfs 默认的 noexec 会把这些判分误作 Permission denied。其余临时目录保留
noexec。派发前检查真实 mount 选项，并上传脚本验证直接执行及判分正负样本。

可信宿主启动守卫在派发前调用 `lock-network.sh`，设置内核规则，只允许 Agent 访问
broker 的 IP:3128。Agent 无 NET_ADMIN，不能更改规则；直接公网、宿主网关和其他服务
访问均被阻断。可信设置阶段的 privileged exec 不赋予后续 Agent 进程该权限。

`api-broker.py` 是独立可信服务，只有它把既有 auth.json 以只读方式挂载到
`/run/secrets/codex-auth.json`。它只接受 `POST /v1/responses`、`gpt-6-luna`、
`reasoning.effort=xhigh`、流式请求及本地 function/custom/namespace 工具，拒绝其他
路由、模型、思考深度和远端工具。它只转发到固定 ChatGPT Codex Responses 地址，
从内存注入既有认证，不提供通用 CONNECT，不返回上游错误正文或身份 headers。
日志只记录状态、来源 IP、模型、深度、请求/会话哈希和计数，不记录正文或认证。
会话来自原生 CLI 的 `session-id` / `thread-id` headers，缺失时只回退到
`x-codex-turn-metadata` 对应字段；要求有效 UUID，冲突或缺失时在读取认证前拒绝。
分别保留 session/thread 哈希供宿主与归档 rollout 核对，不把缓存 key 当作身份。
字段契约依据 [Codex 0.164.0 headers 实现](https://github.com/openai/codex/blob/rust-v0.164.0/codex-rs/codex-api/src/requests/headers.rs)
及 [SessionMeta 定义](https://github.com/openai/codex/blob/rust-v0.164.0/codex-rs/protocol/src/protocol.rs)。

Codex 使用自定义 Responses provider，`requires_openai_auth=false`，没有占位密钥。
`codex-wrapper.py` 固定模型与深度，关闭插件、应用、Memory、多 Agent、搜索等特性。
即使直接调用原生 CLI 绕过 wrapper，broker 仍拒绝其他模型或深度。

## 接口与证据

`isolation.json` 是宿主启动器使用的接口，包含 `image_id`、`create_extra_args`、
`after_start_command`、broker IP 和零模型检查结果。Agent 的 create 参数无 bind。
`after_start_command` 只能由可信宿主在容器启动后、模型派发前执行。
broker 单独连接 internal/egress 两张网络，经可信宿主出口代理访问固定上游。
不要重设 HOME/CODEX_HOME，不把认证复制到镜像、Agent、fixture 或报告。

本批证据位于 `.eval-work/luna-control-isolation/`：`probe-broker.py`、
`probe-inspect-broker.json`、`iptables-broker.txt`、`broker-*.stdout/stderr` 和
`broker-guard-events.jsonl`。`api-broker.py --self-test` 不读认证、不调用模型。
真实 HTTP 拒绝探针也不转发上游。零模型检查只能证明隔离与请求守卫，首次正式案例
还须验证真实 Responses 兼容性；失败应记录为基础设施失败，不能算案例通过。

仅操作 `goal-prompt-luna-control-*` 专用资源。评测完成后按本批 registry 清理，
保留输出、判分和配置证据，不清理其他业务容器或网络。
