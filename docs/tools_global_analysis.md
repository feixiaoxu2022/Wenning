# 工具集全局能力分析

## 当前工具清单（14个）

### 核心工具（3个）
1. **web_search** - 网络搜索
2. **url_fetch** - URL内容抓取
3. **code_executor** - Python代码执行

### 专用多模态生成工具（5个）
4. **image_generation_minimax** - 图像生成（宽高比模式）
5. **text_to_image_minimax** - 图像生成（精确尺寸模式）
6. **video_generation_minimax** - 视频生成
7. **music_generation_minimax** - 音乐生成
8. **tts_minimax** - 语音合成

### 通用辅助工具（6个）
9. **plan** (create_plan) - 任务规划
10. **media_ffmpeg** - FFmpeg媒体处理
11. **shell_executor** - Shell命令执行
12. **file_reader** - 文件读取
13. **file_list** - 文件列表
14. **file_editor** - 文件编辑

---

## 能力矩阵分析

### 1. 信息获取能力

| 工具 | 功能 | 输入 | 输出 | 重叠度 |
|------|------|------|------|--------|
| **web_search** | 搜索互联网 | 搜索关键词 | 搜索结果列表（标题、摘要、URL） | - |
| **url_fetch** | 抓取URL内容 | URL地址 | Markdown格式的网页内容 | - |

**分析**:
- ✅ **职责清晰**：web_search用于"发现内容"，url_fetch用于"获取内容"
- ✅ **无重叠**：典型工作流是先search找URL，再fetch获取详细内容
- ✅ **描述清晰度**：良好

**改进建议**: 无

---

### 2. 代码/命令执行能力

| 工具 | 功能 | 执行内容 | 适用场景 | 重叠度 |
|------|------|----------|----------|--------|
| **code_executor** | Python代码执行 | Python脚本 | 数据处理、图表生成、复杂逻辑 | ⚠️ 低度重叠 |
| **shell_executor** | Bash命令执行 | Shell命令 | 批量文件操作、快速查找、系统工具 | ⚠️ 低度重叠 |

**分析**:
- ⚠️ **有轻微重叠**：Python的subprocess可以执行shell命令
- ✅ **但各有优势**：
  - shell_executor：批量操作更简洁（`for f in *.txt; do...`）
  - code_executor：复杂逻辑更强大（pandas/matplotlib）
- ⚠️ **描述清晰度**：已优化，但仍需强化差异

**改进建议**:
```python
# code_executor
description = (
    "Python代码执行沙箱: 在安全环境中执行Python代码进行数据处理、科学计算和可视化。"
    "适用场景：数据统计分析、科学计算、数据可视化（图表生成）、技术图形绘制、算法演示、数据动画（matplotlib.animation）、视频编辑（moviepy）。"
    "不适用场景：简单的文件操作和批量命令（优先使用shell_executor更简洁）、艺术创作类的图像/视频生成（优先使用专用的MiniMax API工具）。"
)

# shell_executor
description = (
    "Shell命令执行: 在会话目录中执行bash命令（安全受限）。"
    "适用场景：批量文件操作（重命名、移动）、快速查找（find/grep）、管道处理（cat/sort/uniq）、系统工具调用（ffmpeg/imagemagick）。"
    "不适用场景：复杂编程逻辑、需要Python库的数据处理（使用code_executor）。"
    "安全限制：禁止rm、sudo、pip install等危险命令。"
)
```

---

### 3. 图像生成能力 ⚠️ **关键重叠点**

| 工具 | 功能 | 尺寸控制方式 | 特殊能力 | 适用场景 | 重叠度 |
|------|------|--------------|----------|----------|--------|
| **image_generation_minimax** | MiniMax文生图 | 宽高比（16:9、1:1等） | prompt_optimizer | 艺术创作、社交媒体 | 🔴 高度重叠 |
| **text_to_image_minimax** | MiniMax文生图 | 精确尺寸（1920×1080） | quality控制 | 固定规格、打印素材 | 🔴 高度重叠 |
| **code_executor** | PIL/matplotlib绘图 | 完全可控（像素级） | 数据驱动、技术图形 | 数据可视化、技术图 | 🟡 中度重叠 |

**分析**:
- 🔴 **严重问题**：image_generation_minimax 和 text_to_image_minimax 功能**高度重叠**
  - 两者都是MiniMax API
  - 都是文生图
  - 主要差异仅在于参数形式（aspect_ratio vs width×height）
  - Agent很可能混淆使用场景

- 🟡 **中度重叠**：两个MiniMax工具 vs code_executor
  - MiniMax：AI生成艺术风格图像
  - code_executor：代码生成技术图形
  - 已有描述引导，但可能仍有混淆

