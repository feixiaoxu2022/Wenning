# MiniMax工具超时配置优化

## 配置时间
2025-12-09

## 用户需求
将MiniMax生成工具的等待时间延长：
- **TTS/Image/Music**: 5分钟（300秒）
- **Video**: 10分钟（600秒）

并确保周边系统能够配合这个等待时间。

---

## 完整配置清单

### 1. 工具层超时配置

#### TTS/Image/Music工具
**配置位置**：`.env` line 21-22
```bash
CODE_EXECUTOR_TIMEOUT=300  # 5分钟
```

**影响工具**：
- `tts_minimax.py` - 语音合成
- `image_generation_minimax.py` - 图像生成
- `music_generation_minimax.py` - 音乐生成
- `code_executor.py` - 代码执行沙箱

**生效方式**：
```python
# src/tools/atomic/tts_minimax.py line 83
self.timeout = getattr(config, "code_executor_timeout", 180)  # 现在是300秒
```

#### Video工具（独立配置）
**配置位置**：`.env` line 31-34
```bash
MINIMAX_VIDEO_TIMEOUT=600           # API提交超时: 10分钟
MINIMAX_VIDEO_POLL_INTERVAL=10      # 轮询间隔: 10秒（降低API调用频率）
MINIMAX_VIDEO_MAX_POLL_ATTEMPTS=60  # 最大轮询次数: 60次
```

**总等待时间**：10秒 × 60次 = 600秒（10分钟）

**改动说明**：
- 提交超时：300秒 → 600秒（+100%）
- 轮询间隔：5秒 → 10秒（+100%，降低API压力）
- 轮询次数：120次 → 60次（-50%，因为间隔加倍）

---

### 2. FastAPI层超时配置

**配置位置**：`fastapi_app.py` line 1040-1048

**改动前**：
```python
uvicorn.run(app, host="0.0.0.0", port=80)
```

**改动后**：
```python
uvicorn.run(
    app,
    host="0.0.0.0",
    port=80,
    timeout_keep_alive=650,  # keepalive超时: 10分50秒
    timeout_notify=650,       # worker通知超时: 10分50秒
    limit_concurrency=100     # 并发限制
)
```

**参数说明**：
- `timeout_keep_alive`: HTTP keepalive连接超时，设为650秒（略大于最长任务600秒）
- `timeout_notify`: Worker进程通知超时，设为650秒
- `limit_concurrency`: 限制并发连接数为100

**为什么是650秒**：
- Video最长任务600秒 + 50秒缓冲 = 650秒
- 确保连接不会在任务完成前断开

---

### 3. Agent层配置（无需修改）

**配置位置**：`src/agent/master_agent.py` line 53

```python
self.max_iterations = 30  # 最大ReAct迭代次数
```

**说明**：
- Agent使用**迭代次数**控制，不使用时间超时
- 单个工具调用可以运行很长时间（由工具自己的timeout控制）
- ✅ **不需要修改**，Agent不会中断长时间运行的工具

---

## 配置对比表

| 组件 | 配置项 | 旧值 | 新值 | 增幅 |
|-----|-------|-----|------|------|
| **TTS工具** | timeout | 180秒 | **300秒** | +66% |
| **Image工具** | timeout | 180秒 | **300秒** | +66% |
| **Music工具** | timeout | 180秒 | **300秒** | +66% |
| **Video工具** | timeout | 300秒 | **600秒** | +100% |
| | poll_interval | 5秒 | **10秒** | +100% |
| | max_poll_attempts | 120次 | **60次** | -50% |
| | 总等待时间 | 600秒 | **600秒** | 不变 |
| **FastAPI** | timeout_keep_alive | 5秒(默认) | **650秒** | +12900% |
| | timeout_notify | 30秒(默认) | **650秒** | +2067% |
| **Agent** | max_iterations | 30次 | **30次** | 不变 |

---

## 时间链路验证

### 完整请求链路

