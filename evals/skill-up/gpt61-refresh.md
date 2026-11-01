# GPT-6.1 Sol high 定向实测与 Skill 精简

PR复审补充：以下模型结果对应当时冻结快照，不是当前修订Skill的新模型评测。R4补回契约快照的主文为14265字符、long参考6224字符；当前主文另补明确的循环反馈传递要求，为14449字符，long参考不变；历史精简表中的13163/6055保留为原实测版本。R1判分修复已对Luna的12份受影响既有输出做同镜像重放，脚本状态与上一版校准一致；原始成绩不覆盖。

原始输出、冻结快照和运行回执保留在本地`evals/skill-up/evidence/`，已加入ignore，不随源码PR合入。下文以代码路径标注本地证据，获取档案后才能重放；不是可点击的公开下载。

核查日期2026-10-30。**GPT-6.1 Sol已有真实with-Skill定向实测；尚未执行的是完整31例及without-Skill全量对照。** 后续用户限定只测Luna后没有新增6.1运行，本页保留此前结果。

| 项目 | 已核实配置与结果 |
| --- | --- |
| 执行模型 | `gpt-6.1-sol / high`，Codex 0.164.0 |
| 语义评分模型 | `gpt-6.1-terra / high`；确定性脚本评分另列 |
| 主要受控16例 | 原始14 PASS / 2 FAIL / 0 ERROR；两项词面误报用同一输出重判PASS，原FAIL保留 |
| 最终bundle补测 | batch-goal、host-recovery-boundary两次原始PASS；后者与16例重叠 |
| 实际覆盖 | 17个唯一case，包含六个历史失败及选定边界；不是单一最终bundle的17/17或完整31例通过 |

逐项输出、原判分、重判与冻结配置（本地归档：`evidence/gpt61-refresh/summary.md`）和含精确模型的机器汇总（本地归档：`evidence/gpt61-refresh/summary.json`）均已归档。16例来自controlled-research-v2、controlled-after-rest及controlled-after-boundaries；补测来自另一个final-followup快照，不合并伪装成同一批次。

此批用显式Skill配置约束catalog，仍非OS密闭隔离，不作为干净without对照；早期受污染自然六例另存，不能当作精简效果。后续[GPT-6 Luna xhigh实测](../../docs/luna-xhigh-trial.md)的模型、深度和Docker协议不同，结果分列，不能直接作模型排名。历史5.6成绩不改。

## 来源与适用边界

