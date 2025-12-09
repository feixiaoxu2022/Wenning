"""MiniMax 全功能测试脚本

测试所有 MiniMax 工具:
1. TTS (Text-to-Speech)
2. Image Generation (文生图)
3. Video Generation (文生视频) - 可能需要较长时间
4. Music Generation (音乐生成)
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.utils.config import Config
from src.tools.atomic.tts_minimax import TTSMiniMax
from src.tools.atomic.image_generation_minimax import ImageGenerationMiniMax
from src.tools.atomic.video_generation_minimax import VideoGenerationMiniMax
from src.tools.atomic.music_generation_minimax import MusicGenerationMiniMax


# MiniMax API Key
API_KEY = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJHcm91cE5hbWUiOiLotLnmmZPml60iLCJVc2VyTmFtZSI6Iui0ueaZk-aXrSIsIkFjY291bnQiOiIiLCJTdWJqZWN0SUQiOiIxOTk4MDg2MDMwMzM0MzcwMDMyIiwiUGhvbmUiOiIxMzMyMTEwNTQ0MiIsIkdyb3VwSUQiOiIxOTk4MDg2MDMwMzMwMTc1NzI4IiwiUGFnZU5hbWUiOiIiLCJNYWlsIjoiIiwiQ3JlYXRlVGltZSI6IjIwMjUtMTItMDkgMTQ6NDU6MDgiLCJUb2tlblR5cGUiOjEsImlzcyI6Im1pbmltYXgifQ.Cduc9i-LTFkGZqXPTjE2O0bUlSNtM914e8889FxBCYyTOgM2GUWKSG0WmnmUlHajA7tEI_HoSQQusNuOpxun7GGEChsEE3moOYSWmYM43mRk3Vw4lp_L4DBTwSS14KlrO75O6FkiCIgiSIemxvPdb7iRZbLoT0DT5KK32qoXCgiZcyGnjsGKS0XLz8i0LA6oWIU0VNwJkp8AGjGp5Ul3UchqZNfqHsi71If-oPCEBfjekiib9kYtnr250zyomOwD1h9HDXw_-la68pY-a82fHBDXbEp9t3jF_cn1kR9YC4putmkoMnCxbIfHGIEEU5wGA2SQod1qlQLgtM5oT7VOBA"


def print_header(title):
    """打印测试标题"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def test_tts():
    """测试 TTS 功能"""
    print_header("测试 1/4: TTS (Text-to-Speech)")

    os.environ["MINIMAX_API_KEY"] = API_KEY
    config = Config()
    tool = TTSMiniMax(config)

    params = {
        "text": "欢迎使用MiniMax多模态API！这是语音合成测试。",
        "conversation_id": "test_all_minimax",
        "voice_id": "female-tianmei-jingpin",
        "emotion": "happy",
        "format": "mp3"
    }

    print(f"  调用参数: text='{params['text'][:20]}...', voice={params['voice_id']}")
    result = tool.run(**params)

    if result.get("status") == "success":
        print(f"  ✓ TTS 成功: {result.get('generated_files')}")
        return True
    else:
        print(f"  ✗ TTS 失败: {result.get('error')}")
        return False


def test_image():
    """测试文生图功能"""
    print_header("测试 2/4: Image Generation (文生图)")

    os.environ["MINIMAX_API_KEY"] = API_KEY
    config = Config()
    tool = ImageGenerationMiniMax(config)

    params = {
        "prompt": "A serene Japanese garden with cherry blossoms, koi pond, and traditional stone lanterns at sunset",
        "conversation_id": "test_all_minimax",
        "aspect_ratio": "16:9",
        "n": 2,
        "prompt_optimizer": True
    }

    print(f"  调用参数: prompt='{params['prompt'][:50]}...', n={params['n']}")
    result = tool.run(**params)

    if result.get("status") == "success":
        print(f"  ✓ 文生图成功: {result.get('generated_files')}")
        return True
    else:
        print(f"  ✗ 文生图失败: {result.get('error')}")
        return False


