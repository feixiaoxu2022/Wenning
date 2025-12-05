"""基础功能测试脚本

测试Config、LLMClient和Atomic Tools的基本功能。
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.config import get_config
from src.llm.client import LLMClient
from src.tools.atomic.web_search import WebSearchTool
from src.tools.atomic.url_fetch import URLFetchTool
from src.tools.atomic.code_executor import CodeExecutor
from src.utils.logger import get_logger

logger = get_logger(__name__)


def test_config():
    """测试配置加载"""
    print("\n" + "="*60)
    print("测试1: 配置加载")
    print("="*60)

    try:
        config = get_config()
        print(f"✅ 配置加载成功")
        print(f"   可用模型: {config.available_models}")
        print(f"   输出目录: {config.output_dir}")
        print(f"   Tavily API: {'已配置' if config.tavily_api_key else '未配置'}")
        print(f"   Serper API: {'已配置' if config.serper_api_key else '未配置'}")
        return config
    except Exception as e:
        print(f"❌ 配置加载失败: {e}")
        sys.exit(1)


def test_llm_client(config):
    """测试LLM客户端"""
    print("\n" + "="*60)
    print("测试2: LLM客户端")
    print("="*60)

    try:
        llm = LLMClient(config, model_name="ernie-5.0-thinking-preview")
        print(f"✅ LLM客户端初始化成功: {llm.model_name}")

        # 测试简单聊天
        print("   测试聊天功能...")
        response = llm.chat([
            {"role": "user", "content": "请用一句话介绍CreativeFlow"}
        ], temperature=0.7)

        print(f"   LLM响应: {response['content'][:100]}...")
        print(f"   Token使用: {response.get('usage', {})}")

        return llm
    except Exception as e:
        print(f"❌ LLM测试失败: {e}")
        return None


def test_web_search(config):
    """测试Web搜索工具"""
    print("\n" + "="*60)
    print("测试3: Web搜索工具")
    print("="*60)

    try:
        search_tool = WebSearchTool(config)
        print(f"✅ Web搜索工具初始化成功")

        # 执行搜索
        print("   执行搜索: '创意工作流'")
        result = search_tool.run(query="创意工作流", max_results=3)

        if result["status"] == "success":
            data = result["data"]
            print(f"   搜索成功: 找到{data['total']}个结果")
            print(f"   来源: {data['source']}")
            if data.get("answer"):
                print(f"   AI摘要: {data['answer'][:100]}...")
        else:
            print(f"   搜索失败: {result.get('error')}")

    except Exception as e:
        print(f"❌ Web搜索测试失败: {e}")


def test_url_fetch(config):
    """测试URL抓取工具"""
    print("\n" + "="*60)
    print("测试4: URL抓取工具")
    print("="*60)

    try:
        fetch_tool = URLFetchTool(config)
        print(f"✅ URL抓取工具初始化成功")

        # 抓取示例URL
        test_url = "https://example.com"
        print(f"   抓取URL: {test_url}")
        result = fetch_tool.run(url=test_url)

        if result["status"] == "success":
            data = result["data"]
            print(f"   抓取成功: {data['source']}")
            print(f"   标题: {data.get('title', 'N/A')}")
            print(f"   内容长度: {data['length']} characters")
        else:
            print(f"   抓取失败: {result.get('error')}")

    except Exception as e:
        print(f"❌ URL抓取测试失败: {e}")


def test_code_executor(config):
    """测试代码执行器"""
    print("\n" + "="*60)
    print("测试5: 代码执行器")
    print("="*60)

    try:
        executor = CodeExecutor(config)
        print(f"✅ 代码执行器初始化成功")

        # 执行简单代码
        test_code = """
print("Hello from CreativeFlow!")
result = 1 + 1
print(f"1 + 1 = {result}")
"""
        print("   执行测试代码...")
        result = executor.run(code=test_code)

        if result["status"] == "success":
            print(f"   执行成功")
            print(f"   输出:\\n{result['data']['stdout']}")
        else:
            print(f"   执行失败: {result.get('error')}")

    except Exception as e:
        print(f"❌ 代码执行测试失败: {e}")


def main():
    """主测试函数"""
    print("\\n" + "="*60)
    print("CreativeFlow - 基础功能测试")
    print("="*60)

    # 1. 测试配置
    config = test_config()

    # 2. 测试LLM
    llm = test_llm_client(config)

    # 3. 测试Web搜索
    test_web_search(config)

    # 4. 测试URL抓取
    test_url_fetch(config)

    # 5. 测试代码执行
    test_code_executor(config)

    print("\\n" + "="*60)
    print("✅ 所有基础测试完成")
    print("="*60)


if __name__ == "__main__":
    main()