**问题根源**:
- MiniMax实际上提供了**两个不同的API端点**：
  1. `/v1/image_generation` - 使用aspect_ratio
  2. `/v1/text_to_image` - 使用width×height
- 我们将两个API封装成了两个工具，导致Agent需要选择

**改进方案**:

#### 方案A: 合并两个MiniMax图像工具（推荐）⭐

```python
class ImageGenerationMiniMax(BaseAtomicTool):
    name = "image_generation_minimax"
    description = (
        "MiniMax 文生图: 根据文本描述生成艺术风格图像，支持两种尺寸控制方式。"
        "适用场景：社交媒体封面、海报设计、创意插图、网站banner、产品展示图等需要AI生成图像的场景。"
        "不适用：数据图表、技术图形（使用code_executor）。"
        "参数: prompt(必填), aspect_ratio(宽高比如16:9) 或 width/height(精确像素), prompt_optimizer, quality"
    )

    parameters_schema = {
        "properties": {
            "prompt": {"type": "string", "description": "图像描述"},
            "conversation_id": {"type": "string"},
            # 支持两种尺寸控制方式（二选一）
            "aspect_ratio": {"type": "string", "enum": ["1:1", "16:9", "9:16", "4:3", "3:4"]},
            "width": {"type": "integer"},
            "height": {"type": "integer"},
            "prompt_optimizer": {"type": "boolean", "default": True},
            "quality": {"type": "string", "enum": ["standard", "high"], "default": "standard"},
            "n": {"type": "integer", "default": 1}
        }
    }

    def run(self, **kwargs):
        # 自动判断使用哪个API端点
        if kwargs.get("aspect_ratio"):
            # 使用 /v1/image_generation
            return self._generate_by_aspect_ratio(**kwargs)
        elif kwargs.get("width") and kwargs.get("height"):
            # 使用 /v1/text_to_image
            return self._generate_by_exact_size(**kwargs)
        else:
            # 默认使用 aspect_ratio=16:9
            kwargs["aspect_ratio"] = "16:9"
            return self._generate_by_aspect_ratio(**kwargs)
```

**优点**:
- ✅ 减少工具数量（14个 → 13个）
- ✅ 降低Agent选择负担（不需要区分两种尺寸控制方式）
- ✅ 统一的图像生成入口
- ✅ 内部逻辑自动选择合适的API

**缺点**:
- ⚠️ 参数schema稍微复杂（aspect_ratio和width/height二选一）
- ⚠️ 需要重构代码

#### 方案B: 保持分离，但强化描述差异（保守）

```python
# image_generation_minimax
description = (
    "MiniMax 文生图（宽高比模式）🎨: 使用宽高比参数生成艺术图像。"
    "适用场景：不确定具体像素尺寸，只知道需要横屏(16:9)、竖屏(9:16)或方图(1:1)时使用。"
    "典型场景：社交媒体封面（横屏16:9）、手机壁纸（竖屏9:16）、头像（方图1:1）。"
    "参数: prompt, aspect_ratio(16:9/9:16/1:1/4:3/3:4), prompt_optimizer"
)

# text_to_image_minimax
description = (
    "MiniMax 文生图（精确尺寸模式）📐: 使用精确像素尺寸生成图像。"
    "适用场景：明确需要特定像素尺寸（如1920×1080、800×600）时使用。"
    "典型场景：网站banner（固定1920×600）、打印海报（A4尺寸）、产品规格图（统一规格）。"
    "参数: prompt, width(像素), height(像素), quality(standard/high)"
)
```

**优点**:
- ✅ 无需重构代码
- ✅ 保持两个API端点的独立性

**缺点**:
- ❌ 仍然有两个工具，Agent需要选择
- ❌ 使用场景区分可能仍不够清晰

---

### 4. 视频生成能力

| 工具 | 功能 | 适用场景 | 重叠度 |
|------|------|----------|--------|
| **video_generation_minimax** | AI生成6秒短视频 | 自然场景、人物动作、创意效果 | - |
| **code_executor** + matplotlib | 数据动画 | 数据变化、算法演示 | 🟡 轻微重叠 |
| **code_executor** + moviepy | 视频编辑 | 剪辑、字幕、特效 | 🟡 轻微重叠 |

**分析**:
- ✅ **职责清晰**：AI生成 vs 程序化创建 vs 编辑处理
- ✅ **描述已明确区分**："不适用：数据动画、算法演示（使用code_executor+matplotlib）"
- ✅ **无改进需要**

---

### 5. 音频生成能力

