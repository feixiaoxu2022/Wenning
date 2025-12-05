"""批量测试脚本 - 综合任务测试

测试10个不同难度和类型的综合任务,验证后端能力:
- 多源数据收集
- 数据处理和分析
- 多格式文件生成(Excel/PNG/HTML/MP4)
- 复杂可视化
- 代码生成和执行
"""

import asyncio
import httpx
import json
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any


# 测试任务定义
TEST_TASKS = [
    {
        "id": "task_01",
        "name": "AI行业竞品分析仪表盘",
        "difficulty": 4,
        "prompt": """搜索2025年AI Agent领域的主要竞品(Claude、GPT、Gemini、文心一言),收集以下信息并生成分析报告:
1. 定价对比(免费额度、付费套餐价格)
2. 核心功能特性对比
3. 主要发布时间线

要求:
- 生成Excel文件 ai_competitors_analysis.xlsx,包含多个sheet:定价对比、功能矩阵、时间线
- 生成交互式HTML对比页面 ai_dashboard.html,包含表格和简单图表
- 数据要真实准确,来自2024-2025年的最新信息""",
        "expected_files": ["ai_competitors_analysis.xlsx", "ai_dashboard.html"],
        "timeout": 180
    },

    {
        "id": "task_02",
        "name": "技术文章配图批量生成器",
        "difficulty": 4,
        "prompt": """为一篇关于"Python异步编程"的技术博客生成5张配图:

1. async_concept.png - 同步vs异步概念对比图(用简单图形对比两种模式)
2. async_flow.png - asyncio事件循环流程图(展示事件循环的工作原理)
3. async_performance.png - 性能对比柱状图(模拟数据:同步耗时10s,异步耗时2s)
4. async_architecture.png - 协程架构示意图(展示协程、任务、事件循环的关系)
5. async_summary.png - 知识点总结卡片(列出3-5个核心要点)

要求:
- 所有图片尺寸1200x800
- 使用专业的配色方案(蓝色系为主)
- 文字清晰易读
- 风格统一""",
        "expected_files": ["async_concept.png", "async_flow.png", "async_performance.png",
                          "async_architecture.png", "async_summary.png"],
        "timeout": 150
    },

    {
        "id": "task_03",
        "name": "社交媒体内容日历生成器",
        "difficulty": 5,
        "prompt": """搜索2025年11月科技领域的热点事件,为一个技术自媒体账号生成未来一周(7天)的内容发布计划。

每天的内容包括:
- 发布时间(建议早8点/中午12点/晚8点)
- 话题标题
- 300字左右的文案建议
- 配图建议
- 预期互动目标

要求:
1. 生成 content_calendar.xlsx,包含详细的内容日历表
2. 生成 content_preview.html,可视化展示一周的内容安排
3. 话题要结合最新科技热点,有时效性""",
        "expected_files": ["content_calendar.xlsx", "content_preview.html"],
        "timeout": 200
    },

    {
        "id": "task_04",
        "name": "开源项目健康度评估报告",
        "difficulty": 5,
        "prompt": """分析GitHub上5个流行的Python Web框架(FastAPI、Flask、Django、Tornado、Sanic),从多个维度评估项目健康度:

评估维度:
1. Star数量
2. 最近3个月commit数
3. Issue数量和响应速度
4. Pull Request活跃度
5. 贡献者数量
6. 最后更新时间

要求:
1. 生成 github_health_report.xlsx,包含详细数据和评分
2. 生成 health_radar.png,用雷达图对比5个框架
3. 生成 health_ranking.html,展示排名和详细分析

评分模型:每个维度10分,总分100分""",
        "expected_files": ["github_health_report.xlsx", "health_radar.png", "health_ranking.html"],
        "timeout": 180
    },

    {
        "id": "task_05",
        "name": "数据可视化动画生成器",
        "difficulty": 5,
        "prompt": """搜索或模拟2020-2025年全球AI投资额数据(单位:十亿美元),生成一个展示投资趋势变化的动态柱状图动画。

数据建议(如果搜索不到可以使用合理的模拟数据):
2020: 50B, 2021: 70B, 2022: 90B, 2023: 120B, 2024: 180B, 2025: 250B(预测)

要求:
1. 生成 ai_investment_trend.mp4 视频(10-15秒)
2. 使用matplotlib.animation制作
3. 柱状图逐年增长的动画效果
4. 包含标题、坐标轴标签、数值标注
5. 同时生成 investment_data.xlsx 保存原始数据

注意:本机已安装FFmpeg,可以直接导出mp4格式""",
        "expected_files": ["ai_investment_trend.mp4", "investment_data.xlsx"],
        "timeout": 200
    },

    {
        "id": "task_06",
        "name": "知识图谱可视化生成器",
        "difficulty": 5,
        "prompt": """围绕"深度学习"主题,提取10-15个核心概念及其关系,生成知识图谱可视化。

核心概念示例:
- 深度学习、神经网络、卷积神经网络、循环神经网络、Transformer
- 反向传播、梯度下降、优化器、学习率、损失函数
- 过拟合、正则化、Dropout、批归一化

关系类型:
- 属于(is_a): CNN属于神经网络
- 使用(uses): 深度学习使用反向传播
- 解决(solves): Dropout解决过拟合

要求:
1. 生成 knowledge_graph.html,使用简单的图可视化(可以用D3.js或者自己画SVG)
2. 生成 concepts_list.xlsx,包含概念清单和关系表
3. 图谱要清晰美观,节点和边标注完整""",
        "expected_files": ["knowledge_graph.html", "concepts_list.xlsx"],
        "timeout": 180
    },

    {
        "id": "task_07",
        "name": "API性能监控仪表盘",
        "difficulty": 4,
        "prompt": """模拟生成某API最近24小时的性能数据,绘制性能监控图表。

模拟数据要求:
- 时间粒度:每5分钟一个数据点(共288个点)
- 响应时间:50-500ms,正常时段100ms左右,高峰期(9-11点,14-16点,19-21点)200-400ms
- QPS:100-1000,高峰期800-1000,低谷期(凌晨)100-200
- 错误率:0-5%,正常时段<1%,偶尔有小高峰2-3%

要求:
1. 生成 api_monitor.html,包含:
   - 响应时间折线图
   - QPS折线图
   - 错误率折线图
   - 关键指标卡片(P50/P95/P99响应时间,平均QPS,错误率)
2. 生成 performance_data.xlsx,保存时序数据

仪表盘要有专业的监控系统风格""",
        "expected_files": ["api_monitor.html", "performance_data.xlsx"],
        "timeout": 150
    },

    {
        "id": "task_08",
        "name": "多语言代码片段库生成器",
        "difficulty": 4,
        "prompt": """为"快速排序算法"生成Python、JavaScript、Go三种语言的实现,创建一个代码库展示页面。

每种语言的实现要求:
- 完整的快速排序函数实现
- 详细的代码注释
- 时间复杂度和空间复杂度分析
- 简单的测试用例(测试[5,2,8,1,9]的排序)

要求:
1. 生成 quicksort_library.html,展示三种语言的代码(带语法高亮)
2. 生成 quicksort_benchmark.png,对比三种语言的性能(可以模拟数据:Python 100ms, JS 80ms, Go 30ms)
3. HTML页面要有代码切换功能,美观专业""",
        "expected_files": ["quicksort_library.html", "quicksort_benchmark.png"],
        "timeout": 150
    },

    {
        "id": "task_09",
        "name": "音频数据可视化分析器",
        "difficulty": 4,
        "prompt": """模拟生成一段音频信号数据(440Hz正弦波,持续1秒,采样率44100Hz),进行频谱分析并可视化。

分析要求:
1. 生成时域波形图 audio_waveform.png (展示前0.1秒的波形)
2. 生成频域频谱图 audio_spectrum.png (FFT频谱分析)
3. 生成 audio_analysis.xlsx,包含:
   - 采样参数
   - 频率成分分析
   - 能量分布统计
4. 生成 audio_report.html,综合展示以上分析结果

要求图表专业,标注清晰,包含坐标轴和图例""",
        "expected_files": ["audio_waveform.png", "audio_spectrum.png",
                          "audio_analysis.xlsx", "audio_report.html"],
        "timeout": 150
    },

    {
        "id": "task_10",
        "name": "产品路线图时间轴生成器",
        "difficulty": 4,
        "prompt": """搜索OpenAI公司2023-2025年的主要产品发布和里程碑事件,生成可视化的产品路线图。

参考事件(可搜索补充更多):
- 2023.03: GPT-4发布
- 2023.09: DALL-E 3发布
- 2023.11: GPT-4 Turbo发布
- 2024.05: GPT-4o发布
- 2024.12: o1模型发布
- 2025: GPT-5预测

要求:
1. 生成 openai_timeline.png,静态时间轴图(横向布局,事件清晰标注)
2. 生成 openai_roadmap.html,交互式时间轴(可点击查看详情)
3. 生成 product_milestones.xlsx,里程碑事件清单

时间轴设计要专业美观,重大事件要突出显示""",
        "expected_files": ["openai_timeline.png", "openai_roadmap.html",
                          "product_milestones.xlsx"],
        "timeout": 180
    }
]


