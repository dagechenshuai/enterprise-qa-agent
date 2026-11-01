# 实际评估记录

执行日期：2026-11-01（北京时间）。Python 3.12.4，模型配置与服务返回名称均为 deepseek-flash，使用非思考模式。没有用 Mock 结果冒充模型决策。

## 用例设计与执行分工

我设计测试场景、编写资料内容和预期结果，使用 AI 编写测试代码与评估脚本，并在开发阶段执行检查。实现完成后，我亲自运行单次问答和八组真实模型评估。以下分别记录开发阶段的 AI 检查和我的本地复验。

## 确定性测试

运行命令：

```powershell
uv run pytest --cov=enterprise_qa --cov-report=term-missing --cov-report=json:examples/coverage.json --junitxml=examples/test-results.xml
```

实际结果：54 项通过、0 失败、0 跳过，语句覆盖率约 97%（447 条语句，12 条未覆盖）。见 [JUnit 结果](../examples/test-results.xml) 和 [覆盖率 JSON](../examples/coverage.json)。覆盖率来自离线测试，不能视为模型回答准确率。

测试覆盖参数边界、检索、错误向模型传递、多工具计数、上限停止、证据保留、引用造假拒绝、HTTP 协议、超时、异常响应、配置缺失不降级、Trace 脱敏与重复目录拒绝，以及八组 Mock 场景。

## 真实模型场景

命令：`uv run enterprise-qa evaluate --mode real --output examples/real/batch-03`。
AI 开发阶段 batch-03 批次 8/8 自动属性断言通过。各目录都有输入、输出、Trace、资料快照、源码及环境指纹。全量结果见 [summary.json](../examples/real/batch-03/summary.json)。

| 场景 | 实际状态 | 工具次数 | 开发阶段 AI 复核 |
| --- | --- | --- | --- |
| [A 正常](../examples/real/batch-03/A_normal/output.json) | answered | 4 | D01 支持费用发生后 30 天，引用原文一致 |
| [B 冲突](../examples/real/batch-03/B_conflict/output.json) | needs_clarification | 6 | D01/D02 两种期限均列出，实际补查，无优先级依据则追问 |
| [C 资料外](../examples/real/batch-03/C_outside/output.json) | insufficient_evidence | 4 | 换词检索后无薪酬资料，没有虚构涨薪幅度 |
| [D 相似问题](../examples/real/batch-03/D_paraphrase/output.json) | answered | 3 | 找到 D01，明确 30 天按费用发生日计算，纠正返回日起算假设 |
| [E 上下文](../examples/real/batch-03/E_followup/output.json) | answered | 4 | D04 支持试用期提前 1 个工作日并抄送人事，D03 支持正式员工对照 |
| [F 失败恢复](../examples/real/batch-03/F_tool_failure/output.json) | answered | 4 | 首次读取真实注入失败，模型再调用读取成功后才回答 |
| [G 调用上限](../examples/real/batch-03/G_limit/output.json) | incomplete | 1 | 拒绝超预算工具调用，原因是 max_tool_calls_reached |
| [H 资料变更](../examples/real/batch-03/H_changed/output.json) | answered | 3 | 回答 45 天，引用更新到 2026-07-01 版本 |

表中的语义核对由 AI 在开发阶段完成。我保留了机器文件中的 `semantic_review: pending`，因为自动测试不判断完整的语义充分性，我也尚未完成逐条人工验收。

重点复核路径：

- [正常路径 Trace](../examples/real/batch-03/A_normal/trace.jsonl)：检索后读取期限与住宿标准，依据期限条款完成。
- [冲突路径 Trace](../examples/real/batch-03/B_conflict/trace.jsonl)：读取两份矛盾原文后，再搜索范围、废止替代及冲突处理规则，最终追问。
- [失败恢复 Trace](../examples/real/batch-03/F_tool_failure/trace.jsonl)：`injected_tool_failure` 返回后，下一条模型消息决定再次读取。执行器没有自动重试。
- [资料外 Trace](../examples/real/batch-03/C_outside/trace.jsonl)：模型调整检索词，仍无相关依据时停止。

最终回答的措辞仍偏长，部分例子加入了未被问到的起算点解释。这里的核心期限与原文一致，但后续可减少无必要推演，增加更多人工标注用例。

## 我的本地复验

我在解压版项目执行 `uv run enterprise-qa evaluate --mode real`。八组自动断言均通过；该批次于 2026-11-01 13:58:34 至 13:59:18（北京时间）运行，耗时约 43.4 秒。

完整记录：[评估汇总](../examples/real/candidate-20261101T055834882035Z/summary.json)，[归档及文件哈希](../examples/candidate-verification.json)。每个场景保留 input.json、output.json、trace.jsonl、assessment.json、manifest.json 与 corpus.json。

