# Web Search & URL Fetch 服务调研报告

## 文档目的

为CreativeFlow选择最合适的Web Search和URL Fetch服务,对比主流方案的定价、功能、API易用性。

---

## 1. Web Search API 服务对比

### 1.1 核心候选方案

| 服务 | 定位 | 核心特点 | 适用场景 |
|------|------|---------|---------|
| **Tavily** | AI-native搜索API | LLM-ready内容、端到端pipeline | RAG、AI Agent研究 |
| **Serper** | Google SERP API | 快速、低成本、原始SERP数据 | 需要Google搜索结果 |
| **Exa** | 语义搜索引擎 | 基于embeddings的意义搜索 | 深度语义理解 |

---

### 1.2 详细对比

#### **Tavily Search API**

**定价**:
- **免费套餐**: 1,000 API credits/月
- **Project Plan**: $30/月, 4,000 credits
- **Add-on**: $100一次性购买, 8,000 credits永久有效
- **Pay-as-you-go**: $0.008/请求

**Credit消耗**:
- Basic Search: 1 credit/请求
- Advanced Search: 2 credits/请求

**核心功能**:
- ✅ **端到端pipeline**: 搜索→抓取→过滤→提取,一个API搞定
- ✅ **LLM-ready输出**: 结构化内容,直接喂给LLM
- ✅ **可信来源**: 优先权威、可引用的来源
- ✅ **智能查询建议**: Agent可以迭代deepening
- ✅ **自定义控制**: 搜索深度、域名管理、HTML内容控制

**性能**:
- SimpleQA benchmark准确率: **93.3%** (2025年1月)
- 延迟: 比Perplexity Deep Research低约**92%**

**集成**:
- 原生支持: LangChain, LlamaIndex
- 任何LLM都可集成

**优势**:
- ✅ 免费额度最慷慨(1000次/月)
- ✅ 专为AI Agent设计,开箱即用
- ✅ 返回内容质量高,减少hallucination
- ✅ 定价透明,credit永不过期

**劣势**:
- ❌ 不是直接的Google搜索(自有索引)
- ❌ 高级功能需要2 credits

**推荐指数**: ⭐️⭐️⭐️⭐️⭐️ (最推荐)

---

#### **Serper Google Search API**

**定价**:
- **免费额度**: 前2,500次查询免费
- **标准定价**: $0.30/1,000次查询 (=$0.0003/次)
- **高量定价**: 最低可到$0.0004/次

**对比**: 比SerpAPI便宜得多($75/月 5,000次 vs Serper的$1.5)

**核心功能**:
- ✅ **原生Google SERP**: 返回真实的Google搜索结果
- ✅ **极快响应**: 1-2秒返回结果
- ✅ **全产品支持**: Google所有产品(Search/Images/News/Maps等)
- ✅ **清晰文档**: 易于集成

**输出格式**:
- 返回原始SERP JSON(标题、摘要、URL、排名等)
- 需要自行抓取和清洗内容

**优势**:
- ✅ **超低成本**: 可能是市面上最便宜的Google SERP API
- ✅ 免费额度够用(2500次)
- ✅ 真实Google结果,数据新鲜度高

**劣势**:
- ❌ 只返回SERP,不包含网页内容
- ❌ 需要额外的URL Fetch步骤
- ❌ 不是LLM-ready格式

**推荐指数**: ⭐️⭐️⭐️⭐️ (成本敏感型推荐)

---

#### **Exa AI Search API**

**定价**:
- **免费额度**: $10 credits
- **付费套餐**: 从$50/月起
- **Research endpoint**: $5/1M reasoning tokens

**核心功能**:
- ✅ **语义搜索**: 基于embeddings,理解意图而非关键词
- ✅ **实时爬取**: 每分钟更新索引
- ✅ **强大过滤**: 日期/分类/域名,支持1-1000+结果
- ✅ **灵活输出**: 链接/全文/摘要/自定义提取
- ✅ **/research端点**: Agent自动多轮搜索,直到找到答案

**特色能力**:
- **Websets**: 批量查找和丰富人/公司数据(销售/招聘场景)
- **结构化输出**: 返回insights为结构化数据

