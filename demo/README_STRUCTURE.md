# demo 目录说明

为保证“可直接跑”和“文件更整洁”，目录按下列方式整理：

- `demo_agentuniverse.py`：主功能文件（意图识别 + 多 Agent 调度）
- `test_demo.py`：批量测试脚本
- `intent_test_dataset/scenarios.json`：测试语料集（42 条）
- `scripts/`：实际执行脚本
  - `run_demo.bat`
  - `run_test.bat`
  - `check_python.bat`
- `tools/`：辅助工具脚本
  - `extract_docx_text.py`

兼容入口（不改你的习惯）：

- 根目录的 `run_demo.bat` / `run_test.bat` / `CHECK_PYTHON.bat` 仍可直接使用，
  它们会转发到 `scripts/` 下对应脚本。
