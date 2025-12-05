#!/usr/bin/env python3
"""
执行两个模型并运行评测

完整流程:
1. 加载样本
2. 执行Model A
3. 执行Model B
4. 运行评测框架(Rule + LLM Judge)
5. 生成评测结果(待Human Annotation)
"""

import json
import sys
import os
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from src.utils.config import get_config
from src.agent.master_agent import MasterAgent
from src.tools.registry import ToolRegistry
from src.tools.atomic.web_search import WebSearchTool
from src.tools.atomic.url_fetch import URLFetchTool
from src.tools.atomic.code_executor import CodeExecutor
from evaluator import EvaluationOrchestrator


def execute_agent(sample_id: str, query: str, model_name: str):
    """执行单个Agent"""
    print("\n" + "=" * 80)
    print(f"执行模型: {model_name}")
    print("=" * 80)

    # 初始化Agent
    config = get_config()
    registry = ToolRegistry()
    registry.register_atomic_tool(WebSearchTool(config))
    registry.register_atomic_tool(URLFetchTool(config))
    registry.register_atomic_tool(CodeExecutor(config))

    agent = MasterAgent(config, registry, model_name)

    # 设置conversation_id
    conversation_id = f"{sample_id}_{model_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    agent.current_conversation_id = conversation_id
    print(f"✓ Conversation ID: {conversation_id}")

    # 执行任务
    print(f"\n开始执行...")
    try:
        result = agent.process(query)

        # 消费生成器
        if hasattr(result['result'], '__iter__') and hasattr(result['result'], '__next__'):
            for _ in result['result']:
                pass

        status = "success"
        print(f"✓ 执行完成")

    except Exception as e:
        print(f"❌ 执行失败: {e}")
        status = "failed"

    # 扫描生成的文件
    output_dir = Path("outputs") / conversation_id
    final_files = []

    if output_dir.exists():
        for file_path in output_dir.rglob("*"):
            if file_path.is_file():
                rel_path = file_path.relative_to(output_dir)
                file_info = {
                    "path": str(rel_path),
                    "size": file_path.stat().st_size,
                    "type": file_path.suffix[1:] if file_path.suffix else "unknown"
                }
                final_files.append(file_info)

    print(f"✓ 生成文件数: {len(final_files)}")
    if final_files:
        for f in final_files:
            print(f"  - {f['path']} ({f['size']} bytes)")

    # 构建execution_result
    execution_result = {
        "sample_id": sample_id,
        "model_name": model_name,
        "status": status,
        "evaluated_at": datetime.now().isoformat(),
        "initial_state": {"files": []},
        "final_state": {"files": final_files},
        "conversation_history": agent.conversation_history
    }

    # 保存
    executions_dir = Path("executions")
    executions_dir.mkdir(exist_ok=True)
    execution_path = executions_dir / f"{model_name}_{sample_id}.json"

    with open(execution_path, 'w', encoding='utf-8') as f:
        json.dump(execution_result, f, indent=2, ensure_ascii=False)

    print(f"✓ 执行结果已保存: {execution_path}")

    return execution_result, str(output_dir)


def main():
    """主流程"""
    print("=" * 80)
    print("CreativeFlow 完整评测流程")
    print("=" * 80)

    # 1. 加载样本
    sample_path = Path("samples/EVAL_ICON_COLLECTION_TECH.json")
    with open(sample_path, 'r', encoding='utf-8') as f:
        sample = json.load(f)

    sample_id = sample["data_id"]
    query = sample["query"]
    model_a = sample["models"]["model_a"]
    model_b = sample["models"]["model_b"]

    print(f"\n样本ID: {sample_id}")
    print(f"Model A: {model_a}")
    print(f"Model B: {model_b}")
    print(f"\nQuery: {query}")

    # 2. 执行两个模型
    execution_a, output_dir_a = execute_agent(sample_id, query, model_a)
    execution_b, output_dir_b = execute_agent(sample_id, query, model_b)

    # 3. 运行评测
    print("\n" + "=" * 80)
    print("运行评测框架")
    print("=" * 80)

    # 配置LLM Judge
    judge_model = "gemini-3-pro-preview"
    judge_base_url = "http://yy.dbh.baidu-int.com/v1"
    judge_api_key = os.getenv("AGENT_MODEL_API_KEY")

    if not judge_api_key:
        print("❌ 错误: 未找到AGENT_MODEL_API_KEY")
        sys.exit(1)

    print(f"✓ Judge模型: {judge_model}")

    orchestrator = EvaluationOrchestrator(
        judge_model=judge_model,
        judge_base_url=judge_base_url,
        judge_api_key=judge_api_key
    )

    result_path = Path(f"results/{sample_id}_result.json")
    result_path.parent.mkdir(exist_ok=True)

    eval_result = orchestrator.evaluate(
        sample=sample,
        execution_result_a=execution_a,
        execution_result_b=execution_b,
        output_file=result_path
    )

    # 4. 输出结果摘要
    print("\n" + "=" * 80)
    print("评测完成!")
    print("=" * 80)

    print(f"\n评测结果: {result_path}")

    print(f"\n📊 Model A ({model_a}):")
    print(f"  文件数: {len(execution_a['final_state']['files'])}")
    print(f"  输出目录: {output_dir_a}")

    print(f"\n📊 Model B ({model_b}):")
    print(f"  文件数: {len(execution_b['final_state']['files'])}")
    print(f"  输出目录: {output_dir_b}")

    print("\n" + "=" * 80)
    print("下一步: Human Annotation")
    print("=" * 80)
    print("\n请手动:")
    print(f"1. 查看Model A输出: {output_dir_a}")
    print(f"2. 查看Model B输出: {output_dir_b}")
    print(f"3. 编辑评测结果: {result_path}")
    print("4. 在human_annotation字段填写:")
    print('   - winner: "model_a" | "model_b" | "tie"')
    print('   - reason: "..."')
    print('   - annotator: "你的名字"')
    print('   - annotated_at: "当前时间"')


if __name__ == "__main__":
    main()