**企业功能**:
- DPA/SLA支持
- 隐私合规(自动清除查询数据)

**优势**:
- ✅ 语义理解能力最强
- ✅ 独特的/research端点(Agent友好)
- ✅ 数据新鲜度高(分钟级更新)

**劣势**:
- ❌ 定价较高(起步$50/月)
- ❌ 免费额度较少($10)
- ❌ 文档和社区不如Tavily成熟

**推荐指数**: ⭐️⭐️⭐️⭐️ (深度语义场景推荐)

---

### 1.3 Web Search 推荐方案

**CreativeFlow的选择: Tavily (主) + Serper (备)**

**理由**:

1. **Tavily作为主力**:
   - 免费额度1000次/月足够MVP阶段使用
   - LLM-ready输出,无需额外处理,减少开发成本
   - 端到端pipeline,简化架构
   - 专为AI Agent设计,文档和集成最友好

2. **Serper作为备选**:
   - 当需要真实Google结果时(如竞品分析、热点追踪)
   - 成本极低,适合高频查询场景
   - 免费2500次可以覆盖早期测试

**实施策略**:
```python
def web_search(query: str, mode: str = "ai_native"):
    """
    mode:
      - "ai_native": 使用Tavily(默认,LLM-ready)
      - "google_serp": 使用Serper(需要原始Google结果)
    """
    if mode == "ai_native":
        return tavily_search(query)
    elif mode == "google_serp":
        serp_results = serper_search(query)
        # 需要额外调用URL Fetch提取内容
        return extract_content_from_urls(serp_results)
```

---

## 2. URL Fetch API 服务对比

### 2.1 核心候选方案

| 服务 | 定位 | 核心特点 | 适用场景 |
|------|------|---------|---------|
| **Jina Reader** | URL→Markdown转换器 | 免费、简单、LLM-ready | 单URL内容提取 |
| **Firecrawl** | Web数据API for AI | 全功能爬虫+AI提取 | 复杂爬取、整站抓取 |

---

### 2.2 详细对比

#### **Jina Reader API**

**定价**:
- **基础版**: 完全免费!
- **免费限额**: 20次/分钟(无API key) 或 200次/分钟(免费API key)
- **付费**: 超过限额可购买更高配额(具体价格未公开)

**新功能 - ReaderLM-v2** (2025年):
- 高质量HTML→Markdown转换
- 消耗3x token(对于复杂网站)
- 付费用户可用

**核心功能**:
- ✅ **极简使用**: `https://r.jina.ai/[URL]` 即可
- ✅ **LLM-ready输出**: 干净的Markdown格式
- ✅ **无需配置**: 自动处理JS渲染、反爬等
- ✅ **Grounding API**: 事实验证功能(新)

**Token共享**:
- 同一API key可用于Jina全家桶(Reader/Embedding/Reranking/Classifier)

**输出示例**:
```markdown
# 页面标题

正文内容已清洗,无广告无导航...

## 子标题

...
```

**优势**:
- ✅ **完全免费**(基础功能)
- ✅ 最简单的API(只需前缀URL)
- ✅ 输出质量高,LLM直接可用
- ✅ 200次/分钟免费限额够用

**劣势**:
- ❌ 仅支持单URL,不支持整站爬取
- ❌ 不支持自定义提取规则
- ❌ 复杂网站需要ReaderLM-v2(3x成本)

**推荐指数**: ⭐️⭐️⭐️⭐️⭐️ (单URL场景最佳)

---

#### **Firecrawl API**

**定价**:
- **免费套餐**: 500 pages
- **Hobby**: $16/月, 3,000 credits (~$0.005/页)
- **Standard**: $83/月, 100,000 credits (~$0.0008/页)
- **Growth**: $333/月, 500,000 credits
- **Enterprise**: 自定义

**Credit计费**:
- 标准页面: 1 page = 1 credit
- Search功能: 2 credits / 10个结果(不抓取时)

**AI Extract功能**(独立订阅):
- **Starter**: $89/月, 18M tokens/年
- **Explorer**: $359/月
- **Pro**: $719/月
- 按token计费,类似OpenAI定价

**核心功能**:

