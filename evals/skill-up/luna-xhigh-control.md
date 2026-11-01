# GPT-6 Luna xhigh 无 Skill 对照

原始输出、冻结快照和运行回执保留在本地`evals/skill-up/evidence/`，已加入ignore，不随源码PR合入。下文以代码路径标注本地证据，获取档案后才能重放；不是可点击的公开下载。

原30例已完成，原始结果为 **6 PASS / 24 FAIL / 0 ERROR**。
仅运行 `without_skill`，执行和语义Judge均为 `gpt-6-luna` / `xhigh`；
没有运行with-Skill、6.1或新增第31例。
逐例输出、原判分与配置（本地归档：`evidence/luna-xhigh-control/summary.md`）已归档。

## 与历史比较

| 对照组 | PASS | FAIL | ERROR |
| --- | ---: | ---: | ---: |
| 历史5.6 Luna high without-Skill | 6 | 23 | 1 |
| 本轮6 Luna xhigh without-Skill | 6 | 24 | 0 |

五个共同PASS为stage2-doc、trigger-boundary、skip-investigation、existing-spec-plan、native-blocked-scope。
其余变化如下；22个共同FAIL保持原始判分。

| Case | 历史5.6 Luna | 本轮6 Luna | 含义 |
| --- | --- | --- | --- |
| research-brief-boundary | FAIL | PASS | 给出了只读比较框架，并区分证据缺口与偏好缺口 |
| research-goal | PASS | FAIL | 诚实说明缺仓库，但没有完整说明研究要支持的架构选择及证据标准 |
| frontend-ui-acceptance | ERROR | FAIL | 本轮取得可判分输出；缺少可复制的独立`/goal`命令，不能视为通过 |

这是描述性比较。模型、思考深度、语义Judge、工具、确定性Judge版本和隔离方式均不同，
不能将差异单独归因于模型升级，也不能用本轮without组推导当前Skill的收益。
历史5.6 Sol without组因23例读取宿主Skill而整组无效，不参与比较。
历史5.6结果未改，本轮没有对历史模型重新运行或重判。

## 实际暴露的问题

- Stage1与多轮确认仍有提前给最终目标、未守确认门的问题。
- fast-small-task和existing-requirement-design-todo实际进入了代码实现；即使报告测试通过，也没有交付用户要求的目标提示。
- goal-char-limit把目标写进state文件而未在响应中呈现命令；preauthorized-permissions和UI案例只给标题或引用段落，没有独立可复制的`/goal`。原始判分均为FAIL，不能把这些失败统称为超过字符限制。
- **confirmation-brief存在一项本轮新确认的Judge误报。** 响应明确说“这一轮先不写最终 `/goal`”，没有输出最终命令，检查器仍因命中行内token报`premature final goal`。本轮冻结规则，未修改Judge、未重判或把该例计为PASS；原始6/24/0统计包含此项误报。修复及冻结输出replay列为后续TODO。

上次两项修复后的Judge沿用当前版本，未为本轮结果再改评分规则。
此处新发现的否定提及问题说明命令token检查仍有边界缺口，不能把全部24个FAIL都解释为模型行为失败。

## 配置与隔离

- 原30例YAML逐字节与历史版本核对，输入不加Skill调用前缀；排除host-recovery-boundary。判分脚本、案例、模型、镜像和重试策略均冻结，配置与哈希随报告保留。
- skill-up 0.14.0使用[最小计划选择补丁](scripts/without-only.patch)，仅保留原生`without_skill`分支，没有修改执行或评分逻辑。Go计划测试、零模型CLI协议测试及实际30个结果的configuration相互印证。
- Codex 0.164.0，每例全新Docker容器；只读根目录、空只读Skill目录、cap-drop ALL、no-new-privileges。没有宿主源码、Skill、Memory、历史结果、Docker socket或凭据挂载。
- 唯一出站通道是可信Responses broker。只有broker读取既有认证；它固定上游、模型和xhigh，拒绝其他路由、模型、深度及远端工具，日志不含正文或认证。没有占位API密钥。
- 20项零模型检查覆盖catalog、凭据不存在、网络拒绝、身份格式及真实shell/Python Judge正反样本；另以确定性引擎跑通完整Docker上传、Judge执行与下载管线。
- 全量审计核对 **231 accepted = 231 HTTP 200 completed = 231原生token_usage_record**，涉及40个归档会话，逐session及request哈希均匹配；全部Luna/xhigh、thread=session，无未归属请求或上游错误。逐容器、上下文及shell transcript审计没有发现目标Skill内容、宿主Memory或额外模型调用。

session/thread是审计关联，不是抵御容器内恶意root伪造记录的强认证；本轮固定案例没有进行此类攻击测试。
这是提示层契约评测，不能证明生成目标中的部署、Chrome验收或review实际发生。

## 环境失败与审计更正

以下尝试全部保留并排除，不与最终v4拼组。

| 尝试 | 观察与处理 |
| --- | --- |
| v1 | Docker默认cp无法向只读rootfs下的tmpfs上传；ERROR，上游请求0 |
| v2 | 真实API已有响应，但stdout和完整rollout下载失败，会话header也未正确归属；保留ERROR及可捕获日志 |
| v3 | 后续脚本Judge因`/tmp noexec`返回126，被框架记为FAIL；停止整批并排除 |
| v4原审计 | 30例执行完成后，两个只查文件名的命令被词面规则误标为读取Skill，父runner退出1；原审计保留 |

上传/下载改为流式处理，`/tmp`显式可执行后，v4重新完整运行30例。
最后的审计误报只涉及`rg --files`及`find -name SKILL.md`：实际输出仅工作目录、空目录项和权限拒绝，
独立审查确认没有Skill内容。更正审计单独保存，真实内容读取与shell展开仍拒绝；
补充正反测试后仅作离线证据收尾，没有重跑模型或改变任何原始判分。
原审计（本地归档：`evidence/luna-xhigh-control/run/remaining/isolation-audit.json`）与更正审计（本地归档：`evidence/luna-xhigh-control/run/remaining/isolation-audit-reviewed.json`）、
离线收尾脚本、原manifest及所有无效批次均可在归档中复核。
无效尝试另索引9份本地rollout；启动或下载失败项没有完整捕获，未冒称有可判分结果。

本次执行使用的冻结runner/wrapper副本与后续加固的源码明确分开保存。
后续入口已增加显式守卫、严格Docker参数与环境变量白名单、pilot/final逐请求对账及原始结果一致性校验；
优化模式、越权参数和额外同会话请求的拒绝路径均用零模型测试验证，不冒充已用新入口重跑。
旧入口没有保存启动进程的`PYTHONOPTIMIZE`环境快照，因此后补的`-O`探针不能证明当时assert门槛的生效状态。
本轮实际隔离结论依据保存的30份容器元数据、空catalog与上下文、原始输出和全量请求对账；没有观察到实际污染。
收尾已移除专用broker、探针容器及网络，关闭认证挂载；业务容器清理前后保持不变，冻结镜像与证据保留。

## 审查与剩余项

三个独立审查视角已完成源码、结果与证据复审（本地归档：`evidence/luna-xhigh-control/reviews.md`），没有未解决的高严重度问题。
本地静态及针对性检查通过；仅本地提交，不推送，不声称远端CI通过。

后续TODO：修复confirmation-brief的否定提及误报并replay冻结输出；
如需当前Skill收益，再另行冻结同环境的with-Skill配对组。
完整6.1全量及其without对照仍为独立TODO，本次没有执行；Claude Code实测按用户要求在1.3跳过，不作为交付门槛，运行行为未验证。
