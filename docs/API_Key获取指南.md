# CreativeFlow API Key 获取指南

## 文档目的

提供所有第三方服务的API Key获取步骤,帮助开发者快速完成环境配置。

---

## 1. Web Search 服务

### 1.1 Tavily API (主力搜索)

**官网**: https://tavily.com

**注册流程**:

1. **访问官网并注册**
   ```
   https://app.tavily.com/sign-up
   ```
   - 使用邮箱注册或GitHub OAuth登录
   - 无需信用卡即可开始使用

2. **获取API Key**
   - 登录后进入Dashboard
   - 在左侧菜单找到 "API Keys"
   - 点击 "Create API Key"
   - 复制生成的key(格式: `tvly-xxxxxxxxxxxxx`)

3. **免费额度**
   - ✅ 1,000 API credits/月
   - ✅ Basic Search: 1 credit/次
   - ✅ Advanced Search: 2 credits/次
   - 无需信用卡,永久有效

4. **配置环境变量**
   ```bash
   export TAVILY_API_KEY="tvly-xxxxxxxxxxxxx"
   ```

**测试API**:
```bash
curl -X POST https://api.tavily.com/search \
  -H "Authorization: Bearer tvly-xxxxxxxxxxxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "latest AI trends 2025",
    "search_depth": "basic",
    "max_results": 3
  }'
```

**升级付费**(可选):
- 进入Billing页面
- 选择Project Plan ($30/月, 4,000 credits)
- 或购买Add-on ($100一次性, 8,000 credits永久)

---

### 1.2 Serper API (备用搜索)

**官网**: https://serper.dev

**注册流程**:

1. **访问官网并注册**
   ```
   https://serper.dev/signup
   ```
   - 使用Google账号登录(推荐)
   - 或邮箱注册

2. **获取API Key**
   - 注册后自动跳转到Dashboard
   - API Key显示在页面顶部
   - 格式: 一串随机字符(如 `a1b2c3d4e5f6...`)
   - 点击复制按钮

3. **免费额度**
   - ✅ 前2,500次查询免费
   - 用完后自动按$0.30/1000次计费
   - 需要添加信用卡(但有免费额度)

4. **配置环境变量**
   ```bash
   export SERPER_API_KEY="a1b2c3d4e5f6..."
   ```

**测试API**:
```bash
curl -X POST https://google.serper.dev/search \
  -H 'X-API-KEY: a1b2c3d4e5f6...' \
  -H 'Content-Type: application/json' \
  -d '{
    "q": "OpenAI GPT-5"
  }'
```

**付费说明**:
- 自动按使用量计费
- $0.30/1,000次查询
- 可在Dashboard查看用量

---

## 2. URL Fetch 服务

### 2.1 Jina Reader API (主力URL提取)

**官网**: https://jina.ai/reader

**完全免费模式** (无需API Key):

1. **直接使用**
   - 无需注册!
   - 在任何URL前加上 `https://r.jina.ai/`
   - 示例: `https://r.jina.ai/https://github.com`

2. **免费限制**
   - 20次/分钟(无API Key)
   - 完全够用,无需注册

**获取API Key** (提升限额,可选):

1. **注册Jina AI账号**
   ```
   https://jina.ai/
   ```
   - 点击右上角 "Sign Up"
   - 使用邮箱或GitHub登录

2. **获取API Key**
   - 登录后进入 https://jina.ai/reader/
   - 点击 "Get API Key"
   - 或在Dashboard → API Keys → Create New Key
   - 格式: `jina_xxxxxxxxxxxxx`

3. **使用API Key**
   ```bash
   # 方式1: Header
   curl https://r.jina.ai/https://example.com \
     -H "Authorization: Bearer jina_xxxxxxxxxxxxx"

   # 方式2: URL参数
   curl "https://r.jina.ai/https://example.com?api_key=jina_xxxxxxxxxxxxx"
   ```

4. **提升后的限额**
   - 200次/分钟(免费API Key)
   - 可购买更高配额

5. **配置环境变量**
   ```bash
   export JINA_API_KEY="jina_xxxxxxxxxxxxx"  # 可选
   ```

