# 待优化清单（CreativeFlow）

说明：本单是“后端幂等与占位、文件可靠落库、音视频预览、历史去重”一轮修复后的收尾与后续优化计划。带 [x] 为已完成，带 [ ] 为待办/建议。

## 一、消息与持久化

- [x] /chat 幂等与占位
  - 入参 `client_msg_id` 幂等落库 user
  - 创建 assistant 占位（`in_progress`），流内 `files_generated` 持续 update，final 时标记 `completed`
- [x] 近邻规范化合并（后端）
  - role+content（换行/空白折叠）相同则合并文件、更新时间
- [ ] 返回 `server_msg_id`（建议）
  - /chat 在创建占位后回传 `server_msg_id`，前端可用来精准定位这条消息做 UI 高亮或锚点跳转
- [ ] 消息更新 API（建议）
  - 暴露 `/conversations/{id}/messages/{msg_id}` PATCH 接口（目前仅内部 `update_message` 可用）
- [ ] 话务维护脚本（已在本次临时执行，建议固化）
  - `scripts/cleanup_retries.py`：按关键字/窗口保留“最后一组且带文件”的 user→assistant 对，删除其余重试对话

## 二、文件生成与可见性

- [x] 覆盖写文件可靠识别
  - 执行器层使用 `st_mtime_ns` 与 `start_ns`（5ms 容忍窗口）并入“执行期间修改”的文件
  - 适配 code_executor / shell_executor
- [x] SSE 推送与白名单扩展
  - 允许 `.mp4/.webm/.mov/.mp3/.wav/.m4a/.aac/.ogg/.flac` 等
- [x] /chat 收尾兜底
  - 目录差集 ∪ 执行期间修改 ∪ 流内 files_generated → 合并更新占位
- [x] 目录列表端点（避开路由冲突）
  - `GET /outputs/list/{conversation_id}`（前端兜底扫描使用）
- [ ] 统一“列表端点”命名（可选）
  - 保留 `/outputs/list/{id}`，移除容易被 `{filename}` 路由抢占的 `/outputs/{id}/list`

## 三、前端预览与去重

- [x] 图片缩放异常修复
  - 统一 `width:100% + object-fit:contain`，并附 `?t=timestamp` 强制刷新
- [x] 文件标签去重加固
  - 批次内 Set 去重 + 全局 fileKeys，规范化 key（解码+trim）
- [x] 音/视频内联播放
  - 新增 `audio`/`video` 类型，走 `/stream`，支持 Range 快进
- [x] History 只覆盖左侧栏，点击后自动收起
- [x] 计划（Plan）视图增强（进度条、折叠/展开、状态徽记）
- [ ] Workspace 前端持久化交互增强（可选）
  - 删除、重命名、打开定位到预览标签、按类型筛选

## 四、后端接口与能力

- [x] `/stream/{conv}/{file}`、`/stream/{file}` 支持 Range（206）
- [x] 非 ASCII HTML 文件名内联修复（中文名不再设置 filename 避免 latin-1 编码异常）
- [x] Auth：登录/注册/登出 + 模态 UI；前端禁用发送直至登录
- [ ] `/chat` POST 化（可选）
  - 统一放 body，避免超长 query 与编码差异

## 五、模型与工具编排

- [x] 文档化 Gemini 3 Pro（Preview）工具消息限制与二段式 `generateContent` 用法
- [ ] 模型级工具开关（建议）
  - `MODELS_DISABLE_FC=gemini-3-pro-preview` → 该模型仅走纯聊天，避免 400
- [ ] System Prompt SOP（建议）
  - 明确音视频导出优先路径：PIL 生成帧图/WAV → shell_executor + ffmpeg → mp4/mp3

## 六、依赖与环境

- [x] requirements 补充 `matplotlib`（避免 `ModuleNotFoundError`）
- [ ] 可选：加入 `moviepy` / `imageio-ffmpeg` / `pydub`（如偏好纯 Python 流程）
- [ ] 启动自检（建议）
  - 检查 ffmpeg 与关键包是否可用，失败时在首页给出红点提示

## 七、日志与可观测性

- [x] /chat 关键日志：占位创建、files_generated、占位更新完成（含 files）
- [ ] 开关化的 DEBUG：`AGENT_ENABLE_REQUEST_LOGGING=true` 时打印 LLM 请求关键信息（已部分具备）
- [ ] 404/500 附带 request id 显示到前端 toast（可选）

## 八、数据清理（本轮已手动执行）

- [x] f484d3b2：清除重复“我还是需要mp4”成组消息，仅保留带文件的那组
- [ ] 提供通用清理脚本（见“一、消息与持久化”）

---

## 即刻建议（2 步）

1) 前后端已改动部署后，建议执行：
   - `pip install -r requirements.txt`
   - 重启后端 `uvicorn fastapi_app:app --host 0.0.0.0 --port 8000`
   - 前端强制刷新（或无痕）

2) 回归用例（最小闭环）：
   - 生成 5 张 png → ffmpeg 合成为 mp4（或工具直接生成）
   - 观察服务日志“三处信号”应全部命中：
     - 执行器：新增/修改文件列表（含 mp4）
     - SSE：files_generated 推送（含 mp4）
     - /chat：占位更新完成（files 含 mp4）

## 版本足迹（本轮已完成）

- 幂等 / 占位更新 / 覆盖写识别 / Range / 预览兜底 / UI 去重 已上线
- 文档：API测试报告.md 补充 Gemini 原生二段式示例与注意事项

---

如需我把“通用清理脚本 + server_msg_id 回传 + /chat POST 化”一次性补齐，请告诉我优先级，我就继续推进。

