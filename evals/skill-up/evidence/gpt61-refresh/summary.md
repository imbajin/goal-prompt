# GPT 6.1 定向实测证据

with_skill 仅表示已安装目标 Skill，不证明实际加载。原生正文注入、工具读取及宿主 catalog 见 controlled-audit-summary 与各运行 transcript-audit；实际污染审计以主报告为准。
case verdict 原样取自 skill-up result；尚无最终 result 时取 case_completed 事件并标明来源。grading pass_rate 仅为断言统计。
cohort pending 与 case 状态分别记录；RUNNING 表示已派发未完成，NOT_RUN 表示无派发证据。脚本 replay 单独列出，旧 FAIL 保留。
这是 prompt-level with-Skill 实测，不证明生成目标已执行；未覆盖完整复测、without-Skill 对照或 Claude Code 实机行为。输入列为 skill-up 派生口径，不直接代表 CLI 原生 input 或计费；原生字段另见 token-metrics.json。

| Run | Case | 原始结果 | 当前脚本 replay | skill-up 派生输入 / 输出 tokens |
| --- | --- | --- | --- | --- |
| before-pilot | confirmation-brief | FAIL | PASS | 98331 / 1304 |
| before-rest | preauthorized-permissions | FAIL | PASS | 205034 / 4321 |
| before-rest | existing-requirement-design-todo | PASS | 未重放 | 435532 / 5037 |
| before-rest | compaction-checkpoint | PASS | 未重放 | 311932 / 4735 |
| after-six | research-goal | FAIL | 未重放 | 104938 / 606 |
| after-six | no-fabrication | PASS | 未重放 | 124561 / 917 |
| after-six | repository-rule-conflict | FAIL | 未重放 | 206333 / 2616 |
| after-six | existing-requirement-design-todo | FAIL | 未重放 | 224850 / 4529 |
| after-six | preauthorized-permissions | PASS | PASS | 172028 / 3930 |
| after-six | confirmation-brief | FAIL | FAIL | 73437 / 1161 |
| controlled-research-v2 | research-goal | PASS | 未重放 | 126600 / 1339 |
| controlled-before-v2 | preauthorized-permissions | PASS | PASS | 220443 / 5039 |
| controlled-before-v2 | compaction-checkpoint | FAIL | 未重放 | 219580 / 5255 |
| controlled-after-rest | no-fabrication | PASS | 未重放 | 120743 / 1363 |
| controlled-after-rest | repository-rule-conflict | PASS | 未重放 | 175586 / 4580 |
| controlled-after-rest | existing-requirement-design-todo | PASS | 未重放 | 230935 / 5593 |
| controlled-after-rest | preauthorized-permissions | FAIL | PASS | 222886 / 5713 |
| controlled-after-rest | confirmation-brief | PASS | PASS | 74107 / 1526 |
| controlled-after-boundaries | multiturn-confirmation | PASS | 未重放 | 425215 / 5881 |
| controlled-after-boundaries | multiturn-correction | PASS | 未重放 | 308038 / 6590 |
| controlled-after-boundaries | deep-compression-gates | PASS | 未重放 | 178826 / 3966 |
| controlled-after-boundaries | goal-char-limit | FAIL | PASS | 223607 / 6482 |
| controlled-after-boundaries | compaction-checkpoint | PASS | 未重放 | 226923 / 5671 |
| controlled-after-boundaries | native-blocked-scope | PASS | 未重放 | 162942 / 4923 |
| controlled-after-boundaries | skip-investigation | PASS | 未重放 | 90010 / 1735 |
| controlled-after-boundaries | delegated-judgment | PASS | 未重放 | 363445 / 5838 |
| controlled-after-boundaries | host-recovery-boundary | PASS | 未重放 | 154788 / 6193 |
| controlled-after-boundaries | trigger-boundary | PASS | 未重放 | 44434 / 97 |
| final-followup | batch-goal | PASS | 未重放 | 163106 / 3945 |
| final-followup | host-recovery-boundary | PASS | 未重放 | 174002 / 5690 |

## before-pilot