**ReaderLM-v2** (高级功能):
- 需要付费API Key
- 消耗3x tokens
- 用于复杂网站的高质量转换

---

### 2.2 Firecrawl API (高级爬取)

**官网**: https://firecrawl.dev

**注册流程**:

1. **访问官网并注册**
   ```
   https://www.firecrawl.dev/
   ```
   - 点击 "Get Started" 或 "Sign Up"
   - 使用邮箱或GitHub登录

2. **获取API Key**
   - 登录后进入Dashboard
   - 左侧菜单 "API Keys"
   - 点击 "Create API Key"
   - 格式: `fc-xxxxxxxxxxxxx`
   - 复制并保存

3. **免费额度**
   - ✅ 500 pages免费
   - 无需信用卡
   - 1 page = 1 credit(标准页面)

4. **配置环境变量**
   ```bash
   export FIRECRAWL_API_KEY="fc-xxxxxxxxxxxxx"
   ```

**测试API**:

```bash
# 单页抓取
curl -X POST https://api.firecrawl.dev/v0/scrape \
  -H 'Authorization: Bearer fc-xxxxxxxxxxxxx' \
  -H 'Content-Type: application/json' \
  -d '{
    "url": "https://example.com"
  }'
```

**Python SDK**:
```bash
pip install firecrawl-py

# 使用
from firecrawl import FirecrawlApp
app = FirecrawlApp(api_key="fc-xxxxxxxxxxxxx")
result = app.scrape_url("https://example.com")
```

**升级付费**(可选):
- Hobby: $16/月, 3,000 credits
- Standard: $83/月, 100,000 credits
- 在Billing页面选择套餐

**AI Extract功能** (独立订阅):
- 需要单独购买Extract套餐
- Starter: $89/月, 18M tokens/年
- 用于结构化数据提取

---

## 3. LLM 服务

### 3.1 OpenAI API (GPT-4o/GPT-4o-mini)

**官网**: https://platform.openai.com

**注册流程**:

1. **创建账号**
   ```
   https://platform.openai.com/signup
   ```
   - 使用邮箱注册
   - 验证手机号(国内手机可用)

2. **获取API Key**
   - 登录后访问: https://platform.openai.com/api-keys
   - 点击 "Create new secret key"
   - 命名后点击 "Create"
   - **立即复制key**(只显示一次!)
   - 格式: `sk-xxxxxxxxxxxxx`

3. **充值**
   - ⚠️ OpenAI现在需要先充值才能使用
   - 访问 https://platform.openai.com/account/billing
   - 最低充值$5(建议$10-20)
   - 支持信用卡

4. **配置环境变量**
   ```bash
   export OPENAI_API_KEY="sk-xxxxxxxxxxxxx"
   ```

**测试API**:
```bash
curl https://api.openai.com/v1/chat/completions \
  -H "Authorization: Bearer sk-xxxxxxxxxxxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o-mini",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

**定价** (2025):
- GPT-4o-mini: $0.15/1M input tokens, $0.60/1M output
- GPT-4o: $2.50/1M input, $10/1M output

---

### 3.2 Anthropic API (Claude 3.5 Sonnet)

**官网**: https://console.anthropic.com

**注册流程**:

1. **创建账号**
   ```
   https://console.anthropic.com/
   ```
   - 使用邮箱注册
   - 验证邮箱

2. **获取API Key**
   - 登录Console
   - 左侧菜单 "API Keys"
   - 点击 "Create Key"
   - 命名后生成
   - 格式: `sk-ant-xxxxxxxxxxxxx`
   - **立即复制**(只显示一次)

3. **充值**
   - 访问 Billing页面
   - 最低充值$5
   - 支持信用卡

4. **配置环境变量**
   ```bash
   export ANTHROPIC_API_KEY="sk-ant-xxxxxxxxxxxxx"
   ```

**测试API**:
```bash
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: sk-ant-xxxxxxxxxxxxx" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d '{
    "model": "claude-3-5-sonnet-20241022",
    "max_tokens": 1024,
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

