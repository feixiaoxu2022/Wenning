#!/usr/bin/env python3
"""
端到端测试脚本：样本执行 → 评测

流程：
1. 加载评测样本
2. 使用两个模型分别执行任务
3. 保存执行结果
4. 运行评测框架
"""

import json
import sys
from pathlib import Path
from datetime import datetime

# 添加src到路径
sys.path.insert(0, str(Path(__file__).parent))

from src.utils.config import get_config
from src.agent.master_agent import MasterAgent
from src.tools.registry import ToolRegistry
from src.tools.atomic.web_search import WebSearchTool
from src.tools.atomic.url_fetch import URLFetchTool
from src.tools.atomic.code_executor import CodeExecutor
from evaluator import EvaluationOrchestrator


def setup_agent(model_name: str) -> MasterAgent:
    """初始化Agent"""
    config = get_config()
    tool_registry = ToolRegistry()

    # 注册工具
    tool_registry.register_atomic_tool(WebSearchTool(config))
    tool_registry.register_atomic_tool(URLFetchTool(config))
    tool_registry.register_atomic_tool(CodeExecutor(config))

    agent = MasterAgent(config, tool_registry, model_name=model_name)
    return agent


def execute_task(agent: MasterAgent, query: str, sample_id: str, timeout: int = 300) -> dict:
    """执行任务并返回执行结果"""
    print(f"\n🤖 模型 {agent.llm.model_name} 开始执行任务...")
    print(f"📝 Query: {query}")

    # 记录初始状态
    initial_state = {
        "files": []
    }

    # 执行任务
    try:
        result = agent.process(query)
        status = "success" if result.get("status") == "success" else "failed"
    except Exception as e:
        print(f"❌ 执行失败: {e}")
        status = "failed"
        result = {"error": str(e)}

    # 获取最终状态（扫描输出目录）
    output_dir = Path("outputs")
    conversation_id = agent.current_conversation_id

    final_files = []
    if conversation_id and output_dir.exists():
        conv_dir = output_dir / conversation_id
        if conv_dir.exists():
            for file_path in conv_dir.rglob("*"):
                if file_path.is_file():
                    rel_path = file_path.relative_to(conv_dir)
                    file_info = {
                        "path": str(rel_path),
                        "size": file_path.stat().st_size,
                        "type": file_path.suffix[1:] if file_path.suffix else "unknown"
                    }

                    # 添加图片元数据
                    if file_info["type"] in ["png", "jpg", "jpeg"]:
                        try:
                            from PIL import Image
                            img = Image.open(file_path)
                            file_info["metadata"] = {
                                "dimensions": {
                                    "width": img.width,
                                    "height": img.height
                                }
                            }
                        except:
                            pass

                    final_files.append(file_info)

    final_state = {
        "files": final_files
    }

    # 构建执行结果
    execution_result = {
        "sample_id": sample_id,
        "model_name": agent.llm.model_name,
        "status": status,
        "evaluated_at": datetime.now().isoformat(),
        "initial_state": initial_state,
        "final_state": final_state,
        "conversation_history": agent.conversation_history
    }

    print(f"✅ 执行完成！生成 {len(final_files)} 个文件")
    return execution_result