运行状态 `completed`；本地原始目录 `/Users/zhu/.codex/worktrees/3443/goal-prompt/.eval-work/before-pilot`。
工具 `skill-up version 0.14.0` / `codex-cli 0.164.0`；reasoning `high`。
调用方式 invocation_mode：`unknown（旧运行未记录；不推断为显式调用）`；精确 invocation_prefix 见 summary.json 与冻结 manifest。
运行时原隔离声明（含旧 skip-only 声明，仅作原始记录）：每 case 使用 skill-up 新工作区；沿用当前授权登录，HOME/CODEX_HOME 均未改写。禁 host discovery 与附加能力；非 OS hermetic。
目标读取、host catalog 与实际污染审计以 transcript-audit 和主报告为准；原声明不等于已证实隔离。

- `confirmation-brief` 原始 verdict **FAIL**。
  - 未通过断言 `script: /Users/zhu/.codex/worktrees/3443/goal-prompt/.eval-work/before-pilot/snapshot/skill-up/fixtures/scripts/check-confirmation-brief.sh`：script exited with code 1 [stderr: premature final goal]
  - [grading.json](before-pilot/reports/iteration-1/confirmation-brief/with_skill/grading.json)；SHA256 `5f40bc8ecf4783cea8a191e0141d5b29e1cd050b49be502040fd9250250bf378`。
  - [response.md](before-pilot/reports/iteration-1/confirmation-brief/with_skill/outputs/response.md)；SHA256 `042172c6875d663ff32c58bddd4eead19d8575c4f598664a0aff65bdc464d67f`。
  - [当前脚本 replay](before-pilot/reports/iteration-1/confirmation-brief/with_skill/current-script-replay.json)：exit `0`，脚本 SHA256 `8aa4df50ec7795143a1d800db28cc9302d29cd79dd7d0f53438eff7b4bb8fd92`；不修改原 verdict。

## before-rest

运行状态 `completed`；本地原始目录 `/Users/zhu/.codex/worktrees/3443/goal-prompt/.eval-work/before-rest`。
工具 `skill-up version 0.14.0` / `codex-cli 0.164.0`；reasoning `high`。
调用方式 invocation_mode：`unknown（旧运行未记录；不推断为显式调用）`；精确 invocation_prefix 见 summary.json 与冻结 manifest。
运行时原隔离声明（含旧 skip-only 声明，仅作原始记录）：每 case 使用 skill-up 新工作区；沿用当前授权登录，HOME/CODEX_HOME 均未改写。禁 host discovery 与附加能力；非 OS hermetic。
目标读取、host catalog 与实际污染审计以 transcript-audit 和主报告为准；原声明不等于已证实隔离。

- `preauthorized-permissions` 原始 verdict **FAIL**。
  - 未通过断言 `script: /Users/zhu/.codex/worktrees/3443/goal-prompt/.eval-work/before-rest/snapshot/skill-up/fixtures/scripts/check-preauthorized-permissions.sh`：script exited with code 1
  - [grading.json](before-rest/reports/iteration-1/preauthorized-permissions/with_skill/grading.json)；SHA256 `6f459beb313c78537234dd31e54e4109178686546b2dddf4ddfd96fd87a38d5f`。
  - [response.md](before-rest/reports/iteration-1/preauthorized-permissions/with_skill/outputs/response.md)；SHA256 `b175ece9f97e9e1040f0a730083793395660676617030c911ecf9608faf57700`。
  - [当前脚本 replay](before-rest/reports/iteration-1/preauthorized-permissions/with_skill/current-script-replay.json)：exit `0`，脚本 SHA256 `639c808bb029b8f62a298dab0d77556cf340646f9857b1e07277ebb967ef9b0b`；不修改原 verdict。
- `existing-requirement-design-todo` 原始 verdict **PASS**。
  - [grading.json](before-rest/reports/iteration-1/existing-requirement-design-todo/with_skill/grading.json)；SHA256 `a93c8f7d2079dd0d7fc9992da184771e428e6bb47136b694d8427e345e1ec373`。
  - [response.md](before-rest/reports/iteration-1/existing-requirement-design-todo/with_skill/outputs/response.md)；SHA256 `c2757029977b5a80cda5749f9f14abbaee23fd18cc39bd6984e470391bf8c0ae`。
- `compaction-checkpoint` 原始 verdict **PASS**。
  - [grading.json](before-rest/reports/iteration-1/compaction-checkpoint/with_skill/grading.json)；SHA256 `94c8d1ef803e0aa3e28a6646f8c216e1d11d50458b683cb35b4482502266b509`。
  - [response.md](before-rest/reports/iteration-1/compaction-checkpoint/with_skill/outputs/response.md)；SHA256 `f7ea48f34f6a219f4bd6efa28b36a3f75768ae86cca6c5664cab30cb28430567`。