| 工具 | 功能 | 适用场景 | 重叠度 |
|------|------|----------|--------|
| **tts_minimax** | 文本转语音 | 有声内容、旁白、语音合成 | - |
| **music_generation_minimax** | 音乐生成 | 背景音乐、歌曲创作 | - |
| **media_ffmpeg** | 音频处理 | 混音、转码、效果处理 | - |

**分析**:
- ✅ **职责清晰**：TTS vs 音乐 vs 后期处理
- ✅ **无重叠**：各有独特价值
- ✅ **描述清晰**

---

### 6. 文件操作能力

| 工具 | 功能 | 权限 | 操作类型 | 重叠度 |
|------|------|------|----------|--------|
| **file_reader** | 读取文件 | 只读 | 返回文件内容预览 | - |
| **file_list** | 列出文件 | 只读 | 返回文件名列表 | - |
| **file_editor** | 编辑文件 | 读写 | 修改文件内容 | - |
| **code_executor** | 可以读写文件 | 读写 | 通过Python代码操作 | 🟡 中度重叠 |
| **shell_executor** | 可以操作文件 | 受限读写 | 通过shell命令操作 | 🟡 中度重叠 |

**分析**:
- 🟡 **有重叠但合理**：
  - 专用文件工具：简单、安全、结构化输出
  - code/shell executor：强大、灵活、但需要Agent自己写代码

- ⚠️ **潜在混淆点**：Agent什么时候用file_reader vs code_executor读文件？

**改进建议**:
```python
# file_reader
description = (
    "读取会话目录中的文件（只读，返回结构化预览）。"
    "适用场景：快速读取文件内容、预览CSV/Excel表格、读取JSON配置。"
    "优势：自动识别文件类型、返回格式化预览、限长保护（避免大文件）。"
    "不适用：需要完整读取大文件或进行复杂处理（使用code_executor）。"
)

# file_list
description = (
    "列出会话目录中的文件（支持过滤/排序/限制）。"
    "适用场景：查找生成的文件、检查文件是否存在、按类型/时间筛选文件。"
    "优势：支持扩展名过滤、glob模式、排序功能。"
    "不适用：需要递归查找或复杂文件操作（使用shell_executor的find命令）。"
)

# file_editor
description = (
    "编辑会话目录中的文件。支持两种模式：精确字符串替换、行范围编辑。"
    "适用场景：修改配置文件、更新代码片段、替换文本内容。"
    "优势：安全的编辑操作、支持上下文验证、返回diff预览。"
    "不适用：批量编辑多个文件、复杂文本处理（使用code_executor或shell_executor）。"
)
```

---

### 7. 任务规划能力

| 工具 | 功能 | 适用场景 | 重叠度 |
|------|------|----------|--------|
| **plan** (create_plan) | 创建和跟踪任务步骤 | 复杂多步骤任务 | - |

**分析**:
- ✅ **独特功能**：无其他工具提供此能力
- ⚠️ **描述可能不够清晰**：什么时候Agent应该使用plan工具？

**改进建议**:
```python
description = (
    "任务规划工具: 为复杂多步骤任务创建执行计划和进度跟踪。"
    "适用场景：任务包含3个以上步骤、需要分阶段执行、需要向用户展示进度。"
    "典型场景：数据分析项目（获取数据→清洗→分析→可视化）、内容创作流程（调研→撰写→配图→校对）。"
    "不适用：简单的单步任务、不需要进度跟踪的场景。"
    "参数: task_description(总体描述), steps(步骤列表，每步包含action和status)"
)
```

---

### 8. 媒体处理能力

| 工具 | 功能 | 适用场景 | 重叠度 |
|------|------|----------|--------|
| **media_ffmpeg** | FFmpeg音视频处理 | 转码、混音、合成 | 🟡 轻微重叠 |
| **code_executor** + moviepy | 视频编辑 | 剪辑、特效、字幕 | 🟡 轻微重叠 |

**分析**:
- 🟡 **有重叠但定位不同**：
  - media_ffmpeg：底层FFmpeg封装，专业音频处理
  - code_executor+moviepy：高层Python库，视频内容编辑

- ⚠️ **描述需要强化差异**

**改进建议**:
```python
# media_ffmpeg
description = (
    "FFmpeg专业媒体处理: 底层音视频操作，支持转码、格式优化、专业混音。"
    "适用场景：音频混音（旁白+BGM+ducking效果）、视频转码（yuv420p+faststart优化）、音视频流合成（mux）。"
    "优势：专业级音频处理（sidechaincompress、淡入淡出）、格式兼容性优化、底层FFmpeg控制。"
    "不适用：视频内容编辑（剪辑、添加字幕、特效）→ 使用code_executor+moviepy。"
    "支持模式: mux(合成), transcode(转码), mix(混音)"
)
```