**1. /scrape - 单页抓取**
- 输出: Markdown或结构化JSON
- 自动处理: JS/SPA/动态内容
- 支持: PDF、DOCX等文件解析

**2. /crawl - 整站爬取**
- 系统遍历整个网站
- 支持50-100并发浏览器(取决于套餐)
- 智能去重和结构化

**3. /extract - AI驱动提取** ⭐️
- 用自然语言描述提取需求
- 返回自定义JSON结构
- 示例: "提取leadership团队的姓名、职位、邮箱"

**4. /search - 搜索+抓取**
- 执行web搜索
- 可选择性抓取搜索结果
- 支持多种输出格式(markdown/HTML/links/screenshots)

**输出格式**:
```json
{
  "markdown": "# 清洗后的内容...",
  "html": "<原始HTML>",
  "metadata": {
    "title": "页面标题",
    "description": "描述",
    "language": "en"
  },
  "links": ["提取的链接"],
  "screenshot": "截图URL"
}
```

**优势**:
- ✅ **全功能**: 单页/整站/AI提取/搜索,一站式
- ✅ **强大的并发**: 50-100浏览器并行
- ✅ **/extract超强**: 自然语言描述提取需求
- ✅ 处理复杂网站能力强(JS/SPA)
- ✅ 免费500页可试用

**劣势**:
- ❌ 成本较高(单URL场景不如Jina)
- ❌ /extract是独立订阅,额外付费
- ❌ 对于简单需求有点over-engineering

**推荐指数**: ⭐️⭐️⭐️⭐️ (复杂爬取场景推荐)

---

### 2.3 URL Fetch 推荐方案

**CreativeFlow的选择: Jina Reader (主) + Firecrawl (特殊场景)**

**理由**:

1. **Jina Reader作为主力**(80%场景):
   - 大部分场景是单URL内容提取(竞品分析、参考资料)
   - 完全免费,200次/分钟够用
   - 输出质量高,LLM可直接使用
   - API极简,开发成本低

2. **Firecrawl按需使用**(20%场景):
   - 整站爬取(如爬取竞品官网所有产品页)
   - AI Extract(结构化数据提取,如提取团队信息)
   - 复杂网站(需要高并发、反爬能力)
   - 可以从免费500页开始,按需升级

**实施策略**:
```python
def fetch_url(url: str, mode: str = "simple"):
    """
    mode:
      - "simple": 单URL提取(Jina Reader,免费)
      - "crawl": 整站爬取(Firecrawl)
      - "extract": AI结构化提取(Firecrawl /extract)
    """
    if mode == "simple":
        # 80%的场景
        markdown = f"https://r.jina.ai/{url}"
        return requests.get(markdown).text

    elif mode == "crawl":
        # 整站爬取
        return firecrawl_crawl(url)

    elif mode == "extract":
        # AI驱动提取
        return firecrawl_extract(
            url=url,
            prompt="提取leadership团队信息",
            schema={"name": "str", "title": "str", "email": "str"}
        )
```

---

## 3. 成本估算

### 3.1 MVP阶段(月活100用户,每用户平均5次操作)

**场景分布**:
- Web Search: 300次/月 (竞品调研、热点追踪)
- URL Fetch: 200次/月 (参考资料提取)

**成本**:
```
Tavily: 300次 < 1000免费额度 → $0
Jina Reader: 200次 < 免费额度 → $0

总计: $0/月 ✅
```

---

### 3.2 V1.5阶段(月活1000用户)

**场景分布**:
- Web Search: 3,000次/月
- URL Fetch: 2,000次/月
- 整站爬取: 50次/月 (每次500页)

**成本**:
```
Web Search:
  - Tavily: 3,000次 → $30 (Project Plan, 4,000 credits)
  - 或Serper: 3,000次 → $0.9 (超低成本)

URL Fetch:
  - Jina Reader: 2,000次 → $0 (免费)
  - Firecrawl: 50次×500页 = 25,000 pages → $83/月 (Standard Plan)

总计: $30(Tavily) + $83(Firecrawl) = $113/月

优化方案:
如果用Serper替代Tavily → $0.9 + $83 = $83.9/月 ✅
```