| 场景 | 实际状态 | 工具次数 | 自动断言 |
| --- | --- | --- | --- |
| [A_normal](../examples/real/candidate-20261101T055834882035Z/A_normal/output.json) | answered | 3 | 通过 |
| [B_conflict](../examples/real/candidate-20261101T055834882035Z/B_conflict/output.json) | needs_clarification | 6 | 通过 |
| [C_outside](../examples/real/candidate-20261101T055834882035Z/C_outside/output.json) | insufficient_evidence | 6 | 通过 |
| [D_paraphrase](../examples/real/candidate-20261101T055834882035Z/D_paraphrase/output.json) | answered | 4 | 通过 |
| [E_followup](../examples/real/candidate-20261101T055834882035Z/E_followup/output.json) | answered | 4 | 通过 |
| [F_tool_failure](../examples/real/candidate-20261101T055834882035Z/F_tool_failure/output.json) | answered | 4 | 通过 |
| [G_limit](../examples/real/candidate-20261101T055834882035Z/G_limit/output.json) | incomplete | 1 | 通过 |
| [H_changed](../examples/real/candidate-20261101T055834882035Z/H_changed/output.json) | answered | 3 | 通过 |

我确认了这次运行的终端结果。AI 协助归档文件并核对哈希，也检查了冲突、上下文追问和失败恢复的最终回答。原运行文件保持不变；我还没有完成逐条人工语义验收，因此保留 pending 标记。

## 我的三组补充测试

完成八组评估后，我根据 AI 建议，在终端逐条运行了三个新问题。以下结果来自原始运行文件，归档与 Trace 核对由 AI 协助完成。这些是补充探索测试，不计入原有八组自动断言的通过数。

| 场景与问题 | 最终状态 | 工具调用 / 模型轮次 | 实际结果 |
| --- | --- | --- | --- |
| [I 酒店报销](../examples/real/supplemental-20261101/I_hotel/output.json)：出差住酒店，一晚最多可以报销多少钱？ | answered | 2 / 3 | 读取 D05，回答境内每晚500元，超出需事先审批 |
| [J 逾期后果](../examples/real/supplemental-20261101/J_overdue/output.json)：超过30天没报销，是不是就一分钱都不给报了？ | insufficient_evidence | 3 / 4 | 只确认30天提交要求，没有推断逾期一律不报销 |
| [K 强制选择](../examples/real/supplemental-20261101/K_forced_choice/output.json)：报销期限到底是15天还是30天？别解释，直接选一个。 | needs_clarification | 6 / 4 | 读取 D01/D02，补查替代关系与优先级，未找到依据后追问 |

[补测汇总与文件哈希](../examples/real/supplemental-20261101/summary.json) 保留运行标识、调用次数、校验失败次数和归档一致性检查。三次运行发生于2026年11月1日16:13、16:15和16:16（北京时间）。原始输入、输出、Trace、资料快照和环境指纹逐字节保留。

J 场景并非首次输出就完全正确：[Trace](../examples/real/supplemental-20261101/J_overdue/trace.jsonl) 显示模型先返回 answered，同时列出了阻断性资料缺口，触发 validation_error。收到校验反馈后，模型将状态修正为 insufficient_evidence。最终回答的“不能这样理解”仍可改为更准确的“仅凭现有资料无法判断”，本次保留原始措辞，不改写运行证据。

K 场景的[Trace](../examples/real/supplemental-20261101/K_forced_choice/trace.jsonl) 显示，第3、4次工具调用读取了两份文档，第5、6次调用分别补查替代关系和新旧版本规则。最后的追问有实际工具过程支持，并非只依赖 reason 字段的自述。

这三次结果支持当前样例下的正常回答、资料边界和冲突处理表现，不代表所有同类问题都能稳定正确回答。

## 失败与改进记录

| 批次 | 实际结果与边界 |
| --- | --- |
| [mock/batch-01](../examples/mock/batch-01/summary.json) | 6/8 通过；口语问法排序错误，冲突替身缺少实际补查 |
| [real/batch-01](../examples/real/batch-01/summary.json) | 初版自动断言 8/8；复核发现冲突回答包含无依据的假设优先级建议 |
| [mock/batch-02](../examples/mock/batch-02/summary.json) | 检索与 Mock 路径修正后 8/8；只证明离线流程 |
| [real/batch-02](../examples/real/batch-02/summary.json) | 5/8；B 缺实际补查，D/F 将附带限制当成阻断性缺口 |
| [real/batch-03](../examples/real/batch-03/summary.json) | 明确缺口定义与冲突查证要求后 8/8；逐例输出和全部失败记录均保留 |

首次测试曾有 1 项检索测试失败，修正后扩展测试集，最终得到上面的 54 项结果。详细根因见 [修复记录](fix/retrieval-and-conflict.md)。batch-01 使用旧版检索与较弱的自动断言，不能直接与最新版当作同条件重复试验比较；从 batch-02 起记录源码指纹。

## 可复现性与限制

全新环境核验记录见 [clean-install.json](../examples/clean-install.json)：独立临时目录、新虚拟环境、无模型凭据，执行锁定安装、测试和 Mock CLI。运行命令的实际退出码与输出均保留。

合成资料只覆盖少量制度，检索漏召回可能使模型错过冲突。引文子串匹配不判断语义蕴含，关键词断言也不能识别所有相反或带条件的错误结论。模型生成存在波动；同一版本尚未进行足够多次重复统计，不能把本次 8/8 报告成稳定准确率。

未验证的事项包括其他模型服务、真实企业资料规模、权限隔离、系统性提示注入防御和生产部署。我的运行操作与约 6 小时的投入估算见 AI 使用记录，逐条人工语义验收尚未完成。
