# Plan工具合并分析

## 背景

用户提议：是否可以将`create_plan`工具合并到`file_editor`中，并在system prompt中提示Agent用file_editor来创建和编辑plan文档？

## 当前实现分析

### Plan工具的实际功能（src/tools/atomic/plan.py）

**核心特性**：
1. **结构化参数接口** - 接收`task_description`和`steps`数组
2. **严格格式验证** - 验证每个step必须包含`step`、`action`、`status`字段
3. **状态值验证** - 确保status只能是`pending/in_progress/completed/failed`
4. **自动统计计算** - 自动计算`completed_steps`、`pending_steps`等
5. **格式化摘要生成** - 调用`_format_plan_summary()`生成用户友好的展示
6. **内存状态管理** - 保存在`self.current_plan`

**关键问题**：
- ❌ **不持久化到文件** - 只保存在内存中，会话重启后丢失
- ❌ **无法跨轮次追踪** - Agent无法在后续轮次中读取之前的plan

### File Editor的功能（src/tools/atomic/file_editor.py）

**核心特性**：
1. **通用文本编辑** - 支持任意文本文件
2. **两种编辑模式** - 精确字符串替换、行范围编辑
3. **上下文验证** - 确保在正确位置修改
4. **Diff预览** - 显示修改前后对比
5. **文件持久化** - 直接写入文件系统

**不提供的能力**：
- ❌ 无结构化参数验证
- ❌ 无特定格式的验证逻辑
- ❌ 无自动统计计算
- ❌ 无格式化输出

---

## 方案对比

### 方案A：保留plan工具，增强持久化 ✅ 推荐

**实施内容**：
1. **保留plan工具的所有当前能力**（结构化验证、自动统计、格式化摘要）
2. **增加文件持久化** - 将plan同时保存到`{conversation_id}/plan.json`
3. **增加读取能力** - 支持从文件读取已有plan
4. **保持结构化接口** - Agent通过结构化参数调用

**代码改动示例**：
```python
def execute(self, **kwargs) -> Dict[str, Any]:
    # ... 现有验证逻辑 ...

    # 保存计划到内存（现有）
    self.current_plan = { ... }

    # 新增：持久化到文件
    plan_file = self.output_dir / conversation_id / "plan.json"
    with open(plan_file, 'w', encoding='utf-8') as f:
        json.dump(self.current_plan, f, ensure_ascii=False, indent=2)

    return {
        "summary": summary,
        "plan": self.current_plan,
        "saved_to": "plan.json"  # 新增：告知Agent文件位置
    }
```

**优势**：
- ✅ **保留专业性** - 结构化验证避免Agent构造错误格式
- ✅ **自动化便利** - Agent不需要自己计算统计信息
- ✅ **用户友好** - 自动生成格式化摘要
- ✅ **错误预防** - 类型验证和状态验证防止常见错误
- ✅ **持久化** - 解决当前的内存丢失问题
- ✅ **符合最佳实践** - 参考Claude Code的TodoWrite也是专用工具

**劣势**：
- ❌ 工具数量保持13个（不减少）
- ❌ 需要额外的代码改动（增加持久化逻辑）

**对比参考 - Claude Code的TodoWrite工具**：
```python
# Claude Code使用专用的TodoWrite工具，而不是让Agent用文件编辑器
TodoWrite(todos=[
    {"content": "task1", "status": "pending", "activeForm": "..."},
    {"content": "task2", "status": "completed", "activeForm": "..."}
])
```
- Claude Code的设计理念：**专用工具处理特定领域逻辑**
- TodoWrite提供：结构化参数、状态验证、格式化输出
- **没有让Agent用通用文件编辑器手动维护todo列表**

---

### 方案B：合并到file_editor

**实施内容**：
1. **移除plan工具**
2. **System Prompt中提供plan格式指导**：
   ```
   当需要规划复杂任务时，使用file_editor创建plan.json文件，格式：
   {
     "task_description": "...",
     "steps": [
       {"step": 1, "action": "...", "status": "pending", "result": ""},
       {"step": 2, "action": "...", "status": "in_progress", "result": ""}
     ]
   }

   状态值只能是：pending、in_progress、completed、failed
   ```
