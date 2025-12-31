#!/usr/bin/env python3
"""
用户任务数据集生成脚本 - 完整版

根据用户要求完成以下工作：
1. 统计Agent执行轮次
2. 审查低轮次任务价值
3. 过滤低价值任务
4. 提取附件信息
5. 生成完整的Excel数据集
"""

import json
import pandas as pd
from pathlib import Path
from collections import defaultdict
from datetime import datetime
import re

# ===== 配置 =====
DATA_DIR = Path("data/conversations")
OUTPUT_DIR = Path("user_task_analysis")
EXCEL_FILE = OUTPUT_DIR / "data" / "用户任务数据集.xlsx"
ATTACHMENTS_MANIFEST = OUTPUT_DIR / "attachments" / "attachments_manifest.json"

# ===== 工具函数 =====

def load_all_conversations():
    """加载所有对话文件"""
    conversations = []
    for json_file in DATA_DIR.rglob("*.json"):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                conversations.append(data)
        except Exception as e:
            print(f"警告: 无法加载 {json_file}: {e}")
    return conversations

def extract_first_user_query(conv):
    """提取对话的第一条用户消息"""
    messages = conv.get("messages", [])
    for msg in messages:
        if msg.get("role") == "user":
            return msg.get("content", "").strip()
    return ""

def count_agent_turns(conv):
    """统计Agent执行轮次（assistant消息数）"""
    messages = conv.get("messages", [])
    return sum(1 for msg in messages if msg.get("role") == "assistant")

def extract_attachment_info(query):
    """从query中提取附件信息"""
    if "本次输入包含附件" in query:
        # 尝试提取附件名称
        match = re.search(r"本次输入包含附件[：:](.*?)(?:\n|$)", query)
        if match:
            return match.group(1).strip()
    return None

def is_greeting(query):
    """判断是否为问候语"""
    if len(query) < 10:
        greetings = ["你好", "hello", "hi", "嗨"]
        return any(g in query.lower() for g in greetings)
    return False

def is_low_value_task(query, avg_turns, complexity):
    """判断是否为低价值任务"""
    content = query.strip()
    content_lower = content.lower()

    # 规则1: 测试性询问
    test_keywords = ['再试', '测试', 'test', '你能看到', '你是谁', '介绍一下自己']
    if any(kw in content_lower for kw in test_keywords):
        return True

    # 规则2: 配置咨询
    if any(kw in content_lower for kw in ['配置', '窗口是多少', 'codex配置']):
        return True

    # 规则3: 简单yes/no问题
    if len(content) < 30 and ('吗' in content or '?' in content):
        return True

    # 规则4: 只有附件引用，无实际要求
    if content.startswith('本次输入包含附件') and len(content) < 80:
        return True

    # 规则5: 执行轮次极低且复杂度低且内容简单
    if avg_turns < 2 and complexity <= 2 and len(content) < 100:
        return True

    return False

def analyze_task_complexity(query):
    """分析任务复杂度"""
    content_lower = query.lower()

    # 简单的复杂度评估
    complexity = 2  # 默认中等

    if any(kw in content_lower for kw in ["视频", "分析", "调研", "深度"]):
        complexity = max(complexity, 3)

    if len(query) > 300:
        complexity = max(complexity, 3)

    # 所需能力
    capabilities = []
    if any(kw in content_lower for kw in ["检索", "搜索", "调研", "查找"]):
        capabilities.append("信息检索")
    if any(kw in content_lower for kw in ["分析", "洞察", "理解", "解读"]):
        capabilities.append("深度分析")
    if any(kw in content_lower for kw in ["视频", "图片", "音频", "图像"]):
        capabilities.append("多模态处理")
    if any(kw in content_lower for kw in ["制作", "生成", "创作"]):
        capabilities.append("内容创作")

    return {
        "complexity": complexity,
        "capabilities": capabilities
    }

def simple_dedup(conversations):
    """简单的任务去重（基于query相似度）"""
    clusters = defaultdict(list)

    for conv in conversations:
        query = extract_first_user_query(conv)
        if not query or is_greeting(query):
            continue

        # 使用query的前100字符作为聚类键
        key = query[:100]
        clusters[key].append(conv)

    return clusters

# ===== 主流程 =====

