# P1工具描述优化实施记录

## 优化时间
2025-12-09

## 优化的工具（7个）

### 1. ✅ plan (create_plan)

**优化前**:
```python
description = "创建或更新任务计划。用于需要多个步骤的复杂任务,帮助跟踪进度。参数: task_description(任务描述), steps(步骤列表)"
```

**优化后**:
```python
description = (
    "任务规划工具: 为复杂多步骤任务创建执行计划和进度跟踪。"
    "适用场景：任务包含3个以上步骤、需要分阶段执行、需要向用户展示进度。"
    "典型场景：数据分析项目（获取→清洗→分析→可视化）、内容创作流程（调研→撰写→配图→校对）。"
    "不适用：简单的单步或两步任务。"
    "参数: task_description(任务总体描述), steps(步骤列表,每步包含step/action/status/result)"
)
```

**改进点**:
- ✅ 明确使用时机："3个以上步骤"
- ✅ 提供具体场景示例
- ✅ 说明"不适用"场景

---

### 2. ✅ file_reader

**优化前**:
```python
description = "读取会话目录中的文件（只读，返回结构化预览）"
```

**优化后**:
```python
description = (
    "文件读取工具: 读取会话目录中的文件并返回结构化预览（只读，安全限长）。"
    "适用场景：快速查看文件内容、预览CSV/Excel表格（自动识别格式）、读取JSON/文本配置。"
    "优势：自动格式识别、返回结构化预览、限长保护（避免大文件阻塞）、支持多种编码。"
    "不适用：需要完整读取大文件、需要复杂文本处理（使用code_executor）。"
    "参数: filename(文件名), conversation_id(必需), mode(可选:text/json/csv/excel), max_bytes/max_lines"
)
```

**改进点**:
- ✅ 强化与code_executor的区别："快速结构化预览 vs 完整读取+复杂处理"
- ✅ 说明独特优势："自动格式识别、限长保护"
- ✅ 明确"不适用"场景

---

### 3. ✅ file_list

**优化前**:
```python
description = "列出会话目录中的文件（支持过滤/排序/限制）"
```

**优化后**:
```python
description = (
    "文件列表工具: 列出会话目录中的文件，支持过滤、排序和限制。"
    "适用场景：查找生成的文件、检查文件是否存在、按类型/时间筛选文件、统计文件数量。"
    "优势：支持扩展名过滤(.png/.xlsx)、glob模式匹配(*.png)、多种排序方式(name/mtime/size)。"
    "不适用：递归查找子目录、复杂文件操作（使用shell_executor的find命令或code_executor）。"
    "参数: conversation_id(必需), ext(扩展名过滤), pattern(glob模式), limit(条数限制), sort(排序方式)"
)
```

**改进点**:
- ✅ 强化与shell_executor的区别："简单列表筛选 vs 复杂find查找"
- ✅ 说明独特优势："多种过滤和排序功能"
- ✅ 明确"不适用"场景

---

### 4. ✅ file_editor

**优化前**:
```python
description = """编辑会话目录中的文件。支持两种模式：

【模式1：精确字符串替换】适合单次修改
- 参数：old_string（必需）, new_string（必需）, replace_all（可选）
...
"""
```

**优化后**:
```python
description = (
    "文件编辑工具: 编辑会话目录中的文件。支持两种模式：精确字符串替换、行范围编辑。"
    "适用场景：修改配置文件、更新代码片段、替换文本内容、修正错误内容。"
    "优势：安全的编辑操作、支持上下文验证、返回diff预览、两种灵活模式。"
    "不适用：批量编辑多个文件、复杂文本处理（使用code_executor或shell_executor）。"
    "\n模式1-精确替换: old_string(原文), new_string(新文), replace_all(是否全部替换)"
    "\n模式2-行范围: start_line(起始行), end_line(结束行), line_content(新内容), verify_context(上下文验证)"
    "\n参数: filename(必需), conversation_id(必需), 根据模式选择对应参数"
)
```

