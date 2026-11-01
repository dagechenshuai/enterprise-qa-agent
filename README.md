# 企业制度问答 Agent

输入制度问题与可选历史，模型自主调用本地检索、原文读取工具，输出有引用的回答、资料缺口或待澄清问题。资料均为合成内容，真实运行使用 DeepSeek 非思考模式；模型选择工具，程序执行工具并把结果交回模型。

评审从以下文件开始：

- [需求与验收](docs/01-requirements.md)
- [方案与决策循环](docs/02-solution.md)
- [实际评估与限制](docs/03-evaluation.md)
- [AI 使用范围](docs/04-ai-usage.md)
- [复盘](docs/05-retrospective.md)

## 当前交付状态

- 开发阶段 54 项自动化测试通过，覆盖率约 97%。
- 我在本地运行了八组真实模型场景，自动断言全部通过；[查看这次结果](examples/real/candidate-20261101T055834882035Z/summary.json)。
- 我完成方案设计、资料内容和测试用例，借助 AI 实现代码并整理文件，随后在本地执行测试。详细边界见 [AI 使用记录](docs/04-ai-usage.md)。
- 仓库地址：[dagechenshuai/enterprise-qa-agent](https://github.com/dagechenshuai/enterprise-qa-agent)。提交时使用题号 3、仓库 URL 和最终 commit SHA。

- 我另行运行了酒店报销、逾期后果和强制选择三个补充问题；[查看记录与过程分析](docs/03-evaluation.md#我的三组补充测试)。这些补测与原八组评估分别记录。

## 安装与离线运行

需要 Python 3.11+、uv；本次实际环境为 Python 3.12.4。以下命令均在本项目根目录执行，首次安装需要网络。项目不需要数据库、前端或标书平台。

```powershell
uv sync --locked
uv run enterprise-qa ask "报销要在几天内提交？" --mode mock
uv run enterprise-qa evaluate --mode mock
uv run pytest
```

`mock` 是有限规则替身，只能验证程序流程，不能证明真实模型决策效果。默认模式是 `real`，缺配置或模型出错时返回 `incomplete`，不会自动改用 Mock。

## 真实模型

将 `.env.example` 复制为 `.env`，填写 `MODEL_API_KEY`、`MODEL_BASE_URL` 和 `MODEL_NAME`。若 `.env` 已存在，直接编辑，避免覆盖已有配置。程序只读取当前目录 `.env`；已有进程环境变量优先。

```powershell
uv run enterprise-qa ask "报销要在几天内提交？" --mode real
uv run enterprise-qa ask "报销要在几天内提交？" --mode real --dataset data/conflict.json
uv run enterprise-qa ask "试用期也一样吗？" --mode real --history data/history.json
uv run enterprise-qa ask "报销要在几天内提交？" --mode real --fail-first-read
uv run enterprise-qa evaluate --mode real
```

DeepSeek 配置使用 `https://api.deepseek.com` 和 `deepseek-flash`；只在该官方域名发送 `thinking: disabled`。其他服务只实现 Chat Completions 工具协议，未作兼容性保证。真实运行会消耗模型额度；八组评估按顺序执行，调用次数由每个场景预算约束。

## 输出、上限与复现

默认每次在 `runs/<mode>/<UTC时间>/` 创建新目录。通过 `--output` 指定的新目录必须不存在，避免覆盖证据。

每次保存：`input.json`、`corpus.json`、`manifest.json`、`output.json`、`trace.jsonl`。批量评估另存每例 `assessment.json` 和整体 `summary.json`。

- `input.json`：问题、历史、预算、故障配置、资料摘要哈希。
- `corpus.json`：该次实际使用的资料快照。
- `manifest.json`：Python、依赖版本、模型名称和源码哈希。
- `trace.jsonl`：模型动作、参数、实际工具结果、后续动作与终止状态。下一条模型事件表示观察后的实际决定，不另造“决策理由”。
- `output.json`：答案、原文引用、缺口、冲突、追问与状态。

```powershell
uv run enterprise-qa ask "报销期限？" --mode real --max-tool-calls 1 --max-model-turns 3
uv run enterprise-qa ask "报销期限？" --mode real --timeout 30
```

默认最多 8 次工具调用、10 轮模型调用。多个工具分别计数，参数错误也计入预算；最终回答不消耗工具额度。网络超时为 HTTPX 各阶段超时，非严格的整个任务墙钟截止时间。

问答命令：`incomplete` 或输入错误退出码为 2，其余状态为 0。资料不足和待澄清是有效业务结果，并不意味着问题已得到答案。评估命令任一场景断言失败退出码为 1；配置/认证/余额错误会中止并列出未运行场景。

## 测试和证据

```powershell
uv run pytest --cov=enterprise_qa --cov-report=term-missing --junitxml=examples/test-results.xml
uv run black --check src tests
uv run isort --check-only src tests
```

实际结果和对应运行目录见 [评估报告](docs/03-evaluation.md)。示例中的 Mock 与真实记录分开保存；评估脚本只判断稳定属性，`semantic_review: pending` 表示还需要阅读答案与原文，不能自动视为语义通过。

## 限制

关键词检索可能漏掉表达差异大的文档，因此不能保证发现所有冲突。引用校验只证明引文真实且本次读取成功，不证明回答受到引文充分支持。合成资料规模小，当前结果不能外推为企业生产场景准确率。没有企业权限控制、持久对话服务或线上部署。

## 提交前

将整个项目复制到独立仓库目录，排除 `.env`、`.venv`、缓存和 `runs`，保留 `examples` 中的评审证据。不要把外层标书平台一起提交。

在独立目录初始化 Git 并检查暂存文件后提交，例如：

```powershell
git init -b main
git add .
git status --short
git diff --cached --stat
git commit -m "feat: implement evidence-grounded enterprise QA agent"
git rev-parse HEAD
```

自行创建 GitHub 仓库后设置 remote 并推送；私有仓库要给评审账号读取权限。通过 GitHub 页面核对最终提交 SHA 与本地 `git rev-parse HEAD` 一致。提交题号 3、仓库 URL 与该 SHA。交卷由我在考试页面完成。
