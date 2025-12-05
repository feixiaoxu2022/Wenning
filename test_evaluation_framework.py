#!/usr/bin/env python3
"""
评测框架单元测试

验证RuleChecker、LLMJudge、Orchestrator的基本功能
"""

import json
from evaluator import RuleChecker, EvaluationOrchestrator


def test_rule_checker():
    """测试RuleChecker的基本功能"""
    print("=" * 60)
    print("测试 RuleChecker")
    print("=" * 60)

    checker = RuleChecker()

    # 构造测试数据
    execution_result = {
        "sample_id": "TEST_001",
        "model_name": "test-model",
        "status": "success",
        "final_state": {
            "files": [
                {"path": "icon1.png", "size": 2048, "type": "png"},
                {"path": "icon2.svg", "size": 1024, "type": "svg"},
                {"path": "icon3.jpg", "size": 3072, "type": "jpg"},
            ]
        }
    }

    # 测试1: file_count_range (通过)
    check_item = {
        "check_type": "file_count_range",
        "description": "文件数量范围检查",
        "params": {"min": 2, "max": 10},
        "weight": 1.0
    }
    result = checker.check(check_item, execution_result)
    print(f"\n✓ file_count_range 测试通过")
    print(f"  得分: {result['score']}, 通过: {result['passed']}")
    print(f"  详情: {result['details']}")
    assert result["passed"] is True
    assert result["score"] == 1.0

    # 测试2: file_count_equals (不通过)
    check_item = {
        "check_type": "file_count_equals",
        "description": "文件数量精确检查",
        "params": {"expected": 5},
        "weight": 1.0
    }
    result = checker.check(check_item, execution_result)
    print(f"\n✓ file_count_equals 测试通过")
    print(f"  得分: {result['score']}, 通过: {result['passed']}")
    print(f"  详情: {result['details']}")
    assert result["passed"] is False
    assert result["score"] == 0.6  # 3/5

    # 测试3: file_format_check
    check_item = {
        "check_type": "file_format_check",
        "description": "文件格式检查",
        "params": {"expected_formats": ["png", "svg"]},
        "weight": 2.0
    }
    result = checker.check(check_item, execution_result)
    print(f"\n✓ file_format_check 测试通过")
    print(f"  得分: {result['score']:.2f}, 通过: {result['passed']}")
    print(f"  详情: {result['details']}")
    assert result["passed"] is False
    assert abs(result["score"] - 0.667) < 0.01  # 2/3

    # 测试4: image_size_check
    execution_with_metadata = {
        "sample_id": "TEST_002",
        "model_name": "test-model",
        "final_state": {
            "files": [
                {
                    "path": "icon1.png",
                    "size": 2048,
                    "type": "png",
                    "metadata": {"dimensions": {"width": 512, "height": 512}}
                },
                {
                    "path": "icon2.png",
                    "size": 3072,
                    "type": "png",
                    "metadata": {"dimensions": {"width": 600, "height": 512}}
                }
            ]
        }
    }
    check_item = {
        "check_type": "image_size_check",
        "description": "图片尺寸检查",
        "params": {"width": 512, "height": 512, "tolerance": 0.1},
        "weight": 1.5
    }
    result = checker.check(check_item, execution_with_metadata)
    print(f"\n✓ image_size_check 测试通过")
    print(f"  得分: {result['score']}, 通过: {result['passed']}")
    print(f"  详情: {result['details']}")
    assert result["score"] == 0.5  # 1/2

    print("\n" + "=" * 60)
    print("✓ RuleChecker 所有测试通过!")
    print("=" * 60)