**改进点**:
- ✅ 简化描述（去除详细示例，保留核心信息）
- ✅ 强化与code_executor的区别："单文件编辑 vs 批量处理"
- ✅ 说明独特优势："安全、上下文验证、diff预览"

---

### 5. ✅ media_ffmpeg

**优化前**:
```python
description = (
    "FFmpeg媒体处理：\n"
    "- mux: 将音频合入视频(out.mp4)\n"
    "- transcode: 视频转码为yuv420p+faststart(out.mp4)\n"
    "- mix: 旁白+背景音乐混音(out.wav/.m4a，或携带video同时输出out.mp4)\n"
    "示例: {'mode':'mix','vocal':'narration.wav','bgm':'bgm.mp3','out':'mix.m4a','ducking':true,'bgm_gain_db':-14}"
)
```

**优化后**:
```python
description = (
    "FFmpeg专业媒体处理: 底层音视频操作，支持转码、格式优化、专业混音。"
    "适用场景：音频混音（旁白+BGM+ducking效果）、视频转码（yuv420p+faststart优化兼容性）、音视频流合成（mux）。"
    "优势：专业级音频处理（sidechaincompress压缩、淡入淡出）、格式兼容性优化、底层FFmpeg精细控制。"
    "不适用：视频内容编辑（剪辑、添加字幕、特效）→ 使用code_executor+moviepy。"
    "\n支持模式："
    "\n- mux: 音视频合成(video+audio→out.mp4)"
    "\n- transcode: 视频转码优化(video→yuv420p+faststart)"
    "\n- mix: 专业混音(vocal+bgm→out, 支持ducking/淡入淡出/循环)"
    "\n参数: mode(必需), conversation_id(必需), out(输出文件), 根据模式选择video/audio/vocal/bgm等"
)
```

**改进点**:
- ✅ **明确与moviepy的分工**："底层处理 vs 内容编辑"
- ✅ 强调专业能力："sidechaincompress、ducking"
- ✅ 清晰的模式说明

---

### 6. ✅ code_executor

**优化前**:
```python
description = (
    "Python代码执行沙箱: 在安全环境中执行Python代码进行数据处理、科学计算和可视化。"
    "适用场景：数据统计分析、科学计算、数据可视化（图表生成）、技术图形绘制、算法演示、数据动画（matplotlib.animation）、视频编辑（moviepy）。"
    "不适用场景：艺术创作类的图像/视频生成（优先使用专用的MiniMax API工具获得更好的艺术效果）。"
)
```

**优化后**:
```python
description = (
    "Python代码执行沙箱: 在安全环境中执行Python代码进行数据处理、科学计算和可视化。"
    "适用场景：数据统计分析、科学计算、数据可视化（图表生成）、技术图形绘制、算法演示、数据动画（matplotlib.animation）、视频编辑（moviepy）、复杂文件处理。"
    "优势：完整的Python生态（pandas/numpy/matplotlib/PIL/moviepy）、适合复杂编程逻辑、可以使用各种Python库。"
    "不适用场景：艺术创作类的图像/视频生成（优先使用MiniMax API）、简单的批量文件操作和命令（优先使用shell_executor更简洁）。"
    "参数: code(Python代码,必需), conversation_id(会自动注入), language(默认python), timeout(超时秒数)"
)
```

**改进点**:
- ✅ **强化与shell_executor的区别**："复杂逻辑 vs 简单批量命令"
- ✅ 明确优势："完整Python生态、复杂编程"
- ✅ 补充"不适用"场景（简单批量操作）

---

### 7. ✅ shell_executor

**优化前**:
```python
description = "在会话目录中执行受限shell命令（安全受限，不允许破坏性操作）"
```

**优化后**:
```python
description = (
    "Shell命令执行: 在会话目录中执行bash命令（安全受限）。"
    "适用场景：批量文件操作（重命名、移动、复制）、快速查找（find/grep）、管道处理（cat|sort|uniq）、系统工具调用（wc/awk/sed）。"
    "优势：Shell语法简洁（一行完成批量操作）、支持管道和重定向、适合快速命令。"
    "不适用：复杂编程逻辑、需要Python库的数据处理（使用code_executor）。"
    "安全限制：禁止rm、sudo、pip install、ssh等危险命令。"
    "参数: cmd(bash命令,必需), conversation_id(必需), timeout(超时秒数)"
)
```