---

### 3.3 V2.0阶段(月活10,000用户)

**场景分布**:
- Web Search: 30,000次/月
- URL Fetch: 20,000次/月
- 整站爬取: 500次/月 (每次500页)

**成本**:
```
Web Search:
  - Tavily: 30,000次 → 需要多个Project Plan或企业方案
  - Serper: 30,000次 → $9/月 ✅ (超划算)

URL Fetch:
  - Jina Reader: 20,000次 → 可能需要付费,但仍很便宜
  - Firecrawl: 500次×500页 = 250,000 pages → $333/月 (Growth Plan)

总计: $9(Serper) + $333(Firecrawl) = $342/月

如果全用Tavily: 估计$300-500/月
```

---

## 4. 最终推荐方案

### 🎯 CreativeFlow Web Search & URL Fetch 技术栈

```python
# config.py

WEB_SEARCH_CONFIG = {
    "primary": "tavily",  # MVP/V1.5阶段主力
    "fallback": "serper",  # 成本优化/高量场景
    "api_keys": {
        "tavily": os.getenv("TAVILY_API_KEY"),
        "serper": os.getenv("SERPER_API_KEY")
    }
}

URL_FETCH_CONFIG = {
    "primary": "jina_reader",  # 80%单URL场景
    "advanced": "firecrawl",   # 20%复杂场景
    "api_keys": {
        "jina": os.getenv("JINA_API_KEY"),  # 可选,提升限额
        "firecrawl": os.getenv("FIRECRAWL_API_KEY")
    }
}
```

### 📊 分阶段切换策略

| 阶段 | Web Search | URL Fetch | 月成本 |
|------|-----------|----------|--------|
| **MVP** | Tavily免费 | Jina免费 | $0 |
| **V1.5** | Tavily $30 | Jina免费 + Firecrawl $83 | $113 |
| **V2.0** | 切换Serper $9 | Jina + Firecrawl $333 | $342 |

### ✅ 关键优势

1. **MVP零成本**: 免费额度足够验证产品
2. **渐进式付费**: 按需升级,不浪费
3. **灵活切换**: 架构支持主备方案,成本可控
4. **LLM-ready**: 所有输出都是Markdown/JSON,直接喂给LLM

---

## 5. 实现示例

### 5.1 Web Search Tool

```python
from typing import Literal
import requests
import os

class WebSearchTool(BaseAtomicTool):
    def __init__(self):
        super().__init__(
            name="web_search",
            description="搜索互联网内容,返回LLM-ready结果"
        )
        self.tavily_key = os.getenv("TAVILY_API_KEY")
        self.serper_key = os.getenv("SERPER_API_KEY")

    def execute(self, params: dict) -> dict:
        query = params["query"]
        mode = params.get("mode", "ai_native")
        max_results = params.get("max_results", 5)

        if mode == "ai_native":
            return self._tavily_search(query, max_results)
        elif mode == "google_serp":
            return self._serper_search(query, max_results)

    def _tavily_search(self, query: str, max_results: int) -> dict:
        """Tavily搜索: LLM-ready输出"""
        response = requests.post(
            "https://api.tavily.com/search",
            headers={"Authorization": f"Bearer {self.tavily_key}"},
            json={
                "query": query,
                "search_depth": "basic",  # or "advanced" (2 credits)
                "max_results": max_results,
                "include_answer": True,  # AI生成的摘要答案
                "include_raw_content": False,  # 节省tokens
                "include_images": False
            }
        )

        data = response.json()

        return {
            "answer": data.get("answer"),  # AI摘要
            "results": [
                {
                    "title": r["title"],
                    "url": r["url"],
                    "content": r["content"],  # 已提取和清洗
                    "score": r.get("score", 0)
                }
                for r in data.get("results", [])
            ],
            "query": query,
            "source": "tavily"
        }

    def _serper_search(self, query: str, max_results: int) -> dict:
        """Serper搜索: 原始SERP"""
        response = requests.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": self.serper_key},
            json={
                "q": query,
                "num": max_results
            }
        )

        data = response.json()

        return {
            "results": [
                {
                    "title": r["title"],
                    "url": r["link"],
                    "snippet": r["snippet"],  # 仅摘要,需要额外fetch
                    "position": r.get("position")
                }
                for r in data.get("organic", [])
            ],
            "query": query,
            "source": "serper"
        }

    def get_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": "web_search",
                "description": "搜索互联网内容,支持AI-native和Google SERP两种模式",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "搜索查询词"
                        },
                        "mode": {
                            "type": "string",
                            "enum": ["ai_native", "google_serp"],
                            "description": "搜索模式: ai_native=Tavily(LLM-ready), google_serp=Serper(原始SERP)"
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "返回结果数量,默认5",
                            "default": 5
                        }
                    },
                    "required": ["query"]
                }
            }
        }
```