def main():
    """主函数"""
    print("=" * 80)
    print("CreativeFlow 端到端测试")
    print("=" * 80)

    # 1. 加载样本
    sample_path = Path("samples/EVAL_ICON_COLLECTION_TECH.json")
    print(f"\n📂 加载样本: {sample_path}")

    with open(sample_path, 'r', encoding='utf-8') as f:
        sample = json.load(f)

    sample_id = sample["data_id"]
    query = sample["query"]
    model_a = sample["models"]["model_a"]
    model_b = sample["models"]["model_b"]
    timeout = sample.get("timeout", 300)

    print(f"✓ 样本ID: {sample_id}")
    print(f"✓ Model A: {model_a}")
    print(f"✓ Model B: {model_b}")
    print(f"✓ 超时: {timeout}秒")

    # 2. 执行Model A
    print("\n" + "=" * 80)
    print("阶段1: 执行 Model A")
    print("=" * 80)

    agent_a = setup_agent(model_a)
    execution_result_a = execute_task(agent_a, query, sample_id, timeout)

    # 保存执行结果A
    execution_a_path = Path(f"executions/{model_a}_{sample_id}.json")
    execution_a_path.parent.mkdir(exist_ok=True)
    with open(execution_a_path, 'w', encoding='utf-8') as f:
        json.dump(execution_result_a, f, indent=2, ensure_ascii=False)
    print(f"✓ 执行结果已保存: {execution_a_path}")

    # 3. 执行Model B
    print("\n" + "=" * 80)
    print("阶段2: 执行 Model B")
    print("=" * 80)

    agent_b = setup_agent(model_b)
    execution_result_b = execute_task(agent_b, query, sample_id, timeout)

    # 保存执行结果B
    execution_b_path = Path(f"executions/{model_b}_{sample_id}.json")
    with open(execution_b_path, 'w', encoding='utf-8') as f:
        json.dump(execution_result_b, f, indent=2, ensure_ascii=False)
    print(f"✓ 执行结果已保存: {execution_b_path}")

    # 4. 运行评测
    print("\n" + "=" * 80)
    print("阶段3: 运行评测框架")
    print("=" * 80)

    # 检查是否需要LLM Judge
    has_llm_judge = any(
        check["check_type"] == "llm_judge"
        for check in sample["check_list"]
    )

    if has_llm_judge:
        print("\n⚠️  样本包含LLM Judge检查项")
        print("请提供Judge模型配置:")

        # 从环境变量或配置读取
        import os
        judge_model = os.getenv("JUDGE_MODEL", "claude-sonnet-4-5-20250929")
        judge_base_url = os.getenv("JUDGE_BASE_URL", "https://api.anthropic.com/v1")
        judge_api_key = os.getenv("ANTHROPIC_API_KEY")

        if not judge_api_key:
            print("❌ 未找到ANTHROPIC_API_KEY环境变量，跳过LLM Judge")
            judge_model = None
            judge_base_url = None
            judge_api_key = None
        else:
            print(f"✓ 使用Judge模型: {judge_model}")
    else:
        judge_model = None
        judge_base_url = None
        judge_api_key = None

    # 创建评测器
    orchestrator = EvaluationOrchestrator(
        judge_model=judge_model,
        judge_base_url=judge_base_url,
        judge_api_key=judge_api_key
    )

    # 执行评测
    result_path = Path(f"results/{sample_id}_result.json")
    result_path.parent.mkdir(exist_ok=True)

    eval_result = orchestrator.evaluate(
        sample=sample,
        execution_result_a=execution_result_a,
        execution_result_b=execution_result_b,
        output_file=result_path
    )

    print(f"\n✓ 评测结果已保存: {result_path}")

    # 5. 输出结果摘要
    print("\n" + "=" * 80)
    print("评测结果摘要")
    print("=" * 80)

    print(f"\n📊 Model A ({model_a}):")
    print(f"  - 状态: {execution_result_a['status']}")
    print(f"  - 文件数: {len(execution_result_a['final_state']['files'])}")

    print(f"\n📊 Model B ({model_b}):")
    print(f"  - 状态: {execution_result_b['status']}")
    print(f"  - 文件数: {len(execution_result_b['final_state']['files'])}")

    print("\n✅ 端到端测试完成!")
    print("\n下一步:")
    print("1. 查看执行结果文件:")
    print(f"   - {execution_a_path}")
    print(f"   - {execution_b_path}")
    print("2. 查看评测结果:")
    print(f"   - {result_path}")
    print("3. 进行Human Annotation（如果需要）")


if __name__ == "__main__":
    main()
