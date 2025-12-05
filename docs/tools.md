  🔧Atomic Tools（原子工具）- 10个

1. 文件操作类（3个）

- file_list - 列出会话目录中的文件（支持过滤/排序/限制）
- file_reader - 读取会话目录中的文件（只读，返回结构化预览）
  - 支持text/json/csv/excel/binary等多种格式
  - 安全隔离：仅在会话目录内读取，防止路径穿越
- file_editor - 编辑会话目录中的文件

2. 代码执行类（2个）

- code_executor - 在安全沙箱中执行Python代码
- shell_executor - 在会话目录中执行受限shell命令（安全受限）

3. 网络获取类（2个）

- web_search - 搜索互联网获取实时信息和最新内容
- url_fetch - 抓取URL内容并转换为Markdown格式

4. 媒体处理类（2个）

- media_ffmpeg - 音视频处理（基于FFmpeg）
- tts_local - 本地文字转语音

5. 任务规划类（1个）

- create_plan - 创建或更新任务计划
  - 用于需要多个步骤的复杂任务，帮助跟踪进度
