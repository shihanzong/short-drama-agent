#!/usr/bin/env python3
"""
多平台文案生成器 - Platform Copy Generator
"""

import json
import re
from pathlib import Path

SKILL_ROOT = Path(__file__).parent.parent

PLATFORM_RULES = {
    "xiaohongshu": "标题20字以内带情绪词，正文300-800字多用emoji，3-5个标签，重封面",
    "twitter": "单条280字符，短句高密度，观点先行，每段不超过2行",
    "wechat": "标题30字以内，正文800-3000字，开头引入主体展开结尾升华",
    "youtube_shorts": "60秒以内，3秒钩子+核心内容+行动号召，快节奏",
    "tiktok": "60秒以内，年轻化口语化，配合BGM，趋势驱动",
    "linkedin": "专业风格300-1500字，行业洞察/职场经验/商业思考"
}


class PlatformCopyGenerator:
    """多平台文案生成器"""
    
    def __init__(self, llm_client=None):
        self.llm_client = llm_client
    
    def generate_for_platforms(self, topic: dict, scripts: dict = None,
                                platforms: list = None) -> dict:
        if platforms is None:
            platforms = list(PLATFORM_RULES.keys())
        
        result = {}
        for pk in platforms:
            try:
                result[pk] = self._generate_single(topic, pk)
            except Exception as e:
                result[pk] = {"error": str(e), "title": "", "body": "", "hashtags": []}
        
        return result
    
    def _generate_single(self, topic: dict, platform_key: str) -> dict:
        platform_name = PLATFORM_RULES.get(platform_key, platform_key)
        
        prompt = f"""为选题【{topic.get('title', '未命名')}】生成【{platform_name}】平台的独立文案。

选题描述：{topic.get('description', '')}
目标受众：{topic.get('audience', '')}
核心价值：{topic.get('value', '')}
前3秒钩子：{topic.get('hook_3sec', '')}
平台规则：{platform_name} — {PLATFORM_RULES.get(platform_key, '')}

要求：
1. 标题符合平台风格
2. 正文独立重写，不要复制
3. 包含明确的引导语
4. 输出JSON格式

输出：{{"title": "标题", "body": "正文", "hashtags": ["标签1"], "call_to_action": "关注/收藏/评论", "character_count": 字数}}
"""
        
        try:
            if self.llm_client:
                response = self.llm_client.generate(
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"}
                )
            else:
                response = json.dumps({
                    "title": f"[{platform_name}] {topic.get('title', '待生成')}",
                    "body": f"[{platform_name}] 正文内容（需要LLM支持）",
                    "hashtags": [],
                    "call_to_action": ""
                })
            
            match = re.search(r'\{[^{}]*"title"[^{}]*\}', response, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                data["_platform"] = platform_name
                return data
            
            return {"title": f"[{platform_name}] 解析失败", "body": "", "hashtags": []}
        except Exception as e:
            return {"error": str(e), "title": "", "body": "", "hashtags": []}
    
    def format_copies(self, copies: dict) -> str:
        lines = ["=" * 40, "多平台文案", "=" * 40 + "\n"]
        for pk, copy in copies.items():
            lines.append(f"### {pk}")
            lines.append(f"标题：{copy.get('title', 'N/A')}")
            body = copy.get('body', '')
            if len(body) > 200:
                body = body[:200] + "..."
            lines.append(f"正文：{body}")
            if copy.get('hashtags'):
                lines.append(f"标签：{' '.join(copy['hashtags'])}")
            lines.append("")
        return "\n".join(lines)


def generate_platform_copies(topic: dict, scripts: dict = None,
                              platforms: list = None, llm_client=None) -> dict:
    gen = PlatformCopyGenerator(llm_client=llm_client)
    return gen.generate_for_platforms(topic, scripts=scripts, platforms=platforms)