## after-six

运行状态 `completed`；本地原始目录 `/Users/zhu/.codex/worktrees/3443/goal-prompt/.eval-work/after-six`。
工具 `skill-up version 0.14.0` / `codex-cli 0.164.0`；reasoning `high`。
调用方式 invocation_mode：`unknown（旧运行未记录；不推断为显式调用）`；精确 invocation_prefix 见 summary.json 与冻结 manifest。
运行时原隔离声明（含旧 skip-only 声明，仅作原始记录）：每 case 使用 skill-up 新工作区；沿用当前授权登录，HOME/CODEX_HOME 均未改写。禁 host discovery 与附加能力；非 OS hermetic。
目标读取、host catalog 与实际污染审计以 transcript-audit 和主报告为准；原声明不等于已证实隔离。

- `research-goal` 原始 verdict **FAIL**。
  - 未通过断言 `把研究要支持的架构决策和证据标准写清楚，而不是把“研究”本身当作结果。`：final_message 计划比较两种缓存实现的语义、失效策略、并发行为和维护成本，并列出适用条件及迁移影响。; final_message 表示当前缺少项目源码，无法提供文件、行号和测试证据。 | Failures: 没有明确研究要支持的具体架构决策。; 没有写清判断方案所需的证据标准。
  - 未通过断言 `明确只读范围、真实引用要求、缺失证据与用户偏好的区别。`：transcript 开头说明本轮进行只读研究、不修改代码；final_message 也确认未修改文件。; final_message 区分已有测试和实际运行结果，并指出当前缺少文件、行号和测试证据。 | Failures: 没有明确要求使用可核查的真实引用。; 没有说明如何区分证据缺失与需要用户确认的偏好。
  - 未通过断言 `没有机械加入行为变更代码所需的独立 reviewer 门槛，也没有提前生成最终 /goal；允许按 research 规则要求 1 名只读报告 reviewer 复核引用与结论；语义上请用户确认即可，不要求固定状态字符串。`：final_message 明确表示本轮未生成 /goal。; transcript 和 final_message 没有加入针对行为变更代码的独立 reviewer 门槛。; final_message 请求提供目标仓库路径，但没有请求用户确认研究 brief。 | Failures: 没有在语义上请求用户确认研究 brief。
  - [grading.json](after-six/reports/iteration-1/research-goal/with_skill/grading.json)；SHA256 `8870c23c38c824320d26800b99b26f157b37aadd6e9eb4be31ee5428e144953b`。
  - [response.md](after-six/reports/iteration-1/research-goal/with_skill/outputs/response.md)；SHA256 `8673e1c4d77cbaf8a446cb6f6a925ae158c029369d5ac910df90fbec5d4cf73a`。
- `no-fabrication` 原始 verdict **PASS**。
  - [grading.json](after-six/reports/iteration-1/no-fabrication/with_skill/grading.json)；SHA256 `cad464bcda97db84bb0907d2f40a867b650609d20f5555c8e5fe20b2e7cab38c`。
  - [response.md](after-six/reports/iteration-1/no-fabrication/with_skill/outputs/response.md)；SHA256 `41e955ca63792ab90c88e5d735559f4ac0db71a0697fc5644e04c5bdfce1380c`。
- `repository-rule-conflict` 原始 verdict **FAIL**。
  - 未通过断言 `普通策略文档属于任务材料；以用户最新明确指令为优先生成最终 /goal，同时提醒被覆盖的仓库规则、影响和风险。`：final_message 按用户指令生成 /goal，要求删除旧导出、引入认证依赖并跳过 typecheck。; workspace_diff 中的状态文件明确写出“最新用户要求优先于仓库政策”，并列明三条被覆盖的要求。; final_message 要求后续记录未验证项及影响，并要求迁移调用方，但没有直接说明覆盖这些规则可能带来的具体影响和风险。 | Failures: 未向用户具体提醒删除公开接口的兼容性影响、新增依赖的风险，以及跳过 typecheck 可能留下的检查缺口；要求执行时记录影响不能代替当前提醒。
  - [grading.json](after-six/reports/iteration-1/repository-rule-conflict/with_skill/grading.json)；SHA256 `4fadc52b00044d553a7ba1a9c83015e212e4abb10c66d222a4dad9f5337b2b2a`。
  - [response.md](after-six/reports/iteration-1/repository-rule-conflict/with_skill/outputs/response.md)；SHA256 `70c6ed40fdb0d9504caa00852835336ff0e6096c5e0b6ca9870298fb6291ed6e`。