**改进点**:
- ✅ **强化与code_executor的区别**："简洁快速命令 vs 复杂编程"
- ✅ 明确优势："一行完成批量操作、管道"
- ✅ 说明安全限制

---

## 优化效果对比

| 工具 | 优化前描述长度 | 优化后描述长度 | 清晰度提升 |
|------|--------------|--------------|-----------|
| plan | 1行简单 | 5行详细 | ⭐⭐⭐⭐⭐ |
| file_reader | 1行简单 | 5行详细 | ⭐⭐⭐⭐⭐ |
| file_list | 1行简单 | 5行详细 | ⭐⭐⭐⭐⭐ |
| file_editor | 多行但冗长 | 精简但完整 | ⭐⭐⭐⭐ |
| media_ffmpeg | 简单列举 | 详细分工 | ⭐⭐⭐⭐⭐ |
| code_executor | 较详细 | 更详细+区分 | ⭐⭐⭐⭐ |
| shell_executor | 1行简单 | 5行详细 | ⭐⭐⭐⭐⭐ |

---

## 优化的核心原则

### 1. 四段式结构
每个工具描述都包含：
- **功能定位**：这个工具是做什么的
- **适用场景**：什么时候用（具体例子）
- **独特优势**：为什么用这个而不是其他
- **不适用场景**：什么时候不用（引导用其他工具）

### 2. 清晰的边界
- 明确与相似工具的**区别**和**分工**
- file_reader vs code_executor：快速预览 vs 完整处理
- media_ffmpeg vs code_executor+moviepy：底层处理 vs 内容编辑
- code_executor vs shell_executor：复杂逻辑 vs 简单命令

### 3. 具体的示例
- plan：给出具体的多步骤场景（数据分析项目）
- file_reader：说明支持的格式（CSV/Excel/JSON）
- media_ffmpeg：列出三种模式和各自用途

### 4. 引导性语言
- "优先使用XX" - 引导Agent选择更合适的工具
- "不适用：XX（使用YY）" - 明确告诉Agent用什么替代

---

## 预期效果

### 对Agent的影响
✅ **选择准确性提升** - 描述更详细，场景更明确
✅ **理解速度提升** - 四段式结构，快速定位适用场景
✅ **混淆度降低** - 明确了工具间的边界和区别

### 对用户的影响
✅ **任务完成质量提升** - Agent选对工具，结果更准确
✅ **响应速度可能提升** - Agent不需要多次尝试找对工具
✅ **用户体验提升** - 更少的错误和重试

---

## 实施文件清单

### 修改的文件（7个）
1. `src/tools/atomic/plan.py` - line 22
2. `src/tools/atomic/file_reader.py` - line 28
3. `src/tools/atomic/file_list.py` - line 14
4. `src/tools/atomic/file_editor.py` - line 24
5. `src/tools/atomic/media_ffmpeg.py` - line 26
6. `src/tools/atomic/code_executor.py` - line 28
7. `src/tools/atomic/shell_executor.py` - line 29

---

## 下一步

### ✅ 已完成
- System Prompt优化（430行 → 150行）
- 工具集精简（16个 → 13个）
- 核心工具描述优化（MiniMax系列）
- P1工具描述优化（7个工具）

### ⏳ 待进行
- 添加工具使用统计（P2）
- 测试Agent工具选择准确性
- 根据实际数据评估shell_executor保留必要性

---

## 总结

通过P1优化，我们完成了7个工具的描述升级，重点解决了：
1. ✅ plan工具的使用时机不清晰问题
2. ✅ 文件操作工具与code_executor的边界模糊问题
3. ✅ media_ffmpeg与moviepy的分工不明确问题
4. ✅ code_executor和shell_executor的选择困惑问题

所有工具描述现在都遵循统一的四段式结构，提供了清晰的使用指导。
