#!/usr/bin/env python3
"""Manim 安装验证脚本

测试 Manim 是否正确安装并能够渲染简单动画。
"""

import sys
from pathlib import Path

def check_system_dependencies():
    """检查系统依赖"""
    print("=" * 60)
    print("检查系统依赖")
    print("=" * 60)

    import subprocess

    deps = {
        "ffmpeg": "ffmpeg -version",
        "cairo": "pkg-config --modversion cairo",
        "pango": "pkg-config --modversion pango"
    }

    results = {}
    for name, cmd in deps.items():
        try:
            result = subprocess.run(
                cmd.split(),
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                version = result.stdout.split('\n')[0]
                results[name] = ("✅", version)
            else:
                results[name] = ("❌", "未安装或无法访问")
        except Exception as e:
            results[name] = ("❌", str(e))

    for name, (status, info) in results.items():
        print(f"{status} {name}: {info}")

    all_ok = all(status == "✅" for status, _ in results.values())
    print()
    return all_ok


def check_python_package():
    """检查 Python 包"""
    print("=" * 60)
    print("检查 Python 包")
    print("=" * 60)

    try:
        import manim
        print(f"✅ manim 已安装: v{manim.__version__}")
        print(f"   路径: {manim.__file__}")
        return True
    except ImportError as e:
        print(f"❌ manim 未安装: {e}")
        print("\n安装方法:")
        print("  pip install manim")
        return False


def test_simple_render():
    """测试简单渲染"""
    print("\n" + "=" * 60)
    print("测试渲染简单动画")
    print("=" * 60)

    try:
        # 导入 Manim
        import manim as mn
        from manim import Scene, Circle, Text, Create, Write, config

        # 创建测试场景
        class TestScene(Scene):
            def construct(self):
                # 创建圆形
                circle = Circle(radius=1, color=mn.BLUE)

                # 创建文本
                text = Text("Manim OK!", font_size=36)
                text.next_to(circle, mn.DOWN)

                # 动画
                self.play(Create(circle))
                self.play(Write(text))
                self.wait()

        # 配置低质量快速渲染（使用默认输出目录）
        config.quality = "low_quality"
        config.preview = False
        config.write_to_movie = True
        config.verbosity = "WARNING"  # 减少日志输出

        print("\n开始渲染...")
        print("配置: 低质量 (480p, 15fps)")

        # 渲染场景
        scene = TestScene()
        scene.render()

        # Manim 默认输出目录: media/videos/480p15/TestScene.mp4
        default_output = Path("media/videos/480p15/TestScene.mp4")

        # 检查输出文件
        if default_output.exists():
            size_mb = default_output.stat().st_size / (1024 * 1024)
            print(f"\n✅ 渲染成功!")
            print(f"   输出文件: {default_output}")
            print(f"   文件大小: {size_mb:.2f} MB")
            return True
        else:
            # 尝试查找其他可能的输出位置
            media_dir = Path("media")
            if media_dir.exists():
                mp4_files = list(media_dir.rglob("*.mp4"))
                if mp4_files:
                    print(f"\n✅ 渲染成功!")
                    print(f"   输出文件: {mp4_files[0]}")
                    size_mb = mp4_files[0].stat().st_size / (1024 * 1024)
                    print(f"   文件大小: {size_mb:.2f} MB")
                    return True

            print("\n❌ 渲染失败: 未找到输出文件")
            print(f"   预期位置: {default_output}")
            return False

    except Exception as e:
        print(f"\n❌ 渲染测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("\n" + "=" * 60)
    print("Manim 安装验证工具")
    print("=" * 60)
    print()

    # 检查系统依赖
    deps_ok = check_system_dependencies()
    print()

    # 检查 Python 包
    pkg_ok = check_python_package()
    print()

    if not deps_ok:
        print("⚠️  系统依赖未完全安装，请先安装:")
        print("   macOS: brew install ffmpeg cairo pango pkg-config")
        print("   Linux: sudo apt-get install ffmpeg libcairo2-dev libpango1.0-dev")
        return 1

    if not pkg_ok:
        print("⚠️  Manim 包未安装，请运行:")
        print("   pip install manim")
        return 1

    # 测试渲染
    render_ok = test_simple_render()

    print("\n" + "=" * 60)
    if deps_ok and pkg_ok and render_ok:
        print("✅ 所有检查通过! Manim 已正确安装并可以使用")
        print("=" * 60)
        print("\n下一步:")
        print("1. 查看使用指南: docs/MANIM_GUIDE.md")
        print("2. 通过 Agent 请求数学动画: '帮我生成一个勾股定理的动画'")
        return 0
    else:
        print("❌ 部分检查失败，请根据上述提示修复问题")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