- `existing-requirement-design-todo` 原始 verdict **FAIL**。
  - 未通过断言 `按中大型深度任务设计恢复入口、独立工作重排和重大里程碑 3 reviewer，同时不重新询问三份文档已确定的决定。`：final_message 采用 deep 模式，以 .goal-task/import-migration/state.md 作为执行、证据和恢复入口，并要求将等待项移到独立工作之后。; workspace_diff 中的 state.md 要求恢复时核对 HEAD、工作区和证据，且不改写三份定稿的决定。; final_message 和 state.md 均要求 3 名独立 reviewer 审查最终集成 diff，并在修复后复审。 | Failures: 审查门槛只明确覆盖最终集成 diff，未要求在重大行为变更里程碑安排 3 名独立 reviewer。
  - [grading.json](after-six/reports/iteration-1/existing-requirement-design-todo/with_skill/grading.json)；SHA256 `b2f8e9518aeb7c4455f8cfaa84c5b7d061f2b1a067d5768b0a2092a7b83f23fe`。
  - [response.md](after-six/reports/iteration-1/existing-requirement-design-todo/with_skill/outputs/response.md)；SHA256 `c38150a078b000abb63ce30941c50753fc27ffb350d69c653bff2072e3c65eab`。
- `preauthorized-permissions` 原始 verdict **PASS**。
  - [grading.json](after-six/reports/iteration-1/preauthorized-permissions/with_skill/grading.json)；SHA256 `16b6ca6cd8dfeda4075eaace0e600b5559009ccbeebedc662e7008fdef2cf36c`。
  - [response.md](after-six/reports/iteration-1/preauthorized-permissions/with_skill/outputs/response.md)；SHA256 `9da94f3bb1a001d3884cb33de79b0dfd6fa821a3d467cef16523e030de1678b7`。
  - [当前脚本 replay](after-six/reports/iteration-1/preauthorized-permissions/with_skill/current-script-replay.json)：exit `0`，脚本 SHA256 `639c808bb029b8f62a298dab0d77556cf340646f9857b1e07277ebb967ef9b0b`；不修改原 verdict。
- `confirmation-brief` 原始 verdict **FAIL**。
  - 未通过断言 `script: /Users/zhu/.codex/worktrees/3443/goal-prompt/.eval-work/after-six/snapshot/skill-up/fixtures/scripts/check-confirmation-brief.sh`：script exited with code 1 [stderr: premature final goal]
  - [grading.json](after-six/reports/iteration-1/confirmation-brief/with_skill/grading.json)；SHA256 `296b15da15c7b4c27957725e7fa46dd27fd60dc7344ff83f30d8fc21d823a13d`。
  - [response.md](after-six/reports/iteration-1/confirmation-brief/with_skill/outputs/response.md)；SHA256 `0eed108dde96bd2aa04ffbb748b7c46ece517b24525cdb41b5c6415fee961eaf`。
  - [当前脚本 replay](after-six/reports/iteration-1/confirmation-brief/with_skill/current-script-replay.json)：exit `1`，脚本 SHA256 `8aa4df50ec7795143a1d800db28cc9302d29cd79dd7d0f53438eff7b4bb8fd92`；不修改原 verdict。

## controlled-research-v2

运行状态 `completed`；本地原始目录 `/Users/zhu/.codex/worktrees/3443/goal-prompt/.eval-work/controlled-research-v2`。
工具 `skill-up version 0.14.0` / `codex-cli 0.164.0`；reasoning `high`。
调用方式 invocation_mode：`explicit`；精确 invocation_prefix 见 summary.json 与冻结 manifest。
运行时原隔离声明（含旧 skip-only 声明，仅作原始记录）：每 case 使用 skill-up 新工作区；沿用当前授权登录，HOME/CODEX_HOME 均未改写。显式禁用已发现宿主 Skill（含符号链接）并静态核查 catalog 仅含 workspace target；禁附加能力，实际运行另审计；非 OS hermetic。
目标读取、host catalog 与实际污染审计以 transcript-audit 和主报告为准；原声明不等于已证实隔离。

