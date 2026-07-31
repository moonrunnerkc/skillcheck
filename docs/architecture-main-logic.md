# skillcheck 主干逻辑

> 梳理于 2026-07-31。基于 `src/skillcheck/` 源码,行号引用对应当时的 HEAD。
> 本文档描述模块间调用链与模式分发规则,是理解代码库的地图,不是规则手册(规则细节见各 `rules/*.py`)。

## 项目定位

**skillcheck** 是 `SKILL.md` 的静态分析器(Python CLI),对标 [agentskills.io](https://agentskills.io/specification) 规范做跨 agent 校验。核心承诺:**无网络调用、无 LLM 调用、不改动文件**——只读输入、纯函数计算、打印报告。唯一的"写"操作是 `--history` 模式下追加写 `.skillcheck-history.json` 账本。

## 分层架构

整个包是严格的**分层 + 纯函数**设计,数据以不可变 dataclass 单向流动:

```
cli.py(argparse 参数接线 / 模式分发)
  └─ commands.py(路径收集、各模式编排、退出码计算)
       ├─ core/symbolic.py(符号校验主入口 validate())
       │    ├─ parser.py(frontmatter / body 拆分)
       │    └─ rules/__init__.py(规则装配 get_rules())
       │         └─ rules/*.py(每个规则:ParsedSkill -> list[Diagnostic])
       ├─ core/semantic.py(agent 批判响应 → 语义诊断)
       ├─ core/graph.py + graph_analyzers.py(能力图 → 图诊断)
       ├─ core/history.py(历史账本 / 回归检测)
       ├─ agents/(各 agent 提示词变体 + JSON 解析器 + schema)
       └─ formatters.py(text / json / md / agent / github 五种输出)
```

依赖方向自上而下,`core` 与 `rules` 不反向依赖 `cli`/`commands`。`core/history.py` 只从标准库以及 `parser`、`result` 同级模块导入,不导入 `agents`、`cli`(见其模块 docstring),保证可独立测试。

## 数据模型(`result.py`)

- `Severity`:`ERROR` / `WARNING` / `INFO`。
- `Diagnostic`:`rule`、`severity`、`message`、`line`、`context`、`source`、`confidence`。`__post_init__` 按规则 ID 前缀自动推断 `source`(spec / advisory / heuristic / agent / history)与 `confidence`(high / medium / low)——这是诊断可信度分级的基础:规范结论高可信,启发式猜测中等,agent 结论低可信。
- `ValidationResult`:`valid` = 无 ERROR。

## 主流程一:入口与模式分发(`cli.py:main`)

1. 构建 argparse 解析器(`_build_parser`,`cli.py:44`),`_apply_config()` 把 `skillcheck.toml` 配置叠加到 CLI 参数上(CLI 优先,`cli.py:299`)。
2. `--strict` 展开成 strict-vscode + strict-cursor;`--semantic` 在未给 `--ingest-graph` 时隐含 `--analyze-graph`(`cli.py:498`)。
3. `_die_on_mode_conflict()`(`cli.py:406`)用静态冲突表 `_PAIRWISE_CONFLICTS`(`cli.py:355`)拒绝互斥组合,冲突退出码 `2`。
4. `resolve_paths()`(`commands.py:87`)把传入路径解析为 SKILL.md 文件列表(目录递归扫描 `SKILL.md`),不存在或扫不到则退出 `2`。
5. 按优先级分发到不同模式(详见下文"CLI 模式分发")。

## 主流程二:默认校验流水线(`commands.run_validation`,`commands.py:480`)

这是最核心的一条链:

1. **符号校验(总是执行)**:对每个 path 调 `core/symbolic.validate()`(`symbolic.py:10`):
   - `parse()`(`parser.py:33`)用 `_FRONTMATTER_RE` 拆分 frontmatter 与 body,YAML 解析失败报 `parse.error`;
   - `get_rules(...)`(`rules/__init__.py:93`)按参数装配规则集(frontmatter 规则 → 目录名匹配 → sizing → 描述质量 → references → disclosure → compat);
   - 每条规则产出 `Diagnostic` 列表,扁平化拼接;`ignore_prefixes` 按规则 ID 前缀过滤(`symbolic.py:54`);
   - 得到 `ValidationResult(path, diagnostics)`。
2. **语义增补(可选)**:
   - `--ingest-critique`:读 agent 批判 JSON → `core/semantic.ingest_critique_response`(`semantic.py:58`)转成 `semantic.*` 诊断(三档分数阈值 70/85 + missing context + contradiction + findings),合并进结果;
   - `--ingest-graph`:agent 提取图 → 图分析器 + **分歧分析器**(agent 图 vs 启发式图,`commands.py:554`);
   - `--analyze-graph`:纯启发式提取图 → 图分析器(`commands.py:579`)。
   - ingest 类 flag 解析出多个路径时直接退出 `2`(一次响应只能对应一个 skill,`commands.py:489`)。
3. **退出码计算** `_compute_exit_code`(`commands.py:307`):
   - 符号错误或 ingest 解析失败 → `1`;
   - 仅 `semantic.*` 错误(符号校验通过)→ `3`;
   - 仅警告 → `--strict` 时为 `1`,否则 `0`。
4. **`--history`**:构建 `LedgerEntry` 写入账本(`_record_history`,`commands.py:336`),`check_regression()` 对比历史条目检测回归(`history.skill.regressed`),`--fail-on-regression` 可升级退出码。
5. **`_print_report`**(`commands.py:411`):按 format 交给 `formatters` 打印;`--explain-score` 时附带描述质量评分的维度明细。

## 规则体系(`rules/`)

规则注册表 `rules/__init__.py` 按功能分类装配,每类是一组 `(ParsedSkill) -> list[Diagnostic]` 纯函数:

- **frontmatter**(`rules/frontmatter*.py`):name / description 必填、类型、长度、字符集、保留字、目录名匹配、yaml 锚点、未知字段等。
- **sizing**(`rules/sizing.py`):行数 / token 阈值,用工厂函数 `make_line_count_rule` / `make_token_estimate_rule` 按参数定制。
- **description**(`rules/description.py`):0-100 质量评分 + 可选 `--min-desc-score`。
- **references**(`rules/references.py`):坏链接、深度限制。
- **disclosure**(`rules/disclosure.py`):渐进式披露 token 预算(metadata 100 / body 5000)、膨胀检测。
- **compat**(`rules/compat.py`):跨 agent 兼容矩阵(`config.COMPAT_MATRIX`),strict 模式用 `make_strict_vscode_rule` / `make_strict_cursor_rule` 把 INFO 升级成 ERROR,并按 `target_agent` 裁剪。

阈值常量集中在 `config.py`(500 行 / 8000 token / 各预算 / 保留字 / 兼容矩阵);扩展字段与保留字可被 `skillcheck.toml` 覆盖(`config_loader.py`)。

## 扩展子系统

- **agent 提示词**(`agents/`):`SelfCritiquePrompt` / `GraphExtractionPrompt` 抽象基类 + claude / codex / cursor 三个变体(只换措辞,JSON schema 不变,`agents/__init__.py`);schema 随包发布在 `skillcheck/schemas/`。
- **能力图**(`core/graph*.py`):`extract_graph_heuristic`(`graph.py:306`)面向中文 SKILL.md(祈使动词分类、章节前缀剥离、输入/输出章节别名),产出 `CapabilityGraph`;`graph_analyzers`(`graph_analyzers.py`)五个纯函数分析孤儿能力 / 未用输入 / 未产出输出 / 空描述 / 未引用工具。
- **历史账本**(`core/history.py`):追加式 JSON,记录运行模式 / agent / 结果统计 / 技能内容哈希(前 16 位 SHA-256),**不记录诊断细节**,可安全提交 git。

## 分发说明

### CLI 模式分发(mode dispatch)

skillcheck 的所有 CLI 模式分为三类:**emit(替换报告)/ augment(合并进报告)/ validate(默认)**。`cli.py` 先做参数校验与冲突拒绝,再按固定顺序分发。

**模式清单**

| 类别 | Flag | 行为 | 退出 |
|---|---|---|---|
| emit | `--show-history` | 读第一个路径的账本并打印 | 0(无账本/读失败为 2 / 1) |
| emit | `--emit-graph` | 启发式能力图输出,替换报告 | 0 |
| emit | `--emit-critique-prompt` | 打印 agent 批判提示词,跳过校验 | 0 |
| emit | `--emit-graph-prompt` | 打印图提取提示词,跳过校验 | 0 |
| emit | `--agent-reason`(未配 ingest 时) | 打包批判 + 图两份提示词 | 0 |
| emit | `--activation-hypotheses` | 实验性:生成激活触发词 | 0 |
| augment | `--ingest-critique PATH` | 读取 agent 批判 JSON,合并语义诊断 | 见退出码 |
| augment | `--ingest-graph PATH` | 读取 agent 图 JSON,合并图 + 分歧诊断 | 见退出码 |
| augment | `--analyze-graph` | 启发式图分析,合并图诊断 | 见退出码 |
| validate | (默认) | 完整符号校验流水线 | 见退出码 |

**分发顺序**(`cli.py:520` 起,`resolve_paths` 之后):

1. `--show-history` → `run_show_history`;先于所有 emit。
2. `--emit-graph` → `emit_graph`。
3. `--emit-critique-prompt` → `emit_critique_prompts`。
4. `--emit-graph-prompt` → `emit_graph_prompts`。
5. `--agent-reason`(且未配 ingest)→ `emit_agent_reason_packet`。
6. `--activation-hypotheses` → `emit_activation`。
7. 其余全部 → `run_validation`(默认校验流水线)。

**冲突规则**(`_die_on_mode_conflict`,`cli.py:406`):

- **多个 emit 同时激活** → 只报前两个,退出 `2`。
- **静态成对冲突表** `_PAIRWISE_CONFLICTS`(`cli.py:355`)拒绝互斥组合,主要是:
  - `--emit-critique-prompt` ↔ `--ingest-critique`(emit 与 augment 互斥);
  - `--emit-graph` ↔ `--analyze-graph`(替换与增补互斥);
  - `--emit-graph` / `--emit-graph-prompt` ↔ `--ingest-critique`;
  - `--ingest-graph` ↔ `--emit-graph` / `--emit-critique-prompt` / `--analyze-graph`;
  - `--emit-graph-prompt` ↔ `--ingest-graph`(提示词与响应应分两次调用)。
- **emit 与 `--history` / `--show-history` 不兼容**:emit 跳过校验,而历史记录依赖校验,同时给时退出 `2`。
- `--show-history` 与 `--history` 互斥(读 vs 写账本,`cli.py:503`)。
- **ingest 只对一个技能有效**:`--ingest-critique` / `--ingest-graph` 解析出多个 SKILL.md 时退出 `2`(`commands.py:489`)。

**退出码映射**(`_compute_exit_code`,`commands.py:307`):

| 码 | 含义 |
|---|---|
| `0` | 无错误;仅警告时在非 `--strict` 下也算 0 |
| `1` | 有 ERROR;`--strict` 下仅警告;`--fail-on-regression` 下出现回归;ingest 解析失败 |
| `2` | 输入/参数错误(路径缺失、flag 冲突、ingest 指向多技能) |
| `3` | 符号校验通过,但 ingest 的批判报告了 `semantic.*` ERROR |

`1` 与 `3` 同时适用时 `1` 优先,CI 消费者看到更高严重级信号。

### 对外分发渠道(distribution)

skillcheck 同时以四种方式对外分发:

1. **PyPI 包**:`pip install skillcheck`(Python 3.10+);可选 `pip install "skillcheck[tiktoken]"` 获得更准的 token 估算(`tokenizer.py`)。发布流程见 README「Releases」:打 `v*` 标签触发 `.github/workflows/release.yml`,构建 wheel/sdist、SLSA 构建溯源证明、通过 trusted publishing 发 PyPI;未打 tag 的构建不发布。
2. **GitHub Action**:`uses: moonrunnerkc/skillcheck@v1`,输入在 `action.yml`;诊断以 inline PR annotation 呈现(`--format github` 输出 `::error/::warning/::notice` 工作流命令)。
3. **pre-commit hook**:仓库内置 `skillcheck` hook(`.pre-commit-hooks.yaml`),默认传 `--no-color` 保持日志干净,可用 `args:` 覆盖(如 `["--no-color", "--strict"]`)。
4. **自身作为 skill 分发**:`skills/skillcheck/SKILL.md` 是能通过全部规则的自托管 SKILL.md,供 agent 调用 CLI 完成校验、智能体评审、能力图提取、历史检查四种用法。

**设计要点总结**:

1. **模式正交**:emit(替换报告)/ augment(合并进报告)/ 校验三类模式用静态冲突表强制互斥,规则简单可预期。
2. **纯函数为主**:除文件读写(parse、ingest、history、print)外几乎无 I/O,可测试性极强(README 称 776 个测试)。
3. **诊断带元信息**:source + confidence 让规范结论、启发式猜测、agent 低可信结论可以区分对待。
4. **退出码语义化**:`0 / 1 / 2 / 3` 分别对应通过 / 错误 / 输入错误 / 语义漂移,CI 消费者可直接依赖。
