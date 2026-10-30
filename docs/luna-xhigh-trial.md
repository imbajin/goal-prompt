# Luna xhigh 试用验证

此前已完成 **GPT-6.1 Sol / high** 的with-Skill定向实测：17个唯一case，主要16例原14 PASS / 2 FAIL，两项误报用原输出重判PASS，最终bundle另补测2次PASS（其中1例重叠）。详见[6.1实测报告与本地证据索引](../evals/skill-up/gpt61-refresh.md)。它与本页Luna批次分开；下文“完整6.1全量TODO”不表示6.1从未实测。

本轮只使用 `gpt-6-luna / xhigh`，已完成原30例with-Skill及五例小规模版本对照；没有重跑without生成组或新增其它模型。

| 原30例口径 | without PASS / FAIL | with-Skill PASS / FAIL |
| --- | ---: | ---: |
| 原始输出及原生判分 | 6 / 24 | 22 / 8 |
| 同镜像脚本校准 | 7 / 23 | 25 / 5 |
| 再补Batch真实业务文件作局部重判 | 7 / 23 | 26 / 4 |

均无ERROR。局部材料校准不是Skill改进，也不是全30例重新盲评。主30有22例观测到完整Skill读取；13/16语义Judge上下文含G读取的Skill全文，因此不称盲评。

精简前后对照使用同一显式调用前缀、输入、模型/深度、镜像及case门槛，每版每例两次，先long，再batch/preauth，最后research/no-fabrication。case总状态分别为：

| 案例 | 精简前通过 | 当前版通过 |
| --- | ---: | ---: |
| long-running | 2/2 | 2/2 |
| batch | 0/2 | 2/2 |
| preauthorized-permissions | 0/2 | 2/2 |
| research | 0/2 | 2/2 |
| no-fabrication | 2/2 | 2/2 |

Batch两个before没有输出已授权的goal，原expect FAIL、语义项SKIP；current收到实际state后语义PASS。不是两次语义FAIL对两次语义PASS。主文26214→13163字符，同时包含授权路由和宿主边界修复，不能单独归因于长度，也不证明统计稳定性或成本节省。

修正的误报包括把否定提及`/goal`当成提前成品命令、把仓库事实核实当成向用户重新索权，以及Batch评分遗漏final引用的真实state。所有重判复用原生成；真正缺少安全优先级边界的输出仍FAIL，原始分数不覆盖。最终修复经三名独立修后复审、原输出同镜像回放和完整Linux检查；零新增模型请求。英文许可语法只支持已回归的有限表达，不宣称通用自然语言理解。

每次生成和语义评分用fresh Docker；无宿主源码/Memory/凭据/socket挂载，只有独立broker持真实认证。原配置、原输出、评分依据、请求及容器审计已在本地按批次封存；本试用PR先发布实现和这份摘要，没有公开全部本地原始档案或其它聊天资料。详细口径见[配对报告](../evals/skill-up/luna-with-skill-paired.md)；原始档案目录已加入ignore，不随源码合入。

自然30仍有long/research/no-fabrication/preauth未通过；显式小样本成功不代表自然触发或随机遗漏已解决。没有实现capacity自动恢复。完整6.1全量、without全量、Claude Code实机及更多重复/随机化盲评仍是后续TODO，本轮没有启动。
