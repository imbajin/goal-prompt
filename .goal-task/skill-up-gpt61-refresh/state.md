# 评测升级与 Skill 精简：执行状态

## 当前状态

本目标已完成：实现、定向验证、三名独立源码复审、最终文档/证据独立核对及本地代码提交均完成。
完整6.1全量、without-Skill全量及Claude Code实机验证是独立TODO，不是本目标剩余门槛。

## 基线与真相入口

- 工作区：`/Users/zhu/.codex/worktrees/3443/goal-prompt`；初始化基线1d7622c，未重置主checkout。工具/CI里程碑df77f9b；最终代码/证据提交736e18c。完成状态随本地文档提交记录，最新HEAD以git log -1为准；未推送。
- 运行时真相：`skills/goal-prompt/SKILL.md`及references；`evals/skill-up/eval.yaml`、cases、fixtures/scripts和CI。
- 最终报告：`evals/skill-up/gpt61-refresh.md`；逐项证据：`evals/skill-up/evidence/gpt61-refresh/summary.md`及summary.json。原CLI/rollout/HTML仍在`.eval-work/<batch>/`。
- 任务项及独立完整复测TODO见`todo.md`；三项经验候选见`lessons.md`，未推广到AGENTS或Memory。
- 用户选择双轨：自然路由结果保留；核心行为显式调用，前后相同prefix/模型/effort/Judge/策略，不把调用变化算作Skill收益。
- 用户指示优先于任务材料；宿主更高优先级约束始终适用。不得伪造能力、凭据或自动恢复。

## 已完成的门槛与证据

1. 最新skill-up再次核查为0.14.0，固定发行installer与checksum；31例validate/dry-run、确定性正反样例、汇总器自测及Codex/Claude Code的9文件安装比对通过。远端CI未派发，证据为本地CI等价检查。
2. 主Skill从26214降至13163个Unicode字符，long参考从9241降至6055。修复初始化授权、宿主status/blocked/wakeup边界、策略覆盖后果和重大里程碑review；最后对齐Batch及打包基础eval/设计说明。没有宣称普遍效率收益。
3. 原冻结after16例为14PASS/2FAIL/0ERROR；两项词面误判保留原FAIL，并用同一修正脚本重放冻结输出为PASS。最终bundle另补batch-goal和host-recovery-boundary，两例原PASS，共覆盖17个唯一after案例。不是最终bundle全部31例复测。
4. 含before2的20次受控执行均确认精确冻结主Skill原生注入，17次另有工具读取；runner catalog仅工作区目标，语义Judge catalog为空，Sol high/Terra high与配置一致，无宿主目标/Memory读取异常线索。仍非OS密闭隔离，不能据此证明without-Skill干净对照。
5. 三名独立只读审查者review_one/review_two/review_three完成整合审查及修复复审，无未解决高严重度问题；审查记录见证据目录reviews.md。最终结果文档已由review_one独立核对通过。

## 重要事实与边界

- 旧skip_host_skill_discovery-only批次存在host catalog污染；research未加载目标，no-fabrication读宿主write。原始2PASS/4FAIL自然结果保留，不用于精简归因。没有为普通brief扩大触发范围。
- 判分修复不是新模型运行或Skill得分提升；原始result/grading/config从未覆盖。before compaction仍保留缺固定Progress token的FAIL，不能误称恢复契约缺失。
- token原生字段与skill-up派生字段分列。两个代表的原生input略降、output上升、耗时混合，无法推出普遍token/成本/延迟收益；字符量、工具读取和初始context不是同一指标。
- 最后Batch局部变更单列final-followup冻结快照；旧16输入/Skill/断言快照不变，未标成最后bundle重跑。主SKILL SHA d73fa2aa1446c3aa13ecec36676e2fcf8561af274fddca867d39a00372f76c71。
- 自动唤醒未实施或验证；容量、额度和宿主暂停不是Skill修复目标。意外中断时以本state、todo及证据恢复；不创建重复目标，不假定未来自动唤醒。

## 执行、恢复与审查契约

- 第一轮核查本任务需要的写入、命令、网络、子代理、Git、评测身份和唤醒能力；无法确定时记录影响和可行替代。无需询问已授权的范围内常规操作；不假造凭据、工具、重置时间或自动恢复能力。
- 范围内用户可授权操作预先授权；仅使用当前仓库与本地工作分支，里程碑提交到本地，默认不推送或创建 PR。任何远端写入须先有明确范围和目标；不得泄露凭据。
- 并行仅在独立且收益明确时使用；为各工作者指定独占文件及责任、共享文件单写者，由主 agent 整合并重跑交界检查；不得覆盖其他人工作。
- 每个阶段与批次主动记录结果、未完成项、证据、最新提交、未提交改动及下一步；压缩、额度等待或交接前尽可能更新状态，意外中断后按现有证据恢复。核实真实非阻塞唤醒能力；不可用时保留人工恢复入口，不伪造自动恢复。
- 单项最多尝试三次，记录失败和依赖后暂缓并继续独立工作；等待评测额度时可继续文档、配置、静态检查与审查准备。等待、needs input 或暂缓项排到独立工作之后，且不取消完成门槛；仅当所有有意义剩余工作同受真实障碍阻断并符合宿主状态规则时才整体 blocked。
- 任务进展和等待项更新到 `todo.md`；仅在形成有证据、值得复用的经验时创建 `lessons.md`，不预建空文件。
- 每个有效工作循环报告完成内容、证据、剩余工作及唯一主要下一步；仅在分母明确时报告比例。里程碑与最终重大行为变更由 3 名独立只读审查者审查整合 diff，修复后复审；审查缺失不算通过。文档专项审查按需由 1 名独立审查者完成。
- 各里程碑在适用验证和审查通过后本地提交，遵守项目提交规范；必要的中间检查点须注明未满足门槛。总结证据支持的经验，不预建空 lessons 文件。

## 下一步

本目标无剩余范围内工作。保留本入口与报告供复核；如后续开始独立全量复测，先核查git revision、工具及隔离条件，再按todo执行。不要自动重跑模型批次或启动全量TODO。