[GPT-6 官方指导](https://developers.openai.com/api/docs/guides/latest-model?model=gpt-6.1-sol)
明确将 Astra 的行为建议作为 GPT-6 家族的起点，要求对所选模型和任务验证。
本次保留 Sol 执行、Terra 评分，固定 high，不将 Astra 的观察直接当作 6.1 实测。
[官方 Skill 精简建议](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra)
支持明确触发条件、按需加载参考和移除过度流程；跨模型使用时仍需保留必要契约。
因此此次集中去重，不删除历史失败对应的边界，也不宣称官方样例中的效率收益适用于本项目。

## 工具与评测口径

- skill-up 0.14.0，发行源码固定；CI 校验 installer SHA256，安装器再校验发行包。
- 本机 Codex 0.164.0，配置固定版本避免 adapter 安装旧默认。执行 gpt-6.1-sol high，语义 Judge gpt-6.1-terra high。
- 31 个配置用例全部 validate/dry-run；默认仅 with-Skill，生成 state 文件纳入产物。真实受控 Stage1 未创建任务文档，Stage2 只创建 state；before compaction 的 expect gate 失败后 state 仍成功归档，验证了失败时产物采集。
- 多 Judge 的真实 CLI smoke 证明单次 execution、顺序共享 runtime、前项失败后继续评分、expect 失败不增分。该验证使用确定性引擎，没有调用模型。
- 新 `host-recovery-boundary` 使用结构与语义两个独立 Judge；共享文件系统不等于隔离。case 需所有成员通过，成员平均分不是 case 通过率。
- 新版修复 expect 失败时的评分分母；不能把新汇总直接拼接到历史成绩。

本地工具证据在 `.eval-work/tool-upgrade/`；[smoke 脚本](scripts/test-skill-up-upgrade.py)
已加入CI。本报告初次封存时仅本地提交；后续已开放[PR #5](https://github.com/imbajin/goal-prompt/pull/5)，当前远端检查以该PR为准，未因此重跑本页6.1批次。

## 精简与可控问题

| 内容 | 精简前 Unicode 字符 / bytes / lines | 精简后 Unicode 字符 / bytes / lines |
| --- | --- | --- |
| SKILL.md | 26214 / 26256 / 499 | 13163 / 13179 / 225 |
| long-goal-execution.md | 9241 / 9261 / 200 | 6055 / 6055 / 100 |
| scenarios.md | 5247 / 5251 / 103 | 5372 / 5376 / 105 |

长度按 UTF-8 文件实测；不是 token 数。parallel/UI/learning 三个参考文件保留；
scenarios 的 Batch 分母规则在收尾对齐，最终补测单列。
主文件合并重复路由、确认说明、文件职责和输出模板，参考仍按场景加载。
实际读取内容与会话累计 input_tokens 分开记录，不将累计输入误作初始 context，
不将单次运行时长或长度变化直接当作质量、token 或成本收益。

已修复的问题：

- 删除写死的宿主状态枚举，要求遵守当前宿主契约；单项三次尝试不等于跨 goal turns 的 blocked audit。
- 用户任务规则不能绕过更高优先级宿主状态规则；整体 blocked 仍要求所有有意义剩余工作共同受阻。
- 自动唤醒、额度重置时间和恢复命令必须核实，能力未知时保留人工恢复入口。平台 capacity、额度和暂停机制不属于 Skill 修复目标。
- 分母明确才报百分比；保留用户明确指定的进度格式和 reviewer 人数。
- 用户要求基于已批准且覆盖结果/范围的材料生成最终目标时，允许最小必要初始化；不能为已确定内容重复索取确认。
- 实测后保留两项具体要求：当前响应解释每项策略覆盖的实际后果；深度行为变更的重大里程碑和最终集成都需独立审查，不能只在最后审查。

| 保留契约 | 位置与验证关注点 |
| --- | --- |
| 默认确认与显式跳过/委托 | SKILL 路由；确认 brief、multiturn、skip、delegated 定向用例 |
| 上传、已有凭据、Git/PR 等范围内预授权 | SKILL 内联约束；preauthorized-permissions，凭据不可伪造/披露 |
| 多操作目标消歧 | 证据支持单目标直接记录，多实质目标才问范围；打包基础用例保留，本轮未全量执行 |
| 不虚构上下文与真实验证命令 | no-fabrication、repository-rule-conflict、已批准三份文档用例 |
| 最小状态与压缩不丢门槛 | deep-compression、goal-char-limit、compaction-checkpoint |
| 宿主恢复/blocked 和独立工作 | native-blocked-scope、host-recovery-boundary |
| Codex / Claude Code 通用性 | 不假设同名状态/唤醒 API；安装与静态契约验证不替代 Claude Code 模型实测 |
| 独立审查与提交 | 默认重大行为 3 人、报告 1 人、用户人数优先，修复复审，本地提交默认不推送 |

## 代表样本的实际读取与运行指标

固定协议的 preauthorized-permissions 单样本观察如下，保留 CLI 原始口径：

| 指标 | 精简前 | 精简后 |
| --- | ---: | ---: |
| 主文件读取输出 Unicode 字符 | 26214 | 13163 |
| long/UI/parallel 三参考合并读取字符 | 13170 | 9984 |
| 额外场景读取字符 | 0 | 标题索引126 + Feature节457 |
| Agent duration_ms | 137588 | 152587 |
| skill-up result.input_tokens（派生口径） | 220443 | 222886 |
| CLI 原生 input_tokens 字段 | 123931 | 122022 |
| CLI 原生 cached_input_tokens 字段 | 96512 | 100864 |
| Agent output_tokens | 5039 | 5713 |

读取统计是工具输出字符数，按 transcript 的实际 cat/sed/rg 内容核对，排除目录列表和仅检查路径存在的输出；
合并读取按整个命令输出计数，不能冒充某一个参考文件的独立长度。
Codex 的显式调用还会原生注入完整主 Skill；部分多轮案例不再额外cat，其他案例会重复读取。
原生注入与工具读取分开审计，不能将本表当作初始context或完整token用量。
skill-up 0.14.0 的 [Codex adapter](https://github.com/alibaba/skill-up/blob/v0.14.0/internal/agent/codex.go)
将原生 input_tokens 与 cached_input_tokens 等字段相加；本次两个代表的报告值都等于
原生 input + cached。因此该派生字段不能不加说明地当作原生用量或计费口径。

第二代表 compaction 的同口径观察为：Agent duration_ms 144788 → 140732，
skill-up input_tokens 219580 → 226923；CLI input 123708 → 119275，cached 95872 → 107648，
output 5255 → 5671。两样本的原生 input 字段小幅下降、output 上升，耗时一增一减。
源文件变短并未证明普遍 token、成本或延迟收益。
原生及派生字段、来源哈希见归档 token-metrics.json（本地归档：`evidence/gpt61-refresh/token-metrics.json`）。会话累计输入与初始 context 不同，Agent duration 与包含 Judge 的 case wall time 也不同。
单样本不能证明稳定收益或退化；后续完整复测应分别采集质量、累计 token、延迟和重复读取。

## 测量修正

真实 pilot 及受控验证暴露以下词面误判，原始输出和原 FAIL 均保留：

1. `confirmation-brief` 把 `.codex/skills/goal-prompt/` 路径误判成提前输出命令。
   修正为独立命令 token 检查，保留路径正样本及真实命令负样本。
2. `preauthorized-permissions` 不接受“此授权不创造工具、会话、凭据或权限”。
   修正为接受该否定表达，新增相反授权语义的负样本；凭据安全、范围、不得重问和独立工作等原断言保留。
3. 受控 preauth 输出“不得因此重复请求许可、等待、延期或标记 blocked”，旧词面检查不接受。
   当前脚本接受该同义否定，仍拒绝允许再次请求许可及前后矛盾的授权。
4. `goal-char-limit` 已写“门槛，共12/12项”，但旧检查只接受数字在门槛之前。
   修正双向计数与数字边界，保留3999/4001长度边界；拒绝11/12、13/13、二十二和十二十二，未降低12项门槛要求。

前后对比必须用同一修正 Judge 重判冻结输出，并同时展示原始 verdict。
重判不调用执行模型，不算新的实测，也不算 Skill 改善。

## 调用与隔离口径

用户确认采用双轨验证。自动路由保留原输入、输出和 verdict；核心契约测试在
原始首个用户回合前加固定显式调用前缀，原始输入与实际派发输入同时归档。
精简前后比较只在相同前缀、隔离配置、模型/effort/Judge/策略下进行，不将调用变化算作 Skill 改善。
这也符合[官方 Skill 评测建议](https://developers.openai.com/blog/eval-skills)对显式、隐式和负触发的区分。

最早的自然调用批次使用 skip_host_skill_discovery，但实际 catalog 仍包含宿主 Skill。
`research-goal` 未读取目标；`no-fabrication` 读取了宿主 write Skill。这是已确认的污染反例，
不是精简退化的可靠证据，相关批次保留但不能用于隔离效果结论。
新版运行器用显式 skills.config 禁用发现的 33 个宿主 Skill；零模型 prompt-input
已确认 catalog 仅含工作区目标，实际20次受控执行均确认注入精确冻结主Skill全文，其中17次还有工具读取；runner catalog仅目标，语义Judge catalog为空。
完整审计（本地归档：`evidence/gpt61-refresh/controlled-audit-summary.json`）记录了模型/high、原生注入、工具读取及无宿主读取异常线索。
该配置仍不是OS读边界，不用于宣称干净的without-Skill对照。

## 真实定向结果

| 冻结批次 | 原始结果 | 用途与限制 |
| --- | --- | --- |
| 受控精简前2例 | 1 PASS / 1 FAIL / 0 ERROR | 授权及检查点同条件代表比较 |
| 受控精简后6历史 | 5 PASS / 1 FAIL / 0 ERROR | preauth词面误判，当前script replay PASS |
| 受控精简后10边界 | 9 PASS / 1 FAIL / 0 ERROR | 12/12计数词面误判，当前script replay PASS |
| 最终bundle受影响2例 | 2 PASS / 0 FAIL / 0 ERROR | Batch规则及宿主恢复分支补测，另一个冻结快照 |

受控16例逐项如下；`replay PASS`只表示同一真实模型输出的脚本重判，没有重跑执行模型。

| 案例 | 原始结果 | 当前脚本重判 |
| --- | --- | --- |
| research-goal | PASS | 不需要 |
| no-fabrication | PASS | 不需要 |
| repository-rule-conflict | PASS | 不需要 |
| existing-requirement-design-todo | PASS | 不需要 |
| preauthorized-permissions | FAIL | PASS |
| confirmation-brief | PASS | PASS |
| multiturn-confirmation | PASS | 不需要 |
| multiturn-correction | PASS | 不需要 |
| deep-compression-gates | PASS | 不需要 |
| goal-char-limit | FAIL | PASS |
| compaction-checkpoint | PASS | 不需要 |
| native-blocked-scope | PASS | 不需要 |
| skip-investigation | PASS | 不需要 |
| delegated-judgment | PASS | 不需要 |
| host-recovery-boundary | PASS | 不需要 |
| trigger-boundary | PASS | 不需要 |

4,000字符案例正文为1606个Unicode字符，并保留5名独立审查者、全部模块及子门槛；
该结果来自Codex执行，不能当作Claude Code实机兼容证明。
最后发现Batch旧规则仍允许未知分母估算时，保持上述16例快照不变，仅对齐受影响参考、打包基础eval及设计说明，
再以最终bundle补测固定8项批任务与未知分母/宿主恢复，两例均原始PASS。
没有把原16例标为整个最终bundle的重新执行；完整31例仍是TODO。

受控精简前 compaction 的原FAIL仅因 expect 要求固定英文Progress，而输出使用中文进度说明，
script被gate跳过；恢复和里程碑提交内容实际存在。该FAIL保留，不将精简后PASS解释为恢复语义提升。

原自然六例结果保留为2 PASS / 4 FAIL / 0 ERROR；该批次存在host catalog污染，不能计算精简效果。
其中confirmation的FAIL是出现否认生成目标的字面命令token，并非实际提前生成可执行目标；仍保留按当前契约的FAIL。
研究/证据不足brief的自动触发与明确目标准备之间仍需独立验证，未为提高分数扩大到普通写作任务。

原始CLI/rollout/HTML及完整工作区证据保留在 `.eval-work/<batch>/`；提交的小体积证据保留配置、
输出、判分、生成state和来源哈希，不复制凭据或完整rollout。

## 检查与审查

最终31例validate/dry-run、所有确定性正反样例、汇总器状态自测和安装文件比对通过。
Codex与Claude Code项目内copy安装均为9个文件，逐字节匹配最终Skill；完整评测与报告不随Skill安装。
三名独立只读审查及修复复审（本地归档：`evidence/gpt61-refresh/reviews.md`）完成，无未解决高严重度问题。
原始输出中合法的Markdown行尾双空格逐字节保留，.gitattributes仅对归档response允许该硬换行，不放宽源码检查。
原定向批次初次封存时仅本地提交；后续代码和本报告已随PR #5开放试用，原始模型结果未重跑或改写。

## 后续完整复测 TODO

- [ ] 按[完整复测命令](README.md#full-run-follow-up-command-not-run-in-this-refresh)在最终冻结 revision 上运行全部 31 个 with-Skill 用例。固定 skill-up、Codex、执行/Judge 模型、high、420 秒、重试策略、并发和所有断言；保留 case 级配置/输入/输出/判分/模型来源。
- [ ] 单独建立 without-Skill 全量对照：必须先验证 OS 隔离或等价读边界，隐藏全局 Skill、源码、历史结果和状态。两组用相同原始任务输入及模型/effort/Judge/策略；此次显式目标路径前缀不能直接用于自然 A/B 并宣称单变量收益。逐 transcript 审计；污染 cohort 必须剔除并记录。
- [ ] 对其余 14 例补实际验证：audit-goal、deep-existing-docs、delegated-goal、existing-spec-plan、fast-small-task、frontend-ui-acceptance、parallel-agents-goal、research-brief-boundary、reviewer-stop-condition、stage1-grounded-feature、stage1-long-running、stage1-vague-draft、stage2-doc、stage2-migration。不能从历史 5.6 通过推断 6.1 通过。
- Claude Code实机：按用户要求在1.3跳过，不作为本次交付门槛。安装/静态检查已完成，运行行为未验证；若以后恢复该项，须独立固定execution与兼容Judge配置。

本轮六个历史失败与选定边界已经真实定向执行；上述全量与其他引擎TODO不作为此次完成门槛。
