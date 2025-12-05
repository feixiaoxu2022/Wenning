#!/usr/bin/env python3
"""
评测执行脚本

使用方式：
python run_evaluation.py \
    --sample samples/EVAL_ICON_COLLECTION_TECH.json \
    --execution-a executions/ernie-5.0_ICON_COLLECTION.json \
    --execution-b executions/gpt-5_ICON_COLLECTION.json \
    --output results/EVAL_ICON_COLLECTION_TECH_result.json \
    --judge-model claude-sonnet-4-5-20250929 \
    --judge-base-url https://api.anthropic.com/v1 \
    --judge-api-key your_api_key
"""

import argparse
import json
import sys
from pathlib import Path

from evaluator import EvaluationOrchestrator


def load_json(file_path: str) -> dict:
    """加载JSON文件"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(description="CreativeFlow 评测执行脚本")

    # 必需参数
    parser.add_argument(
        "--sample",
        required=True,
        help="样本JSON文件路径（evaluation_sample_schema格式）"
    )
    parser.add_argument(
        "--execution-a",
        required=True,
        help="Model A的执行结果JSON文件（agent_execution_result_schema格式）"
    )
    parser.add_argument(
        "--execution-b",
        required=True,
        help="Model B的执行结果JSON文件（agent_execution_result_schema格式）"
    )
    parser.add_argument(
        "--output",
        required=True,
        help="评测结果输出路径（evaluation_result_schema格式）"
    )

    # LLM Judge配置（可选，如果样本中有llm_judge检查项才需要）
    parser.add_argument(
        "--judge-model",
        help="LLM Judge模型名称（如claude-sonnet-4-5-20250929）"
    )
    parser.add_argument(
        "--judge-base-url",
        help="LLM Judge API base URL"
    )
    parser.add_argument(
        "--judge-api-key",
        help="LLM Judge API密钥"
    )

    args = parser.parse_args()

    # 加载数据
    print("=" * 60)
    print("CreativeFlow 评测系统")
    print("=" * 60)
    print(f"\n加载样本: {args.sample}")
    sample = load_json(args.sample)

    print(f"加载 Model A 执行结果: {args.execution_a}")
    execution_a = load_json(args.execution_a)

    print(f"加载 Model B 执行结果: {args.execution_b}")
    execution_b = load_json(args.execution_b)

    # 验证sample_id一致性
    sample_id = sample["data_id"]
    if execution_a.get("sample_id") != sample_id:
        print(f"⚠️  警告: execution_a的sample_id ({execution_a.get('sample_id')}) 与样本ID ({sample_id}) 不一致")
    if execution_b.get("sample_id") != sample_id:
        print(f"⚠️  警告: execution_b的sample_id ({execution_b.get('sample_id')}) 与样本ID ({sample_id}) 不一致")

    # 检查是否需要LLM Judge
    has_llm_judge = any(
        check["check_type"] == "llm_judge"
        for check in sample["check_list"]
    )

    if has_llm_judge:
        if not all([args.judge_model, args.judge_base_url, args.judge_api_key]):
            print("\n❌ 错误: 样本中包含llm_judge检查项，但未提供完整的LLM Judge配置")
            print("请提供: --judge-model, --judge-base-url, --judge-api-key")
            sys.exit(1)
        print(f"\n✓ LLM Judge配置: {args.judge_model}")

    # 创建评测器
    orchestrator = EvaluationOrchestrator(
        judge_model=args.judge_model,
        judge_base_url=args.judge_base_url,
        judge_api_key=args.judge_api_key
    )

    # 执行评测
    print("\n" + "=" * 60)
    result = orchestrator.evaluate(
        sample=sample,
        execution_result_a=execution_a,
        execution_result_b=execution_b,
        output_file=Path(args.output)
    )
    print("=" * 60)

    print(f"\n✓ 评测完成！结果已保存至: {args.output}")
    print("\n注意:")
    print("1. 此结果仅包含Rule-based和LLM Judge的自动评测")
    print("2. 需要进行Human Annotation后才能计算final_scores和winner")
    print("3. Human Annotation字段目前为空，请手动标注后更新JSON文件")


if __name__ == "__main__":
    main()
