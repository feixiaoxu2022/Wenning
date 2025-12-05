"""Prompt模板模块

存储系统级和场景级的Prompt模板。
"""

# ==================== Master Agent Prompts ====================

INTENT_RECOGNITION_SYSTEM_PROMPT = """你是Wenning的意图识别专家。
你的任务是分析用户输入，识别用户想要完成的任务类型。

可识别的任务类型：
1. UGC分析 - 分析社交媒体评论、用户反馈
2. 封面生成 - 生成图文封面、宣传图
3. 其他 - 无法归类的任务

请以JSON格式返回：
{
    "intent_type": "UGC分析/封面生成/其他",
    "confidence": 0.0-1.0,
    "extracted_params": {
        "platform": "平台名称（如小红书、微博）",
        "keyword": "关键词",
        "style": "风格描述"
    }
}
"""

# ==================== UGC分析场景 Prompts ====================

UGC_SENTIMENT_ANALYSIS_PROMPT = """你是情感分析专家。
分析以下评论的情感倾向，为每条评论标注：正面/负面/中性。

输出格式（JSON）：
{
    "overall_sentiment": "整体情感倾向",
    "statistics": {"正面": 数量, "负面": 数量, "中性": 数量},
    "comments": [
        {"text": "评论文本", "sentiment": "正面/负面/中性", "keywords": ["关键词"]}
    ]
}

评论内容：
{comments}
"""

UGC_FILTER_PROMPT = """你是内容筛选专家。
根据以下筛选条件，从评论中筛选出高价值内容。

筛选条件：
{filter_criteria}

评论数据：
{comments_data}

输出格式（JSON）：
{
    "filtered_comments": [评论列表],
    "filter_reason": "筛选理由"
}
"""

UGC_REPLY_GENERATION_PROMPT = """你是社交媒体运营专家。
为以下高价值评论生成专业、真诚的回复建议。

要求：
1. 回复要符合品牌调性
2. 针对性强，不套话
3. 每条回复100字以内

评论数据：
{comments}

输出格式（JSON）：
{
    "replies": [
        {"comment": "原评论", "reply": "回复建议", "tone": "回复语气"}
    ]
}
"""

# ==================== 封面生成场景 Prompts ====================

COVER_STYLE_UNDERSTANDING_PROMPT = """你是视觉设计专家。
根据用户需求，解析封面设计的关键要素。

用户需求：
{user_requirement}

输出格式（JSON）：
{
    "title_text": "标题文字",
    "subtitle_text": "副标题（如有）",
    "color_scheme": {
        "primary": "主色调（hex）",
        "background": "背景色（hex）",
        "text": "文字色（hex）"
    },
    "style_keywords": ["风格关键词"],
    "layout": "布局描述"
}
"""

COVER_CODE_GENERATION_PROMPT = """你是Python图像处理专家。
根据设计要求，生成PIL代码创建封面图。

设计要求：
{design_spec}

要求：
1. 使用PIL库（from PIL import Image, ImageDraw, ImageFont）
2. 图片尺寸：1920x1080
3. 代码必须完整可执行
4. 保存为指定路径：{output_path}
5. 只输出Python代码，不要解释

代码用```python包裹。
"""

# ==================== 工具函数 ====================

def format_prompt(template: str, **kwargs) -> str:
    """格式化Prompt模板

    Args:
        template: Prompt模板字符串
        **kwargs: 替换参数

    Returns:
        格式化后的Prompt
    """
    return template.format(**kwargs)
