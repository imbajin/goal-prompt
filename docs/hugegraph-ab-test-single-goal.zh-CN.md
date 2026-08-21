# HugeGraph A/B 测试单一执行 Goal

> 使用说明：复制下面唯一一个代码块执行即可。本文件只生成 Goal，不代表已经启动或完成任何 A/B。

```text
/goal

总目标
在当前 goal-prompt 仓库中，完整实现并执行一套 HugeGraph 两阶段配对 A/B：使用 Apache HugeGraph Toolchain、HugeGraph Server、hugegraph-doc 的三个代表任务，比较相同原始任务在“不安装 goal-prompt”和“安装 goal-prompt”时生成的 /goal，并把两组生成结果原样交给同一执行器，在隔离且同源的上游工作源码中实施，最终用真实行为、版本准确性、完成率和成本判断 goal-prompt 的实际效果。

本 Goal 是唯一执行入口。不要再要求用户分别运行前端、后端、文档、套件实现或实验运行 Prompt。持续维护 .goal-task/hugegraph-ab-tests/state.md 作为跨会话状态，但以下目标、范围、任务体、评分和完成条件全部以本 Goal 为准。

已核验的版本事实
1. canonical 仓库是 apache/hugegraph-toolchain、apache/hugegraph、apache/hugegraph-doc；用户最初给出的 hugegraph/* 仓库是公开 fork，只能作为 fork/PR 来源，不能作为事实基线。
2. Toolchain 有正式 1.5.0、1.7.0；没有正式 1.8 tag/release。当前 master 根 POM 是 Toolchain 1.8.0 开发线，但 hugegraph.version 仍为 1.7.0。不得写成“已发布 Toolchain/Hubble 1.8”。
3. HugeGraph Server 有正式 1.5.0、1.7.0；没有正式 1.8 tag/release/release branch，调研时 master POM 仍为 1.7.0。只能写“1.7.0”或“post-1.7 master snapshot”。
4. hugegraph-doc 有 release-1.5.0 branch、1.7.0 tag/release和滚动 master；没有 1.8 ref。
5. 所有 master 事实在运行前必须重新 preflight。发布版本只用官方 tag/branch 名。不要新增或提交固定 commit hash；每个 A/B pair 只解析一次移动 ref，A/B 复制同一份源码，解析结果只写入 .eval-work 当次元数据。

核心 A/B 因果协议
1. Prompt 生成阶段：A=without_skill，B=with_skill；两臂收到逐字节相同的 Raw Request，只生成 /goal，不执行任务。
2. 下游执行阶段：把 A/B response 原样交给同一执行器，不人工润色、不添加只给某一臂的说明。
3. 唯一主变量是 Prompt 生成阶段是否安装 goal-prompt。固定模型、reasoning effort、timeout、max turns、工具权限、JDK/Node/Maven、依赖策略、重试策略、reviewer 规则、fixture、隐藏评分和数据。
4. 每个 variant/repeat 使用全新且独立的 workspace、HOME、session、graph/data 目录；不能继承另一臂历史。Prompt 两臂分别在 OpenSandbox 单臂 runtime 中执行，对照臂 runtime 根目录不得出现 Skill 文件。
5. 执行工作区必须包含可修改的上游工作源码，以及可信 preflight 生成、两臂完全相同的只读 version-evidence/必要 ref 源码证据；排除 .git 历史、公开 issue/PR、修复根因、judge、oracle、结果和 variant 名。
6. 下游执行 Agent 只能在每臂独立创建的 Docker internal network 中运行：容器只挂载当前匿名臂、私有 workspace volume、只读 version-evidence 和 Agent 专用 artifact 目录，不挂载 trusted score/run、pair mapping、兄弟臂、pristine、主仓库、judge 或 oracle。每臂使用独占 data root；私有服务 health、provider-only policy、公开外网拒绝和 CONNECT 拒绝必须从实际容器网络探测。command oracle 在第二个受限容器中运行，不继承宿主凭据；退出后才由宿主 judge 写可信评分。
7. judge 在 variant 匿名化后评分，完成后才解盲。评分基于行为，不基于预期 patch。
8. 上游缺陷已修复或不再复现时，preflight 将该 case 标 stale 并排除，不把它记成模型失败，也不偷偷选择未声明的历史 hash。
9. 不把“手写短 Prompt”和“结构化长 Prompt”作为主 A/B；两臂必须使用下方同一个 Raw Request，由 Skill 可用性产生差异。

阶段一：实现独立 A/B suite
在 evals/skill-up/hugegraph-ab/ 建立：
- README.md；
- 独立 eval.yaml；
- cases/toolchain-empty-graph-edit.yaml；
- cases/server-hstore-graph-isolation.yaml；
- cases/docs-graphs-api-version-truth.yaml；
- rubrics/toolchain.md、server.md、docs.md；
- scripts/prepare-fixtures.sh、preflight.sh、run-prompt-pairs.sh、run-execution-pairs.sh、summarize-pairs.py；
- 只在确有必要时增加职责不重叠的测试 fixture，不新增重复状态文档。

Suite 规则
1. 与现有快速 eval 分离，不改变 evals/skill-up/eval.yaml 的现有语义。
2. 默认 `benchmark.enabled=false`。只有用户显式运行本 Goal 的 paired comparison 阶段时才从 pair 内冻结的 Skill/case/Raw Request/source/evidence 创建两个独立的单臂配置；除了 `skills: []` 与本地 `goal-prompt` 外，固定模型、reasoning effort、runtime、timeout、max turns、源码和证据，并用 `--order ab|ba` 平衡先后顺序。不得创建或提交持久历史基准、golden 输出或阈值。
3. 当前 skill-up 若不在 PATH，复用仓库现有 validate workflow 所用的官方版本/安装方式，把临时 CLI 放入 .eval-work；不得新增依赖 hash。若安装或网络仍失败，继续完成 scaffold 和静态测试，但不得宣称 suite 已完成。
4. 如果当前 skill-up 不能直接串联“生成 Prompt → 执行 Prompt”，使用薄 wrapper 编排；response 必须原样传递，不要求固定 JSON、标题或固定措辞。
5. clone、archive、临时 CLI、HOME、上游源码、模型输出、oracle 和运行记录都留在已有忽略目录 .eval-work；不把它们提交进仓库。
6. 不新增持久 source hash、不冻结输出格式、不建立持久历史基准、不接入 CI/merge 强制门禁。
7. Prompt 与下游均记录固定模型、reasoning effort、timeout、max turns 和顺序；自动重试为 0。模型失败保留可信零分；环境失败保留原 cohort 的匿名未评分终态，如需重试则新建完整 cohort，不单独重跑某一臂或用成功 pair 替换失败 pair。
8. 下游真实运行只接受仓库内经 review 的容器隔离脚本；它必须对 seed/Agent/copy 容器和 volume 做超时/信号清理。fake wrapper 只能用于 deterministic cohort，并明确标为 simulated-only，不能作为真实隔离证明。
9. oracle 使用 Agent 工作区外的 reviewed command spec：每个 rubric check、critical fact 和 `claims.complete` 恰好定义一次 argv；completion claim 探针独立读取只读 `agent-artifacts`/`executor-stdout`，不能从 checks 自动推导。PUT/MERGE、doGet、truncate、rollback 和 L1 REST 分别走真实命令，超时或非 0/1 退出视为环境失败。oracle 容器中的 root controller 持有 root-only spec/runner/evidence，测试命令降权并只操作 disposable workspace/pristine volume，不能在宿主直接执行模型修改过的 Maven/Node/Hugo。
10. Pilot、Formal 使用 `.eval-work` 临时 cohort ledger；先登记完整 pair 及 Prompt/执行计划顺序，2/1 校验后 seal，任何 arm 只能按 sealed plan 运行。正常汇总的显式 pair 集必须与 ledger 完全一致并绑定所有 terminal arms，所有匿名臂存在可信绑定 score 后才能读取 mapping。Pilot 每题 repeat=1，跨三题验证 Prompt/执行首角色 2/1；Formal 每题 repeat=1/2/3，各题分别验证 2/1。移动 ref 每 pair 只解析一次并复制给两臂，报告逐 pair 保留 snapshot，不把不同 preflight 时间戳误判为策略漂移。

CASE 1：Toolchain/Hubble 前端
共享 Raw Request：
“请为下面的真实仓库任务生成一个可复制执行的 /goal prompt，只输出最终 prompt，不要实施任务。用户授权读取当前工作源码、自主判断并跳过确认；不要虚构版本、测试结果或完成状态。

仓库是 Apache HugeGraph Toolchain canonical 工作源码。可信 preflight 提供当前根 POM、HugeGraph 依赖和官方 1.5.0/1.7.0 的本地只读 version-evidence。执行环境无外网、无 .git，不要求提交。

修复完整交互闭环：0 vertex/0 edge 的空图执行空查询后，用户能通过‘新建 → 添加顶点’创建第一个顶点。fixture：vertex label=person，PRIMARY_KEY=name，nullable property=description。先只填 name=alice 创建；节点进入 2D canvas，计数为 1。随后真实点击该节点进入编辑，即使返回对象没有 description，schema 中的可空 description 也显示为空输入框；填 first vertex 保存，刷新或重查后仍存在。

覆盖空状态视觉、按钮/Drawer 可达性、真实点击、当前 graphspace/graph 的 POST/PUT、请求次数、成功与失败状态。空图没有端点时边操作不能错误启用；POST/PUT 失败不能产生幽灵节点、假成功或无条件清空输入。先验证现有后端契约，已有能力时不要改 API。

给出范围、非目标、1.5.0/1.7.0/当前开发线版本矩阵、组件测试、浏览器 E2E、Server 1.7.0 持久化、失败恢复、独立 review 和完成报告。不要 backport、全面视觉重构、依赖/版本升级、持久 hash、冻结输出、持久基准、CI/merge 门禁、提交或 push。”

前端固定 fixture
- HugeGraph Server 1.7.0；每臂独立 graphspace/graph。
- 初始 0 vertex、0 edge。
- name: TEXT；description: TEXT；person；PRIMARY_KEY=name；nullable=description。
- 新增 name=alice 且不填 description；后续编辑 description=first vertex。

前端必须通过
1. 空查询成功后真实点击 New → Add Vertex 可达；边操作因无端点保持不可用。
2. Add Drawer 挂载并显示 person、name、description。
3. 新增只发送一次正确 graphspace/graph POST；成功后 canvas 出现一个节点、count 由 0 变 1。
4. 点击 alice → Edit 时，缺失的 nullable description 仍出现为空输入框。
5. 保存只发送一次正确 PUT；本地 UI 更新，Server 1.7 重查后 name/description 均持久化。
6. POST/PUT 失败不更新 graphData/count、不出现幽灵数据、不无条件关闭或清空表单，并保留已有错误反馈。
7. 非空图新增/编辑、2D/3D、导入入口不回归。
8. 运行项目实际存在的前端 test、lint、build；增加 React Testing Library/user-event 覆盖。
9. 基于仓库现有 browser smoke/Playwright 做独立真实点击场景，断言 URL、method、request count、body、响应、计数和 console；不接强制门禁。
10. 若后端没有改动，用 1.7 E2E 证明现有 POST/PUT 契约；若修改后端，补对应单测。

前端评分 100
- 空图真实点击创建首顶点 15；canvas/count 状态 10；缺失 nullable 可见可编辑 15；PUT 与重查持久化 15；失败状态 10；API URL/method/body/request count 10；组件测试 10；Playwright 点击/网络 10；版本准确 5。
- 只改视觉/disabled、真实点击或 API 不通：最高 40。
- 无浏览器点击与网络证据：扣 20。
- 破坏无端点边操作：扣 15。
- 把 master 称正式 1.8：扣 10。

CASE 2：HugeGraph/HStore 后端
共享 Raw Request：
“请为下面的真实仓库任务生成一个可复制执行的 /goal prompt，只输出最终 prompt，不要实施任务。用户授权读取当前工作源码、自主判断并跳过确认；不要虚构版本、测试结果或完成状态。

仓库是 Apache HugeGraph canonical 工作源码。可信 preflight 提供官方 1.5.0、1.7.0、当前 master 的本地只读 version-evidence。稳定复现面是 1.7.0 HStore；master 只在仍复现时作实现对照。执行环境无外网、无 .git，不要求提交。

修复 HStore 多图首次事务批写隔离：两个新 graph 使用不同 graphspace、graph、store，落到相同 partition/table 并使用相同 logical key。只向 A 首次 batch PUT 时，B 不能读取、覆盖或删除 A；MERGE counter 不能跨 graph 累加；truncate B 不能影响 A。

沿真实 REST/transaction/batch/store 调用链定位根因。验收分两层：L1 是 auth-enabled HugeGraph 1.7 + HStore/PD/Store direct REST smoke，创建不同 graphspace/graph/store 并证明 A marker 在 B 不可见；L2 是真实 BusinessHandler + RocksDB，PUT/MERGE 经 doBatch，读取经 doGet，清理经 truncate，rollback/失败走实际 session/handler API。验证多个新 graph 并发首次写入无竞态、死锁或超时；失败 batch 无部分可见数据且可重试；已有有效 graph identity 数据仍可读。不能只做 mock。

历史异常前缀无法可靠归属时不自动猜测迁移，但说明兼容边界。不得改变 public API、配置、physical-key 格式、依赖、版本或 backend 矩阵。给出 red/green、REST smoke、store-core test、compile、失败恢复、三路 review 和完成报告。不新增持久 hash、冻结输出、持久基准、CI/merge 门禁、提交或 push。”

后端必须通过
1. L1 direct REST：auth-enabled 1.7 HStore/PD/Store，从 REST 创建两套 graphspace/graph/store；只向 A 写 marker；A 可见、B 不可见，并证明路由到独立 store identity。
2. L2 PUT：真实 BusinessHandler.doBatch + RocksDB，同 partition/table/logical key 的 A/B 值独立；读取使用 doGet。
3. L2 MERGE：counter 不跨 graph 累加。
4. L2 truncate：调用真实 truncate，清理 B 不损坏 A。
5. L2 rollback/retry：实际 handler/session 失败路径无部分可见数据，重试成功。
6. 多个新 graph 并发首次写入在有界超时内完成，得到不同有效 identity，无竞态、死锁或 sentinel namespace。
7. 已有有效 identity 的数据仍可读；public API、配置、physical-key 格式、backend 支持不变。
8. 不自动迁移无法归属的历史异常前缀数据，报告兼容边界。
9. 修复前测试红、修复后绿。
10. 运行：mvn test -pl hugegraph-store/hg-store-test -am -P store-core-test -Djacoco.skip=true -ntp；mvn clean compile -Dmaven.javadoc.skip=true -ntp；另运行实现阶段基于现有设施确定的 1.7 auth-enabled HStore direct REST smoke，不能臆造不存在的脚本名。

后端评分 100
- REST namespace 隔离 15；PUT 12；MERGE 8；truncate 8；rollback 7；并发首次写 15；兼容性 10；L1+L2 测试质量 12；范围质量 7；验证/review 6。
- 任一跨图读取/覆盖/MERGE/truncate 泄漏、并发死锁、改变 public API/physical-key、只 mock、版本造假均为硬失败。
- 未运行 L1 REST smoke 时最高 80，且不能声称完整 GraphSpace/graph/store 缺陷已修复。
- 1.5.0 只作静态风险/兼容分析；未真实运行不得声称完整复现。

CASE 3：hugegraph-doc Graphs REST API
共享 Raw Request：
“请为下面的真实仓库任务生成一个可复制执行的 /goal prompt，只输出最终 prompt，不要实施任务。用户授权读取当前工作源码、自主判断并跳过确认；不要虚构版本、命令、引用或完成状态。

仓库是 Apache HugeGraph Doc canonical 工作源码。可信 preflight 提供 doc release-1.5.0、1.7.0、master 及相同 refs 的 Server GraphsAPI 本地只读 version-evidence。执行环境无外网、无 .git，不要求提交。

修正 Graphs REST API 中英文文档，使 1.5.0、1.7.0、当前 master 读者分别获得可执行且不混写的建图、查询、删除流程。当前页面混合 legacy endpoint/text/plain properties 与 GraphSpace endpoint/application/json，中英文对 NPE 版本范围互相矛盾，示例还可能保留对应版本不支持的 backend。

核验并准确区分：1.5 legacy 流程；1.7 auth-enabled 动态建图支持路径；1.7 non-auth 上下文 creator 取值 NPE；post-1.7 master 修复边界。不能泛化成所有 1.7 动态建图都 NPE，也不能把后续 master 修复写成已进入 1.7 release。核对 endpoint、Content-Type、auth、body、backend 和状态码。

范围限定在中英文 REST 总览和 Graphs API 对应文件，除非本地 primary evidence 证明必须扩大。两种语言语义等价，每个版本有独立可复制流程。运行 Hugo build、链接检查，并用 server source 或隔离 smoke 验证 API 行为；站点构建不能替代行为验证。纯文档实施使用一名独立 reviewer。不要全站重构、持久 hash、冻结输出、持久基准、CI/merge 门禁、提交或 push。”

文档限定路径
- content/en/docs/clients/restful-api/_index.md
- content/cn/docs/clients/restful-api/_index.md
- content/en/docs/clients/restful-api/graphs.md
- content/cn/docs/clients/restful-api/graphs.md

文档必须通过
1. 1.5.0：legacy graph endpoint、Content-Type:text/plain、properties body、对应鉴权/删除流程；不混用 1.7 GraphSpace JSON。
2. 1.7.0：/graphspaces/{space}/graphs/{graph}、application/json、当前支持 backend、鉴权要求、状态码；auth-enabled 是支持路径；另准确描述 non-auth creator NPE。
3. 当前 master：只写 server source 可证实的 post-1.7 行为，并明确后续修复边界；不得发明 1.8。
4. 删除、替换或明确隔离不适用版本的 Cassandra/backend 示例。
5. 中英文 endpoint、警告、版本范围、示例和状态码语义等价。
6. 运行 bash dist/validate-links.sh、核验执行环境已提供的预装依赖、hugo --minify；只有依赖缺失且环境允许时才按项目推荐命令安装，条件允许时做隔离 API smoke。
7. 使用 server source 证明 API 行为；不得只凭 Hugo/link 成功宣称完成。

文档评分 100
- 版本事实 30；API 行为 25；独立可执行流程 15；双语一致 10；站点质量 10；primary evidence/范围 10。
- 虚构正式 1.8：最高 50。
- 把后续 NPE 修复写进 1.7 release，或泛化成 auth-enabled 也必然 NPE：最高 59。
- 只改一种语言：最高 75。
- Hugo build 失败：最高 70。

Preflight 与 fixture 验收
1. 重新核验三个 canonical、官方 refs、release/POM、候选 issue/PR 状态和缺陷是否仍复现。
2. 为每题生成不含解决方案的 version-evidence，至少包含 ref 名、版本文件相关片段、必要历史源码差异与核验日期；不要规定固定 JSON schema。
3. 使用 git archive 或等价方式生成无 .git 的可修改源码。每个 pair 的 A/B source tree 在注入相同 version-evidence 后必须一致。
4. 通过确定性测试证明 fixture/workspace/HOME/session/data 分离、stale/drift 分类、匿名映射和结果目录无交叉污染；fake 只证明编排。Pilot 前另用真实容器隔离 probe 证明兄弟臂/宿主文件不可见、version-evidence 只读、私有服务可达、公开外网不可达且超时后无残留容器/进程。
5. 执行任务体不出现公开 issue/PR 编号、链接、根因、精确 patch 或 judge 路径。

Suite 确定性验证
1. 所有 shell 通过 bash -n；Python 通过项目可用的语法/测试检查。
2. skill-up validate 新 eval，dry-run 显示三个 case，并验证 paired comparison 会产生两个仅 Skill 不同的独立单臂配置。
3. 用 fake generator/executor 完成两阶段 smoke，不消耗真实模型调用。
4. judge 合成自测至少拒绝：前端只改 disabled/视觉；后端只做 mock；只通过 store-core 却声称完整 REST 修复；文档只改一种语言；任一 case 虚构正式 1.8。
5. 当前项目既有 validate 和 judge 测试保持通过。
6. Suite 实现完成后进行恰好三名独立只读 reviewer：A/B 因果/隔离、HugeGraph 事实/版本、脚本/judge 安全正确性。修复所有高危项并 re-review，最多三轮。

阶段二：Pilot
只有 suite 的全部确定性验收通过后才能运行真实模型。
1. 确认模型认证/额度可用，不输出凭据。
2. 三题各运行 1 pair：共 6 次 Prompt 生成和 6 次下游执行。
3. 每个 run 记录匿名 ID、raw task score、critical failures、Prompt 目标覆盖分、完成状态、tokens、wall time、turns、重试和环境失败。
4. 检查 fixture、网络隔离、答案泄漏、行为 oracle、timeout、成本和评分上限。
5. 自动重试固定为 0；模型失败保留可信零分。环境失败保留原 ledger 且不解盲；需要重试时新建完整、顺序平衡的 cohort，不能只重跑单臂、低分臂或替换原失败 pair。
6. Pilot 出现协议/脚本问题时先修 suite、重跑确定性验证和三路 review；不要带病进入正式运行。

阶段三：正式配对 A/B
1. Pilot 健康后，每题运行 3 pairs：共 18 次 Prompt 生成和 18 次下游执行。
2. Prompt 与下游执行都显式交替 A/B 顺序；每题三个 Formal pair 的首执行角色必须为 2/1 平衡，否则汇总失败关闭。
3. 不筛选最好结果，不删除失败 run；环境失败与模型失败分开。
4. 当次模型原文、上游源码和运行目录留在 .eval-work，不提交。
5. 三次重复只作为工程探索，不宣称统计显著。需要扩大到 5+ repeats 时列为需用户决策的可选项，不能混入主线完成度。

指标与汇总
1. 主指标：每题下游 0–100 行为分、主线完成率、critical failure rate。
2. 每个 pair 计算 B-A；每题报告全部三次原始 A/B、差值、中位数、win/tie/loss 和分数离散。
3. 次指标：Prompt 目标覆盖分、tokens、wall time、turns、重试。
4. 总体展示权重：前端 35%、后端 40%、文档 25%；总体分不能掩盖任一题硬失败。
5. 生成 docs/hugegraph-ab-results-<date>.md，包含可复算命令、聚合数据、必要证据摘要、stale/excluded runs、观察/推断/未知和局限；不包含凭据或完整思维过程。

范围与禁止项
1. 不修改、发布或向三个上游仓库 push/MR；上游源码修改仅存在于隔离 evaluator workspace。
2. 当前 goal-prompt 仓库只提交 suite、确定性测试、必要文档和最终聚合报告；不提交模型原文、上游源码或运行快照。
3. 不新增持久 hash、不冻结输出格式、不建立持久历史基准、不接入 CI/merge 强制门禁。
4. 不升级无关依赖/项目版本，不扩大为 Toolchain 全面 UI 重构、HugeGraph 历史 sentinel 数据迁移、GraphIdManager 全生命周期重构或 docs 全站改版。
5. typed DEFAULT_VALUE 仅是可选低成本校准题，不属于本 Goal 主线，不能影响主线完成度。
6. 不 push、不创建 MR；完成的当前仓库持久改动在验证和 review 通过后按仓库 commit message 规则本地提交。

持续执行与恢复
1. 每完成一个 productive loop 更新 .goal-task/hugegraph-ab-tests/state.md，并报告：基于验收项的进度百分比、本轮完成/剩余、一个主要下一步。
2. 单项默认最多尝试三种有依据的方法。仍失败时记录错误、证据、恢复尝试和依赖，defer 该项并继续所有独立工作；defer 不等于放弃，未满足项仍阻止 100%。
3. 网络、下载、构建、Docker/HStore 启动、模型额度或工具等待期间，继续不冲突的 fixture、judge、脚本、文档或证据工作，不 busy-poll。
4. 权限/认证缺口标 needs input；不要自动把整体标 blocked。
5. 只有完成有持久改动的 major milestone、相关验证通过、恰好三名独立 reviewer 无未解决高危项后，才创建当前 goal-prompt 仓库本地 commit；不 push。
6. 最终 major milestone 使用恰好三名独立只读 reviewer，分别复核：因果协议/隔离与结果计算；HugeGraph 版本/任务事实与行为证据；脚本/judge 安全、可复算性和范围。修复后 re-review，最多三轮。
7. 只有在有证据的可复用教训出现时才写 lessons.md；不得自动修改 AGENTS 或 Memory。

全部完成条件，必须同时满足
1. 独立 suite、三个共享 Raw Request、fixture/preflight、两阶段 runner、rubric、judge 和 summary 已实现。
2. 新 suite validate/dry-run、shell/Python 检查、fake 两阶段 smoke、judge 合成测试和当前项目既有验证全部通过。
3. A/B source identity、version-evidence、workspace/HOME/session/data 隔离、执行器无外网、答案/variant/judge 不泄漏均有确定性证据。
4. 前端行为 oracle 能区分真实点击闭环与视觉假修；后端同时具备 L1 REST 和 L2 store-core oracle；文档 oracle 区分 1.5/1.7/master、auth/non-auth 与双语一致性。
5. Suite-ready milestone 的三路 review 已完成且无未解决高危项。
6. Pilot 三题各 1 pair 全部完成，协议健康；若 case stale，已按规则排除并解释。
7. 正式实验三题各 3 pairs 全部完成，所有 run/失败/重试均保留并正确分类。
8. 最终结果文档包含逐题原始配对、B-A、中位数、W/T/L、硬失败率、完成率、成本、总体权重、限制和可复算证据；不宣称统计显著。
9. 最终三路独立 review 完成，计算和证据复核通过，无未解决高危项。
10. 当前 goal-prompt 仓库必要持久改动已按规则本地提交；没有 push/MR；所有禁止项得到遵守。
11. 最终报告严格包含：本轮完成度与主线是否完成、关键改动和验证、未完成/阻塞、可选建议/需决策项；同时报告整体完成度、百分比口径和下一步。未满足任一主线条件时不得报告 100%，也不得宣称 Treatment 更优。

整体 blocked 条件
只有当三题 suite、所有可独立实现/验证/分析工作都已完成或穷尽，经过最多三种有依据的恢复、替代方案、任务拆分和重新排序后，所有剩余主线工作仍共同依赖同一个已验证的强制外部条件，例如所有真实模型运行都缺少不可替代的认证/额度，或强制隔离运行时完全不可用，才可把整体标 blocked。普通单测失败、单个 case stale、一个 Docker 启动失败、一次网络错误、一个 reviewer 发现问题或某一题暂时不可运行，都不能直接把整体标 blocked。
```
