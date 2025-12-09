# MiniMax API配置修复记录

## 问题发现
2025-12-09

### 问题描述
用户发现MiniMax工具无法正常工作，日志显示：
```
2025-12-09 17:21:41 | WARNING  | src.agent.master_agent:_react_loop_with_progress:814
错误信息: 缺少 MINIMAX_API_KEY 环境变量
```

### 根本原因
所有4个MiniMax工具（TTS、Image、Video、Music）直接使用`os.getenv()`读取环境变量，而不是从config对象读取：

```python
# 错误的做法
def __init__(self, config):
    super().__init__(config)
    self.api_key = os.getenv("MINIMAX_API_KEY") or ""  # ❌ 直接读取环境变量
    self.api_url = os.getenv("MINIMAX_TTS_API_URL") or "..."
```

而`src/utils/config.py`中已经有完整的MiniMax配置（line 54-59）：
```python
# MiniMax API - 多模态能力
self.minimax_api_key = os.getenv("MINIMAX_API_KEY", "")
self.minimax_tts_api_url = os.getenv("MINIMAX_TTS_API_URL", "https://api.minimaxi.com/v1/t2a_v2")
self.minimax_image_api_url = os.getenv("MINIMAX_IMAGE_API_URL", "https://api.minimaxi.com/v1/image_generation")
self.minimax_video_api_url = os.getenv("MINIMAX_VIDEO_API_URL", "https://api.minimaxi.com/v1/video_generation")
self.minimax_music_api_url = os.getenv("MINIMAX_MUSIC_API_URL", "https://api.minimaxi.com/v1/music_generation")
```

**问题**：工具绕过了Config类的统一配置管理，导致配置不一致。

---

## 修复方案

### 修复原则
**所有工具必须从config对象读取配置，不能直接访问环境变量**

### 优势
1. ✅ **统一配置管理** - 所有配置都通过Config类管理
2. ✅ **更好的测试性** - 可以mock config对象进行测试
3. ✅ **灵活的配置源** - 将来可以从数据库、配置中心等读取，工具无需修改
4. ✅ **配置验证** - Config类可以在启动时验证必需配置

---

## 修复实施

### 修改的文件（4个）

#### 1. src/tools/atomic/tts_minimax.py

**改动位置**：line 79-84

**修改前**：
```python
def __init__(self, config):
    super().__init__(config)
    self.api_key = os.getenv("MINIMAX_API_KEY") or ""
    self.api_url = os.getenv("MINIMAX_TTS_API_URL") or "https://api.minimaxi.com/v1/t2a_v2"
    self.timeout = getattr(config, "code_executor_timeout", 180)
    self.output_dir = config.output_dir
```

**修改后**：
```python
def __init__(self, config):
    super().__init__(config)
    self.api_key = config.minimax_api_key
    self.api_url = config.minimax_tts_api_url
    self.timeout = getattr(config, "code_executor_timeout", 180)
    self.output_dir = config.output_dir
```

---

#### 2. src/tools/atomic/image_generation_minimax.py

**改动位置**：line 76-80

**修改前**：
```python
def __init__(self, config):
    super().__init__(config)
    self.api_key = os.getenv("MINIMAX_API_KEY") or ""
    self.api_url = os.getenv("MINIMAX_IMAGE_API_URL") or "https://api.minimaxi.com/v1/image_generation"
    self.timeout = getattr(config, "code_executor_timeout", 180)
```

**修改后**：
```python
def __init__(self, config):
    super().__init__(config)
    self.api_key = config.minimax_api_key
    self.api_url = config.minimax_image_api_url
    self.timeout = getattr(config, "code_executor_timeout", 180)
```

---

#### 3. src/tools/atomic/video_generation_minimax.py

**改动位置**：line 67-75

**修改前**：
```python
def __init__(self, config):
    super().__init__(config)
    self.api_key = os.getenv("MINIMAX_API_KEY") or ""
    self.api_url = os.getenv("MINIMAX_VIDEO_API_URL") or "https://api.minimaxi.com/v1/video_generation"
    # 视频生成通常需要更长时间
    self.timeout = int(os.getenv("MINIMAX_VIDEO_TIMEOUT", "300"))
    self.poll_interval = int(os.getenv("MINIMAX_VIDEO_POLL_INTERVAL", "5"))
    self.max_poll_attempts = int(os.getenv("MINIMAX_VIDEO_MAX_POLL_ATTEMPTS", "120"))
    self.output_dir = config.output_dir
```