**定价** (2025):
- Claude 3.5 Sonnet: $3/1M input, $15/1M output
- Claude 3 Haiku: $0.25/1M input, $1.25/1M output

---

### 3.3 文心一言 API (可选,中文场景)

**官网**: https://cloud.baidu.com/product/wenxinworkshop

**注册流程**:

1. **注册百度智能云**
   ```
   https://login.bce.baidu.com/
   ```
   - 使用手机号注册
   - 完成实名认证(必需)

2. **开通文心一言服务**
   - 进入 "千帆大模型平台"
   - 选择 "文心一言"
   - 点击 "立即使用"

3. **创建应用获取API Key**
   - 进入 "应用列表"
   - 点击 "创建应用"
   - 填写应用名称
   - 获取:
     - API Key: `xxxxxx`
     - Secret Key: `xxxxxx`

4. **配置环境变量**
   ```bash
   export QIANFAN_AK="your-api-key"
   export QIANFAN_SK="your-secret-key"
   ```

**免费额度**:
- 新用户赠送一定tokens
- 具体额度查看官网最新政策

**定价**:
- 文心4.0: ¥0.008/1k tokens(约$0.0011)
- 比OpenAI便宜很多

---

## 4. 环境变量配置文件

### 4.1 创建 `.env` 文件

```bash
# 在项目根目录创建
touch .env

# 添加到.gitignore(重要!)
echo ".env" >> .gitignore
```

### 4.2 完整的 `.env` 模板

```bash
# ============================================
# Web Search APIs
# ============================================

# Tavily (主力搜索)
TAVILY_API_KEY=tvly-xxxxxxxxxxxxx

# Serper (备用搜索)
SERPER_API_KEY=xxxxxxxxxxxxx

# ============================================
# URL Fetch APIs
# ============================================

# Jina Reader (可选,提升限额)
JINA_API_KEY=jina_xxxxxxxxxxxxx

# Firecrawl (整站爬取)
FIRECRAWL_API_KEY=fc-xxxxxxxxxxxxx

# ============================================
# LLM APIs
# ============================================

# OpenAI
OPENAI_API_KEY=sk-xxxxxxxxxxxxx

# Anthropic
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxx

# 文心一言(可选)
QIANFAN_AK=your-api-key
QIANFAN_SK=your-secret-key

# ============================================
# 其他配置
# ============================================

# 数据库
DATABASE_URL=postgresql://user:pass@localhost:5432/creativeflow

# Redis
REDIS_URL=redis://localhost:6379

# MinIO
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
```

### 4.3 Python中加载环境变量

```python
# config.py
import os
from dotenv import load_dotenv

# 加载.env文件
load_dotenv()

class Config:
    # Web Search
    TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
    SERPER_API_KEY = os.getenv("SERPER_API_KEY")

    # URL Fetch
    JINA_API_KEY = os.getenv("JINA_API_KEY")
    FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")

    # LLM
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

    # 验证必需的key
    @classmethod
    def validate(cls):
        required = [
            "TAVILY_API_KEY",
            "OPENAI_API_KEY"
        ]
        missing = [k for k in required if not getattr(cls, k)]
        if missing:
            raise ValueError(f"缺少必需的API Key: {missing}")

# 使用
from config import Config
Config.validate()
```

---

## 5. 快速开始检查清单

### MVP阶段(必需):

- [ ] ✅ **Tavily API Key** - 免费注册,1000次/月
- [ ] ✅ **OpenAI API Key** - 充值$10即可
- [ ] ✅ **Jina Reader** - 无需注册,直接用

**总成本**: $10(OpenAI充值)

---

### V1.5阶段(推荐):

- [ ] ✅ **Tavily API Key** - 升级Project Plan $30/月
- [ ] ✅ **Firecrawl API Key** - 注册免费500页,按需付费
- [ ] ✅ **Anthropic API Key** - 充值$10用于高质量分析
- [ ] ✅ **Serper API Key** - 注册免费2500次

**总成本**: $30(Tavily) + $20(LLM充值) = $50首月

---

### 可选(高级功能):