3. **Agent自行管理**：
   - 自己构造正确的JSON格式
   - 自己计算进度统计
   - 自己生成摘要展示

**优势**：
- ✅ **减少工具数量** - 13个→12个
- ✅ **自然持久化** - 文件天然持久化
- ✅ **简化工具集** - 更少的工具学习成本

**劣势**：
- ❌ **失去格式验证** - Agent可能构造错误的JSON或使用无效的status值
- ❌ **增加Agent负担** - Agent需要自己计算completed_steps、pending_steps等
- ❌ **失去自动摘要** - Agent需要自己格式化用户友好的展示
- ❌ **潜在错误风险** - 手动编辑JSON易出错（缺少字段、状态拼写错误等）
- ❌ **与最佳实践不符** - Claude Code选择了专用工具而非通用编辑器

**风险场景示例**：
```python
# Agent可能犯的错误：
{
  "steps": [
    {"step": 1, "action": "...", "status": "complete"},  # ❌ 应该是"completed"
    {"step": 2, "action": "..."}  # ❌ 缺少required字段"status"
  ]
}
```

---

## 核心决策点

### 1. 工具设计哲学

**Anthropic的"Just Right"原则**：
- 工具应该有**清晰的责任边界**
- 避免"Too Vague"（太通用，缺少引导）
- 避免"Too Specific"（过度限制灵活性）

**Plan工具的定位**：
- **特定领域逻辑** - 任务规划、进度跟踪、状态管理
- **结构化保证** - 确保数据格式正确性
- **用户体验优化** - 自动生成友好摘要

### 2. Agent能力 vs 工具职责

**方案A的理念**：工具承担专业逻辑，Agent专注任务
- Plan工具负责：格式验证、统计计算、摘要生成
- Agent负责：决定何时创建plan、更新哪些步骤

**方案B的理念**：Agent自行管理一切
- File Editor只负责：写入文件
- Agent负责：构造JSON、验证格式、计算统计、生成摘要

**类比**：
- 方案A ≈ 使用ORM（对象关系映射）- 框架处理细节
- 方案B ≈ 使用原生SQL - 开发者处理一切

### 3. 参考案例对比

| 系统 | Plan/Todo管理方式 | 设计选择 |
|------|------------------|---------|
| **Claude Code** | TodoWrite（专用工具） | ✅ 结构化工具 |
| **LangChain** | PlanAndExecute（专用组件） | ✅ 结构化组件 |
| **AutoGPT** | Task管理器（专用模块） | ✅ 结构化模块 |
| **方案A** | create_plan（专用工具） | ✅ 结构化工具 |
| **方案B** | file_editor（通用编辑） | ❌ 通用工具 |

**行业趋势**：主流Agent系统都选择了**专用的结构化工具**来处理Plan/Todo管理，而非通用文件编辑器。

---

## 推荐决策

### ✅ 推荐方案A：保留并增强plan工具

**理由**：
1. **符合行业最佳实践** - Claude Code等主流系统都使用专用工具
2. **保持专业性** - 结构化验证和自动化处理体现工具价值
3. **降低错误风险** - 避免Agent手动构造JSON的常见错误
4. **用户体验更好** - 自动生成的格式化摘要更友好
5. **边界清晰** - Plan工具负责任务规划领域逻辑，职责明确

**实施步骤**：
1. 修改`plan.py`增加文件持久化逻辑（约20行代码）
2. 增加从文件读取已有plan的能力（可选）
3. 在description中说明plan会自动保存到文件

**代码改动量**：小（约30行）

### ⚠️ 备选方案B：仅在以下情况考虑