- `research-goal` 原始 verdict **PASS**。
  - [grading.json](controlled-research-v2/reports/iteration-1/research-goal/with_skill/grading.json)；SHA256 `f41bbca6229b502f9316f01746b2f5ca6aa24cad6e893396e5596be58aeadc47`。
  - [response.md](controlled-research-v2/reports/iteration-1/research-goal/with_skill/outputs/response.md)；SHA256 `042eeed50e6d90ab9bf5b204f1013f1a046e9be38f186bcbed471d45cea1bae1`。

## controlled-before-v2

运行状态 `completed`；本地原始目录 `/Users/zhu/.codex/worktrees/3443/goal-prompt/.eval-work/controlled-before-v2`。
工具 `skill-up version 0.14.0` / `codex-cli 0.164.0`；reasoning `high`。
调用方式 invocation_mode：`explicit`；精确 invocation_prefix 见 summary.json 与冻结 manifest。
运行时原隔离声明（含旧 skip-only 声明，仅作原始记录）：每 case 使用 skill-up 新工作区；沿用当前授权登录，HOME/CODEX_HOME 均未改写。显式禁用已发现宿主 Skill（含符号链接）并静态核查 catalog 仅含 workspace target；禁附加能力，实际运行另审计；非 OS hermetic。
目标读取、host catalog 与实际污染审计以 transcript-audit 和主报告为准；原声明不等于已证实隔离。

- `preauthorized-permissions` 原始 verdict **PASS**。
  - [grading.json](controlled-before-v2/reports/iteration-1/preauthorized-permissions/with_skill/grading.json)；SHA256 `d028858d339dfbc54c88de06bb446ca56be8c45c2aa1af5e1a4d52fc5043a335`。
  - [response.md](controlled-before-v2/reports/iteration-1/preauthorized-permissions/with_skill/outputs/response.md)；SHA256 `2fcf2f0436fc3f6aa534cf39d1dcd11e6a17c6f6d48fd4a660d93838586b8039`。
  - [当前脚本 replay](controlled-before-v2/reports/iteration-1/preauthorized-permissions/with_skill/current-script-replay.json)：exit `0`，脚本 SHA256 `639c808bb029b8f62a298dab0d77556cf340646f9857b1e07277ebb967ef9b0b`；不修改原 verdict。
- `compaction-checkpoint` 原始 verdict **FAIL**。
  - 未通过断言 `expect.must_contain`：output does not contain "Progress"
  - 未通过断言 `script: skill-up/fixtures/scripts/check-compaction-checkpoint.sh`：not evaluated: expect gate failed
  - [grading.json](controlled-before-v2/reports/iteration-1/compaction-checkpoint/with_skill/grading.json)；SHA256 `050d6d035bb26c7692000e86aae476bcf86679093e1610abd164afee2621a6da`。
  - [response.md](controlled-before-v2/reports/iteration-1/compaction-checkpoint/with_skill/outputs/response.md)；SHA256 `9c2ae5cb9089f79c30b5451f7120497b3a6d5d62056b139651923a8184026e93`。

## controlled-after-rest

运行状态 `completed`；本地原始目录 `/Users/zhu/.codex/worktrees/3443/goal-prompt/.eval-work/controlled-after-rest`。
工具 `skill-up version 0.14.0` / `codex-cli 0.164.0`；reasoning `high`。
调用方式 invocation_mode：`explicit`；精确 invocation_prefix 见 summary.json 与冻结 manifest。
运行时原隔离声明（含旧 skip-only 声明，仅作原始记录）：每 case 使用 skill-up 新工作区；沿用当前授权登录，HOME/CODEX_HOME 均未改写。显式禁用已发现宿主 Skill（含符号链接）并静态核查 catalog 仅含 workspace target；禁附加能力，实际运行另审计；非 OS hermetic。
目标读取、host catalog 与实际污染审计以 transcript-audit 和主报告为准；原声明不等于已证实隔离。