def test_orchestrator_without_llm():
    """测试Orchestrator（不包含LLM Judge）"""
    print("\n" + "=" * 60)
    print("测试 EvaluationOrchestrator (仅Rule-based)")
    print("=" * 60)

    orchestrator = EvaluationOrchestrator()

    # 构造测试样本
    sample = {
        "data_id": "TEST_SAMPLE_001",
        "query": "测试任务",
        "models": {
            "model_a": "test-model-a",
            "model_b": "test-model-b"
        },
        "check_list": [
            {
                "check_type": "file_count_range",
                "description": "文件数量范围检查",
                "params": {"min": 2, "max": 10},
                "weight": 0,
                "is_required": True
            },
            {
                "check_type": "file_format_check",
                "description": "文件格式检查",
                "params": {"expected_formats": ["png", "svg"]},
                "weight": 2.0
            }
        ]
    }

    # 构造执行结果
    execution_result_a = {
        "sample_id": "TEST_SAMPLE_001",
        "model_name": "test-model-a",
        "status": "success",
        "final_state": {
            "files": [
                {"path": "icon1.png", "size": 2048, "type": "png"},
                {"path": "icon2.svg", "size": 1024, "type": "svg"},
                {"path": "icon3.jpg", "size": 3072, "type": "jpg"},
            ]
        },
        "conversation_history": [
            {"role": "user", "content": "生成图标"},
            {"role": "assistant", "content": "好的，开始生成"}
        ]
    }

    execution_result_b = {
        "sample_id": "TEST_SAMPLE_001",
        "model_name": "test-model-b",
        "status": "success",
        "final_state": {
            "files": [
                {"path": "icon1.png", "size": 2048, "type": "png"},
                {"path": "icon2.png", "size": 2048, "type": "png"},
                {"path": "icon3.svg", "size": 1024, "type": "svg"},
                {"path": "icon4.svg", "size": 1024, "type": "svg"},
            ]
        },
        "conversation_history": [
            {"role": "user", "content": "生成图标"},
            {"role": "assistant", "content": "好的，开始生成"}
        ]
    }

    # 执行评测
    result = orchestrator.evaluate(
        sample=sample,
        execution_result_a=execution_result_a,
        execution_result_b=execution_result_b,
        output_file=None  # 不保存文件
    )

    # 验证结果结构
    assert "sample_id" in result
    assert "evaluated_at" in result
    assert "executions" in result
    assert "check_results" in result

    # 验证Model A结果
    assert result["executions"]["model_a"]["model_name"] == "test-model-a"
    assert result["executions"]["model_a"]["file_count"] == 3
    assert len(result["check_results"]["model_a"]) == 2

    # 验证Model B结果
    assert result["executions"]["model_b"]["model_name"] == "test-model-b"
    assert result["executions"]["model_b"]["file_count"] == 4
    assert len(result["check_results"]["model_b"]) == 2

    # 验证检查结果
    model_a_file_format = result["check_results"]["model_a"][1]
    assert model_a_file_format["check_type"] == "file_format_check"
    assert abs(model_a_file_format["score"] - 0.667) < 0.01

    model_b_file_format = result["check_results"]["model_b"][1]
    assert model_b_file_format["check_type"] == "file_format_check"
    assert model_b_file_format["score"] == 1.0
    assert model_b_file_format["passed"] is True

    print("\n✓ Model B (4/4格式正确) 优于 Model A (2/3格式正确)")
    print("\n" + "=" * 60)
    print("✓ EvaluationOrchestrator 测试通过!")
    print("=" * 60)


def main():
    """运行所有测试"""
    print("\n" + "🧪" * 30)
    print("CreativeFlow 评测框架单元测试")
    print("🧪" * 30 + "\n")

    try:
        test_rule_checker()
        test_orchestrator_without_llm()

        print("\n" + "=" * 60)
        print("🎉 所有测试通过！评测框架工作正常")
        print("=" * 60)
        print("\n说明:")
        print("1. RuleChecker 的4种检查类型均可正常工作")
        print("2. EvaluationOrchestrator 能够正确协调评测流程")
        print("3. 评测结果格式符合schema规范")
        print("\n下一步:")
        print("- 准备实际的Agent执行结果文件")
        print("- 配置LLM Judge参数（如需要）")
        print("- 运行 run_evaluation.py 进行完整评测")

    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        raise
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        raise


if __name__ == "__main__":
    main()
