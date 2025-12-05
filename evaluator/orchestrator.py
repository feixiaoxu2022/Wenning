"""
Evaluation Orchestrator

评测流程总控：
1. 读取样本和Agent执行结果
2. 运行Rule-based检查
3. 运行LLM Judge
4. 汇总结果并保存
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from .rule_checker import RuleChecker
from .llm_judge import LLMJudge


class EvaluationOrchestrator:
    """评测编排器"""

    def __init__(
        self,
        judge_model: Optional[str] = None,
        judge_base_url: Optional[str] = None,
        judge_api_key: Optional[str] = None
    ):
        """
        Args:
            judge_model: LLM Judge模型名称
            judge_base_url: LLM Judge API URL
            judge_api_key: LLM Judge API密钥
        """
        self.rule_checker = RuleChecker()

        # LLM Judge（可选，如果check_list中有llm_judge才需要）
        self.llm_judge = None
        if judge_model and judge_base_url and judge_api_key:
            self.llm_judge = LLMJudge(
                model=judge_model,
                base_url=judge_base_url,
                api_key=judge_api_key
            )

    def evaluate(
        self,
        sample: Dict[str, Any],
        execution_result_a: Dict[str, Any],
        execution_result_b: Dict[str, Any],
        output_file: Optional[Path] = None
    ) -> Dict[str, Any]:
        """
        执行评测

        Args:
            sample: 评测样本（包含check_list）
            execution_result_a: Model A的执行结果
            execution_result_b: Model B的执行结果
            output_file: 输出文件路径（可选）

        Returns:
            evaluation_result: 评测结果
        """
        sample_id = sample["data_id"]
        check_list = sample["check_list"]

        print(f"开始评测样本: {sample_id}")

        # 初始化结果
        evaluation_result = {
            "sample_id": sample_id,
            "evaluated_at": datetime.now().isoformat(),
            "executions": {
                "model_a": self._summarize_execution(execution_result_a),
                "model_b": self._summarize_execution(execution_result_b)
            },
            "check_results": {
                "model_a": [],
                "model_b": []
            }
        }

        # 运行所有检查项
        for check_item in check_list:
            check_type = check_item["check_type"]

            if check_type in ["file_count_range", "file_count_equals", "file_format_check", "image_size_check"]:
                # Rule-based检查
                print(f"  运行Rule检查: {check_item.get('description', check_type)}")
                result_a = self.rule_checker.check(check_item, execution_result_a)
                result_b = self.rule_checker.check(check_item, execution_result_b)

                evaluation_result["check_results"]["model_a"].append(result_a)
                evaluation_result["check_results"]["model_b"].append(result_b)

            elif check_type == "llm_judge":
                # LLM Judge
                if not self.llm_judge:
                    print(f"  跳过LLM Judge（未配置）: {check_item.get('description', check_type)}")
                    continue

                print(f"  运行LLM Judge: {check_item.get('description', check_type)}")
                result_a = self.llm_judge.evaluate(check_item, execution_result_a)
                result_b = self.llm_judge.evaluate(check_item, execution_result_b)

                evaluation_result["check_results"]["model_a"].append(result_a)
                evaluation_result["check_results"]["model_b"].append(result_b)

            elif check_type == "human_annotation":
                # Human Annotation（跳过，需要手动标注）
                print(f"  跳过Human Annotation（需手动标注）: {check_item.get('description', check_type)}")
                continue

            else:
                print(f"  未知检查类型: {check_type}")

        # 保存结果
        if output_file:
            output_file.parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(evaluation_result, f, ensure_ascii=False, indent=2)
            print(f"评测结果已保存: {output_file}")

        print(f"评测完成: {sample_id}")
        self._print_summary(evaluation_result)

        return evaluation_result

    def _summarize_execution(self, execution_result: Dict) -> Dict:
        """提取执行摘要"""
        final_state = execution_result.get("final_state", {})
        files = final_state.get("files", [])

        return {
            "model_name": execution_result.get("model_name", "unknown"),
            "status": execution_result.get("status", "unknown"),
            "file_count": len(files),
            "execution_file": None  # 可以记录执行结果文件路径
        }

    def _print_summary(self, evaluation_result: Dict):
        """打印评测摘要"""
        print("\n" + "=" * 60)
        print("评测摘要")
        print("=" * 60)

        model_a = evaluation_result["executions"]["model_a"]["model_name"]
        model_b = evaluation_result["executions"]["model_b"]["model_name"]

        print(f"\nModel A: {model_a}")
        print(f"  文件数: {evaluation_result['executions']['model_a']['file_count']}")

        results_a = evaluation_result["check_results"]["model_a"]
        if results_a:
            avg_score_a = sum(r["score"] for r in results_a) / len(results_a)
            passed_a = sum(1 for r in results_a if r["passed"])
            print(f"  平均得分: {avg_score_a:.2f}")
            print(f"  通过检查: {passed_a}/{len(results_a)}")

        print(f"\nModel B: {model_b}")
        print(f"  文件数: {evaluation_result['executions']['model_b']['file_count']}")

        results_b = evaluation_result["check_results"]["model_b"]
        if results_b:
            avg_score_b = sum(r["score"] for r in results_b) / len(results_b)
            passed_b = sum(1 for r in results_b if r["passed"])
            print(f"  平均得分: {avg_score_b:.2f}")
            print(f"  通过检查: {passed_b}/{len(results_b)}")

        print("=" * 60)
        print("\n注意: 以上是自动评测结果，最终得分需要Human Annotation")
