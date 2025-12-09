# Agent工具集合设计分析与优化方案

## 核心设计原则（基于Anthropic最佳实践）

### 1. 单一职责原则（Single Responsibility）
- 每个工具应该只做一件事，并把它做好
- 避免"瑞士军刀"式的多功能工具

### 2. 清晰的边界（Clear Boundaries）
- 工具之间职责不应重叠
- 当重叠不可避免时，应明确使用场景的差异

### 3. 合理的粒度（Right Level of Granularity）
- 不要过于原子化（atomic）- 导致需要多次调用才能完成简单任务
- 不要过于复杂（complex）- 导致工具难以理解和使用

### 4. 描述驱动选择（Description-Driven Selection）
- 工具的description应清晰说明：**做什么**、**何时用**、**不做什么**
- 参数schema应该是自解释的

### 5. 错误信息友好（Helpful Error Messages）
- 返回格式规范，错误信息有指导性
- 告诉Agent如何修复问题

---

## 当前工具集合分析

### 现有工具（11个原子工具）

| 工具名 | 职责 | 粒度评价 | 问题 |
|--------|------|----------|------|
| web_search | 网络搜索 | ✅ 适中 | 无 |
| url_fetch | 获取URL内容 | ✅ 适中 | 无 |
| code_executor | 执行Python代码 | ⚠️ 过于通用 | 职责过广，既能做数据分析、又能做图像生成、还能做视频处理 |
| shell_executor | 执行Shell命令 | ✅ 适中 | 无 |
| file_reader | 读取文件 | ✅ 适中 | 无 |
| file_list | 列出文件 | ✅ 适中 | 无 |
| file_editor | 编辑文件 | ✅ 适中 | 无 |
| plan | 创建任务计划 | ✅ 适中 | 无 |
| tts_local | 本地TTS | ✅ 适中 | 与云端TTS有重叠 |
| media_ffmpeg | FFmpeg媒体处理 | ⚠️ 过于通用 | 职责过广，音视频编辑、格式转换等 |
| webpage_preview | 网页预览 | ✅ 适中 | 无 |

### 新增MiniMax工具（4个）

| 工具名 | 职责 | 与现有工具重叠 |
|--------|------|----------------|
| tts_minimax | MiniMax TTS | 与 tts_local 重叠（TTS功能） |
| image_generation_minimax | MiniMax文生图（宽高比） | 与 code_executor + PIL 重叠（图像生成） |
| text_to_image_minimax | MiniMax文生图（精确尺寸） | 与 image_generation_minimax 重叠（文生图）<br>与 code_executor + PIL 重叠（图像生成） |
| video_generation_minimax | MiniMax文生视频 | 与 code_executor + moviepy 重叠（视频生成） |
| music_generation_minimax | MiniMax音乐生成 | 无重叠（独特能力） |

---

## 关键问题识别

### 问题1: code_executor职责过广 ⚠️

**现状**:
- code_executor既能做数据分析、图表绘制
- 也能做图像生成（PIL）
- 还能做视频生成（matplotlib.animation、moviepy）
- 甚至能做音频处理（pydub）

**风险**:
- Agent难以判断何时用专用工具（如MiniMax API），何时用code_executor
- 容易过度依赖code_executor，忽略专用工具
- 代码执行风险更大（安全性考虑）

**Anthropic原则违反**: 违反了"单一职责"和"合理粒度"原则

### 问题2: 两个文生图工具的必要性 🤔

**现状**:
- `image_generation_minimax`: 使用宽高比（16:9、1:1等）+ prompt_optimizer
- `text_to_image_minimax`: 使用精确尺寸（width×height）+ quality参数

**分析**:
- 两者都是调用MiniMax API的文生图服务
- 参数差异：aspect_ratio vs width×height
- 功能高度重叠

**选项A**: 保持两个工具，明确使用场景
**选项B**: 合并为单一工具，支持两种参数模式

### 问题3: TTS工具的多样性管理 ✅

**现状**:
- tts_local: 本地快速TTS
- tts_minimax: 云端中文TTS，支持情感
- tts_google/tts_azure: 云端多语言TTS（已注释，未启用）

**评价**: 这种多样性是**合理的**，因为：
- 每个工具有明确的差异化价值
- tts_local: 快速、无API依赖
- tts_minimax: 中文优化、情感表达
- tts_google/azure: 多语言支持

