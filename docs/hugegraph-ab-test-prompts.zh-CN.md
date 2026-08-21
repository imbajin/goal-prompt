# HugeGraph A/B 测试可执行 Prompts

> 配套计划：[hugegraph-ab-test-plan.zh-CN.md](hugegraph-ab-test-plan.zh-CN.md)
>
> 如果希望只复制一个完整 `/goal`，使用 [hugegraph-ab-test-single-goal.zh-CN.md](hugegraph-ab-test-single-goal.zh-CN.md)。
>
> 这些 Prompt 只供复制执行。本轮没有启动任何 `/goal`，也没有修改 HugeGraph 上游仓库。

## 1. 使用顺序

| 场景 | 使用内容 | 说明 |
| --- | --- | --- |
| 实现当前项目的 A/B 套件 | [Prompt I](#6-prompt-i实现-ab-套件推荐先执行) | 推荐先执行；只实现和验证套件，不花模型 A/B 成本 |
| 套件就绪后跑实验 | [Prompt II](#7-prompt-ii运行-pilot-与正式-ab套件就绪后执行) | 先 Pilot，再三次配对正式运行 |
| 手工实施某个上游任务 | 第 3–5 节的 Reference `/goal` | 用于单题调试或人工验收，不是正式 A/B 的输入 |
| 配置 `skill-up` 主 A/B | 第 2 节的三个 Raw Request | A/B 必须收到逐字相同的 Raw Request |

正式 A/B 的唯一主变量是生成阶段有没有安装 `goal-prompt`。不要把下方人工 Reference `/goal` 分别塞给 A/B 两组；那会改变不止一个变量。

## 2. Prompt 生成阶段：三份共享 Raw Request

### 2.1 统一运行规则

每份 Raw Request 在 `skill-up` 中运行两次：

- A：`without_skill`；
- B：`with_skill`。

两臂都只生成 `/goal`，不执行任务。模型、reasoning effort、timeout、max turns、工具权限、仓库 fixture 和网络策略必须相同。fixture 必须包含可修改的工作源码，以及可信 preflight 生成、两臂相同的只读 `version-evidence`；执行 Agent 不应看到 `.git` 历史、variant 名称、公开 issue/PR、修复根因或 judge 文件。

### 2.2 前端 Raw Request

```text
请为下面的真实仓库任务生成一个可复制执行的 /goal prompt，只输出最终 prompt，不要实施任务。用户授权你读取当前 checkout、自主判断并跳过确认；不要虚构版本、测试结果或已经完成的行为。

仓库是 Apache HugeGraph Toolchain 的 canonical 工作源码。可信 preflight 已把当前根 POM、HugeGraph 依赖以及官方 1.5.0/1.7.0 的必要源码证据写入只读 version-evidence；执行时必须核对这些本地证据，准确说明 master 是什么开发线，不得把不存在的正式版本写成已发布。执行环境无外网、无 .git，不要求提交。

需要修复一个完整交互闭环：在 0 vertex/0 edge 的空图上执行空查询后，用户应能通过“新建 → 添加顶点”创建第一个顶点。fixture 的 vertex label 是 person，PRIMARY_KEY 是 name，可空属性是 description。先只填 name=alice 创建；节点应出现在 2D canvas，计数为 1。随后真实点击该节点进入编辑，即使返回对象没有 description，schema 中声明的可空 description 也必须作为空输入框出现；填 first vertex 保存，刷新或重查后仍存在。

目标必须覆盖视觉空状态、按钮/Drawer 可达性、真实点击、当前 graphspace/graph 的 POST/PUT、请求次数、成功与失败状态。空图没有端点时，边操作不能错误启用；POST/PUT 失败不能产生幽灵节点、假成功或无条件清空输入。先验证现有后端契约，后端已有能力时不要改 API。

要求给出范围、非目标、1.5.0/1.7.0/当前开发线的只读版本矩阵、组件测试、浏览器 E2E、Server 1.7.0 持久化验证、失败恢复、独立 review 和完成报告。不要 backport，不做全面视觉改版，不新增持久 hash、不冻结输出格式、不建立持久对照基准、不接 CI/merge 强制门禁，不提交、不 push。
```

### 2.3 后端 Raw Request

```text
请为下面的真实仓库任务生成一个可复制执行的 /goal prompt，只输出最终 prompt，不要实施任务。用户授权你读取当前 checkout、自主判断并跳过确认；不要虚构版本、测试结果或已经完成的行为。

仓库是 Apache HugeGraph 的 canonical 工作源码。可信 preflight 已把官方 1.5.0、1.7.0、当前 master 的必要源码/版本事实写入只读 version-evidence；执行时必须核对这些本地证据，不能把不存在的正式 1.8.0 当成执行版本。主要稳定复现面是 HugeGraph 1.7.0 的 HStore；当前 master 只在 preflight 仍复现时作为实现对照。执行环境无外网、无 .git，不要求提交。

修复 HStore 多图首次事务批写的数据隔离缺陷。两个全新的 graph 使用不同 graphspace、graph 和 store 名称，但落到相同 partition/table 并使用同一个 logical key。只向 graph A 做首次 batch PUT 时，graph B 不能读到、覆盖或删除 A 的值；batch MERGE counter 不能跨 graph 累加；truncate B 不能影响 A。

目标必须沿真实 REST/transaction/batch/store 调用链定位根因，并验证多个新 graph 并发首次写入无竞态、死锁或超时；失败 batch 不暴露部分数据，重试可成功；已有有效图标识的数据仍可读。验收分两层：一是 auth-enabled 1.7 HStore 的 direct REST smoke，创建不同 graphspace/graph/store 并证明 A marker 在 B 不可见；二是真实 BusinessHandler + RocksDB 回归，其中 PUT/MERGE 经 doBatch()、读取经 doGet()、清理经 truncate()，rollback/失败走实际 session/handler API，不能只做 mock。无法可靠归属的历史异常前缀数据不自动猜测迁移，但要说明兼容边界。

不得改变 public API、配置格式、现有 physical-key 格式、依赖、项目版本或 backend 支持矩阵。要求给出修复前红/修复后绿、REST smoke、store-core 测试、全量 compile、失败恢复、三路独立 review 和完成报告。不新增持久 hash、不冻结输出格式、不建立持久对照基准、不接 CI/merge 强制门禁，不提交、不 push。
```

### 2.4 文档 Raw Request

```text
请为下面的真实仓库任务生成一个可复制执行的 /goal prompt，只输出最终 prompt，不要实施任务。用户授权你读取当前 checkout、自主判断并跳过确认；不要虚构版本、命令、引用或已经完成的验证。

仓库是 Apache HugeGraph Doc 的 canonical 工作源码。修正 Graphs REST API 的中英文文档，使 1.5.0、1.7.0 和当前 master 的读者能各自找到可执行且不混写的建图、查询和删除流程。可信 preflight 已把 doc 的 release-1.5.0、1.7.0、当前页面以及相同 refs 的 HugeGraph Server GraphsAPI 必要证据写入只读 version-evidence；执行时必须核对本地证据，确认是否真的存在 1.8，不得编造未发布版本。执行环境无外网、无 .git，不要求提交。

当前页面把 legacy endpoint/text/plain properties body 与 GraphSpace endpoint/application/json 混在同一叙述中，中英文对动态建图 NPE 的受影响版本说明还互相矛盾，示例也可能保留当前版本不支持的 backend。需要确认 1.7.0 release 的真实行为，并准确区分 auth-enabled 支持路径与 non-auth 上下文 creator 取值 NPE、post-1.7 master 修复边界、endpoint、Content-Type、body、backend 与状态码；不能泛化成所有 1.7 动态建图都 NPE。

目标应限定在 REST 总览和 Graphs API 的中英文对应文件，除非 primary evidence 证明必须扩大。要求两种语言语义等价，每个支持版本有独立可复制流程；运行 Hugo build 和链接检查，并用 server source 或隔离 smoke 验证 API 行为。说明站点构建不能替代行为验证。纯文档任务最终使用一名独立 reviewer。不要做全站重构，不新增持久 hash、不冻结输出格式、不建立持久对照基准、不接 CI/merge 强制门禁，不提交、不 push。
```

## 3. 前端 Reference `/goal`

这份 Prompt 用于人工执行或检查 evaluator 是否覆盖关键行为；正式 A/B 仍应使用第 2.2 节的相同 Raw Request 自动生成 A/B 两份 `/goal`。

```text
/goal

目标
在准备好的 apache/hugegraph-toolchain canonical 工作源码中完成 Hubble“空图创建首顶点 → 点击顶点 → 补填缺失 nullable 属性 → 保存并重查”的端到端修复。先核对 fixture 内可信 preflight 生成的 version-evidence：1.5.0、1.7.0 仅作只读历史对照；master 根 POM若仍为 1.8.0，只能称 Toolchain 1.8.0 开发线，并明确其 HugeGraph 依赖仍为 1.7.0，不能称已发布 1.8。fixture 无外网、无 .git；直接修改工作源码，不提交。

确定性 fixture
- HugeGraph Server 1.7.0；每次运行使用独立 graphspace/graph。
- 初始 0 vertex、0 edge。
- property key：name TEXT、description TEXT。
- vertex label：person；PRIMARY_KEY=name；nullable=description。

必须消除的行为失败
1. 空查询成功后，用户可真实点击“新建 → 添加顶点”；添加顶点可用，因无合法端点，入边/出边仍不可用。
2. 创建 person(name=alice) 时 description 可留空；只发送一次当前 graphspace/graph 的 POST。成功后 Drawer 关闭、2D canvas 出现 alice、节点数从 0 变 1。
3. 点击 alice 并进入编辑时，schema 已声明但对象中缺失的 description 仍显示为空输入框。保存 first vertex 时只发一次正确 PUT；本地 UI 更新，刷新或重查后 name 与 description 都持久化。
4. POST/PUT 失败不更新 graphData/count、不出现幽灵节点或假成功，也不无条件关闭/清空表单；沿用项目既有错误反馈。
5. 非空图的新增/编辑、2D/3D 和导入入口不回归。

实现边界
- 先追踪当前前端挂载、菜单状态、Drawer、schema/form model、graphData/count 与现有 GraphController/GraphService 契约；后端已有能力时不要改 REST API。
- 不修改 1.5.0/1.7.0 refs，不 backport，不全面重做视觉设计。
- 不升级依赖或版本，不新增持久 hash、不冻结输出格式、不建立持久对照基准、不接 CI/merge 强制门禁，不提交、不 push。

验证
- 为菜单启用规则、空图 Drawer、首节点状态转移、缺失 nullable 字段、POST/PUT 成功与失败补组件测试。
- 执行前端 test、lint、build；命令以当前 package scripts 为准，先读取后运行，不臆造。
- 基于仓库现有 browser smoke/Playwright 基础设施增加独立场景，但不接 CI/merge 强制门禁：实际点击 New、Add Vertex、节点、Edit、Save，并断言 URL、method、request count、响应、计数和 console。
- 用 Server 1.7.0 重新查询证明持久化；后端如有改动，补并运行对应单测。
- 保留修复前失败与修复后通过的证据。

执行方式
- 持续更新 .goal-task/hubble-empty-graph-edit/state.md；遇到单项失败最多尝试三种有依据的方法，记录证据后继续其他独立工作。
- 行为代码完成后进行恰好三路独立最终 review：前端状态/交互、API/E2E、版本/回归。修复所有高危问题并重跑相关验证。
- 所有主线验收条件通过后保留 fixture 内修改与证据，不提交、不 push、不创建 MR。只有所有剩余主线项同时依赖同一外部阻塞时才能标 blocked。

最终报告
分别列出版本判断、修改路径、视觉与点击证据、网络/持久化证据、自动验证、三路 review、未完成/阻塞、可选建议、本轮与整体完成度。不能用组件测试替代浏览器点击，也不能把未运行项写成通过。
```

## 4. 后端 Reference `/goal`

```text
/goal

目标
在准备好的 apache/hugegraph 1.7.0 HStore 工作源码 fixture 中修复多图首次事务批写的数据隔离缺陷。先核对 fixture 内可信 preflight 生成的 canonical/version-evidence；1.5.0 只作静态兼容分析，1.7.0 是主复现版本，post-1.7 master 只作证据对照，不得把不存在的正式 1.8.0 当作版本。fixture 无外网、无 .git；直接修改工作源码，不提交。

可观察失败
- 创建两个使用不同 graphspace、graph、store 名称的新图，使其落到同一 partition/table 并使用相同 logical key。
- 只向 A 做首次 batch PUT，B 不得读取、覆盖或删除 A 的值。
- A/B 的 batch MERGE counter 不得合并；truncate B 不得影响 A。

实现与不变量
1. 追踪 Graph 生命周期、HStore session、client transaction、gRPC/Raft batch、BusinessHandler.doBatch、TxBuilder key 编码、Graph ID 管理和 RocksDB physical key 的完整链路，用修复前红测试确认根因。
2. 首次 batch PUT/MERGE 在编码 physical key 前，每个 graph 必须原子获得互不冲突且有效的图标识；任何“未分配”保留值都不能作为持久 key namespace。
3. 多个新 graph 并发首次写入必须在有界超时内完成，各自只能读到自己的值，不竞态、不死锁。
4. 失败 batch 不暴露部分数据，之后重试可成功；已有有效图标识的数据仍可读。
5. 不自动猜测或迁移历史异常前缀数据，因为无法可靠反推原 graph；最终报告明确此边界。
6. 不改变 public API、配置格式、physical-key 格式、依赖、版本或 backend 支持矩阵。

验证
- L1 运行 auth-enabled HugeGraph 1.7.0 + HStore/PD/Store direct REST smoke：REST 创建不同 graphspace/graph/store，只向 A 写 marker，A 可见、B 不可见。
- L2 回归覆盖同 key 双 graph PUT、双 graph MERGE、truncate 隔离、并发首次分配、rollback/retry、已分配 ID 的兼容读取。PUT/MERGE 经真实 BusinessHandler.doBatch()，读取经 doGet()，truncate 与 rollback/失败分别走实际 handler/session API 和 RocksDB，而非只 mock GraphIdManager。
- 先证明修复前红，再证明修复后绿。
- 运行：
  mvn test -pl hugegraph-store/hg-store-test -am -P store-core-test -Djacoco.skip=true -ntp
  mvn clean compile -Dmaven.javadoc.skip=true -ntp
- 不新增持久 hash、不冻结输出格式、不建立持久对照基准、不接 CI/merge 强制门禁；不提交、不 push。

执行方式
- 持续更新 .goal-task/hstore-graph-isolation/state.md；每个阻塞最多尝试三种有依据的方法，独立工作继续推进。
- 行为代码完成后进行恰好三路独立最终 review：事务/锁/并发、存储/版本兼容、测试 oracle/回归。修复所有高危项并重跑对应测试。
- 主线验收条件全部通过后保留 fixture 内修改与证据，不提交、不 push、不创建 MR。只有全部剩余主线工作同时依赖同一外部阻塞时才能标 blocked。

最终报告
列出根因、修改路径、L1 REST 与 L2 store-core red/green、真实存储证据、命令、兼容边界、三路 review、未完成/阻塞、可选建议、本轮与整体完成度。任一跨图泄漏、死锁、只做 mock、未运行 REST 却声称完整 #3095 修复、改变 public API 或版本造假都不能报告主线完成。
```

## 5. 文档 Reference `/goal`

```text
/goal

目标
在准备好的 apache/hugegraph-doc canonical 工作源码中修正 Graphs REST API 的中英文版本真相和可执行性，使 HugeGraph 1.5.0、1.7.0 与当前 master 的读者能选对 endpoint、Content-Type、鉴权、body、backend 及建图/查询/删除流程。先核对 fixture 内可信 preflight 生成的 release-1.5.0、1.7.0、doc master、Server GraphsAPI 与 release version-evidence；没有正式 1.8 ref 时必须明确不存在，不得臆造。fixture 无外网、无 .git；直接修改工作源码，不提交。

范围
- content/en/docs/clients/restful-api/_index.md
- content/cn/docs/clients/restful-api/_index.md
- content/en/docs/clients/restful-api/graphs.md
- content/cn/docs/clients/restful-api/graphs.md
- 只有 primary source 证明必要时才扩大范围；不做全站重构或版本选择器。

必须完成
1. 建立证据矩阵：1.5.0 使用 legacy graph endpoint + text/plain properties；1.7.0 使用 GraphSpace endpoint + application/json；当前 master 只描述源码可证实的 post-1.7 行为。
2. 核清 1.7.0 auth-enabled 支持路径，以及 non-auth 上下文 creator 取值 NPE 与后续 master 修复的时间边界；不能泛化成所有 1.7 动态建图都坏，也不能把后续修复倒推为已进入 1.7 release。
3. 删除或隔离不适用于对应版本的 backend 示例；每个版本给出可复制、互不混写的 create/query/delete 流程。
4. 中英文 endpoint、警告、版本范围、示例和状态码语义等价；不靠逐字翻译掩盖事实差异。
5. 对照 server source 验证行为。运行 bash dist/validate-links.sh、核验执行环境已提供的预装依赖和 hugo --minify；只有依赖缺失且环境允许时才按项目推荐命令安装。条件允许时做隔离 API smoke。Hugo/link 通过不能替代 API 证据。
6. 不新增持久 hash、不冻结输出格式、不建立持久对照基准、不接 CI/merge 强制门禁；不提交、不 push。

执行方式
- 持续更新 .goal-task/graphs-api-doc/state.md；遇到阻塞记录证据并继续其他独立工作。
- 纯文档完成后使用恰好一名独立 reviewer，重点核对双语、版本和 API 行为；修复其高危发现并重跑验证。
- 主线验收条件全部通过后保留 fixture 内修改与证据，不提交、不 push、不创建 MR。

最终报告
列出证据矩阵、修改路径、两种语言的对应关系、命令/行为验证、review 结论、未完成/阻塞、可选建议、本轮与整体完成度。虚构 1.8、误写修复进入 1.7、只改一种语言或构建失败时不得报告主线完成。
```

## 6. Prompt I：实现 A/B 套件（推荐先执行）

```text
/goal

目标
在当前 goal-prompt 仓库实现一套独立、可复现但默认不运行的 HugeGraph 两阶段 A/B suite。严格以 docs/hugegraph-ab-test-plan.zh-CN.md、docs/hugegraph-ab-test-prompts.zh-CN.md 和 .goal-task/hugegraph-ab-tests/state.md 为 active truth；先读取当前 evals/skill-up、仓库规则和 skill-up 的实际可用状态/能力，不执行上游修复。

主线范围
1. 在 evals/skill-up/hugegraph-ab/ 建立 README、独立 eval 配置、三份 case、三份 rubric 和安全的 fixture/preflight/prompt-pair/execution-pair/summary 脚本。
2. 三份 case 分别覆盖：Toolchain 空图首顶点与 nullable 编辑、HugeGraph HStore 首次 batch 多图隔离、hugegraph-doc Graphs API 双语版本真相。Raw Request 必须使用 prompts 文档中的内容，A/B 逐字相同。
3. Prompt 阶段的唯一变量是是否加载 `goal-prompt`；suite 默认 `benchmark.enabled=false`。paired runner 必须从 pair 内冻结的 Skill/case/Raw Request/source/evidence 快照建立两个独立的单臂 skill-up 配置，除 `skills: []` 与本地 `goal-prompt` 外，模型、reasoning effort、runtime、timeout、max turns、源码和证据完全相同；显式记录并平衡 `--order ab|ba`，不得依赖 CLI 内部固定 benchmark 顺序。真实 OpenSandbox 在 config 与进程环境同时绑定 credential-free control-plane base，并分别从私密环境变量注入 OpenSandbox API key 与模型 API key；网络只允许声明的模型 hostname，engine 显式绑定 credential-free model base URL。运行前使用与 Agent 相同的模型凭据从同 host 的 policy endpoint 验证 provider-api-only、公开答案源拒绝与 HTTPS 内带认证 CONNECT 拒绝，并在可信 attestation 记录解析后的 sandbox image、control-plane base 与非敏感认证身份。不得提交模型输出、golden 输出或历史阈值。
4. 下游阶段把每臂 response 原样交给同一执行器和全新 fixture，以行为 oracle 评分；若当前 skill-up 不能串联，使用薄 wrapper，不要求固定输出 JSON 或标题格式。每个匿名臂必须由 reviewed service spec 创建独立 Docker internal network 和独占 data root，并实测私有服务 health、公开外网拒绝和模型端点 policy；不能让前一臂的 Graph/HStore 状态污染后一臂。
5. fixture 使用官方 tag/branch；master 每个 pair 只解析一次并复制两份，解析结果只写 .eval-work 运行元数据。可修改的上游工作源码必须进入执行 Agent 工作区；只排除 .git 历史、issue/PR 答案、judge、variant 和结果。可信 preflight 生成不含修复答案的只读 version-evidence/必要 ref 源码证据，并向两臂注入完全相同内容。
6. preflight 能检测 canonical、版本、master 漂移和缺陷是否仍复现；已修复 case 标 stale，不记为模型失败。
7. Agent 只可写 `agent-artifacts`，不得挂载 trusted evidence/score/run、mapping、兄弟臂、pristine、主仓库、judge 或 oracle。command oracle 必须在独立受限容器中由 root controller 运行，测试命令降权到独立 UID 并只操作 disposable workspace/pristine volume，不能读取 root-only spec/runner 或改写 root-owned evidence；不继承宿主凭据，不在宿主执行模型可修改的 Maven/Node/Hugo。完成后才由宿主 judge 写入与 anonymous run/pair/source/evidence/执行策略绑定的 score。
8. judge 实现计划文档中的逐题 100 分 rubric、硬失败上限、匿名 variant、配对 B-A、中位数、W/T/L、tokens/time/turns。用合成好/坏样例自测 judge，不以预期 patch 评分。执行器只用约定 exit 10 表示已确认的模型/任务失败并保留可信零分；其他非零、容器/copy/runtime、Prompt timeout/missing-result 都按环境失败未评分且不得解盲。
9. Pilot/Formal 在 `.eval-work` 使用显式 cohort ledger；prepare 时同时登记 case/repeat/pair 与 Prompt/执行计划顺序，完整 3/9 pair 的 2/1 排程校验通过后 seal，任何 arm 只能按 sealed plan 运行。正常汇总显式 pair 集必须与 ledger 完全一致并绑定所有 terminal arms；Pilot 三题在 Prompt/执行阶段分别为 2/1 首角色平衡，Formal 每题三次分别为 2/1。失败 pair 不得被新增成功 pair 替换或从汇总省略。
10. 不修改现有快速 eval 的语义，不新增依赖/版本 hash、不冻结输出格式、不建立持久对照基准、不接 CI/merge 强制门禁，不 push。

验证
- 对所有 shell 运行 bash -n，对 Python 运行项目可用的测试/语法检查。
- 先检查 skill-up 是否可用；若不在 PATH，复用仓库现有验证流程所用的官方版本/安装方式，将临时 CLI 放入 .eval-work，不新增依赖 hash。随后 validate 新 eval，并用 dry-run 验证 3 cases 和显式 paired mode。若网络或安装仍阻塞，可继续 scaffold 和静态测试，但不得报告套件实现完成。
- 对 fixture 同源、variant/HOME/session/data/service 隔离、stale 分类、匿名映射、rubric 硬失败、run/score 绑定、cohort ledger、Pilot/Formal 顺序和汇总复算补确定性测试。
- 使用 fake generator/executor 完成两阶段 smoke，不消耗真实模型调用；让 fake executor 主动伪造 `score.json`，证明 Agent-writable 结果不会覆盖 trusted score；另证明非空 quality `FAIL` 仍原样执行、partial Prompt ERROR 不进入执行、环境失败不能解盲、公开 oracle 不泄漏。
- 当前项目既有 validate 和 judge 测试必须通过。

执行与恢复
- 每完成一个阶段更新 .goal-task/hugegraph-ab-tests/state.md，记录证据、阻塞和下一步；不要另建重复的 goal.md/todo.md/design.md。
- 单个失败最多尝试三种有依据的方法；网络或工具阻塞时继续可独立完成的脚本、fixture、judge 和文档工作。只有所有剩余主线项共同依赖同一阻塞时才标 blocked。
- 行为脚本完成后进行恰好三路独立最终 review：A/B 因果与隔离、HugeGraph 事实/版本、脚本/judge 安全正确性。修复全部高危问题并重跑相关验证。
- 所有主线验收条件通过后按仓库规则本地提交；不 push、不创建 MR。

完成报告
按“本轮完成度、主线是否完成、关键改动与验证、未完成/阻塞、可选建议/需决策项”收尾；同时报告整体完成度、百分比口径和下一步。明确本 Goal 只实现套件，未运行真实模型 A/B，不能宣称 B 胜出。
```

## 7. Prompt II：运行 Pilot 与正式 A/B（套件就绪后执行）

```text
/goal

目标
使用当前 goal-prompt 仓库已经验证通过的 evals/skill-up/hugegraph-ab suite，完成一次三题 Pilot，并在 Pilot 健康后完成每题三次配对的正式两阶段 A/B；生成可复算的结果报告。以 docs/hugegraph-ab-test-plan.zh-CN.md、docs/hugegraph-ab-test-prompts.zh-CN.md、suite README 和 .goal-task/hugegraph-ab-tests/state.md 为 active truth。

运行前门槛
1. 重新核验 canonical repos、官方 refs、release/POM 和三个缺陷状态；stale case 记录并排除，不偷偷选历史 hash。
2. 确认 A/B 使用同一模型、reasoning effort、timeout、max turns、权限、依赖环境和每 pair 一次解析后复制给两臂的同源 fixture；各 variant/repeat 的 workspace、HOME、session、数据目录、私有服务网络均独立。先 prepare 全部 pair 并登记 Prompt/执行顺序，确认完整 2/1 排程已 seal 后才允许运行第一个 arm。
3. 执行 Agent 关闭公开外网；工作区包含可修改的工作源码和相同只读 version-evidence，但不含 .git 历史、公开 issue/PR、根因、oracle、trusted score 或 variant 名。Prompt 和下游分别通过真实 policy/health/CONNECT probe；oracle 在隔离容器中执行，judge 在宿主盲评后再解盲。
4. 确认模型认证/额度已可用；不得输出凭据。若外部认证是全部剩余运行的共同阻塞，保留预检证据并标 blocked，不伪造结果。

执行
- Pilot：三题各 1 pair，共 6 次 Prompt 生成和 6 次下游执行；Prompt 与执行的首角色跨三题分别为 2/1。逐题检查 fixture、行为 oracle、硬失败、timeout、成本和答案泄漏。
- Pilot 任一协议性问题先修 suite 并重新做确定性验证；若产生行为代码变更，完成恰好三路独立 review 后才重跑 Pilot。
- Pilot 健康后正式运行：三题各 3 pairs，共 18 次 Prompt 生成和 18 次下游执行；Prompt 与下游执行分别显式交替 A/B 顺序，确保每题三次中的首执行角色为 2/1 平衡，汇总器对不平衡 Formal cohort 失败关闭。自动重试固定为 0；模型失败保留可信零分；环境失败保留在原 ledger 且该 cohort 不解盲，如需重试必须新建完整 cohort，不能只重跑单臂、低分臂或用新成功 pair 替换。
- 保留每个 pair 的 raw score、critical failures、Prompt 目标/范围/证据分、完成率、tokens、wall time、turns 和重试；结果放 .eval-work，不提交模型原文或上游源码。

分析与报告
- 生成 docs/hugegraph-ab-results-<date>.md，只写聚合、必要证据摘要和可复算命令，不包含敏感凭据或完整模型思维过程。
- 每题报告三次配对的 A/B 原始分、B-A、中位数、W/T/L、硬失败率、完成率和成本；总体 35% 前端、40% 后端、25% 文档，但不能用总体分掩盖逐题硬失败。
- 三次重复只称工程探索，不宣称统计显著；区分观察、推断和未知。
- 纯运行/分析最终使用恰好一名独立 reviewer 复核因果协议、匿名映射和计算；如果本轮修改了行为脚本，则改为恰好三路独立最终 review。
- 不新增持久 hash、不冻结输出格式、不建立持久历史基准、不接 CI/merge 强制门禁，不 push、不创建 MR。

完成报告
按“本轮完成度、主线是否完成、关键运行与证据、未完成/阻塞、可选建议/需决策项”收尾，并报告整体完成度、百分比口径与下一步。只有 Pilot、正式配对、盲评、复算和 reviewer 都完成时才报告实验主线 100%。
```