```
用户请求 → FastAPI(650秒) → Agent(无时间限制) → 工具(300/600秒) → MiniMax API
```

### 各层超时关系

```
FastAPI超时(650秒)
  ↓
  > Agent超时(无限制)
      ↓
      > Video工具超时(600秒)
          ↓
          > MiniMax Video API
      ↓
      > TTS/Image/Music工具超时(300秒)
          ↓
          > MiniMax TTS/Image/Music API
```

**验证结论**：✅ 所有层级超时配置一致，最长任务（Video 600秒）< FastAPI超时（650秒）

---

## 修改的文件清单

| 文件 | 修改内容 | 行数 |
|-----|---------|------|
| `.env` | 增加CODE_EXECUTOR_TIMEOUT=300 | +2行 |
| `.env` | 调整Video配置（timeout/interval/attempts） | 修改4行 |
| `fastapi_app.py` | uvicorn超时参数配置 | +7行 |

**总改动**：3个文件，约13行

---

## 客户端配置建议

### HTTP客户端超时

如果使用curl或其他HTTP客户端测试，需要设置相应的超时：

```bash
# curl示例（设置700秒超时）
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  --max-time 700 \
  -d '{
    "message": "生成一个6秒的视频",
    "conversation_id": "test_video_001"
  }'
```

### Python requests示例

```python
import requests

response = requests.post(
    "http://localhost:8000/api/chat",
    json={
        "message": "生成一首音乐",
        "conversation_id": "test_music_001"
    },
    timeout=700  # 客户端超时设为700秒
)
```

### 前端JavaScript示例

```javascript
// Fetch API
fetch('/api/chat', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    message: '生成视频',
    conversation_id: 'test_001'
  }),
  signal: AbortSignal.timeout(700000)  // 700秒超时
})

// Axios
axios.post('/api/chat', {
  message: '生成音乐',
  conversation_id: 'test_001'
}, {
  timeout: 700000  // 700秒超时
})
```

---

## 潜在风险和注意事项

### 1. 服务器资源占用 ⚠️

**风险**：长时间运行的请求会占用服务器资源

**影响**：
- 每个Video生成请求占用1个worker进程10分钟
- 每个Music生成请求占用1个worker进程5分钟
- 并发限制设为100，理论上最多100个长任务同时运行

**建议**：
- 监控服务器CPU/内存使用情况
- 考虑使用异步任务队列（Celery/RQ）处理长任务
- 增加worker进程数量（如果资源允许）

### 2. 用户体验 ⚠️

**风险**：用户等待时间过长

**建议**：
- 前端显示进度条或Loading动画
- 提供任务状态查询接口
- 考虑使用WebSocket推送进度更新
- 提供任务取消功能

### 3. API限流 ⚠️

**风险**：MiniMax API可能有调用频率限制

**Video工具优化**：
- 轮询间隔从5秒增加到10秒
- 降低API调用频率（从120次降到60次）

**建议**：
- 监控API调用次数和限流情况
- 根据实际情况调整轮询间隔

### 4. 超时错误处理

**当前行为**：
- 工具超时 → 抛出timeout异常 → Agent捕获 → 返回错误

**建议增强**：
- 超时前30秒发送警告
- 提供重试机制
- 记录超时任务便于分析

---

## 测试验证计划

### 1. 基本功能测试

```bash
# 测试TTS（5分钟内应完成）
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "生成一段语音", "conversation_id": "test_tts_001"}'

# 测试Image（5分钟内应完成）
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "生成一张图片", "conversation_id": "test_image_001"}'

# 测试Music（5分钟内应完成）
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "生成一首音乐", "conversation_id": "test_music_001"}'

# 测试Video（10分钟内应完成）
curl -X POST http://localhost:8000/api/chat \
  --max-time 700 \
  -H "Content-Type: application/json" \
  -d '{"message": "生成一个6秒的视频", "conversation_id": "test_video_001"}'
```

### 2. 压力测试

