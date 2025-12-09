# 工具移除实施总结

## 执行时间
2025-12-09

## 移除的工具

### 1. webpage_preview ✅
**移除理由**:
- 功能过于简单，仅返回URL给前端iframe
- 使用场景极少，Agent很少需要"预览"网页
- CORS限制导致很多网站无法预览
- 可以用url_fetch（获取内容）或code_executor+playwright（截图）替代

### 2. tts_local ✅
**移除理由**:
- 已有TTSMiniMax提供高质量中文TTS服务
- 本地TTS质量较差，情感表达能力弱
- 在有网络的情况下，云端TTS是更好的选择
- 简化工具集，减少Agent选择负担

## 修改的文件

### fastapi_app.py
**修改内容**:
1. 移除导入语句:
   - `from src.tools.atomic.webpage_preview import WebPagePreviewTool`
   - `from src.tools.atomic.tts_local import TTSLocal`

2. 移除工具注册:
   - `tool_registry.register_atomic_tool(WebPagePreviewTool(config))`
   - `tool_registry.register_atomic_tool(TTSLocal(config))`

## 工具集变化

### 移除前（16个工具）
1. web_search
2. url_fetch
3. code_executor
4. shell_executor
5. plan
6. file_reader
7. file_list
8. file_editor
9. **tts_local** ❌
10. media_ffmpeg
11. **webpage_preview** ❌
12. image_generation_minimax
13. text_to_image_minimax
14. video_generation_minimax
15. music_generation_minimax
16. tts_minimax

### 移除后（14个工具）

#### 核心工具（3个）
1. web_search
2. url_fetch
3. code_executor

#### 专用多模态生成工具（5个）
4. image_generation_minimax
5. text_to_image_minimax
6. video_generation_minimax
7. music_generation_minimax
8. tts_minimax

#### 通用辅助工具（6个）
9. plan
10. media_ffmpeg
11. shell_executor
12. file_reader
13. file_list
14. file_editor

## 预期效果

✅ **工具数量精简**: 16个 → 14个（减少12.5%）
✅ **降低选择复杂度**: 移除了功能简单或被覆盖的工具
✅ **提升工具质量**: 保留的都是有明确独特价值的工具
✅ **减少功能重叠**: TTS只保留高质量的TTSMiniMax

## 后续观察

建议在未来1-2周内观察：
1. Agent的工具选择准确性是否提升
2. 是否有用户抱怨找不到某个功能
3. shell_executor的使用频率（如果很低，考虑进一步移除）

## 回滚方案

如果需要恢复被移除的工具，只需：
1. 恢复fastapi_app.py中的导入和注册语句
2. 工具实现文件仍保留在src/tools/atomic/目录中
