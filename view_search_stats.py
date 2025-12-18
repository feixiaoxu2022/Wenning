#!/usr/bin/env python3
"""查看搜索API使用统计

分析 data/search_usage.jsonl 文件，生成使用报告。
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict, Counter

STATS_FILE = Path("data/search_usage.jsonl")


def load_usage_data():
    """加载使用数据"""
    if not STATS_FILE.exists():
        print(f"❌ 统计文件不存在: {STATS_FILE}")
        print("💡 提示：需要先启用带统计功能的web_search工具")
        return []

    records = []
    with open(STATS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            try:
                records.append(json.loads(line))
            except:
                continue

    return records


def analyze_usage(records, days=30):
    """分析使用数据

    Args:
        records: 使用记录列表
        days: 统计最近N天

    Returns:
        分析结果字典
    """
    if not records:
        return None

    # 时间过滤
    cutoff_date = datetime.now() - timedelta(days=days)
    filtered = []

    for r in records:
        try:
            record_time = datetime.fromisoformat(r["timestamp"])
            if record_time >= cutoff_date:
                filtered.append(r)
        except:
            continue

    if not filtered:
        return None

    # 统计
    total = len(filtered)
    api_counter = Counter(r["api"] for r in filtered)
    success_count = sum(1 for r in filtered if r.get("success", False))

    # 按日期统计
    daily_usage = defaultdict(lambda: {"tavily": 0, "serper": 0, "total": 0})
    for r in filtered:
        try:
            date = datetime.fromisoformat(r["timestamp"]).date()
            daily_usage[date]["total"] += 1
            daily_usage[date][r["api"]] += 1
        except:
            continue

    # 最近使用
    recent_searches = sorted(filtered, key=lambda x: x["timestamp"], reverse=True)[:10]

    return {
        "period_days": days,
        "total_searches": total,
        "tavily_count": api_counter.get("tavily", 0),
        "serper_count": api_counter.get("serper", 0),
        "success_count": success_count,
        "success_rate": round(success_count / total * 100, 2) if total > 0 else 0.0,
        "daily_usage": dict(daily_usage),
        "recent_searches": recent_searches
    }


def print_report(stats, days):
    """打印统计报告

    Args:
        stats: 分析结果
        days: 统计天数
    """
    if not stats:
        print(f"\n❌ 最近{days}天没有使用记录")
        return

    print("\n" + "="*70)
    print(f"📊 搜索API使用统计（最近{days}天）")
    print("="*70)

    print(f"\n📈 总览:")
    print(f"   总搜索次数: {stats['total_searches']}")
    print(f"   成功次数: {stats['success_count']}")
    print(f"   成功率: {stats['success_rate']}%")

    print(f"\n🔧 API使用分布:")
    tavily_pct = round(stats['tavily_count'] / stats['total_searches'] * 100, 1) if stats['total_searches'] > 0 else 0
    serper_pct = round(stats['serper_count'] / stats['total_searches'] * 100, 1) if stats['total_searches'] > 0 else 0

    print(f"   Tavily: {stats['tavily_count']}次 ({tavily_pct}%)")
    print(f"   Serper: {stats['serper_count']}次 ({serper_pct}%)")

    # 每日使用趋势
    if stats['daily_usage']:
        print(f"\n📅 每日使用趋势（最近7天）:")
        sorted_dates = sorted(stats['daily_usage'].keys(), reverse=True)[:7]

        for date in sorted_dates:
            usage = stats['daily_usage'][date]
            bar_length = min(usage["total"], 50)  # 最长50个字符
            bar = "█" * bar_length
            print(f"   {date}: {bar} {usage['total']}次 (T:{usage['tavily']} S:{usage['serper']})")

    # 最近搜索
    if stats['recent_searches']:
        print(f"\n🔍 最近10次搜索:")
        for i, search in enumerate(stats['recent_searches'][:10], 1):
            timestamp = datetime.fromisoformat(search["timestamp"]).strftime("%m-%d %H:%M")
            api = search["api"].upper()[0]  # T or S
            query = search["query"][:40]
            status = "✅" if search.get("success", False) else "❌"
            print(f"   {i:2d}. [{timestamp}] [{api}] {status} {query}")

    # 配额预警
    print(f"\n⚠️  配额预警:")

    # Tavily配额（假设Free tier: 1000/月）
    if stats['tavily_count'] > 0:
        tavily_limit = 1000  # Free tier
        tavily_usage_pct = round(stats['tavily_count'] / tavily_limit * 100, 1)

        if days <= 30:
            # 如果统计周期是30天或更少，可以估算月度用量
            estimated_monthly = int(stats['tavily_count'] / days * 30)
            print(f"   Tavily:")
            print(f"      当前用量: {stats['tavily_count']}/1000 ({tavily_usage_pct}%)")
            print(f"      预计月度: {estimated_monthly}次")

            if estimated_monthly > 1000:
                print(f"      🚨 警告：预计超出Free tier限额！建议升级套餐")
            elif estimated_monthly > 800:
                print(f"      ⚠️  注意：用量接近限额，请关注")
            else:
                print(f"      ✅ 用量正常")

    # Serper配额（假设Free tier: 2500次一次性）
    if stats['serper_count'] > 0:
        serper_limit = 2500  # Free tier (lifetime)
        print(f"   Serper:")
        print(f"      累计用量: {stats['serper_count']}/2500")
        remaining = serper_limit - stats['serper_count']
        print(f"      剩余额度: {remaining}次")

        if remaining < 500:
            print(f"      🚨 警告：额度即将用完！")
        elif remaining < 1000:
            print(f"      ⚠️  注意：额度已使用过半")
        else:
            print(f"      ✅ 额度充足")

    print("\n💡 建议:")
    print("   • 定期检查配额使用情况")
    print("   • 考虑升级到付费套餐以避免服务中断")
    print("   • 监控搜索质量，优化查询策略")


def main():
    """主函数"""
    print("🔍 Wenning 搜索API使用统计分析")
    print(f"⏰ 分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 加载数据
    records = load_usage_data()

    if not records:
        print("\n❌ 没有可用的统计数据")
        sys.exit(1)

    print(f"\n✅ 已加载 {len(records)} 条使用记录")

    # 分析不同时间周期
    for days in [7, 30]:
        stats = analyze_usage(records, days)
        if stats:
            print_report(stats, days)

    print("\n" + "="*70)
    print("✅ 分析完成")
    print("="*70)

    print("\n📌 查看详细配额:")
    print("   Tavily: https://app.tavily.com/home")
    print("   Serper: https://serper.dev/dashboard")


if __name__ == "__main__":
    main()