class BatchTestRunner:
    """批量测试运行器"""

    def __init__(self, base_url: str = "http://172.26.117.227:8000", model: str = "gpt-5"):
        self.base_url = base_url
        self.model = model
        self.results_dir = Path(__file__).parent / "batch_test_results"
        self.results_dir.mkdir(exist_ok=True)

        # 当前测试会话ID
        self.conversation_id = None

    async def create_conversation(self) -> str:
        """创建新对话"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.base_url}/conversations",
                params={"model": self.model}
            )
            resp.raise_for_status()
            conv_id = resp.json()["conversation_id"]
            print(f"✅ 创建对话: {conv_id}")
            return conv_id

    async def send_message(self, message: str, timeout: int = 180) -> Dict[str, Any]:
        """发送消息并接收流式响应"""
        async with httpx.AsyncClient(timeout=timeout) as client:
            result = {
                "status": "unknown",
                "final_answer": "",
                "generated_files": [],
                "error": None,
                "thinking_process": [],
                "duration": 0
            }

            start_time = time.time()

            try:
                async with client.stream(
                    "GET",
                    f"{self.base_url}/chat",
                    params={
                        "message": message,
                        "model": self.model,
                        "conversation_id": self.conversation_id
                    }
                ) as resp:
                    resp.raise_for_status()

                    async for line in resp.aiter_lines():
                        if not line.strip() or not line.startswith("data: "):
                            continue

                        data = line[6:]  # 去掉 "data: "
                        if data == "[DONE]":
                            break

                        try:
                            update = json.loads(data)

                            # 记录思考过程
                            if update.get("type") == "thinking":
                                result["thinking_process"].append(update.get("full_content", ""))

                            # 记录生成的文件
                            elif update.get("type") == "files_generated":
                                files = update.get("files", [])
                                result["generated_files"].extend(files)

                            # 最终答案
                            elif update.get("type") == "final":
                                final_result = update.get("result", {})
                                result["status"] = final_result.get("status", "unknown")
                                result["final_answer"] = final_result.get("result", "")
                                result["error"] = final_result.get("error")

                        except json.JSONDecodeError:
                            continue

                result["duration"] = time.time() - start_time

            except Exception as e:
                result["status"] = "failed"
                result["error"] = str(e)
                result["duration"] = time.time() - start_time

            return result

    async def run_single_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """运行单个测试任务"""
        print(f"\n{'='*80}")
        print(f"🧪 开始测试: [{task['id']}] {task['name']}")
        print(f"   难度: {'⭐' * task['difficulty']}")
        print(f"   预期文件: {', '.join(task['expected_files'])}")
        print(f"{'='*80}\n")

        # 发送任务
        result = await self.send_message(task['prompt'], timeout=task['timeout'])

        # 分析结果
        test_result = {
            "task_id": task["id"],
            "task_name": task["name"],
            "difficulty": task["difficulty"],
            "status": result["status"],
            "duration": result["duration"],
            "expected_files": task["expected_files"],
            "generated_files": result["generated_files"],
            "final_answer": result["final_answer"],
            "error": result["error"],
            "thinking_steps": len(result["thinking_process"]),
            "timestamp": datetime.now().isoformat()
        }

        # 检查文件生成情况
        expected_set = set(task["expected_files"])
        generated_set = set(result["generated_files"])

        test_result["files_matched"] = list(expected_set & generated_set)
        test_result["files_missing"] = list(expected_set - generated_set)
        test_result["files_extra"] = list(generated_set - expected_set)
        test_result["file_match_rate"] = len(test_result["files_matched"]) / len(expected_set) if expected_set else 0

        # 打印结果
        print(f"\n📊 测试结果:")
        print(f"   状态: {result['status']}")
        print(f"   耗时: {result['duration']:.1f}s")
        print(f"   思考步数: {test_result['thinking_steps']}")
        print(f"   文件匹配率: {test_result['file_match_rate']*100:.1f}%")
        print(f"   ✅ 已生成: {', '.join(test_result['files_matched'])}")
        if test_result['files_missing']:
            print(f"   ❌ 缺失: {', '.join(test_result['files_missing'])}")
        if test_result['files_extra']:
            print(f"   ➕ 额外: {', '.join(test_result['files_extra'])}")

        if result['error']:
            print(f"   ⚠️  错误: {result['error']}")

        return test_result

    async def run_all_tasks(self, task_ids: List[str] = None) -> List[Dict[str, Any]]:
        """运行所有测试任务"""
        # 创建对话
        self.conversation_id = await self.create_conversation()

        # 筛选任务
        tasks_to_run = TEST_TASKS
        if task_ids:
            tasks_to_run = [t for t in TEST_TASKS if t["id"] in task_ids]

        print(f"\n🚀 开始批量测试,共{len(tasks_to_run)}个任务\n")
        print(f"   对话ID: {self.conversation_id}")
        print(f"   模型: {self.model}")
        print(f"   服务器: {self.base_url}\n")

        all_results = []

        for i, task in enumerate(tasks_to_run, 1):
            print(f"\n进度: [{i}/{len(tasks_to_run)}]")

            try:
                result = await self.run_single_task(task)
                all_results.append(result)

                # 短暂延迟,避免压力过大
                await asyncio.sleep(2)

            except Exception as e:
                print(f"❌ 任务执行异常: {str(e)}")
                all_results.append({
                    "task_id": task["id"],
                    "task_name": task["name"],
                    "status": "error",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                })

        return all_results

    def generate_report(self, results: List[Dict[str, Any]]):
        """生成测试报告"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # JSON详细报告
        json_report_path = self.results_dir / f"test_results_{timestamp}.json"
        with open(json_report_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        # 统计信息
        total = len(results)
        success = len([r for r in results if r.get("status") == "success"])
        failed = total - success
        avg_duration = sum(r.get("duration", 0) for r in results) / total if total > 0 else 0
        avg_match_rate = sum(r.get("file_match_rate", 0) for r in results) / total if total > 0 else 0

        # Markdown报告
        md_report_path = self.results_dir / f"test_report_{timestamp}.md"
        with open(md_report_path, "w", encoding="utf-8") as f:
            f.write(f"# CreativeFlow 批量测试报告\n\n")
            f.write(f"**测试时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"**对话ID**: {self.conversation_id}\n\n")
            f.write(f"**模型**: {self.model}\n\n")
            f.write(f"## 📊 整体统计\n\n")
            f.write(f"- 总任务数: {total}\n")
            f.write(f"- ✅ 成功: {success} ({success/total*100:.1f}%)\n")
            f.write(f"- ❌ 失败: {failed} ({failed/total*100:.1f}%)\n")
            f.write(f"- ⏱️  平均耗时: {avg_duration:.1f}s\n")
            f.write(f"- 📁 平均文件匹配率: {avg_match_rate*100:.1f}%\n\n")

            f.write(f"## 📝 详细结果\n\n")
            f.write(f"| 任务ID | 任务名称 | 难度 | 状态 | 耗时(s) | 文件匹配率 |\n")
            f.write(f"|--------|---------|------|------|---------|------------|\n")

            for r in results:
                status_emoji = "✅" if r.get("status") == "success" else "❌"
                difficulty = "⭐" * r.get("difficulty", 0)
                duration = r.get("duration", 0)
                match_rate = r.get("file_match_rate", 0) * 100

                f.write(f"| {r.get('task_id', 'N/A')} | {r.get('task_name', 'N/A')} | {difficulty} | {status_emoji} | {duration:.1f} | {match_rate:.1f}% |\n")

            f.write(f"\n## 🔍 失败任务详情\n\n")
            failed_tasks = [r for r in results if r.get("status") != "success"]
            if failed_tasks:
                for r in failed_tasks:
                    f.write(f"### {r.get('task_name', 'Unknown')}\n\n")
                    f.write(f"- **错误**: {r.get('error', 'Unknown error')}\n")
                    if r.get('files_missing'):
                        f.write(f"- **缺失文件**: {', '.join(r['files_missing'])}\n")
                    f.write(f"\n")
            else:
                f.write(f"🎉 所有任务都成功了!\n\n")

        print(f"\n" + "="*80)
        print(f"📄 测试报告已生成:")
        print(f"   JSON: {json_report_path}")
        print(f"   Markdown: {md_report_path}")
        print(f"="*80 + "\n")

        # 打印总结
        print(f"📊 测试总结:")
        print(f"   总任务: {total}")
        print(f"   成功: {success} ({success/total*100:.1f}%)")
        print(f"   失败: {failed} ({failed/total*100:.1f}%)")
        print(f"   平均耗时: {avg_duration:.1f}s")
        print(f"   平均文件匹配率: {avg_match_rate*100:.1f}%")


async def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="CreativeFlow 批量测试工具")
    parser.add_argument("--url", default="http://172.26.117.227:8000", help="服务器地址")
    parser.add_argument("--model", default="gpt-5", help="模型名称")
    parser.add_argument("--tasks", nargs="*", help="指定要运行的任务ID,不指定则运行全部")

    args = parser.parse_args()

    runner = BatchTestRunner(base_url=args.url, model=args.model)

    try:
        results = await runner.run_all_tasks(task_ids=args.tasks)
        runner.generate_report(results)
    except KeyboardInterrupt:
        print("\n⚠️  测试被用户中断")
    except Exception as e:
        print(f"\n❌ 测试执行失败: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