---

## 全局问题总结

### 🔴 严重问题（需立即解决）

#### 1. 两个图像生成工具高度重叠 ⚠️⚠️⚠️

**问题**: image_generation_minimax 和 text_to_image_minimax 功能几乎完全重叠

**影响**:
- Agent需要在两个工具间选择，增加认知负担
- 很可能选错或混用
- 工具数量冗余

**解决方案**: **强烈建议合并为单一工具**（方案A）

### 🟡 中度问题（建议优化）

#### 2. code_executor 和 shell_executor 的使用场景可能混淆

**问题**: Agent可能不清楚何时用Python、何时用Bash

**解决方案**: 强化description中的场景差异（已提供改进建议）

#### 3. 文件操作工具与code/shell executor的边界不够清晰

**问题**: file_reader/file_list/file_editor 与 code_executor 都能操作文件

**解决方案**: 明确专用工具的优势（简单、安全、结构化），引导优先使用

### 🟢 轻微问题（可选优化）

#### 4. plan工具的使用时机不够明确

**问题**: Agent可能不知道什么时候应该创建plan

**解决方案**: 在description中明确"3个以上步骤时使用"

---

## 描述清晰度评分

| 工具 | 当前描述清晰度 | 建议改进 |
|------|---------------|---------|
| web_search | ⭐⭐⭐⭐⭐ 优秀 | 无需改进 |
| url_fetch | ⭐⭐⭐⭐ 良好 | 可补充"与web_search配合使用" |
| code_executor | ⭐⭐⭐⭐ 良好 | 已优化，可再强化"不适用简单命令" |
| shell_executor | ⭐⭐⭐⭐ 良好 | 已有建议改进 |
| plan | ⭐⭐⭐ 一般 | **需要改进**（何时使用） |
| file_reader | ⭐⭐⭐ 一般 | **需要改进**（与code_executor区别） |
| file_list | ⭐⭐⭐ 一般 | **需要改进**（优势说明） |
| file_editor | ⭐⭐⭐⭐ 良好 | 描述较完整，可保持 |
| media_ffmpeg | ⭐⭐⭐ 一般 | **需要改进**（与moviepy区别） |
| image_generation_minimax | ⭐⭐⭐ 一般 | **需要合并或强化差异** |
| text_to_image_minimax | ⭐⭐⭐ 一般 | **需要合并或强化差异** |
| video_generation_minimax | ⭐⭐⭐⭐ 良好 | 已明确"不适用"场景 |
| music_generation_minimax | ⭐⭐⭐⭐ 良好 | 独特功能，无混淆 |
| tts_minimax | ⭐⭐⭐⭐ 良好 | 已优化，清晰 |

---

## 优先级行动清单

### P0 - 立即处理

1. **合并image_generation_minimax和text_to_image_minimax** 🔴
   - 减少工具冗余
   - 降低Agent选择负担
   - 统一图像生成入口

### P1 - 重要优化

2. **优化plan工具描述** - 明确使用时机（3+步骤）
3. **优化file_reader/file_list描述** - 强化与code_executor的区别
4. **优化media_ffmpeg描述** - 明确与moviepy的分工

### P2 - 可选优化

5. **观察code_executor和shell_executor的使用数据** - 1-2周后决定是否需要进一步调整
6. **添加工具使用统计** - 为未来优化提供数据支持

---

## 最终工具集规划（优化后）

### 建议最终保留13个工具（合并图像生成工具后）

#### 核心工具（3个）
1. web_search
2. url_fetch
3. code_executor

#### 专用多模态生成（4个）
4. **image_generation_minimax** ⭐ （合并后）
5. video_generation_minimax
6. music_generation_minimax
7. tts_minimax

#### 通用辅助工具（6个）
8. plan
9. media_ffmpeg
10. shell_executor
11. file_reader
12. file_list
13. file_editor

**预期效果**:
- 工具数量：14个 → 13个
- 降低Agent选择复杂度（不需要区分两种图像生成方式）
- 统一的文生图入口
- 保持所有独特功能

---

## 总结

### 核心发现
1. **最严重问题**：两个图像生成工具高度重叠，强烈建议合并
2. **次要问题**：部分工具描述不够清晰，需要强化使用场景说明
3. **整体结构**：工具集职责基本清晰，大部分工具有独特价值

### 推荐的下一步行动
1. ✅ **合并图像生成工具**（P0）
2. ✅ **批量优化工具描述**（P1）
3. ⏳ **添加使用统计**（P2）
4. ⏳ **1-2周后根据数据评估shell_executor**（P2）