**修改后**：
```python
def __init__(self, config):
    super().__init__(config)
    self.api_key = config.minimax_api_key
    self.api_url = config.minimax_video_api_url
    # 视频生成通常需要更长时间
    self.timeout = int(os.getenv("MINIMAX_VIDEO_TIMEOUT", "300"))
    self.poll_interval = int(os.getenv("MINIMAX_VIDEO_POLL_INTERVAL", "5"))
    self.max_poll_attempts = int(os.getenv("MINIMAX_VIDEO_MAX_POLL_ATTEMPTS", "120"))
    self.output_dir = config.output_dir
```

**注意**：video工具的`timeout`、`poll_interval`、`max_poll_attempts`仍从环境变量读取，因为这些是运行时参数，不是API凭据。

---

#### 4. src/tools/atomic/music_generation_minimax.py

**改动位置**：line 65-70

**修改前**：
```python
def __init__(self, config):
    super().__init__(config)
    self.api_key = os.getenv("MINIMAX_API_KEY") or ""
    self.api_url = os.getenv("MINIMAX_MUSIC_API_URL") or "https://api.minimaxi.com/v1/music_generation"
    self.timeout = getattr(config, "code_executor_timeout", 180)
    self.output_dir = config.output_dir
```

**修改后**：
```python
def __init__(self, config):
    super().__init__(config)
    self.api_key = config.minimax_api_key
    self.api_url = config.minimax_music_api_url
    self.timeout = getattr(config, "code_executor_timeout", 180)
    self.output_dir = config.output_dir
```

---

## 代码改动统计

| 工具 | 修改文件 | 修改行数 | 改动类型 |
|------|---------|---------|---------|
| TTS | tts_minimax.py | 2行 | API配置读取方式 |
| Image | image_generation_minimax.py | 2行 | API配置读取方式 |
| Video | video_generation_minimax.py | 2行 | API配置读取方式 |
| Music | music_generation_minimax.py | 2行 | API配置读取方式 |
| **总计** | 4个文件 | **8行** | - |

**改动量**：极小，每个工具只修改2行

---

## 配置方式

### 环境变量配置（.env文件）

用户需要在项目根目录的`.env`文件中配置：

```bash
# MiniMax API配置（必需）
MINIMAX_API_KEY=your_minimax_api_key_here

# MiniMax API URLs（可选，有默认值）
MINIMAX_TTS_API_URL=https://api.minimaxi.com/v1/t2a_v2
MINIMAX_IMAGE_API_URL=https://api.minimaxi.com/v1/image_generation
MINIMAX_VIDEO_API_URL=https://api.minimaxi.com/v1/video_generation
MINIMAX_MUSIC_API_URL=https://api.minimaxi.com/v1/music_generation

# Video工具额外配置（可选）
MINIMAX_VIDEO_TIMEOUT=300
MINIMAX_VIDEO_POLL_INTERVAL=5
MINIMAX_VIDEO_MAX_POLL_ATTEMPTS=120
```

### 配置验证

当前Config类**未验证**MiniMax API Key是否存在。如果需要强制验证，可以在`src/utils/config.py`的`_validate()`方法中添加：

```python
def _validate(self):
    """验证必需的配置项是否存在"""
    errors = []

    # 现有验证...

    # 新增：验证MiniMax API Key（可选）
    if not self.minimax_api_key:
        errors.append("必须配置 MINIMAX_API_KEY（用于MiniMax多模态能力）")

    if errors:
        error_msg = "配置验证失败:\n" + "\n".join(f"  - {e}" for e in errors)
        raise ValueError(error_msg)
```

**建议**：暂不强制验证，因为用户可能不使用MiniMax工具。只在工具实际调用时报错即可。

---

## 验证方法

### 1. 启动时验证

确保`.env`文件配置正确：

```bash
# 检查配置是否生效
python -c "from src.utils.config import get_config; c = get_config(); print(f'MiniMax API Key: {c.minimax_api_key[:10]}...' if c.minimax_api_key else 'Not configured')"
```

### 2. 工具调用验证

通过API测试MiniMax工具：

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "生成一张夕阳下的海滩图片",
    "conversation_id": "test_conv_001"
  }'
