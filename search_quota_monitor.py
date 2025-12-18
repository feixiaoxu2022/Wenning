#!/usr/bin/env python3
"""搜索API余额监控脚本

检查Tavily和Serper API的配额使用情况。
"""

import os
import sys
import requests
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime

# 加载环境变量
env_file = Path(__file__).parent / ".env"
if not env_file.exists():
    print(f"❌ 未找到.env文件: {env_file}")
    sys.exit(1)

load_dotenv(env_file)

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")


def check_tavily_quota():
    """检查Tavily API配额

    Tavily的配额信息通常在响应header中返回
    """
    print("\n" + "="*60)
    print("📊 Tavily API 配额检查")
    print("="*60)

    if not TAVILY_API_KEY:
        print("❌ 未配置TAVILY_API_KEY")
        return

    try:
        # 执行一次测试搜索（使用最小参数）
        url = "https://api.tavily.com/search"
        headers = {"Content-Type": "application/json"}
        payload = {
            "api_key": TAVILY_API_KEY,
            "query": "test",
            "max_results": 1,
            "include_answer": False,
            "include_raw_content": False
        }

        print("🔍 正在查询配额信息...")
        response = requests.post(url, headers=headers, json=payload, timeout=10)

        # 检查响应状态
        if response.status_code == 200:
            print("✅ API连接正常")

            # 尝试从响应头获取配额信息
            headers_dict = dict(response.headers)

            # 常见的配额header名称
            quota_headers = [
                'X-RateLimit-Limit',
                'X-RateLimit-Remaining',
                'X-RateLimit-Reset',
                'X-Quota-Limit',
                'X-Quota-Remaining',
                'X-Credits-Remaining',
                'X-Credits-Total'
            ]

            found_quota_info = False
            for header_name in quota_headers:
                if header_name in headers_dict:
                    print(f"📈 {header_name}: {headers_dict[header_name]}")
                    found_quota_info = True

            if not found_quota_info:
                print("ℹ️  响应header中未找到配额信息")
                print("💡 建议：访问 https://app.tavily.com/home 查看配额")

            # 显示响应数据（可能包含配额信息）
            data = response.json()
            if 'credits_remaining' in data:
                print(f"💰 剩余积分: {data['credits_remaining']}")
            if 'credits_total' in data:
                print(f"📊 总积分: {data['credits_total']}")

        elif response.status_code == 429:
            print("⚠️  配额已用完！(HTTP 429 - Too Many Requests)")
            print("💡 请升级套餐或等待下个计费周期")
        elif response.status_code == 401:
            print("❌ API Key无效或已过期")
        else:
            print(f"⚠️  请求失败: HTTP {response.status_code}")
            print(f"响应: {response.text[:200]}")

    except requests.exceptions.Timeout:
        print("⏱️  请求超时")
    except Exception as e:
        print(f"❌ 检查失败: {str(e)}")

    print("\n📌 查看详细配额信息:")
    print("   👉 https://app.tavily.com/home")


def check_serper_quota():
    """检查Serper API配额

    Serper的配额信息在响应header中返回
    """
    print("\n" + "="*60)
    print("📊 Serper API 配额检查")
    print("="*60)

    if not SERPER_API_KEY:
        print("❌ 未配置SERPER_API_KEY")
        return

    try:
        # 执行一次测试搜索（使用最小参数）
        url = "https://google.serper.dev/search"
        headers = {
            "X-API-KEY": SERPER_API_KEY,
            "Content-Type": "application/json"
        }
        payload = {
            "q": "test",
            "num": 1
        }

        print("🔍 正在查询配额信息...")
        response = requests.post(url, headers=headers, json=payload, timeout=10)

        # 检查响应状态
        if response.status_code == 200:
            print("✅ API连接正常")

            # 从响应头获取配额信息
            headers_dict = dict(response.headers)

            # Serper通常使用这些header
            if 'X-Credits-Remaining' in headers_dict:
                remaining = headers_dict['X-Credits-Remaining']
                print(f"💰 剩余搜索次数: {remaining}")

            if 'X-Credits-Total' in headers_dict:
                total = headers_dict['X-Credits-Total']
                print(f"📊 总搜索次数: {total}")

            if 'X-Credits-Used' in headers_dict:
                used = headers_dict['X-Credits-Used']
                print(f"📉 已使用次数: {used}")

            # 尝试其他可能的header
            quota_headers = [
                'X-RateLimit-Limit',
                'X-RateLimit-Remaining',
                'X-RateLimit-Reset',
                'X-Quota-Limit',
                'X-Quota-Remaining'
            ]

            other_info_found = False
            for header_name in quota_headers:
                if header_name in headers_dict:
                    print(f"📈 {header_name}: {headers_dict[header_name]}")
                    other_info_found = True

            # 如果没有找到任何配额信息
            if 'X-Credits-Remaining' not in headers_dict and not other_info_found:
                print("ℹ️  响应header中未找到配额信息")
                print("💡 建议：访问 https://serper.dev/dashboard 查看配额")

        elif response.status_code == 429:
            print("⚠️  配额已用完！(HTTP 429 - Too Many Requests)")
            print("💡 请升级套餐或等待下个计费周期")
        elif response.status_code == 401:
            print("❌ API Key无效或已过期")
        else:
            print(f"⚠️  请求失败: HTTP {response.status_code}")
            print(f"响应: {response.text[:200]}")

    except requests.exceptions.Timeout:
        print("⏱️  请求超时")
    except Exception as e:
        print(f"❌ 检查失败: {str(e)}")

    print("\n📌 查看详细配额信息:")
    print("   👉 https://serper.dev/dashboard")


def show_summary():
    """显示配置摘要和建议"""
    print("\n" + "="*60)
    print("📋 配置摘要")
    print("="*60)

    tavily_configured = bool(TAVILY_API_KEY)
    serper_configured = bool(SERPER_API_KEY)

    print(f"Tavily API: {'✅ 已配置' if tavily_configured else '❌ 未配置'}")
    print(f"Serper API: {'✅ 已配置' if serper_configured else '❌ 未配置'}")

    print("\n💡 使用策略:")
    if tavily_configured:
        print("   • Tavily 为主要搜索引擎（优先使用）")
    if serper_configured:
        print("   • Serper 为备用搜索引擎（Tavily失败时自动切换）")

    if not tavily_configured and not serper_configured:
        print("   ⚠️  警告：没有配置任何搜索API！")

    print("\n📊 套餐参考:")
    print("   Tavily:")
    print("   • Free: 1,000次/月")
    print("   • Basic: $49/月，20,000次")
    print("   • Pro: $199/月，100,000次")
    print("")
    print("   Serper:")
    print("   • Free: 2,500次（一次性）")
    print("   • Developer: $50/月，5,000次")
    print("   • Startup: $100/月，15,000次")


if __name__ == "__main__":
    print("🔍 Wenning 搜索API配额监控")
    print(f"⏰ 检查时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 检查两个API的配额
    check_tavily_quota()
    check_serper_quota()

    # 显示配置摘要
    show_summary()

    print("\n" + "="*60)
    print("✅ 检查完成")
    print("="*60)