### 5.2 URL Fetch Tool

```python
import requests
from firecrawl import FirecrawlApp

class URLFetchTool(BaseAtomicTool):
    def __init__(self):
        super().__init__(
            name="url_fetch",
            description="从URL提取内容,支持单页/整站/AI提取"
        )
        self.firecrawl = FirecrawlApp(api_key=os.getenv("FIRECRAWL_API_KEY"))

    def execute(self, params: dict) -> dict:
        url = params["url"]
        mode = params.get("mode", "simple")

        if mode == "simple":
            return self._jina_reader(url)
        elif mode == "crawl":
            return self._firecrawl_crawl(url, params)
        elif mode == "extract":
            return self._firecrawl_extract(url, params)

    def _jina_reader(self, url: str) -> dict:
        """Jina Reader: 最简单的方式"""
        reader_url = f"https://r.jina.ai/{url}"
        response = requests.get(reader_url)

        return {
            "url": url,
            "markdown": response.text,
            "source": "jina_reader"
        }

    def _firecrawl_crawl(self, url: str, params: dict) -> dict:
        """Firecrawl: 整站爬取"""
        crawl_result = self.firecrawl.crawl_url(
            url,
            params={
                "limit": params.get("max_pages", 100),
                "scrapeOptions": {
                    "formats": ["markdown", "html"],
                }
            },
            wait_until_done=True
        )

        return {
            "url": url,
            "pages": [
                {
                    "url": page["metadata"]["sourceURL"],
                    "markdown": page["markdown"],
                    "title": page["metadata"].get("title")
                }
                for page in crawl_result["data"]
            ],
            "total_pages": len(crawl_result["data"]),
            "source": "firecrawl_crawl"
        }

    def _firecrawl_extract(self, url: str, params: dict) -> dict:
        """Firecrawl Extract: AI驱动提取"""
        extract_result = self.firecrawl.extract(
            url,
            params={
                "prompt": params["extract_prompt"],
                "schema": params.get("extract_schema")
            }
        )

        return {
            "url": url,
            "extracted_data": extract_result["data"],
            "source": "firecrawl_extract"
        }

    def get_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": "url_fetch",
                "description": "从URL提取内容,支持单页/整站/AI结构化提取",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "要提取的URL"
                        },
                        "mode": {
                            "type": "string",
                            "enum": ["simple", "crawl", "extract"],
                            "description": "提取模式: simple=单页Markdown, crawl=整站, extract=AI提取"
                        },
                        "max_pages": {
                            "type": "integer",
                            "description": "crawl模式下最大页数,默认100"
                        },
                        "extract_prompt": {
                            "type": "string",
                            "description": "extract模式下的提取指令,如'提取团队成员信息'"
                        },
                        "extract_schema": {
                            "type": "object",
                            "description": "extract模式下的输出结构定义"
                        }
                    },
                    "required": ["url"]
                }
            }
        }
```

---

## 6. 总结

✅ **Web Search推荐**: Tavily(主) + Serper(备)
✅ **URL Fetch推荐**: Jina Reader(主) + Firecrawl(特殊场景)
✅ **MVP成本**: $0/月
✅ **V1.5成本**: $113/月
✅ **V2.0成本**: $342/月

**关键决策理由**:
1. Tavily的LLM-ready输出节省大量后处理成本
2. Jina Reader免费且质量高,覆盖80%场景
3. 灵活切换策略,成本可控
4. 所有服务都是AI-native,集成简单