如果满足以下**所有条件**，可以考虑方案B：
1. 强烈需要减少工具数量（如有硬性限制）
2. 使用的LLM能力极强，自我管理能力突出
3. 愿意在system prompt中提供详细的格式指导
4. 接受Agent可能犯错导致的plan格式问题
5. 愿意监控和修复Agent的格式错误

---

## 实施建议

### 如果选择方案A

**立即改动**（优先级高）：
```python
# src/tools/atomic/plan.py - 增加持久化
def execute(self, **kwargs) -> Dict[str, Any]:
    conversation_id = kwargs.get("conversation_id")
    if not conversation_id:
        raise ValueError("缺少conversation_id参数")

    # ... 现有验证逻辑 ...

    # 保存计划（内存）
    self.current_plan = { ... }

    # 新增：持久化到文件
    plan_dir = self.output_dir / conversation_id
    plan_dir.mkdir(parents=True, exist_ok=True)
    plan_file = plan_dir / "plan.json"

    with open(plan_file, 'w', encoding='utf-8') as f:
        json.dump(self.current_plan, f, ensure_ascii=False, indent=2)

    logger.info(f"Plan已保存到: {plan_file}")

    return {
        "summary": summary,
        "plan": self.current_plan,
        "saved_to": "plan.json"
    }
```

**可选改动**（优先级中）：
- 增加`load_plan()`方法从文件读取
- 增加`update_step()`方法更新单个步骤

**Description优化**：
```python
description = (
    "任务规划工具: 为复杂多步骤任务创建执行计划和进度跟踪（自动保存到plan.json）。"
    "适用场景：任务包含3个以上步骤、需要分阶段执行、需要向用户展示进度。"
    "典型场景：数据分析项目（获取→清洗→分析→可视化）、内容创作流程（调研→撰写→配图→校对）。"
    "优势：结构化验证、自动统计进度、格式化摘要展示、自动持久化。"
    "不适用：简单的单步或两步任务。"
    "参数: task_description(任务总体描述), steps(步骤列表), conversation_id(必需)"
)
```

### 如果选择方案B

**System Prompt增加**（约30行）：
```markdown
## 任务规划管理

当任务包含3个以上步骤时，使用file_editor创建plan.json来跟踪进度：

**格式规范**：
{
  "task_description": "任务总体描述",
  "steps": [
    {
      "step": 1,
      "action": "步骤1描述",
      "status": "pending",  // 必须是：pending, in_progress, completed, failed
      "result": "执行结果（可选）"
    },
    {
      "step": 2,
      "action": "步骤2描述",
      "status": "in_progress",
      "result": ""
    }
  ]
}

**更新流程**：
1. 创建plan.json - 使用file_editor创建初始计划
2. 更新进度 - 每完成一步，更新对应step的status和result
3. 向用户汇报 - 读取plan.json，计算进度并展示

**常见错误**：
- ❌ status拼写错误（如"complete"应为"completed"）
- ❌ 缺少必需字段（step、action、status）
- ❌ JSON格式错误（缺少逗号、引号不匹配）
```

**移除工具**：
- 从`fastapi_app.py`移除`PlanTool`注册
- 删除`src/tools/atomic/plan.py`

---

## 结论

**强烈推荐方案A**：保留并增强plan工具

**核心论据**：
1. **行业标准** - Claude Code、LangChain等都使用专用工具
2. **职责清晰** - Plan工具有明确的领域逻辑价值
3. **风险更低** - 结构化验证避免常见错误
4. **用户体验** - 自动化处理提升质量
5. **改动成本** - 仅需约30行代码增加持久化

**不推荐方案B的原因**：
- 虽然减少1个工具，但增加了Agent的认知负担
- 失去了专业化工具的价值（验证、统计、格式化）
- 与行业最佳实践不符
- 潜在的格式错误风险

---

## 下一步

等待决策：
- [ ] 选择方案A - 我立即实施plan工具的持久化增强
- [ ] 选择方案B - 我准备system prompt的plan管理指导并移除plan工具
- [ ] 需要更多信息 - 我提供其他角度的分析