- [ ] **Exa API** - 语义搜索,$50/月
- [ ] **文心一言** - 中文场景,成本低
- [ ] **Jina API Key** - 提升到200次/分钟

---

## 6. 常见问题

### Q1: 哪些服务可以完全免费使用?

**A**:
- ✅ **Jina Reader** - 完全免费,无需注册
- ✅ **Tavily** - 1000次/月免费额度
- ✅ **Serper** - 前2500次免费

MVP阶段只需OpenAI充值,其他都免费!

---

### Q2: API Key泄露了怎么办?

**A**: 立即采取以下措施:
1. 登录对应平台Dashboard
2. 找到API Keys管理页面
3. **Revoke/Delete**泄露的key
4. 创建新的key
5. 检查Usage页面,看是否有异常调用
6. 如有异常,联系客服申诉

**预防措施**:
- ❌ 永远不要把`.env`文件提交到Git
- ✅ 添加`.env`到`.gitignore`
- ✅ 使用环境变量而非硬编码
- ✅ 定期rotate key(每3-6个月)

---

### Q3: 如何控制API成本?

**A**:
1. **设置用量限制**
   - OpenAI: 在Billing页面设置"Usage Limits"
   - Anthropic: 设置"Spending Limits"

2. **监控用量**
   - 每周检查Usage Dashboard
   - 设置告警(超过80%发邮件)

3. **优化调用**
   - 使用Tavily而非OpenAI做搜索(更便宜)
   - 缓存常见查询结果
   - 用GPT-4o-mini替代GPT-4o(便宜10倍)

4. **分阶段投入**
   - MVP: $10-20/月
   - V1.5: $50-100/月
   - V2.0: $300-500/月

---

### Q4: 国内网络访问问题?

**A**:
- **OpenAI/Anthropic**: 可能需要代理
- **Tavily/Serper/Firecrawl**: 国内可直接访问 ✅
- **Jina Reader**: 国内可直接访问 ✅

**解决方案**:
```python
# 设置代理
import os
os.environ["HTTP_PROXY"] = "http://127.0.0.1:7890"
os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7890"
```

或使用**文心一言**替代OpenAI(国内服务,无需代理)

---

### Q5: 测试API Key是否有效?

**A**: 使用提供的curl命令测试,或:

```python
# test_api_keys.py
import requests
import os
from dotenv import load_dotenv

load_dotenv()

def test_tavily():
    try:
        response = requests.post(
            "https://api.tavily.com/search",
            headers={"Authorization": f"Bearer {os.getenv('TAVILY_API_KEY')}"},
            json={"query": "test", "max_results": 1}
        )
        return "✅ Tavily OK" if response.status_code == 200 else f"❌ Tavily Failed: {response.status_code}"
    except Exception as e:
        return f"❌ Tavily Error: {e}"

def test_openai():
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=5
        )
        return "✅ OpenAI OK"
    except Exception as e:
        return f"❌ OpenAI Error: {e}"

def test_jina():
    try:
        response = requests.get("https://r.jina.ai/https://example.com")
        return "✅ Jina Reader OK" if response.status_code == 200 else f"❌ Jina Failed"
    except Exception as e:
        return f"❌ Jina Error: {e}"

if __name__ == "__main__":
    print("Testing API Keys...")
    print(test_tavily())
    print(test_openai())
    print(test_jina())
```

运行:
```bash
python test_api_keys.py
```

---

## 7. 总结

✅ **最小MVP配置**:
- Tavily (免费1000次)
- Jina Reader (免费)
- OpenAI ($10充值)

**总成本**: $10 一次性

✅ **推荐V1.5配置**:
- 上述全部
- Firecrawl (免费500页起)
- Serper (免费2500次)
- Anthropic ($10充值)

**总成本**: $50 首月(含API Key充值)

🎯 **获取优先级**:
1. **必需**: Tavily + OpenAI (立即获取)
2. **推荐**: Firecrawl + Serper (V1.5时获取)
3. **可选**: Anthropic + Exa (V2.0或特殊需求)

记得把所有key添加到`.env`文件并加入`.gitignore`! 🔐
