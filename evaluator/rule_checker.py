"""
Rule-based Checker

基于确定性规则的检查：
- 文件数量范围
- 文件格式
- 图片尺寸
- Excel sheets
等
"""

import json
from pathlib import Path
from typing import Dict, List, Any


class RuleChecker:
    """基于规则的自动检查器"""

    def check(
        self,
        check_item: Dict[str, Any],
        execution_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        执行规则检查

        Args:
            check_item: 检查项定义（来自sample的check_list）
            execution_result: Agent执行结果

        Returns:
            CheckResult: {
                "check_type": str,
                "description": str,
                "score": float (0-1),
                "passed": bool,
                "details": str,
                "weight": float
            }
        """
        check_type = check_item["check_type"]
        params = check_item["params"]

        # 根据check_type调用对应的检查方法
        if check_type == "file_count_range":
            return self._check_file_count_range(execution_result, params, check_item)
        elif check_type == "file_count_equals":
            return self._check_file_count_equals(execution_result, params, check_item)
        elif check_type == "file_format_check":
            return self._check_file_format(execution_result, params, check_item)
        elif check_type == "image_size_check":
            return self._check_image_size(execution_result, params, check_item)
        else:
            raise ValueError(f"Unknown rule check type: {check_type}")

    def _check_file_count_range(
        self,
        execution_result: Dict,
        params: Dict,
        check_item: Dict
    ) -> Dict:
        """检查文件数量是否在范围内"""
        final_state = execution_result.get("final_state", {})
        files = final_state.get("files", [])
        actual_count = len(files)

        min_count = params["min"]
        max_count = params["max"]

        passed = min_count <= actual_count <= max_count

        # 计算得分
        if passed:
            score = 1.0
        elif actual_count < min_count:
            score = actual_count / min_count
        else:  # actual_count > max_count
            score = max(0, 1 - (actual_count - max_count) / max_count)

        return {
            "check_type": check_item["check_type"],
            "description": check_item.get("description", "文件数量范围检查"),
            "score": score,
            "passed": passed,
            "details": f"生成{actual_count}个文件，要求{min_count}-{max_count}个",
            "weight": check_item.get("weight", 1.0)
        }

    def _check_file_count_equals(
        self,
        execution_result: Dict,
        params: Dict,
        check_item: Dict
    ) -> Dict:
        """检查文件数量是否等于期望值"""
        final_state = execution_result.get("final_state", {})
        files = final_state.get("files", [])
        actual_count = len(files)

        expected = params["expected"]
        passed = actual_count == expected
        score = 1.0 if passed else actual_count / expected

        return {
            "check_type": check_item["check_type"],
            "description": check_item.get("description", "文件数量检查"),
            "score": score,
            "passed": passed,
            "details": f"生成{actual_count}个文件，要求{expected}个",
            "weight": check_item.get("weight", 1.0)
        }

    def _check_file_format(
        self,
        execution_result: Dict,
        params: Dict,
        check_item: Dict
    ) -> Dict:
        """检查文件格式"""
        final_state = execution_result.get("final_state", {})
        files = final_state.get("files", [])

        expected_formats = params["expected_formats"]

        matched = 0
        for file_info in files:
            file_type = file_info.get("type", "").lower()
            if file_type in expected_formats:
                matched += 1

        total = len(files)
        score = matched / total if total > 0 else 0
        passed = score == 1.0

        return {
            "check_type": check_item["check_type"],
            "description": check_item.get("description", "文件格式检查"),
            "score": score,
            "passed": passed,
            "details": f"{matched}/{total}个文件格式正确（期望: {', '.join(expected_formats)}）",
            "weight": check_item.get("weight", 1.0)
        }

    def _check_image_size(
        self,
        execution_result: Dict,
        params: Dict,
        check_item: Dict
    ) -> Dict:
        """检查图片尺寸"""
        final_state = execution_result.get("final_state", {})
        files = final_state.get("files", [])

        expected_width = params["width"]
        expected_height = params["height"]
        tolerance = params.get("tolerance", 0.1)

        # 只检查图片文件
        image_files = [f for f in files if f.get("type", "").lower() in ["png", "jpg", "jpeg", "svg"]]

        if not image_files:
            return {
                "check_type": check_item["check_type"],
                "description": check_item.get("description", "图片尺寸检查"),
                "score": 0,
                "passed": False,
                "details": "没有图片文件",
                "weight": check_item.get("weight", 1.0)
            }

        matched = 0
        details_list = []

        for img_file in image_files:
            metadata = img_file.get("metadata", {})
            dimensions = metadata.get("dimensions", {})

            if not dimensions:
                details_list.append(f"{img_file['path']}: 无尺寸信息")
                continue

            width = dimensions.get("width", 0)
            height = dimensions.get("height", 0)

            w_diff = abs(width - expected_width) / expected_width if expected_width > 0 else 1
            h_diff = abs(height - expected_height) / expected_height if expected_height > 0 else 1

            if w_diff <= tolerance and h_diff <= tolerance:
                matched += 1
            else:
                details_list.append(f"{img_file['path']}: {width}x{height} (期望{expected_width}x{expected_height})")

        score = matched / len(image_files)
        passed = score == 1.0

        details = f"{matched}/{len(image_files)}张图片尺寸符合"
        if details_list:
            details += f"\n不符合: {'; '.join(details_list[:3])}"  # 最多显示3个

        return {
            "check_type": check_item["check_type"],
            "description": check_item.get("description", "图片尺寸检查"),
            "score": score,
            "passed": passed,
            "details": details,
            "weight": check_item.get("weight", 1.0)
        }