def main():
    print("=" * 80)
    print("用户任务数据集生成")
    print("=" * 80)

    # 创建输出目录
    OUTPUT_DIR.mkdir(exist_ok=True)
    (OUTPUT_DIR / "scripts").mkdir(exist_ok=True)
    (OUTPUT_DIR / "data").mkdir(exist_ok=True)
    (OUTPUT_DIR / "reports").mkdir(exist_ok=True)
    (OUTPUT_DIR / "attachments").mkdir(exist_ok=True)

    # 1. 加载所有对话
    print("\n步骤1: 加载对话数据...")
    conversations = load_all_conversations()
    print(f"  加载了 {len(conversations)} 个对话")

    # 2. 简单去重和聚类
    print("\n步骤2: 任务去重...")
    clusters = simple_dedup(conversations)
    print(f"  识别出 {len(clusters)} 个unique任务")

    # 3. 分析每个任务
    print("\n步骤3: 分析任务并统计执行轮次...")
    task_data = []
    attachments_data = []

    for idx, (key, convs) in enumerate(clusters.items(), 1):
        # 选择最长的query作为代表
        representative_conv = max(convs, key=lambda c: len(extract_first_user_query(c)))
        query = extract_first_user_query(representative_conv)

        # 统计执行轮次
        turns_list = [count_agent_turns(c) for c in convs if count_agent_turns(c) > 0]
        if not turns_list:
            continue

        avg_turns = round(sum(turns_list) / len(turns_list), 1)
        max_turns = max(turns_list)
        min_turns = min(turns_list)

        # 分析复杂度
        analysis = analyze_task_complexity(query)
        complexity = analysis["complexity"]

        # 过滤低价值任务
        if is_low_value_task(query, avg_turns, complexity):
            print(f"  ✗ 跳过低价值任务: {query[:50]}...")
            continue

        # 提取附件信息
        attachment = extract_attachment_info(query)
        if attachment:
            attachments_data.append({
                "task_id": representative_conv.get("id", "")[:8],
                "attachment_name": attachment,
                "query": query,
                "conversation_ids": [c.get("id", "") for c in convs]
            })

        # 构建任务记录
        task_record = {
            "任务ID": representative_conv.get("id", "")[:8],
            "重复次数": len(convs),
            "复杂度评分": complexity,
            "平均执行轮次": avg_turns,
            "最大执行轮次": max_turns,
            "最小执行轮次": min_turns,
            "所需核心能力": " | ".join(analysis["capabilities"]) if analysis["capabilities"] else "基础能力",
            "原始用户Query": query,
            "Query长度": len(query),
            "附件名称": attachment if attachment else "无",
            "用户": representative_conv.get("user", "unknown"),
            "使用模型": representative_conv.get("model", "unknown"),
            "创建时间": representative_conv.get("created_at", ""),
            "对话ID数量": len(convs),
            "所有对话ID": " | ".join([c.get("id", "") for c in convs])
        }

        task_data.append(task_record)
        print(f"  ✓ [{idx}] 复杂度{complexity}星, 平均{avg_turns}轮: {query[:50]}...")

    # 4. 生成Excel
    print(f"\n步骤4: 生成Excel数据集...")
    df = pd.DataFrame(task_data)
    df = df.sort_values(by=["复杂度评分", "平均执行轮次"], ascending=[False, False])

    with pd.ExcelWriter(EXCEL_FILE, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name="所有任务", index=False)

        # 按复杂度分类
        for complexity in [5, 4, 3]:
            complexity_df = df[df["复杂度评分"] == complexity]
            if not complexity_df.empty:
                complexity_df.to_excel(writer, sheet_name=f"复杂度-{complexity}星", index=False)

        # 统计sheet
        stats_data = {
            "指标": [
                "Unique任务数",
                "平均复杂度评分",
                "平均执行轮次",
                "最大执行轮次",
                "平均Query长度",
                "需要附件的任务数"
            ],
            "数值": [
                len(df),
                round(df["复杂度评分"].mean(), 2),
                round(df["平均执行轮次"].mean(), 1),
                int(df["最大执行轮次"].max()),
                round(df["Query长度"].mean(), 0),
                len([t for t in task_data if t["附件名称"] != "无"])
            ]
        }
        stats_df = pd.DataFrame(stats_data)
        stats_df.to_excel(writer, sheet_name="统计摘要", index=False)

    print(f"  ✓ Excel已生成: {EXCEL_FILE}")
    print(f"    - Unique任务数: {len(df)}")
    print(f"    - 平均复杂度: {df['复杂度评分'].mean():.2f}星")
    print(f"    - 平均执行轮次: {df['平均执行轮次'].mean():.1f}轮")

    # 5. 生成附件清单
    if attachments_data:
        print(f"\n步骤5: 生成附件清单...")
        attachments_manifest = {
            "total_tasks": len(attachments_data),
            "attachments": attachments_data,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        with open(ATTACHMENTS_MANIFEST, 'w', encoding='utf-8') as f:
            json.dump(attachments_manifest, f, ensure_ascii=False, indent=2)

        print(f"  ✓ 附件清单已生成: {ATTACHMENTS_MANIFEST}")
        print(f"    - 需要附件的任务数: {len(attachments_data)}")

    print("\n" + "=" * 80)
    print("✓ 生成完成！")
    print("=" * 80)
    print(f"\n输出位置: {OUTPUT_DIR.absolute()}/")
    print(f"  - data/用户任务数据集.xlsx")
    if attachments_data:
        print(f"  - attachments/attachments_manifest.json")

if __name__ == "__main__":
    main()
