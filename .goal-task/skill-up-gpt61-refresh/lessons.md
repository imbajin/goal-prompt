# 评测证据经验候选

以下仅为本任务验证后的候选经验，不自动写入 AGENTS.md 或全局 Memory。

## 安装、调用与隔离分层

- 建议：将 Skill 安装、catalog 可见性、实际读取、宿主读取边界分开验证；显式调用测核心契约，自动调用测触发行为。
- 范围：Codex 0.164.0 / skill-up 0.14.0 本地 none runtime；不能据此推断其他版本或 OS 沙箱的行为。
- 证据：原 after-six 的 research 未读目标、no-fabrication 读宿主 write；controlled-research-v2 的 catalog 仅含目标且实际读取。
- 验证：零模型 prompt-input、实际 rollout catalog、成功读取命令及输出哈希交叉核查。
- 状态：pending；未经用户单独接受，不作为全局规则推广。

## 判分校准保留原始结果

- 建议：修正已复现的词面误判时同时补等价正例、相反或矛盾语义负例；用同一新 Judge 重放前后冻结输出，原 verdict 不改。
- 范围：当前确定性脚本的语义等价修复；不能用来删除有效断言、降低阈值或把未测改为通过。
- 证据：goal-prompt 路径误判、不创造工具、不得重复请求许可；test-judges.sh 与各 current-script-replay.json。
- 验证：原始 result/grading 与重放判分、脚本 SHA 分列；case status 使用 result 或 case_completed，不使用断言均分推断。
- 状态：pending。

## 压缩收益必须实测

- 建议：分开记录源文件长度、实际参考读取、CLI 累计 token、Agent 耗时和含 Judge 的 wall time，不能相互替代。
- 范围：此次代表性单样本，仅支持观测，不支持普遍效率结论。
- 证据：preauth 读取变短，skill-up 派生 input 为 220443 → 222886，CLI 原生 input 为 123931 → 122022，output 为 5039 → 5713，Agent duration_ms 为 137588 → 152587。
- 口径：skill-up 0.14.0 归一化额外加上 cached 字段，应与原生字段分列；不能直接推断实际消耗或计费。
- 验证：controlled-before-v2 / controlled-after-rest 的同协议清单、result 和 transcript-audit。
- 状态：pending；需更多样本才可形成稳定性能结论。
