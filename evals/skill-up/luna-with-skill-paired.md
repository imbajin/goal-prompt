# GPT-6 Luna xhigh 配对评测与精简前后验证

R1复审补充：以下模型结果对应当时冻结快照，不是当前R1修订Skill的新模型评测。恢复未知事实执行门槛、fast完成/blocked约束和deep反思后，主文为13616字符、long参考6224字符；历史精简表中的13163/6055保留为原实测版本。R1最终判分器已对12份受影响的既有输出作同镜像before/current重放（24个全新、无外连容器），脚本状态与上一版校准一致；不重跑生成，不覆盖原始成绩，也不视为新Skill行为验证。

原始输出、冻结快照和运行回执保留在本地`evals/skill-up/evidence/`，已加入ignore，不随源码PR合入。下文以代码路径标注本地证据，获取档案后才能重放；不是可点击的公开下载。

2026-10-30。原30例with-Skill及五个定向案例的精简前后对照均已真实执行完毕。生成模型和语义Judge统一为`gpt-6-luna / xhigh`；没有重跑without生成组，没有新增其他模型实测。[PR #5](https://github.com/imbajin/goal-prompt/pull/5)已先开放已验收的Skill/工具升级快照供试用；最新判分器边界修复已完成三名独立修后复审、原12输出同镜像零模型回放及完整Linux测试；原始与各版校准档案分别保留。

## 主30例：原始与校准分别保留

| 口径 | without PASS / FAIL / ERROR | with-Skill PASS / FAIL / ERROR |
| --- | ---: | ---: |
| 原始模型输出及原生判分 | 6 / 24 / 0 | 22 / 8 / 0 |
| 已有输出的确定性脚本校准，同Docker复核 | 7 / 23 / 0 | 25 / 5 / 0 |
| 再补Batch必要业务产物的局部语义校准 | 7 / 23 / 0 | 26 / 4 / 0 |

最后一行只对Batch补齐原final引用的真实业务文件，并统一重判两组同一案例；其他案例沿用对应原判或脚本校准，不是全30例重新盲评。该口径中，19例只有with通过，7例双方通过，4例双方未通过。原始status、grading及历史5.6结果均未覆盖；校准字段和来源另列。

原始30例与配置（本地归档：`evidence/luna-paired/with/summary.md`）、脚本第一次重放（本地归档：`evidence/luna-paired/replay/`）、同源脚本校准v3（本地归档：`evidence/luna-paired/replay-v3/summary.md`）、最终多口径汇总（本地归档：`evidence/luna-paired/calibrated-final/summary.md`）、Batch真实产物新上下文（本地归档：`evidence/luna-paired/state-aware/summary.md`）分开保存。完整rollout仅在本地保留，以绝对路径、大小和SHA索引；没有把归一化stdout当作完整原生证据。

## 五个原未通过案例：先小批，再扩围

初始只测long-running，再扩到batch/preauth，最后才测research/no-fabrication。每case每版两次，顺序`before,current,current,before`；所有生成都保留，不用重测挑一次好结果替换失败。

| 案例 | 精简前 PASS / 2 | 当前版 PASS / 2 | 判分材料及实际区别 |
| --- | ---: | ---: | --- |
| stage1-long-running | 2 / 2 | 2 / 2 | fresh J最终简报；未复现全局停止条件的遗漏 |
| batch-goal | 0 / 2（原expect FAIL） | 2 / 2（语义PASS） | 两个before未给已授权goal，原expect失败、语义SKIP；current补齐真实state后分别语义PASS |
| preauthorized-permissions | 0 / 2 | 2 / 2 | 同镜像脚本重放；旧版确缺显式安全优先级边界，新版两份原文符合合同 |
| research-goal | 0 / 2 | 2 / 2 | 最终brief＋统一真实初始环境事实；旧版未完整区分证据缺口与偏好缺口 |
| no-fabrication | 2 / 2 | 2 / 2 | 同上；两版都能给诚实的有限brief，没有观察到精简退化 |

原件分别见first small batch（本地归档：`evidence/luna-paired/failed-stage1/summary.md`）、第二批原始8FAIL（本地归档：`evidence/luna-paired/failed-stage2-raw/summary.md`）、必要业务产物重判（本地归档：`evidence/luna-paired/state-aware/summary.md`）、第三批（本地归档：`evidence/luna-paired/failed-stage3/summary.md`）。第二批原始final-only/旧script分数是8FAIL；上述校准利用同一批生成输出，未重新生成。Batch沿用两版相同的原expect门槛；两个before的0/2是case总状态没有PASS，语义项未评分（SKIP），不是两次新上下文语义FAIL。不能据此比较两版语义分数的增幅。

两版使用相同显式调用前缀，均核实读取了实际冻结Skill。before是真实`1d7622c`九文件快照，current是主30的冻结快照；主文26214→13163字符，long参考9241→6055字符。版本差异包括压缩、授权路由及宿主契约修正，不能把改善单独归因于长度。两次重复没有统计稳定性或普遍成本收益保证。原自然30没有显式前缀，不能把调用变化算作版本收益。

## 判分误报与修复

- **否定提及不等于成品命令。** `confirmation-brief`曾把路径、句末否定及“不会直接给最终可复制的 /goal”当成提前生成。修复按命令token和局部否定判断，保留真实命令行、正向inline命令及标点后payload反例；without只重放旧输出，原6/24保留。
- **事实核实不等于重新索权。** preauth把“从仓库证据确认remote/分支/PR”误作向用户再申请批准，也漏认“不得因授权停下/停摆”。同镜像重放确认这是词面误报；两个before及主30preauth的真实边界缺项仍FAIL。扩展语法的反例审查又发现吞掉后续批准请求等漏报，已保留每版结果，最终修复增加同一请求的局部否定及范围目标检查，英文apply-for与合法范围外前缀共用语法；三名独立审查者在完整真实输出上验证重要反例关闭。封板源码在原镜像对原12输出回放及全Linux测试均通过，两窗口新增模型请求均0。
- **必要产物属于评测输入。** Batch当前版已在真实state规定固定分母，但final-only J没有收到state。原Skill允许deep执行细节置于state，本例也未要求必须在goal内复述。新J完整include被引用业务文件、原final逐字不改，不带原Skill corpus或完整G轨迹；两组和四个版本trial统一处理。main-without的806字节证据文件从原生成功FileChange.content逐字恢复，并校验之后没有工具/修改事件，未凭路径编造内容。
- **词面门槛不代替合同。** compaction删除不必要的外层英文`Progress`要求，仍用原脚本检查中英进度、每轮事项、剩余、下一步、里程碑commit和压缩前state；migration接受“独立推进的工作”同义，同时补局部否定反例，不能接受“不应继续独立推进”。

曾准备强制Batch进度内联的通用候选，静态三审无契约回归；随后证实判分漏state，故候选未实测、未采用。生产Skill一直保持当前冻结版，避免为迎合缺材料的判分器堆规则。

## 隔离与证据限度

原30输入、顺序、阈值、重试、CLI/二进制、模型/深度、镜像和容器策略保持；每次G/J隔离，没有宿主源码、Memory、凭据或Docker socket挂载，只有可信broker持真实认证。源9文件冻结，SDK按规则排除evals后运行7文件；catalog、实际全文加载和原生注入分别记录。主30有22例完整读取观测，不能说30例都用了Skill；普通非goal负触发允许不加载。

主30有16个语义Judge，全部清除目标catalog；但13份J上下文含G读取过的完整Skill，因此主30不称盲评。后续版本对照用fresh J，仅给应评产物及必要事实；少数产物措辞/task slug仍可能让评分者推测版本，不保证绝对盲化。

主30请求为218次尝试＝213次HTTP200/native用量记录＋5次已记录URLError/502后同请求成功重试。原严格全200审计失败保留，补充outcomes按请求/会话/连续计数闭环；不把传输故障称作capacity。SDK配置、expect短路和metadata-only文件名发现造成的采集错误均另存，恢复复用原G/J，不抹掉失败。

第三批仅验证缺项目材料时的brief合同，不证明缓存调查完成。真实初始环境probe没有业务源码/测试；共同事实完整进入实际J提示。8份G的工具过程另有索引与原始日志：观察到56条只读查询命令事件、0 FileChange，未观察到业务写入，但没有把事件列表当作OS层零副作用证明；未来拟定报告路径不是已有产物。

## 尚未解决或不在本轮门槛内

- preauth确定性检查器只覆盖已回归的有限语法，不保证任意自然语言判定。旧版失败与各版校准记录均保留，最终结果见calibrated-final；没有通过反复生成挑分。
- 自然30中仍有long-running、research、no-fabrication、preauth未通过；显式小样本成功不表示自动触发或随机遗漏已普遍解决。research/no-fab原自然输入没有观测到完整Skill读取，不为过例扩大普通brief的触发范围。
- 本次没有实施或验证capacity自动恢复。本地宿主边界记录`docs/capacity-goal-stall-evidence.md`把真实错误、当前源码、用户手动继续和可控checkpoint减损分开。
- 完整6.1全量及without全量对照、更多重复/随机化盲评、原30全部必要产物统一重判是明确后续TODO。本轮没有启动这些测试；Claude Code实机按用户要求在1.3跳过，不作为交付门槛，未标为通过。