```

**预期结果**：
- ✅ 工具调用成功，生成图片
- ❌ 如果仍报错"缺少 MINIMAX_API_KEY"，检查`.env`文件路径和格式

### 3. 日志验证

查看日志确认配置读取：

```bash
# 启动应用时应该看到Config初始化成功
INFO: Config loaded successfully
INFO: MiniMax API configured
```

---

## 潜在问题排查

### 问题1：仍然报错"缺少 MINIMAX_API_KEY"

**可能原因**：
- `.env`文件不在项目根目录
- `.env`文件格式错误（如有空格）
- 环境变量名拼写错误

**排查方法**：
```bash
# 1. 检查.env文件位置
ls -la .env

# 2. 检查环境变量是否加载
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print(os.getenv('MINIMAX_API_KEY'))"

# 3. 检查Config类是否读取到
python -c "from src.utils.config import get_config; print(get_config().minimax_api_key)"
```

### 问题2：API调用返回401 Unauthorized

**可能原因**：
- API Key无效或过期
- API Key格式不正确

**排查方法**：
```bash
# 直接测试MiniMax API
curl -X POST https://api.minimaxi.com/v1/image_generation \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "test"}'
```

### 问题3：Config类找不到.env文件

**Config类的.env查找逻辑**（`src/utils/config.py` line 24-30）：
```python
if env_file is None:
    # 自动查找项目根目录的 .env（src/utils/config.py -> repo_root）
    current_dir = Path(__file__).resolve().parent
    repo_root = current_dir.parent.parent.parent
    candidate = repo_root / ".env"
    # 兜底：如果未找到，则尝试当前工作目录
    env_file = candidate if candidate.exists() else Path.cwd() / ".env"
```

**解决方法**：
- 确保`.env`在项目根目录（与`fastapi_app.py`同级）
- 或者在启动时指定：`Config(env_file="/path/to/.env")`

---

## 与其他工具的对比

### 正确的配置读取方式

**✅ 正确示例**（从config读取）：
```python
class WebSearchTool(BaseAtomicTool):
    def __init__(self, config):
        super().__init__(config)
        self.tavily_api_key = config.tavily_api_key  # ✅
        self.serper_api_key = config.serper_api_key  # ✅
```

**❌ 错误示例**（直接读取环境变量）：
```python
class WebSearchTool(BaseAtomicTool):
    def __init__(self, config):
        super().__init__(config)
        self.api_key = os.getenv("TAVILY_API_KEY")  # ❌
```

### 代码审查建议

在添加新工具时，确保：
1. ✅ 所有API凭据从`config`对象读取
2. ✅ 在`src/utils/config.py`中添加对应的配置项
3. ✅ 在`.env.example`中添加配置说明
4. ✅ 更新文档说明配置方法

---

## 总结

### ✅ 修复完成
- 修改4个MiniMax工具，统一从config对象读取API配置
- 代码改动量：8行（每个工具2行）
- 向后兼容：配置方式不变，仍从`.env`读取

### 📊 效果评估
| 指标 | 修复前 | 修复后 | 改进 |
|-----|-------|-------|------|
| 配置一致性 | ❌ 不一致 | ✅ 统一管理 | 100% |
| 代码可维护性 | ❌ 分散配置 | ✅ 集中配置 | ⬆️ |
| 测试便利性 | ❌ 难以mock | ✅ 易于mock | ⬆️ |
| 配置灵活性 | ❌ 仅环境变量 | ✅ 可扩展 | ⬆️ |

### 🎯 关键经验
1. **统一配置管理** - 所有配置应通过Config类集中管理
2. **避免直接访问环境变量** - 工具应从config对象读取，不直接使用`os.getenv()`
3. **代码审查重点** - 新增工具时检查配置读取方式
4. **配置验证** - Config类应在启动时验证必需配置（当前未对MiniMax强制验证）

---

## 相关文件
- 配置类：`src/utils/config.py`
- MiniMax工具：
  - `src/tools/atomic/tts_minimax.py`
  - `src/tools/atomic/image_generation_minimax.py`
  - `src/tools/atomic/video_generation_minimax.py`
  - `src/tools/atomic/music_generation_minimax.py`
- 工具注册：`fastapi_app.py` lines 112-115
