#!/usr/bin/env python3
"""
完整评测测试：包含Rule-based + LLM Judge

使用mock数据测试完整评测流程
"""

import json
import sys
import os
from pathlib import Path
from datetime import datetime

# 添加src到路径
sys.path.insert(0, str(Path(__file__).parent))

from evaluator import EvaluationOrchestrator


def create_mock_execution_result(sample_id: str, model_name: str, file_count: int) -> dict:
    """创建mock执行结果"""
    files = []

    # 模拟生成的图标文件
    categories = ["ai", "cloud", "code", "data", "security"]
    formats = ["png", "svg"]

    for i in range(file_count):
        category = categories[i % len(categories)]
        format_type = formats[i % len(formats)]

        file_info = {
            "path": f"{category}/icon_{i+1}.{format_type}",
            "size": 2048 + i * 100,
            "type": format_type
        }

        # 添加图片元数据
        if format_type in ["png", "jpg"]:
            file_info["metadata"] = {
                "dimensions": {
                    "width": 512,
                    "height": 512
                }
            }

        files.append(file_info)

    return {
        "sample_id": sample_id,
        "model_name": model_name,
        "status": "success",
        "evaluated_at": datetime.now().isoformat(),
        "initial_state": {"files": []},
        "final_state": {"files": files},
        "conversation_history": [
            {
                "role": "user",
                "content": "搜集科技类图标",
                "timestamp": datetime.now().isoformat()
            },
            {
                "role": "assistant",
                "content": f"我已经搜集了{file_count}个科技类图标，覆盖了AI、云计算、代码、数据、网络安全等场景，并按类别组织在不同文件夹中。",
                "timestamp": datetime.now().isoformat()
            }
        ]
    }


def main():
    """主函数"""
    print("=" * 80)
    print("CreativeFlow 完整评测测试 (Rule-based + LLM Judge)")
    print("=" * 80)

    # 1. 加载样本
    sample_path = Path("samples/EVAL_ICON_COLLECTION_TECH.json")
    print(f"\n📂 加载样本: {sample_path}")

    with open(sample_path, 'r', encoding='utf-8') as f:
        sample = json.load(f)

    sample_id = sample["data_id"]
    model_a = sample["models"]["model_a"]
    model_b = sample["models"]["model_b"]

    print(f"✓ 样本ID: {sample_id}")
    print(f"✓ Model A: {model_a}")
    print(f"✓ Model B: {model_b}")

    # 2. 创建mock执行结果
    print("\n" + "=" * 80)
    print("创建Mock执行结果")
    print("=" * 80)

    # Model A: 15个文件,质量较高
    execution_result_a = create_mock_execution_result(sample_id, model_a, 15)
    print(f"✓ Model A mock: {len(execution_result_a['final_state']['files'])} 个文件")

    # Model B: 25个文件,数量更多
    execution_result_b = create_mock_execution_result(sample_id, model_b, 25)
    print(f"✓ Model B mock: {len(execution_result_b['final_state']['files'])} 个文件")

    # 3. 配置LLM Judge
    print("\n" + "=" * 80)
    print("配置LLM Judge")
    print("=" * 80)

    judge_model = os.getenv("JUDGE_MODEL", "claude-sonnet-4-5-20250929")
    judge_base_url = os.getenv("JUDGE_BASE_URL", "https://api.anthropic.com/v1")
    judge_api_key = os.getenv("ANTHROPIC_API_KEY")

    if not judge_api_key:
        print("❌ 错误: 未找到ANTHROPIC_API_KEY环境变量")
        print("请在.env文件中添加: ANTHROPIC_API_KEY=your_key")
        sys.exit(1)

    print(f"✓ Judge模型: {judge_model}")
    print(f"✓ Base URL: {judge_base_url}")

    # 4. 运行评测(包含LLM Judge)
    print("\n" + "=" * 80)
    print("运行完整评测 (Rule-based + LLM Judge)")
    print("=" * 80)

    # 过滤掉human_annotation
    sample_copy = sample.copy()
    sample_copy["check_list"] = [
        check for check in sample["check_list"]
        if check["check_type"] != "human_annotation"
    ]

    print(f"✓ 包含 {len(sample_copy['check_list'])} 个检查项:")
    for check in sample_copy["check_list"]:
        print(f"  - [{check['check_type']}] {check['description']}")

    # 创建评测器
    orchestrator = EvaluationOrchestrator(
        judge_model=judge_model,
        judge_base_url=judge_base_url,
        judge_api_key=judge_api_key
    )

    # 执行评测
    result_path = Path(f"results/{sample_id}_full_result.json")
    result_path.parent.mkdir(exist_ok=True)

    try:
        eval_result = orchestrator.evaluate(
            sample=sample_copy,
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
        print(f"  - 文件数: {len(execution_result_a['final_state']['files'])}")
        for check_result in eval_result['check_results']['model_a']:
            print(f"  - [{check_result['check_type']}] {check_result['description']}")
            print(f"    得分: {check_result['score']:.2f}, 通过: {check_result['passed']}")

        print(f"\n📊 Model B ({model_b}):")
        print(f"  - 文件数: {len(execution_result_b['final_state']['files'])}")
        for check_result in eval_result['check_results']['model_b']:
            print(f"  - [{check_result['check_type']}] {check_result['description']}")
            print(f"    得分: {check_result['score']:.2f}, 通过: {check_result['passed']}")

        print("\n✅ 完整评测测试成功!")

    except Exception as e:
        print(f"\n❌ 评测失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print("\n说明:")
    print("1. ✓ 使用了mock数据")
    print("2. ✓ 测试了Rule-based检查")
    print("3. ✓ 测试了LLM Judge检查")
    print("4. ⏭  跳过了Human Annotation")


if __name__ == "__main__":
    main()