---

## 优化方案

### 方案A: 保守优化（推荐） ✅

**核心思路**: 通过工具描述优化和system prompt引导，明确使用场景

#### 1. 优化code_executor的描述

**当前描述**:
```python
description = "执行Python代码，可用于数据处理、计算、文件操作等"
```

**优化后**:
```python
description = """执行Python代码进行数据分析和处理。
适用场景：数据统计、科学计算、数据可视化（图表）、技术图形绘制、算法演示。
不适用场景：艺术创作类图像/视频生成（优先使用专用API工具）"""
```

#### 2. 优化MiniMax工具的描述

**image_generation_minimax**:
```python
description = """MiniMax 文生图（艺术创作模式）。
使用宽高比参数（16:9、1:1等），支持AI优化prompt。
适用：社交媒体封面、海报设计、创意插图等艺术创作场景。"""
```

**text_to_image_minimax**:
```python
description = """MiniMax 文生图（精确控制模式）。
使用精确尺寸参数（width×height），支持质量级别控制。
适用：网站banner、产品展示图、打印素材等需要固定尺寸的场景。"""
```

**video_generation_minimax**:
```python
description = """MiniMax 文生视频（AI生成模式）。
生成6秒自然场景短视频，支持720P/1080P。
适用：产品宣传片段、自然风景视频、创意视觉效果等AI生成内容。
不适用：数据动画、算法演示（使用code_executor+matplotlib）、视频编辑（使用code_executor+moviepy）"""
```

**tts_minimax**:
```python
description = """MiniMax 语音合成（中文优化）。
支持多种情感表达（开心、悲伤、愤怒等）。
适用：中文有声内容、需要情感色彩的语音场景。"""
```

**music_generation_minimax**:
```python
description = """MiniMax 音乐生成。
根据prompt生成音乐，支持歌词、风格控制。
适用：背景音乐、歌曲创作、音效制作。"""
```

#### 3. 在system prompt中强化引导

已在`master_agent.py`中实现（参见 docs/system_prompt_optimization.md）

#### 4. 工具注册顺序优化

**原理**: 某些LLM在选择工具时，会受到工具列表顺序的影响

**建议顺序**:
```python
# 1. 核心工具（优先级最高）
tool_registry.register_atomic_tool(WebSearchTool(config))
tool_registry.register_atomic_tool(URLFetchTool(config))
tool_registry.register_atomic_tool(CodeExecutor(config, conv_manager))

# 2. 专用多模态生成工具（优先级高）
tool_registry.register_atomic_tool(ImageGenerationMiniMax(config))
tool_registry.register_atomic_tool(TextToImageMiniMax(config))
tool_registry.register_atomic_tool(VideoGenerationMiniMax(config))
tool_registry.register_atomic_tool(MusicGenerationMiniMax(config))
tool_registry.register_atomic_tool(TTSMiniMax(config))

# 3. 通用辅助工具
tool_registry.register_atomic_tool(TTSLocal(config))
tool_registry.register_atomic_tool(MediaFFmpeg(config))
tool_registry.register_atomic_tool(ShellExecutor(config))
tool_registry.register_atomic_tool(FileReader(config))
tool_registry.register_atomic_tool(FileList(config))
tool_registry.register_atomic_tool(FileEditor(config))
tool_registry.register_atomic_tool(PlanTool(config))
tool_registry.register_atomic_tool(WebPagePreviewTool(config))
```

---

### 方案B: 激进优化（需谨慎）

**核心思路**: 合并重叠工具，减少工具数量

#### 1. 合并两个文生图工具

**合并后的工具**: `image_generation_minimax`

**参数设计**:
```python
{
    "prompt": "图像描述",
    "mode": "aspect_ratio" | "exact_size",  # 模式选择
    "aspect_ratio": "16:9",  # mode=aspect_ratio时使用
    "width": 1920,           # mode=exact_size时使用
    "height": 1080,          # mode=exact_size时使用
    "prompt_optimizer": true,
    "quality": "standard" | "high"
}
```

**风险**:
- 参数复杂度提高，Agent理解成本上升
- 违反"单一职责"原则

**Anthropic建议**: **不推荐** - 增加工具复杂性

#### 2. 拆分code_executor

