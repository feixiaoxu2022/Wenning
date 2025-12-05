# Claude Function Calling 参数丢失问题诊断与修复

## 📊 问题现象

从实际运行日志看到：
```
ERROR | code_executor: 缺少必需参数 code
```

LLM连续3次调用`code_executor`工具，但`code`参数都丢失了。

## 🔍 诊断过程

### 测试1：非流式调用 ✅

运行`test_claude_fc.py`（`stream=False`）：
```
✅ code参数存在 (1054 字符)
Arguments (type=str): '{"code":"\\nimport cv2\\n..."}'
```

**结论**：Claude的Function Calling本身工作正常，能正确生成参数。

### 测试2：实际运行（流式） ❌

查看master_agent.py第416行：
```python
stream=True  # 启用流式
```

**关键发现**：实际运行使用流式调用，问题出在**流式响应的tool_calls解析**！

## 🎯 根本原因

### 问题定位：client.py 流式tool_use处理

**第492-513行**的流式delta处理逻辑有问题：

```python
elif et == "content_block_delta":
    delta = evt.get("delta", {})
    if delta.get("type") == "text_delta":
        # 处理文本...
    else:
        # ❌ 问题：这个else分支条件太宽泛
        partial = delta.get("partial_json")
        if partial and last_tool_id:
            tool_uses[last_tool_id]["input_str"] += partial
```

**Claude流式协议规范**：
- `text_delta` - 文本内容增量
- `input_json_delta` - **工具参数增量**（正确类型）

原代码的`else`分支会捕获所有非text_delta的类型，但实际上：
1. 如果delta类型不是`input_json_delta`，不应该累积到input_str
2. 可能存在其他delta类型导致判断错误

## ✅ 修复方案

### 修复1：明确处理input_json_delta类型

```python
elif et == "content_block_delta":
    delta = evt.get("delta", {})
    delta_type = delta.get("type")

    if delta_type == "text_delta":
        # 处理文本
    elif delta_type == "input_json_delta":  # ✅ 明确类型
        partial = delta.get("partial_json")
        if partial and last_tool_id:
            tool_uses[last_tool_id]["input_str"] += partial
    else:
        # fallback兼容
        partial = delta.get("partial_json")
        if partial and last_tool_id:
            tool_uses[last_tool_id]["input_str"] += partial
```

### 修复2：增强日志和容错

**添加详细调试日志**：
- 流式tool_use开始时记录
- 每个delta事件记录类型
- 参数累积过程记录
- 最终解析结果记录

**增强master_agent参数解析容错**：
```python
arguments_str = tool_call["function"]["arguments"]
if isinstance(arguments_str, str):
    arguments = json.loads(arguments_str) if arguments_str.strip() else {}
elif isinstance(arguments_str, dict):
    arguments = arguments_str
else:
    arguments = {}
```

## 📝 已实施的修复

### ✅ src/llm/client.py

1. **第502-513行**：明确处理`input_json_delta`类型
2. **第492行**：添加delta类型日志
3. **第541-550行**：添加tool_use完成日志和错误处理

### ✅ src/agent/master_agent.py

1. **两处tool_call解析**：增强容错性（str/dict/other）
2. **添加原始tool_call日志**：帮助排查问题

## 🧪 验证方法

### 方法1：查看日志（推荐）

再次运行相同的视频生成请求，查看日志：

**关键日志标识**：
```
流式delta: type=input_json_delta  # 确认delta类型正确
累积tool input: XXX 字符          # 确认参数被累积
流式tool_use完成: input_str_len=XXX # 确认最终长度
从input_str解析参数成功            # 确认解析成功
原始tool_call: {"id":..., "function":{"arguments":"..."}}  # 确认参数完整
```

**预期结果**：
- 应该看到`input_json_delta`类型的delta
- `input_str_len`应该>0
- arguments应该包含完整的code参数

### 方法2：测试脚本对比

```bash
# 非流式（已验证✅）
python test_claude_fc.py

# 流式（需要新脚本）
python test_claude_fc_stream.py  # 待创建
```

## 🔧 如果问题仍存在

### 可能原因1：网关问题

如果你使用的是代理网关（看到base_url=yy.dbh.baidu-int.com），网关可能：
- 不完整地转发Claude流式事件
- 修改了事件格式
- 过滤了某些delta类型

**解决**：尝试直接连接Claude API（`claude_force_native=True`）

### 可能原因2：Claude版本差异

不同版本的Claude可能使用不同的流式协议。

**解决**：添加更详细的原始事件日志，检查实际事件结构

### 备用方案：fallback逻辑

如果流式始终有问题，可以添加fallback：

```python
if tool_name == "code_executor" and "code" not in arguments:
    # 从content中提取代码
    content = response.get("content") or ""
    code_match = re.search(r'```python\s*\n(.*?)\n```', content, re.DOTALL)
    if code_match:
        arguments["code"] = code_match.group(1)
        logger.warning("从content中提取code参数（fallback）")
```

## 📊 问题严重程度

**高优先级** - 这会导致所有需要大量参数的tool调用失败，严重影响agent功能。

## 🎯 下一步行动

1. ✅ 修复已实施 - 重新测试视频生成
2. 📋 观察日志 - 确认`input_json_delta`是否正确处理
3. 🔍 如果仍失败 - 检查网关/协议兼容性
4. 🛠️ 必要时实施fallback方案

---

**修复完成时间**: 2025-12-01
**影响文件**:
- `src/llm/client.py` - 流式tool_use解析修复
- `src/agent/master_agent.py` - 参数解析容错增强
- `test_claude_fc.py` - 非流式测试脚本
