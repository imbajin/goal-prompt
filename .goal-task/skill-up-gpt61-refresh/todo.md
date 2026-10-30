# 评测升级与 Skill 精简：任务清单

## 本轮门槛

- [x] 核查并升级skill-up 0.14.0及CI，校验发行包，验证31例配置/dry-run。
- [x] 验证独立多Judge/expect计分语义及失败后产物采集；真实模型多Judge案例通过。
- [x] 记录长度及实际读取基线，修复可控契约并去重，保留通用契约和关键限制。
- [x] 相同显式prefix/模型/high/Judge/策略比较preauth与compaction两个代表，不虚报效率收益。
- [x] 六历史失败及十选定边界真实执行，原16为14PASS/2FAIL/0ERROR；两项误判同输出重放PASS，原FAIL保留。
- [x] 最后分支修复用最终bundle另测batch-goal和host-recovery-boundary，两例原PASS；唯一覆盖17/31。
- [x] 20次受控模型/加载/catalog审计，记录原生注入、额外读取和非OS隔离限制。
- [x] 更新中英文README、评测说明、报告、设计说明和证据，保留历史5.6数据。
- [x] 三名独立源码/配置审查及修复复审，无未解决高严重度。
- [x] 最终报告、证据归档和剩余TODO独立核对（review_one，153份归档字节/SHA一致）。
- [x] 最终代码/证据本地提交736e18c；本清单完成状态随文档提交保存，工作区检查通过，不推送。

证据入口：`evals/skill-up/gpt61-refresh.md`及`evals/skill-up/evidence/gpt61-refresh/summary.md`。
工具/CI里程碑df77f9b，代码/证据提交736e18c；原CLI/rollout/HTML位于`.eval-work/`，提交证据逐文件保留来源路径/SHA。

## 独立后续TODO，不作为本目标门槛

- [ ] 最终冻结revision的完整31例with-Skill复测，固定CLI、模型、high、Judge、timeout/retry及断言。
- [ ] 真正隔离target/源码/历史结果的without-Skill全量对照；两组用相同原始任务输入，不能沿用显式目标路径前缀冒充自然A/B；逐transcript审计并剔除污染cohort。
- [ ] 其余14例实测：audit-goal、deep-existing-docs、delegated-goal、existing-spec-plan、fast-small-task、frontend-ui-acceptance、parallel-agents-goal、research-brief-boundary、reviewer-stop-condition、stage1-grounded-feature、stage1-long-running、stage1-vague-draft、stage2-doc、stage2-migration。
- [ ] Claude Code真实execution与兼容Judge cohort；安装及4,000字符文本检查不替代实机验证。
- [ ] 更多同条件样本检验质量、token、延迟、自动触发和重复加载，保持CLI原生/工具派生指标分列。

本轮无等待中的模型调用或额度/capacity故障；不削弱上述未来完整复测的证据要求，也不自动启动。
