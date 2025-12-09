#!/usr/bin/env python3
"""测试中文字体注入功能"""

import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from src.tools.atomic.code_executor import CodeExecutor
from src.utils.config import Config


def test_font_detection():
    """测试字体检测功能"""
    print("=" * 60)
    print("测试1: 中文字体检测")
    print("=" * 60)

    config = Config()
    executor = CodeExecutor(config)

    font_path = executor._get_chinese_font_path()

    if font_path:
        print(f"✅ 成功检测到中文字体: {font_path}")
        print(f"   字体文件存在: {Path(font_path).exists()}")
    else:
        print("❌ 未检测到中文字体")

    return bool(font_path)


def test_font_injection():
    """测试字体注入功能"""
    print("\n" + "=" * 60)
    print("测试2: 字体注入功能")
    print("=" * 60)

    config = Config()
    executor = CodeExecutor(config)

    # 测试代码
    test_code = """
import matplotlib.pyplot as plt
import numpy as np

x = np.linspace(0, 10, 100)
y = np.sin(x)

plt.figure()
plt.plot(x, y)
plt.title('正弦曲线')
plt.xlabel('X轴')
plt.ylabel('Y轴')
plt.savefig('test_chinese.png', dpi=100)
"""

    print("\n原始代码长度:", len(test_code))

    injected_code = executor._inject_chinese_font_support(test_code)

    print("注入后代码长度:", len(injected_code))
    print("\n注入的配置代码预览:")
    print("-" * 60)

    # 显示注入的部分
    lines = injected_code.split('\n')
    in_injection = False
    for line in lines:
        if '==== 自动注入' in line:
            in_injection = True
        if in_injection:
            print(line)
        if '==== 注入结束' in line:
            break

    print("-" * 60)

    # 检查关键内容
    checks = [
        ('_CHINESE_FONT_PATH' in injected_code, "字体路径变量"),
        ('matplotlib.rcParams' in injected_code, "matplotlib配置"),
        ('_MOVIEPY_FONT_CONFIG' in injected_code, "moviepy配置"),
        ('axes.unicode_minus' in injected_code, "负号修复"),
    ]

    print("\n注入内容检查:")
    for passed, desc in checks:
        status = "✅" if passed else "❌"
        print(f"  {status} {desc}")

    return all(check[0] for check in checks)


def test_moviepy_example():
    """测试moviepy示例代码"""
    print("\n" + "=" * 60)
    print("测试3: moviepy示例代码生成")
    print("=" * 60)

    config = Config()
    executor = CodeExecutor(config)

    test_code = """
from moviepy.editor import TextClip, ColorClip, CompositeVideoClip

# 创建背景
bg = ColorClip(size=(640, 480), color=(0, 0, 0), duration=3)

# 使用注入的字体配置创建文本
text = TextClip("你好世界", **_MOVIEPY_FONT_CONFIG).set_position('center').set_duration(3)

# 合成
video = CompositeVideoClip([bg, text])
video.write_videofile('test_video.mp4', fps=24, codec='libx264',
                      audio=False, preset='ultrafast',
                      ffmpeg_params=['-pix_fmt', 'yuv420p'])
"""

    injected_code = executor._inject_chinese_font_support(test_code)

    # 检查moviepy相关配置
    has_font_path = '_CHINESE_FONT_PATH' in injected_code
    has_moviepy_config = '_MOVIEPY_FONT_CONFIG' in injected_code
    has_usage = '**_MOVIEPY_FONT_CONFIG' in test_code

    print("\nmoviepy代码检查:")
    print(f"  {'✅' if has_font_path else '❌'} 包含字体路径")
    print(f"  {'✅' if has_moviepy_config else '❌'} 包含moviepy配置")
    print(f"  {'✅' if has_usage else '❌'} 用户代码使用配置")

    return has_font_path and has_moviepy_config


def main():
    """运行所有测试"""
    print("\n")
    print("🎬 " + "=" * 58)
    print("   中文字体注入功能测试套件")
    print("=" * 60)

    results = []

    # 运行测试
    results.append(("字体检测", test_font_detection()))
    results.append(("字体注入", test_font_injection()))
    results.append(("moviepy示例", test_moviepy_example()))

    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status} - {name}")

    print(f"\n通过: {passed}/{total}")

    if passed == total:
        print("\n🎉 所有测试通过！中文字体注入功能正常工作。")
    else:
        print("\n⚠️  部分测试失败，请检查配置。")

    print("=" * 60)

    return passed == total


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