def test_video():
    """测试文生视频功能"""
    print_header("测试 3/4: Video Generation (文生视频) - 可能需要1-2分钟")

    os.environ["MINIMAX_API_KEY"] = API_KEY
    config = Config()
    tool = VideoGenerationMiniMax(config)

    params = {
        "prompt": "A butterfly lands on a flower and slowly opens its wings",
        "conversation_id": "test_all_minimax",
        "duration": 6,
        "resolution": "720P"  # 使用720P更快
    }

    print(f"  调用参数: prompt='{params['prompt'][:50]}...', duration={params['duration']}s")
    print(f"  ⏳ 视频生成中，请耐心等待...")
    result = tool.run(**params)

    if result.get("status") == "success":
        print(f"  ✓ 文生视频成功: {result.get('generated_files')}")
        return True
    else:
        print(f"  ✗ 文生视频失败: {result.get('error')}")
        return False


def test_music():
    """测试音乐生成功能"""
    print_header("测试 4/4: Music Generation (音乐生成)")

    os.environ["MINIMAX_API_KEY"] = API_KEY
    config = Config()
    tool = MusicGenerationMiniMax(config)

    params = {
        "prompt": "轻快的流行音乐,钢琴主导,积极向上",
        "conversation_id": "test_all_minimax",
        "lyrics": "[verse]\n轻快的节奏响起来\n阳光照进窗台\n",
        "format": "mp3"
    }

    print(f"  调用参数: prompt='{params['prompt']}', has_lyrics=True")
    result = tool.run(**params)

    if result.get("status") == "success":
        print(f"  ✓ 音乐生成成功: {result.get('generated_files')}")
        return True
    else:
        print(f"  ✗ 音乐生成失败: {result.get('error')}")
        return False


def main():
    """主测试流程"""
    print("\n" + "=" * 70)
    print("  MiniMax 多模态工具集成测试")
    print("=" * 70)

    results = {
        "TTS": False,
        "Image": False,
        "Video": False,
        "Music": False
    }

    # 测试 TTS
    try:
        results["TTS"] = test_tts()
    except Exception as e:
        print(f"  ✗ TTS 测试异常: {e}")

    # 测试文生图
    try:
        results["Image"] = test_image()
    except Exception as e:
        print(f"  ✗ Image 测试异常: {e}")

    # 测试文生视频（耗时较长，可选）
    print("\n  提示: 文生视频测试可能需要1-2分钟，是否继续? (y/n): ", end="")
    choice = input().strip().lower()
    if choice == 'y':
        try:
            results["Video"] = test_video()
        except Exception as e:
            print(f"  ✗ Video 测试异常: {e}")
    else:
        print("  ⊘ 跳过文生视频测试")
        results["Video"] = None

    # 测试音乐生成
    try:
        results["Music"] = test_music()
    except Exception as e:
        print(f"  ✗ Music 测试异常: {e}")

    # 汇总结果
    print("\n" + "=" * 70)
    print("  测试结果汇总")
    print("=" * 70)

    for name, success in results.items():
        if success is True:
            status = "✓ 通过"
        elif success is False:
            status = "✗ 失败"
        else:
            status = "⊘ 跳过"
        print(f"  {name:15s}: {status}")

    passed = sum(1 for s in results.values() if s is True)
    failed = sum(1 for s in results.values() if s is False)
    skipped = sum(1 for s in results.values() if s is None)

    print("-" * 70)
    print(f"  总计: 通过 {passed}, 失败 {failed}, 跳过 {skipped}")

    # 输出文件位置
    output_dir = Path(__file__).parent / "outputs" / "test_all_minimax"
    if output_dir.exists():
        print(f"\n  生成文件位置: {output_dir}")
        print(f"  共 {len(list(output_dir.glob('*')))} 个文件")

    print("=" * 70 + "\n")

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