**测试场景**：
1. 单个长任务（Video 10分钟）
2. 多个短任务并发（5个TTS同时）
3. 混合任务（2个Video + 5个Music）

**监控指标**：
- 响应时间
- 成功率
- 资源使用率（CPU/内存）
- 超时错误数量

### 3. 边界测试

**测试目标**：
- 接近超时但成功（295秒完成）
- 刚好超时（305秒）
- 远超超时（400秒）

**预期行为**：
- 300秒内完成 → 成功返回
- 300秒未完成 → timeout异常 → 错误返回

---

## 监控和日志

### 关键日志点

1. **工具开始调用**
   ```
   INFO | 调用 MiniMax Music Generation API: model=music-2.0
   ```

2. **超时警告**（工具内未实现，建议添加）
   ```
   WARNING | 任务接近超时（已运行270秒/300秒）
   ```

3. **超时错误**
   ```
   ERROR | music_generation_minimax 执行失败: Timeout
   ```

4. **成功完成**
   ```
   INFO | base64解码成功，音频数据大小: 925678 字节
   INFO | 音乐文件保存成功: generated_music.mp3
   ```

### 监控指标建议

| 指标 | 说明 | 告警阈值 |
|-----|------|---------|
| 平均响应时间 | 工具平均执行时间 | >200秒 |
| 超时率 | 超时任务占比 | >10% |
| 并发任务数 | 同时运行的任务 | >80 |
| 资源使用率 | CPU/内存占用 | >80% |

---

## 回滚计划

如果新配置导致问题，可以快速回滚：

### 1. 恢复原配置

```bash
# .env文件
CODE_EXECUTOR_TIMEOUT=180           # 改回3分钟
MINIMAX_VIDEO_TIMEOUT=300           # 改回5分钟
MINIMAX_VIDEO_POLL_INTERVAL=5       # 改回5秒
MINIMAX_VIDEO_MAX_POLL_ATTEMPTS=120 # 改回120次
```

### 2. 恢复FastAPI配置

```python
# fastapi_app.py
uvicorn.run(app, host="0.0.0.0", port=80)  # 使用默认配置
```

### 3. 重启应用

```bash
# 停止应用 (Ctrl+C)
# 重新启动
python fastapi_app.py
```

---

## 总结

### ✅ 已完成
- 调整4个MiniMax工具超时配置
- 配置FastAPI服务器支持长任务
- 验证Agent层无需修改
- 创建完整配置文档

### 📊 配置总览

| 工具 | 超时时间 | 配置位置 | 备注 |
|-----|---------|---------|------|
| TTS | 300秒 | .env:CODE_EXECUTOR_TIMEOUT | +66% |
| Image | 300秒 | .env:CODE_EXECUTOR_TIMEOUT | +66% |
| Music | 300秒 | .env:CODE_EXECUTOR_TIMEOUT | +66% |
| Video | 600秒 | .env:MINIMAX_VIDEO_TIMEOUT | +100% |
| FastAPI | 650秒 | fastapi_app.py:timeout_keep_alive | +12900% |
| Agent | 无限制 | - | 使用迭代次数 |

### 🎯 关键要点
1. **分层配置**：工具→FastAPI→Agent，每层都配置了合理的超时
2. **缓冲时间**：FastAPI超时（650秒）略大于最长任务（600秒）
3. **客户端配置**：建议设置700秒超时（留有余量）
4. **监控告警**：建议添加超时前警告和资源监控

### ⚠️ 注意事项
- 重启应用后新配置才生效
- 客户端也需要设置相应超时
- 建议添加进度展示提升用户体验
- 监控服务器资源使用情况

---

## 相关文件
- 环境配置：`.env`
- FastAPI应用：`fastapi_app.py`
- Agent核心：`src/agent/master_agent.py`
- MiniMax工具：
  - `src/tools/atomic/tts_minimax.py`
  - `src/tools/atomic/image_generation_minimax.py`
  - `src/tools/atomic/video_generation_minimax.py`
  - `src/tools/atomic/music_generation_minimax.py`
