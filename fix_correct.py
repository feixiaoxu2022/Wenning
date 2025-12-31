import json
import shutil
from datetime import datetime

# 备份
backup_path = 'data/conversations/feixiaoxu2011/2025-12/20251224_194933_35d41330.json.backup_' + datetime.now().strftime('%Y%m%d_%H%M%S')
shutil.copy2(
    'data/conversations/feixiaoxu2011/2025-12/20251224_194933_35d41330.json',
    backup_path
)
print(f'✅ 已备份到: {backup_path}')

# 读取对话文件
with open('data/conversations/feixiaoxu2011/2025-12/20251224_194933_35d41330.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

messages = data.get('messages', [])
fixed_count = 0

for i, msg in enumerate(messages):
    if msg.get('role') == 'assistant':
        has_tool_calls = bool(msg.get('tool_calls'))
        has_gemini_parts = bool(msg.get('_gemini_original_parts'))
        content = msg.get('content', '')

        # 只清理那些：没有真实tool_calls，没有_gemini_original_parts，但content只是"(工具调用进行中...)"
        if not has_tool_calls and not has_gemini_parts and isinstance(content, str):
            stripped = content.strip()
            if '(工具调用进行中' in stripped:
                # 移除所有"(工具调用进行中...)"后看是否还有实质内容
                cleaned = stripped.replace('(工具调用进行中...)', '').replace('\n', '').strip()
                if len(cleaned) == 0:
                    msg['content'] = ''  # 清空误导性文本
                    fixed_count += 1
                    if fixed_count <= 5:
                        print(f'清理消息#{i}: 移除了幻觉文本（无真实tool_calls）')

print(f'\n✅ 总共清理了 {fixed_count} 条幻觉消息（保留了有真实tool_calls的消息）')

# 保存
with open('data/conversations/feixiaoxu2011/2025-12/20251224_194933_35d41330.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print('✅ 已保存修复后的对话文件')
