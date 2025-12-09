# Test脚本整理方案

## 当前问题

项目中的test脚本分散在多个位置：
- **根目录**：11个test文件
- **scripts/目录**：3个test文件

这导致项目结构混乱，难以维护。

---

## 发现的Test文件清单

### 根目录 (项目根/Wenning/)
1. `test_evaluation_framework.py` - 评测框架测试
2. `test_end_to_end.py` - 端到端测试
3. `test_evaluation_only.py` - 仅评测测试
4. `test_evaluation_with_llm_judge.py` - LLM评判器测试
5. `test_agent_execution.py` - Agent执行测试
6. `test_font_injection.py` - 字体注入测试
7. `test_claude_fc.py` - Claude函数调用测试
8. `test_gemini_integration.py` - Gemini集成测试
9. `test_minimax_tts.py` - MiniMax TTS测试
10. `test_all_minimax.py` - MiniMax全套测试
11. `test_gemini_multiround.py` - Gemini多轮测试
12. `test_gemini_merge_messages.py` - Gemini消息合并测试

### scripts/目录
1. `scripts/test_basic.py` - 基础功能测试
2. `scripts/test_agent_e2e.py` - Agent端到端测试
3. `scripts/test_conversation_manager_v2.py` - 对话管理器V2测试

---

## 整理方案

### 目标结构

```
Wenning/
├── tests/                          # 新建：统一测试目录
│   ├── __init__.py
│   ├── unit/                       # 单元测试
│   │   ├── __init__.py
│   │   ├── test_conversation_manager_v2.py
│   │   └── test_font_injection.py
│   ├── integration/                # 集成测试
│   │   ├── __init__.py
│   │   ├── test_claude_fc.py
│   │   ├── test_gemini_integration.py
│   │   ├── test_gemini_multiround.py
│   │   ├── test_gemini_merge_messages.py
│   │   ├── test_minimax_tts.py
│   │   └── test_all_minimax.py
│   ├── e2e/                        # 端到端测试
│   │   ├── __init__.py
│   │   ├── test_end_to_end.py
│   │   ├── test_agent_execution.py
│   │   ├── test_agent_e2e.py
│   │   └── test_basic.py
│   └── evaluation/                 # 评测系统测试
│       ├── __init__.py
│       ├── test_evaluation_framework.py
│       ├── test_evaluation_only.py
│       └── test_evaluation_with_llm_judge.py
├── scripts/                        # 工具脚本（非测试）
│   ├── cleanup_duplicates.py
│   ├── dedupe_conversations.py
│   ├── migrate_attach_generated_files.py
│   └── update_output_dirs.py
└── ...
```

---

## 分类逻辑

### 1. 单元测试 (tests/unit/)
- 测试单个模块或类的功能
- 文件：
  - `test_conversation_manager_v2.py` - 对话管理器单元测试
  - `test_font_injection.py` - 字体处理单元测试

### 2. 集成测试 (tests/integration/)
- 测试多个模块/服务的集成
- 文件：
  - `test_claude_fc.py` - Claude API集成
  - `test_gemini_integration.py` - Gemini API集成
  - `test_gemini_multiround.py` - Gemini多轮对话集成
  - `test_gemini_merge_messages.py` - Gemini消息处理集成
  - `test_minimax_tts.py` - MiniMax TTS集成
  - `test_all_minimax.py` - MiniMax全套工具集成

### 3. 端到端测试 (tests/e2e/)
- 测试完整的用户场景
- 文件：
  - `test_end_to_end.py` - 完整流程测试
  - `test_agent_execution.py` - Agent完整执行测试
  - `test_agent_e2e.py` - Agent端到端场景
  - `test_basic.py` - 基础功能端到端测试

### 4. 评测系统测试 (tests/evaluation/)
- 测试评测框架本身
- 文件：
  - `test_evaluation_framework.py` - 评测框架测试
  - `test_evaluation_only.py` - 独立评测功能测试
  - `test_evaluation_with_llm_judge.py` - LLM评判器测试

---

## 执行步骤

### 步骤1: 创建目录结构
```bash
mkdir -p tests/{unit,integration,e2e,evaluation}
touch tests/__init__.py
touch tests/unit/__init__.py
touch tests/integration/__init__.py
touch tests/e2e/__init__.py
touch tests/evaluation/__init__.py
```

### 步骤2: 移动文件
```bash
# 单元测试
mv scripts/test_conversation_manager_v2.py tests/unit/
mv test_font_injection.py tests/unit/

# 集成测试
mv test_claude_fc.py tests/integration/
mv test_gemini_integration.py tests/integration/
mv test_gemini_multiround.py tests/integration/
mv test_gemini_merge_messages.py tests/integration/
mv test_minimax_tts.py tests/integration/
mv test_all_minimax.py tests/integration/

# 端到端测试
mv test_end_to_end.py tests/e2e/
mv test_agent_execution.py tests/e2e/
mv scripts/test_agent_e2e.py tests/e2e/
mv scripts/test_basic.py tests/e2e/

# 评测系统测试
mv test_evaluation_framework.py tests/evaluation/
mv test_evaluation_only.py tests/evaluation/
mv test_evaluation_with_llm_judge.py tests/evaluation/
```

### 步骤3: 修复导入路径
移动后需要检查每个test文件的import语句，确保路径正确。

例如，如果原来是：
```python
from src.utils.config import get_config
```

现在可能需要改为：
```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.config import get_config
```

或者使用相对导入（如果有pytest配置）。

---

## 附加建议

### 1. 创建pytest配置
创建 `pytest.ini` 或 `pyproject.toml` 配置pytest：

```ini
# pytest.ini
[pytest]
pythonpath = .
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
```

### 2. 创建测试运行脚本
创建 `run_tests.sh`：

```bash
#!/bin/bash
# 运行所有测试
pytest tests/ -v

# 运行特定类型的测试
# pytest tests/unit/ -v
# pytest tests/integration/ -v
# pytest tests/e2e/ -v
# pytest tests/evaluation/ -v
```

### 3. 添加到.gitignore
确保测试产生的临时文件被忽略：

```gitignore
# 测试缓存
.pytest_cache/
__pycache__/

# 测试输出
tests/outputs/
tests/logs/
```

---

## 清理后的目录结构预览

```
Wenning/
├── tests/                          # ✅ 统一测试目录
│   ├── unit/                       # 2个文件
│   ├── integration/                # 6个文件
│   ├── e2e/                        # 4个文件
│   └── evaluation/                 # 3个文件
├── scripts/                        # ✅ 仅保留工具脚本（非测试）
├── src/                            # ✅ 源代码
├── docs/                           # ✅ 文档
├── static/                         # ✅ 前端资源
├── fastapi_app.py                  # ✅ 主应用
├── requirements.txt                # ✅ 依赖
└── pytest.ini                      # ✅ 测试配置
```

---

## 风险提示

⚠️ **移动前请确认**：
1. 这些test文件是否还在使用？
2. 是否有CI/CD流程依赖这些文件的路径？
3. 是否有文档引用了这些文件的路径？

建议：先备份当前状态，然后逐步迁移和验证。
