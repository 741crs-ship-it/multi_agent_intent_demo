# demo 项目说明（意图识别 + 多 Agent 调度）

这个 `demo` 文件夹是一个可运行的 Python 示例项目，核心目标是演示：

- 自然语言输入的**意图识别**
- 基于意图的**多 Agent 调度**
- 支持**串行 / 并行**两种调度模式

适合用于快速验证“总控 Agent + 子 Agent 协作”这条主流程。

---

## 1. 文件夹结构说明

> 以下是你最常用、最关键的文件和目录。

- `demo_agentuniverse.py`：核心功能文件（意图识别 + 多 Agent 调度）
- `test_demo.py`：批量测试脚本，循环测试语料
- `intent_test_dataset/scenarios.json`：测试语料集（42 条问题）
- `scripts/`：可执行脚本目录（内部脚本）
- `run_demo.bat`、`run_test.bat`、`CHECK_PYTHON.bat`：根目录可直接执行脚本（推荐直接使用）
- `tools/`：辅助工具脚本（例如 `extract_docx_text.py`，用于 docx 提取）

可忽略目录/文件：

- `.vscode/`
- `__pycache__/`
- 其他临时缓存文件

---

## 2. 环境依赖

- Python 3.10+
- 安装依赖：

```bash
pip install agentuniverse
```

> 如果你的环境里 `pip` 不可用，也可以用：
> `python -m pip install agentuniverse`

---

## 3. 运行步骤

先进入项目目录：

```bash
cd C:\Users\1\Desktop\demo
```

### 3.1 运行 Demo（核心脚本）

```bash
python demo_agentuniverse.py
```

说明：

- 支持**交互式输入**（手动输入问题）
- 也支持**内置示例**（不输入问题，直接回车）

你也可以直接使用根目录脚本（更稳）：

```bash
run_demo.bat
```

---

### 3.2 运行批量测试

```bash
python test_demo.py
```

作用：

- 批量执行测试问题
- 自动触发意图识别 + 多 Agent 调度
- 输出每条问题对应的执行日志和结果汇总

你也可以用：

```bash
run_test.bat
```

---

### 3.3 串行 / 并行调度模式

- 串行：`mode="serial"`
  - 按依赖顺序执行
  - 适合有前后依赖关系的场景（例如先风控，再转账）
- 并行：`mode="parallel"`
  - 同时发起多个子任务
  - 适合无强依赖、偏信息聚合的场景

---

## 4. 测试数据说明

- 测试数据在：`intent_test_dataset/scenarios.json`
- 共 42 条问题，包含：
  - 单一意图场景
  - 多意图组合场景
- 每条问题都会被总控 Agent 处理：
  1. 识别意图
  2. 生成调度计划
  3. 调用对应子 Agent
  4. 汇总结果

可用于验证：

- 意图识别是否符合预期
- 多 Agent 调度是否符合依赖关系
- 串行/并行模式行为是否正确

---

## 5. 示例输出（便于理解）

输入：

```text
帮我查询余额并转账100万
```

示例输出：

```text
[intent_classifier_agent] 意图识别: ['balance_query', 'transfer', 'risk_check']
[master_agent] 串行模式调度顺序: ['risk_check', 'balance_query', 'transfer']
[risk_agent] 执行风控检查
[balance_agent] 执行余额查询
[transfer_agent] 执行转账
[结果汇总] 所有 Agent 执行完成
```

---

## 6. 使用建议

1. 先跑 `python demo_agentuniverse.py`，熟悉单条输入流程
2. 再跑 `python test_demo.py`，看批量结果
3. 看日志时重点关注三行：
   - 意图识别结果
   - 调度顺序
   - 最终结果汇总
4. 如果 `python` 命令异常，先执行 `CHECK_PYTHON.bat` 排查解释器路径

---

## 7. 一句话总结

这个 demo 已经具备“可演示、可测试、可扩展”的基本形态，适合用于同事快速理解和验证：

**意图识别 -> 任务路由 -> 多 Agent 调度 -> 结果汇总**

