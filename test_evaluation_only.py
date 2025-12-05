#!/usr/bin/env python3
"""
简化版测试：使用mock数据测试评测框架

跳过Agent执行,直接使用构造的执行结果测试评测流程
"""

import json
import sys
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
    print("CreativeFlow 评测框架测试 (使用Mock数据)")
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

    # 保存mock结果
    executions_dir = Path("executions")
    executions_dir.mkdir(exist_ok=True)

    execution_a_path = executions_dir / f"{model_a}_{sample_id}_mock.json"
    with open(execution_a_path, 'w', encoding='utf-8') as f:
        json.dump(execution_result_a, f, indent=2, ensure_ascii=False)
    print(f"✓ 保存至: {execution_a_path}")

    execution_b_path = executions_dir / f"{model_b}_{sample_id}_mock.json"
    with open(execution_b_path, 'w', encoding='utf-8') as f:
        json.dump(execution_result_b, f, indent=2, ensure_ascii=False)
    print(f"✓ 保存至: {execution_b_path}")

    # 3. 运行评测(仅Rule-based,跳过LLM Judge)
    print("\n" + "=" * 80)
    print("运行评测框架 (仅Rule-based检查)")
    print("=" * 80)

    # 过滤掉LLM Judge检查项
    sample_copy = sample.copy()
    sample_copy["check_list"] = [
        check for check in sample["check_list"]
        if check["check_type"] != "llm_judge" and check["check_type"] != "human_annotation"
    ]

    print(f"✓ 保留 {len(sample_copy['check_list'])} 个Rule检查项:")
    for check in sample_copy["check_list"]:
        print(f"  - {check['description']}")

    # 创建评测器(不配置LLM Judge)
    orchestrator = EvaluationOrchestrator()

    # 执行评测
    result_path = Path(f"results/{sample_id}_mock_result.json")
    result_path.parent.mkdir(exist_ok=True)

    eval_result = orchestrator.evaluate(
        sample=sample_copy,
        execution_result_a=execution_result_a,
        execution_result_b=execution_result_b,
        output_file=result_path
    )

    print(f"\n✓ 评测结果已保存: {result_path}")

    # 4. 输出结果摘要
    print("\n" + "=" * 80)
    print("评测结果摘要")
    print("=" * 80)

    print(f"\n📊 Model A ({model_a}):")
    print(f"  - 文件数: {len(execution_result_a['final_state']['files'])}")
    for check_result in eval_result['check_results']['model_a']:
        print(f"  - {check_result['description']}: {check_result['score']:.2f} (通过: {check_result['passed']})")

    print(f"\n📊 Model B ({model_b}):")
    print(f"  - 文件数: {len(execution_result_b['final_state']['files'])}")
    for check_result in eval_result['check_results']['model_b']:
        print(f"  - {check_result['description']}: {check_result['score']:.2f} (通过: {check_result['passed']})")

    print("\n✅ 评测框架测试完成!")
    print("\n说明:")
    print("1. 使用了mock数据,没有实际执行Agent")
    print("2. 仅测试了Rule-based检查(file_count_range, file_format_check)")
    print("3. 跳过了LLM Judge和Human Annotation")
    print("\n下一步:")
    print("1. 修复Agent执行问题,生成真实文件")
    print("2. 配置LLM Judge API密钥(如需要)")
    print("3. 运行完整评测流程")


if __name__ == "__main__":
    main()
