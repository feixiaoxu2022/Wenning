# Wenning 开发备忘

## 远程服务
- **URL**: http://10.25.70.163:8081/
- **测试账号**: claude_test/test123456

## 本地测试
- **URL**: http://localhost:80/
- **测试账号**: test/test (首次使用需注册)

## 测试规范
- **浏览器测试**: 使用Playwright自动化，不要手动操作
- **测试原则**: 创建新对话测试，不要在历史对话上发消息污染数据

## 代码修改SOP
1. 修改代码
2. 更新static/index.html中的版本号（cache busting）
3. git commit & push
4. 远程服务重启（用户操作）
5. Playwright自动化验证

## 远程服务部署
- **部署脚本**: docs/deploy_improved.sh
- **目标目录**: /home/work/Wenning
- **服务端口**: 8081（自动从80修改）
- **日志位置**: app.log, logs/wenning_YYYY-MM-DD.log
- **关键步骤**:
  1. 清理Python缓存（__pycache__/*.pyc）- 避免加载旧代码
  2. 创建/激活虚拟环境 (.venv)
  3. 升级pip并安装依赖 (requirements.txt)
  4. 停止旧服务 (PID from app.pid)
  5. 修改端口配置 (sed -i 's/port=80/port=8081/g')
  6. 启动服务 (nohup python3 fastapi_app.py)
  7. 验证服务状态 (检查进程存活)
- **代理配置**: export https_proxy=http://agent.baidu.com:8891

## 关键技术点
- **SSE流式处理**: onFinal/onDone不能用async/await阻塞，用.then()
- **反馈按钮时机**: 直接DOM查询最后的.result-box，不依赖Promise时序
- **会话ID同步**: 所有赋值点都要同步到window.currentConversationId

## @mention工作区文件功能 (2025-12-29)
### 功能概述
允许用户在输入框中@某个已保存到工作区的文件，类似Cursor的@mention功能

### 技术架构
**后端实现**:
- `src/utils/workspace_store.py`: 保持简单的字符串数组存储
  - 存储格式: `{"username": {"conv_id": ["file1.png", "file2.txt"]}}`
  - conversation_id已作为key，无需在文件条目中重复存储
  - 仅在跨对话查询（list_all_files）时返回带source_conv_id的对象
- `src/utils/mention_handler.py`: @mention解析和文件复制
  - 解析消息中的`@filename`或`@"filename with spaces.txt"`
  - 从源对话目录复制文件到当前对话目录（file_reader工具安全限制）
- `fastapi_app.py`: 集成MentionHandler到chat端点
  - `/workspace/files/autocomplete`: 返回用户所有工作区文件列表（带source_conv_id）

**前端实现**:
- `static/js/mention_autocomplete.js`: 独立autocomplete组件
  - 监听输入框，检测@字符
  - 展示文件列表下拉框，支持键盘导航（↑↓Enter Tab）
  - 高亮匹配项，自动处理文件名中的空格（加引号）
- `static/js/app.js`: 在initAppAfterAuth中初始化
- `static/css/style.css`: 下拉框样式（支持暗色主题）

### 核心设计决策
- **显示方式**: 输入框中显示纯文本`@filename`，不用chips
- **内容处理**: 不自动包含文件内容到消息，让LLM决定是否调用file_reader工具
- **文件复制**: 跨对话@mention时，必须先复制文件到当前对话目录（file_reader安全限制）
- **系统提示**: 复制成功后在用户消息末尾追加`[系统提示：已将以下工作区文件复制到当前对话: xxx]`
- **存储设计**: conversation_id作为key已包含来源信息，无需在每个文件条目中重复存储

## 最近测试结果 (2025-12-29)
### ✅ @mention工作区文件功能
- ✅ 输入@触发文件列表下拉框
- ✅ 键盘导航（↑↓Enter）正确选择文件
- ✅ 跨对话文件访问（自动复制到当前对话目录）
- ✅ LLM成功读取@mentioned文件内容

### ✅ 回车键相关修复
- ✅ @mention下拉框显示时按Enter，只选择文件不发送消息（使用stopImmediatePropagation）
- ✅ 中文输入法按Enter确认选词，不误发送消息（检查e.isComposing）
- ✅ 正常情况下按Enter，正常发送消息

### ✅ 反馈按钮功能
- 3个反馈按钮正确显示（满意/一般/不满意）
- 点击后正常提交，console显示成功，无错误
- 按钮状态正确更新（selected + disabled）

### ✅ 历史会话保存完整性
**测试用例1**: 简单对话（无工具调用）
- 对话ID: ebd64935 ("搜索一下今天的天气")
- 刷新前后: user消息 + assistant回答 + 反馈按钮完整一致

**测试用例2**: 复杂对话（多轮工具调用）
- 对话ID: 90c934a0 ("今天北京天气如何")
- 后端保存: 8条消息（3轮工具调用 + 最终回答）
- 刷新前: user消息 + 3个iter-box（工具执行过程）+ result-box（最终回答）+ 反馈按钮
- 刷新后: **完整恢复**，工具调用过程和最终回答内容一致
- **结论**: 多轮工具调用场景的历史保存完全正常