**拆分为**:
- `code_executor`: 仅用于数据处理和计算
- `chart_generator`: 专门用于图表生成
- `video_animator`: 专门用于数据动画

**风险**:
- 过度原子化，简单任务需要多次调用
- 违反"合理粒度"原则

**Anthropic建议**: **不推荐** - 粒度过细

---

## 最终推荐方案

### ✅ 采用方案A（保守优化）

**理由**:
1. **符合Anthropic原则** - 清晰的边界、合理的粒度
2. **最小化风险** - 不破坏现有功能
3. **渐进式改进** - 先观察效果，再决定是否进一步调整

**具体实施步骤**:
1. ✅ 已完成：优化system prompt（docs/system_prompt_optimization.md）
2. 🔄 进行中：优化各工具的description（本文档）
3. ⏳ 待完成：注册MiniMax工具到fastapi_app.py
4. ⏳ 待完成：调整工具注册顺序
5. ⏳ 待完成：测试Agent的工具选择行为

---

## 测试计划

### 测试用例设计

#### 场景1: 艺术创作类图像
**用户请求**: "生成一张16:9的赛博朋克风格城市夜景"
**期望行为**: 调用 `image_generation_minimax`（而非code_executor）
**验证点**: 检查tool_calls中的工具名称

#### 场景2: 数据图表
**用户请求**: "绘制2023年销售数据的柱状图"
**期望行为**: 调用 `code_executor`（而非image_generation_minimax）
**验证点**: 检查tool_calls中的工具名称

#### 场景3: 精确尺寸图像
**用户请求**: "生成一张1920×1080像素的网站banner"
**期望行为**: 调用 `text_to_image_minimax`（而非image_generation_minimax）
**验证点**: 检查tool_calls中的工具名称和参数

#### 场景4: 自然场景视频
**用户请求**: "生成一段海边日落的6秒短视频"
**期望行为**: 调用 `video_generation_minimax`（而非code_executor）
**验证点**: 检查tool_calls中的工具名称

#### 场景5: 数据动画
**用户请求**: "制作股票价格变化的动画"
**期望行为**: 调用 `code_executor` + matplotlib.animation（而非video_generation_minimax）
**验证点**: 检查tool_calls中的工具名称和代码内容

#### 场景6: 中文情感语音
**用户请求**: "用开心的语气朗读这段文字"
**期望行为**: 调用 `tts_minimax`（而非tts_local）
**验证点**: 检查tool_calls中的工具名称

---

## 监控指标

### 工具使用统计
- 各工具的调用频率
- code_executor的使用场景分布（数据分析 vs 图像生成 vs 视频生成）
- MiniMax工具的实际使用率

### 工具选择准确性
- 在艺术创作场景中，MiniMax API的选择率
- 在数据可视化场景中，code_executor的选择率
- 错误选择的案例分析

### 用户体验指标
- 任务完成成功率
- 需要用户干预的次数（Agent选错工具）
- 平均任务完成时间

---

## 后续迭代方向

根据测试结果和监控数据，可能的优化方向：

1. **如果MiniMax工具使用率过低**
   - 进一步强化system prompt引导
   - 调整工具description
   - 考虑调整code_executor的限制

2. **如果出现频繁的工具选择错误**
   - 分析具体错误模式
   - 优化工具description的差异化表述
   - 考虑在system prompt中增加更多示例

3. **如果两个文生图工具的使用场景模糊**
   - 收集实际使用案例
   - 评估合并工具的可行性
   - 或进一步明确使用场景

---

## 附录：Anthropic工具设计核心原则摘要

### 1. Tool Granularity（工具粒度）
- **Too Fine**: 完成简单任务需要多次调用
- **Just Right**: 单次调用完成有意义的操作
- **Too Coarse**: 工具过于复杂，难以理解

### 2. Tool Boundaries（工具边界）
- 每个工具应有清晰的职责范围
- 避免重叠，或明确重叠的使用场景差异

### 3. Description Quality（描述质量）
- 说明工具做什么（What）
- 说明何时使用（When）
- 说明不做什么（What Not）

### 4. Parameter Design（参数设计）
- 必填参数应该明确且最少
- 可选参数应有合理默认值
- 参数名称应自解释

### 5. Error Handling（错误处理）
- 返回格式规范
- 错误信息有指导性
- 告诉Agent如何修复
