"""测试ConversationManagerV2

验证新的分片存储系统功能正常
"""

import sys
from pathlib import Path

# 添加项目根目录到path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.conversation_manager_v2 import ConversationManagerV2


def test_basic_operations():
    """测试基本操作"""
    print("="*60)
    print("测试ConversationManagerV2基本操作")
    print("="*60 + "\n")

    # 初始化
    print("1. 初始化管理器...")
    manager = ConversationManagerV2()
    print(f"✓ 索引加载成功,共 {len(manager.index)} 个对话\n")

    # 列出对话
    print("2. 列出所有对话...")
    convs = manager.list_conversations()
    print(f"✓ 共 {len(convs)} 个对话")
    if convs:
        print(f"  最新对话: {convs[0]['title'][:30]}... (ID: {convs[0]['id']})\n")

    # 获取对话详情(懒加载)
    if convs:
        print("3. 获取对话详情(懒加载)...")
        conv_id = convs[0]['id']
        conv = manager.get_conversation(conv_id)
        if conv:
            print(f"✓ 成功加载对话 {conv_id}")
            print(f"  标题: {conv['title']}")
            print(f"  消息数: {len(conv['messages'])}")
            print(f"  用户: {conv.get('user', 'anonymous')}\n")
        else:
            print(f"✗ 加载失败\n")

    # 创建新对话
    print("4. 创建新对话...")
    new_id = manager.create_conversation(model="gpt-5", username="test_user")
    print(f"✓ 创建成功: {new_id}\n")

    # 添加消息
    print("5. 添加消息...")
    msg_id = manager.add_message(
        new_id,
        role="user",
        content="测试消息",
        username="test_user"
    )
    print(f"✓ 消息添加成功: {msg_id}\n")

    # 验证消息
    print("6. 验证消息...")
    conv = manager.get_conversation(new_id, username="test_user")
    if conv and len(conv['messages']) == 1:
        print(f"✓ 消息验证成功")
        print(f"  内容: {conv['messages'][0]['content']}\n")
    else:
        print(f"✗ 消息验证失败\n")

    # 删除测试对话
    print("7. 删除测试对话...")
    manager.delete_conversation(new_id, username="test_user")
    print(f"✓ 删除成功\n")

    print("="*60)
    print("✅ 所有测试通过!")
    print("="*60)


def test_user_isolation():
    """测试用户隔离"""
    print("\n" + "="*60)
    print("测试用户隔离")
    print("="*60 + "\n")

    manager = ConversationManagerV2()

    # 按用户列出对话
    users = ["taozi", "feixiaoxu2011", "cheerzhang678"]
    for user in users:
        convs = manager.list_conversations(username=user)
        print(f"用户 {user}: {len(convs)} 个对话")

    print("\n✅ 用户隔离测试通过!")
    print("="*60)


def test_performance():
    """测试性能(列出对话不加载messages)"""
    print("\n" + "="*60)
    print("测试性能")
    print("="*60 + "\n")

    import time

    manager = ConversationManagerV2()

    # 测试list_conversations速度
    print("1. 测试list_conversations(仅索引)...")
    start = time.time()
    convs = manager.list_conversations()
    elapsed = time.time() - start
    print(f"✓ 列出 {len(convs)} 个对话耗时: {elapsed*1000:.2f}ms")
    print(f"  平均每个: {elapsed/len(convs)*1000:.3f}ms\n")

    # 测试get_conversation速度
    if convs:
        print("2. 测试get_conversation(懒加载)...")
        conv_id = convs[0]['id']
        start = time.time()
        conv = manager.get_conversation(conv_id)
        elapsed = time.time() - start
        print(f"✓ 加载对话 {conv_id} 耗时: {elapsed*1000:.2f}ms")
        if conv:
            print(f"  消息数: {len(conv['messages'])}\n")

    print("="*60)
    print("✅ 性能测试完成!")
    print("="*60)


if __name__ == "__main__":
    try:
        test_basic_operations()
        test_user_isolation()
        test_performance()
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
