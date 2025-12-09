"""MiniMax TTS 工具测试脚本

测试 MiniMax Text-to-Speech API 集成是否正常工作。
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.utils.config import Config
from src.tools.atomic.tts_minimax import TTSMiniMax


def test_minimax_tts():
    """测试 MiniMax TTS 基本功能"""

    print("=" * 60)
    print("MiniMax TTS 工具测试")
    print("=" * 60)

    # 从 apiinfo.md 中读取的 API key
    api_key = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJHcm91cE5hbWUiOiLotLnmmZPml60iLCJVc2VyTmFtZSI6Iui0ueaZk-aXrSIsIkFjY291bnQiOiIiLCJTdWJqZWN0SUQiOiIxOTk4MDg2MDMwMzM0MzcwMDMyIiwiUGhvbmUiOiIxMzMyMTEwNTQ0MiIsIkdyb3VwSUQiOiIxOTk4MDg2MDMwMzMwMTc1NzI4IiwiUGFnZU5hbWUiOiIiLCJNYWlsIjoiIiwiQ3JlYXRlVGltZSI6IjIwMjUtMTItMDkgMTQ6NDU6MDgiLCJUb2tlblR5cGUiOjEsImlzcyI6Im1pbmltYXgifQ.Cduc9i-LTFkGZqXPTjE2O0bUlSNtM914e8889FxBCYyTOgM2GUWKSG0WmnmUlHajA7tEI_HoSQQusNuOpxun7GGEChsEE3moOYSWmYM43mRk3Vw4lp_L4DBTwSS14KlrO75O6FkiCIgiSIemxvPdb7iRZbLoT0DT5KK32qoXCgiZcyGnjsGKS0XLz8i0LA6oWIU0VNwJkp8AGjGp5Ul3UchqZNfqHsi71If-oPCEBfjekiib9kYtnr250zyomOwD1h9HDXw_-la68pY-a82fHBDXbEp9t3jF_cn1kR9YC4putmkoMnCxbIfHGIEEU5wGA2SQod1qlQLgtM5oT7VOBA"

    # 设置环境变量
    os.environ["MINIMAX_API_KEY"] = api_key

    # 初始化配置
    print("\n[1/4] 初始化配置...")
    try:
        config = Config()
        print("✓ 配置加载成功")
        print(f"  - 输出目录: {config.output_dir}")
    except Exception as e:
        print(f"✗ 配置加载失败: {e}")
        return False

    # 初始化工具
    print("\n[2/4] 初始化 TTSMiniMax 工具...")
    try:
        tts_tool = TTSMiniMax(config)
        print("✓ 工具初始化成功")
        print(f"  - 工具名称: {tts_tool.name}")
        print(f"  - API URL: {tts_tool.api_url}")
    except Exception as e:
        print(f"✗ 工具初始化失败: {e}")
        return False

    # 测试参数
    test_params = {
        "text": "你好，这是一个测试音频。今天天气真不错！",
        "conversation_id": "test_minimax_tts",
        "voice_id": "male-qn-qingse",
        "speed": 1.0,
        "vol": 1.0,
        "pitch": 0,
        "emotion": "happy",
        "format": "mp3",
        "filename": "test_audio.mp3"
    }

    print("\n[3/4] 调用 MiniMax TTS API...")
    print(f"  - 文本: {test_params['text']}")
    print(f"  - 音色: {test_params['voice_id']}")
    print(f"  - 情感: {test_params['emotion']}")
    print(f"  - 格式: {test_params['format']}")

    try:
        result = tts_tool.run(**test_params)

        if result.get("status") == "success":
            print("✓ API 调用成功！")
            print(f"\n[4/4] 结果信息:")
            print(f"  - 状态: {result['status']}")
            print(f"  - 生成文件: {result.get('generated_files', [])}")

            data = result.get("data", {})
            print(f"\n  音频参数:")
            print(f"    - 模型: {data.get('model')}")
            print(f"    - 音色: {data.get('voice_id')}")
            print(f"    - 语速: {data.get('speed')}")
            print(f"    - 情感: {data.get('emotion')}")
            print(f"    - 文件路径: {data.get('file_path')}")

            # 检查文件是否存在
            file_path = data.get('file_path')
            if file_path and Path(file_path).exists():
                file_size = Path(file_path).stat().st_size
                print(f"\n  ✓ 音频文件已保存: {file_size} 字节")
                print(f"  ✓ 完整路径: {file_path}")
                return True
            else:
                print(f"\n  ✗ 音频文件不存在: {file_path}")
                return False
        else:
            print(f"✗ API 调用失败")
            print(f"  - 错误信息: {result.get('error')}")
            return False

    except Exception as e:
        print(f"✗ 执行失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("\n开始测试 MiniMax TTS 集成...\n")

    success = test_minimax_tts()

    print("\n" + "=" * 60)
    if success:
        print("✓ 测试通过！MiniMax TTS 集成正常工作")
    else:
        print("✗ 测试失败！请检查错误信息")
    print("=" * 60 + "\n")

    sys.exit(0 if success else 1)