- `no-fabrication` 原始 verdict **PASS**。
  - [grading.json](controlled-after-rest/reports/iteration-1/no-fabrication/with_skill/grading.json)；SHA256 `f34834d91b828c6e7f82ce1a86ee1d9684b290072735f4b1cd208da77941f340`。
  - [response.md](controlled-after-rest/reports/iteration-1/no-fabrication/with_skill/outputs/response.md)；SHA256 `9600162b84f09e5d5946332096cb26b598fa645ee5bcd4c15e36c83405a28922`。
- `repository-rule-conflict` 原始 verdict **PASS**。
  - [grading.json](controlled-after-rest/reports/iteration-1/repository-rule-conflict/with_skill/grading.json)；SHA256 `b93d306ad7f6f621ea7f941506b6f861735892902c68974903e2ec7a184c24f8`。
  - [response.md](controlled-after-rest/reports/iteration-1/repository-rule-conflict/with_skill/outputs/response.md)；SHA256 `d181cd10bdb24705e228f0b6bccf0515299d1ca002b218d9840e7f362400c029`。
- `existing-requirement-design-todo` 原始 verdict **PASS**。
  - [grading.json](controlled-after-rest/reports/iteration-1/existing-requirement-design-todo/with_skill/grading.json)；SHA256 `5bc03f820f0e0718a290818594041f73be850f952db564310a42149989dfbf55`。
  - [response.md](controlled-after-rest/reports/iteration-1/existing-requirement-design-todo/with_skill/outputs/response.md)；SHA256 `40c5ed4025c720b0a233a3ab5864fff513679c4e63321d54aa7b2dfb21e213c4`。
- `preauthorized-permissions` 原始 verdict **FAIL**。
  - 未通过断言 `script: /Users/zhu/.codex/worktrees/3443/goal-prompt/.eval-work/controlled-after-rest/snapshot/skill-up/fixtures/scripts/check-preauthorized-permissions.sh`：script exited with code 1
  - [grading.json](controlled-after-rest/reports/iteration-1/preauthorized-permissions/with_skill/grading.json)；SHA256 `958780a1a1ed6daaba4c9fea133319ee7647af06142696c5c4274b739229c3ee`。
  - [response.md](controlled-after-rest/reports/iteration-1/preauthorized-permissions/with_skill/outputs/response.md)；SHA256 `2eceed9665d1d47e2fa5e5d107367c5a4dfd8975d6105c5e83c416fbadaa314a`。
  - [当前脚本 replay](controlled-after-rest/reports/iteration-1/preauthorized-permissions/with_skill/current-script-replay.json)：exit `0`，脚本 SHA256 `639c808bb029b8f62a298dab0d77556cf340646f9857b1e07277ebb967ef9b0b`；不修改原 verdict。
- `confirmation-brief` 原始 verdict **PASS**。
  - [grading.json](controlled-after-rest/reports/iteration-1/confirmation-brief/with_skill/grading.json)；SHA256 `243d02efe35d44774421077bea65f8de83e083afddaaf057a676f2570a608fa1`。
  - [response.md](controlled-after-rest/reports/iteration-1/confirmation-brief/with_skill/outputs/response.md)；SHA256 `65f848e9a6c0211fdbb321b0d5273cd8f13a2acfdd33be00ba1d0d3b4ed14953`。
  - [当前脚本 replay](controlled-after-rest/reports/iteration-1/confirmation-brief/with_skill/current-script-replay.json)：exit `0`，脚本 SHA256 `8aa4df50ec7795143a1d800db28cc9302d29cd79dd7d0f53438eff7b4bb8fd92`；不修改原 verdict。

## controlled-after-boundaries

运行状态 `completed`；本地原始目录 `/Users/zhu/.codex/worktrees/3443/goal-prompt/.eval-work/controlled-after-boundaries`。
工具 `skill-up version 0.14.0` / `codex-cli 0.164.0`；reasoning `high`。
调用方式 invocation_mode：`explicit`；精确 invocation_prefix 见 summary.json 与冻结 manifest。
运行时原隔离声明（含旧 skip-only 声明，仅作原始记录）：每 case 使用 skill-up 新工作区；沿用当前授权登录，HOME/CODEX_HOME 均未改写。显式禁用已发现宿主 Skill（含符号链接）并静态核查 catalog 仅含 workspace target；禁附加能力，实际运行另审计；非 OS hermetic。
目标读取、host catalog 与实际污染审计以 transcript-audit 和主报告为准；原声明不等于已证实隔离。

