# Wenning 部署清单

## 📦 部署步骤

### 1. 拉取最新代码
```bash
cd /home/work/Wenning/output
git pull origin main
```

### 2. 更新部署脚本
确保 `docs/deploy_improved.sh` 使用环境变量方式启动：
```bash
# 应该包含以下内容：
export WENNING_PORT=8081
nohup .venv/bin/python3 fastapi_app.py > app.log 2>&1 &
```

**新增功能**：脚本现在会自动安装Playwright系统依赖
- ✅ 自动安装Chromium浏览器
- ✅ 尝试安装系统依赖（如libatk-1.0.so.0等）
- ⚠️ 如果没有sudo权限，需要手动执行（见步骤2.1）

#### 2.1 手动安装Playwright系统依赖（如果自动安装失败）
```bash
cd /home/work/Wenning/output
# 方法1：使用playwright命令（推荐）
sudo .venv/bin/playwright install-deps chromium

# 方法2：手动安装具体的库
sudo apt-get update
sudo apt-get install -y libatk1.0-0 libatk-bridge2.0-0 libcups2 \
  libxkbcommon0 libxcomposite1 libxdamage1 libxrandr2 libgbm1 \
  libpango-1.0-0 libcairo2 libasound2
```

### 3. 清理Python缓存（重要！）
```bash
cd /home/work/Wenning/output
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true
```

### 4. 运行部署脚本
```bash
cd /home/work/Wenning/output
bash docs/deploy_improved.sh
```

### 5. 验证服务启动
```bash
# 检查进程
ps -p $(cat app.pid)

# 查看日志
tail -f app.log

# 测试端口
curl http://localhost:8081/
```

## 🧪 功能测试

### 测试1：验证修复的对话可访问
1. 访问 http://10.25.70.163:8081
2. 登录用户"桃子"
3. 查看对话历史中是否有 f82a4c05 对话
4. 尝试切换到该对话，应该正常加载

### 测试2：验证文件锁机制
1. 开始一个新对话
2. 发送消息触发streaming
3. 检查 `data/conversations/{username}/{year-month}/` 下的JSON文件
4. 确认文件格式正确，无损坏

### 测试3：验证多标签页同步
1. 打开两个浏览器标签页，都访问 http://10.25.70.163:8081
2. 登录同一用户
3. 在两个标签页切换到同一个对话
4. 在标签页A发送消息
5. 观察标签页B：
   - ✅ 应该显示警告横幅："⚠️ 其他标签页正在此对话中发送消息，请稍候..."
   - ✅ 输入框应该被禁用
   - ✅ 发送按钮应该被禁用
6. 等标签页A的消息发送完成
7. 观察标签页B：
   - ✅ 警告横幅应该消失
   - ✅ 输入框应该恢复可用
   - ✅ 发送按钮应该恢复可用

### 测试4：验证标签页切换对话
1. 保持两个标签页打开
2. 在标签页A和B切换到不同的对话
3. 在各自的对话中发送消息
4. ✅ 应该都能正常发送，互不影响（因为是不同对话）

## 🐛 排错指南

### 如果服务启动失败
```bash
# 查看完整错误日志
tail -100 app.log

# 检查端口是否被占用
lsof -i :8081

# 检查Python环境
.venv/bin/python3 --version
.venv/bin/pip3 list | grep fastapi
```

### 如果对话仍然报"对话不存在"
```bash
# 检查对话文件是否存在
ls -la data/conversations/{username}/{year-month}/*.json

# 检查索引是否有该对话
grep '{conv_id}' data/index.json

# 验证JSON文件格式
python3 -c "import json; json.load(open('data/conversations/{username}/{year-month}/{timestamp}_{conv_id}.json'))"
```

### 如果多标签页同步不工作
1. 打开浏览器开发者工具（F12）
2. 查看Console标签，搜索"[TabSync]"日志
3. 检查localStorage中是否有"conv_*:sending"键值
4. 确认tab_sync.js已正确加载

## 📝 回滚方案

如果新版本有问题，可以回滚到之前的提交：
```bash
cd /home/work/Wenning/output
git log --oneline -10  # 查看最近10次提交
git checkout {previous_commit_hash}
bash docs/deploy_improved.sh
```

## ✅ 验收标准

所有以下条件满足才算部署成功：
- [ ] 服务正常启动在8081端口
- [ ] 对话 f82a4c05 可以正常访问和加载
- [ ] 新创建的对话文件格式正确，无损坏
- [ ] 多标签页在同一对话上发送消息时，其他标签页会被阻塞
- [ ] 标签页在不同对话上可以并发发送消息
- [ ] 没有出现新的错误日志