- `multiturn-confirmation` 原始 verdict **PASS**。
  - [grading.json](controlled-after-boundaries/reports/iteration-1/multiturn-confirmation/with_skill/grading.json)；SHA256 `7808f362d3859f651b55e4e23ceb2ad070f0a7509b3ba48debb7f73636b82a09`。
  - [response.md](controlled-after-boundaries/reports/iteration-1/multiturn-confirmation/with_skill/outputs/response.md)；SHA256 `266615430e009b43dbb417278b1d00a84f849cdf2fb21b27c9716c5f2710a04a`。
- `multiturn-correction` 原始 verdict **PASS**。
  - [grading.json](controlled-after-boundaries/reports/iteration-1/multiturn-correction/with_skill/grading.json)；SHA256 `2aab70cadcc08bbd32eecbae0442d74ad88b84554b9a1039ff8a89505a5fe202`。
  - [response.md](controlled-after-boundaries/reports/iteration-1/multiturn-correction/with_skill/outputs/response.md)；SHA256 `3062ed506c5c8492464a49a103f52c5b7a4d6788c5f28b63433ae99a0bec4b22`。
- `deep-compression-gates` 原始 verdict **PASS**。
  - [grading.json](controlled-after-boundaries/reports/iteration-1/deep-compression-gates/with_skill/grading.json)；SHA256 `5595f24dfc734f880888367a09d4f761e8ee18801b579c68c3d0cb6ef9937ba5`。
  - [response.md](controlled-after-boundaries/reports/iteration-1/deep-compression-gates/with_skill/outputs/response.md)；SHA256 `e561c1f28579c3fe0f77b02e131ea29b7ec4e4a9695eac4fca8de05c20ff1889`。
- `goal-char-limit` 原始 verdict **FAIL**。
  - 未通过断言 `script: /Users/zhu/.codex/worktrees/3443/goal-prompt/.eval-work/controlled-after-boundaries/snapshot/skill-up/fixtures/scripts/check-goal-char-limit-case.py`：script exited with code 1 [stderr: goal body is missing: twelve sub-gates]
  - [grading.json](controlled-after-boundaries/reports/iteration-1/goal-char-limit/with_skill/grading.json)；SHA256 `4b2d9004069138ad921ae035c9d7889bba18d058a72e69677e13b1520f945d85`。
  - [response.md](controlled-after-boundaries/reports/iteration-1/goal-char-limit/with_skill/outputs/response.md)；SHA256 `65ccc20966b406c79a8e21670bebd5f60f7f683f6a6409d8848edff68ade7e7e`。
  - [当前脚本 replay](controlled-after-boundaries/reports/iteration-1/goal-char-limit/with_skill/current-script-replay.json)：exit `0`，脚本 SHA256 `7f7748145881ca7d01d128394674cecb5ae873056bbd69bf6feb9ca3056ecf2c`；不修改原 verdict。
- `compaction-checkpoint` 原始 verdict **PASS**。
  - [grading.json](controlled-after-boundaries/reports/iteration-1/compaction-checkpoint/with_skill/grading.json)；SHA256 `883f95b34e3d06a78b833f9889ce72421149a8ce7143786800126077c5806f3d`。
  - [response.md](controlled-after-boundaries/reports/iteration-1/compaction-checkpoint/with_skill/outputs/response.md)；SHA256 `fa4aadd2ba50f93c59b8849b81094e5b41b559f7f8c28c6b45f10d2564c6051c`。
- `native-blocked-scope` 原始 verdict **PASS**。
  - [grading.json](controlled-after-boundaries/reports/iteration-1/native-blocked-scope/with_skill/grading.json)；SHA256 `88c3bae466c0902f2bfe11e20b8928e4bc9a1c14d6b418c2b1f96b9e487d3c90`。
  - [response.md](controlled-after-boundaries/reports/iteration-1/native-blocked-scope/with_skill/outputs/response.md)；SHA256 `a63dfceaf94bfb214a14149ff1e2e6800eb55f3c54525573bb2806486243da81`。
- `skip-investigation` 原始 verdict **PASS**。
  - [grading.json](controlled-after-boundaries/reports/iteration-1/skip-investigation/with_skill/grading.json)；SHA256 `708e6a2e027152b4641683266c8c664b5c2c216b54c5390fd47483a9fa6cde9c`。
  - [response.md](controlled-after-boundaries/reports/iteration-1/skip-investigation/with_skill/outputs/response.md)；SHA256 `596327eab6b8daa974ee278cfc3f4f1ee2cba01128b0f55a6356912376136795`。
- `delegated-judgment` 原始 verdict **PASS**。
  - [grading.json](controlled-after-boundaries/reports/iteration-1/delegated-judgment/with_skill/grading.json)；SHA256 `433b0082aa954bda73a959b83a6b6b968ea522f27bd56afc66bbc0e38afabe57`。
  - [response.md](controlled-after-boundaries/reports/iteration-1/delegated-judgment/with_skill/outputs/response.md)；SHA256 `1902f8a58babc6a64394d3210eed3b3b36b61a150d4c2de153437a2f3ef62bc2`。
- `host-recovery-boundary` 原始 verdict **PASS**。
  - [grading.json](controlled-after-boundaries/reports/iteration-1/host-recovery-boundary/with_skill/grading.json)；SHA256 `e9b29563025e99a9c973b2322e0b33edd61a0d48f116206b241b3124b2e0241b`。
  - [evaluation.json](controlled-after-boundaries/reports/iteration-1/host-recovery-boundary/with_skill/evaluation.json)；SHA256 `091072b5f112186c4a17de8c5398997fffe707cc073268516099258171f29ffb`。
  - [response.md](controlled-after-boundaries/reports/iteration-1/host-recovery-boundary/with_skill/outputs/response.md)；SHA256 `37b57f33c87bf82b362f9adc71a597075d572deb3691cfd2c551a644adc06a54`。
- `trigger-boundary` 原始 verdict **PASS**。
  - [grading.json](controlled-after-boundaries/reports/iteration-1/trigger-boundary/with_skill/grading.json)；SHA256 `8b857d8a2f9972356d148836fa6ccfa19fcc2239659ae9465e6e57d56591ba8a`。
  - [response.md](controlled-after-boundaries/reports/iteration-1/trigger-boundary/with_skill/outputs/response.md)；SHA256 `adbad1f0642bee884388e2909689a60e3c50d50fa5e4093bca567af6944618fa`。

## final-followup

运行状态 `completed`；本地原始目录 `/Users/zhu/.codex/worktrees/3443/goal-prompt/.eval-work/final-followup`。
工具 `skill-up version 0.14.0` / `codex-cli 0.164.0`；reasoning `high`。
调用方式 invocation_mode：`explicit`；精确 invocation_prefix 见 summary.json 与冻结 manifest。
运行时原隔离声明（含旧 skip-only 声明，仅作原始记录）：每 case 使用 skill-up 新工作区；沿用当前授权登录，HOME/CODEX_HOME 均未改写。显式禁用已发现宿主 Skill（含符号链接）并静态核查 catalog 仅含 workspace target；禁附加能力，实际运行另审计；非 OS hermetic。
目标读取、host catalog 与实际污染审计以 transcript-audit 和主报告为准；原声明不等于已证实隔离。

- `batch-goal` 原始 verdict **PASS**。
  - [grading.json](final-followup/reports/iteration-1/batch-goal/with_skill/grading.json)；SHA256 `db924140a04493e03dc734f3b0210607261acb582e653f8938d2dd3c3fb9c24d`。
  - [response.md](final-followup/reports/iteration-1/batch-goal/with_skill/outputs/response.md)；SHA256 `165999e379742a776ec73432bda4c19cce50b51b800c32c53e6a39f200a930b6`。
- `host-recovery-boundary` 原始 verdict **PASS**。
  - [grading.json](final-followup/reports/iteration-1/host-recovery-boundary/with_skill/grading.json)；SHA256 `e9b29563025e99a9c973b2322e0b33edd61a0d48f116206b241b3124b2e0241b`。
  - [evaluation.json](final-followup/reports/iteration-1/host-recovery-boundary/with_skill/evaluation.json)；SHA256 `30ec849152b5a1a26c8d371a700b8f4d718ecaeb4fb5ea8ac7e70a728e6edbea`。
  - [response.md](final-followup/reports/iteration-1/host-recovery-boundary/with_skill/outputs/response.md)；SHA256 `f874f50f9113e8014e18ee4b6dec8942b32fbe2e9b7aac77be8e4116621e0c29`。
