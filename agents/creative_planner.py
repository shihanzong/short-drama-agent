"""Creative Planner Agent - Market analysis, topic planning, character design, episode outlines."""

import os
import json
from typing import Optional, Dict, List
from modules.llm_client import LLMClient


class CreativePlannerAgent:
    """Plans the creative direction for a short drama series."""

    SYSTEM_PROMPT = """你是短剧创意策划专家。精通短视频短剧的爆款规律、人设设计、剧情节奏。
擅长分析市场热点、设计强冲突的人物关系、规划每集钩子和反转。

工作原则:
1. 每集必须包含至少1个强冲突/反转
2. 每集结尾必须留有悬念钩子
3. 人物关系要有张力(爱恨交织、身份反差)
4. 题材要贴合当前平台热点
5. 输出JSON格式，不要多余解释"""

    GENRE_TEMPLATES = {
        "重生复仇": {
            "description": "主角重生回到过去，利用先知能力复仇或挽回人生",
            "key_elements": ["前世惨死", "重生回到关键节点", "改变命运", "智斗反派"],
            "target_audience": "女频25-40岁",
            "conflict_style": "智斗+情感纠葛",
        },
        "霸总": {
            "description": "霸道总裁与平凡女主之间的甜虐爱情故事",
            "key_elements": ["身份差距", "先婚后爱", "追妻火葬场", "豪门恩怨"],
            "target_audience": "女频18-35岁",
            "conflict_style": "情感拉扯+甜蜜互动",
        },
        "逆袭": {
            "description": "被看不起的主角通过努力和能力逆袭打脸",
            "key_elements": ["被轻视的主角", "隐藏实力", "打脸时刻", "成长蜕变"],
            "target_audience": "男频20-45岁",
            "conflict_style": "打脸+爽感",
        },
        "悬疑": {
            "description": "围绕谜团展开的悬疑推理短剧",
            "key_elements": ["连环谜团", "身份反转", "心理博弈", "层层揭秘"],
            "target_audience": "全年龄段20-45岁",
            "conflict_style": "烧脑+反转",
        },
        "战神": {
            "description": "隐藏身份的强者被看不起后亮出真实身份",
            "key_elements": ["隐藏身份", "被轻视", "亮身份", "碾压对手"],
            "target_audience": "男频25-50岁",
            "conflict_style": "爽感+碾压",
        },
        "甜宠": {
            "description": "纯甜无虐的宠溺恋爱故事",
            "key_elements": ["双向奔赴", "撒糖日常", "小误会", "甜蜜结局"],
            "target_audience": "女频16-30岁",
            "conflict_style": "甜蜜+轻微拉扯",
        },
    }

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm = llm_client or LLMClient()

    def analyze_hot_topics(self) -> Dict:
        """Analyze current short drama hot topics and trends.

        Returns a dict with trending topics, genres, and engagement data.
        """
        prompt = """请分析当前短剧市场热点趋势，包括:
1. 当前最受欢迎的题材TOP5
2. 各题材的爆款特征
3. 竞争程度和入局建议
4. 推荐一个最适合当前入局的题材

请输出JSON格式:
{
  "trending_genres": [{"name": "题材名", "hot_score": 85, "competition": "high/medium/low", "tips": "建议"}],
  "recommended_genre": "推荐的题材",
  "market_analysis": "市场分析摘要"
}"""
        try:
            return self.llm.chat_structured(prompt, self.SYSTEM_PROMPT)
        except Exception as e:
            # Fallback: return template-based recommendation
            return self._recommend_from_templates()

    def _recommend_from_templates(self) -> Dict:
        """Generate recommendation based on genre templates when LLM is unavailable."""
        genre = "重生复仇"
        return {
            "trending_genres": [
                {"name": g, "hot_score": 80 + i * 5, "competition": "medium", "tips": f"{self.GENRE_TEMPLATES[g]['description']}"}
                for i, g in enumerate(list(self.GENRE_TEMPLATES.keys())[:5])
            ],
            "recommended_genre": genre,
            "market_analysis": f"推荐题材: {genre} - {self.GENRE_TEMPLATES[genre]['description']}",
        }

    def generate_character_cards(
        self,
        genre: str,
        series_count: int = 3,
    ) -> List[Dict]:
        """Generate character cards for a drama series.

        Args:
            genre: Drama genre.
            series_count: Number of character set variations to generate.

        Returns:
            List of character card dicts.
        """
        genre_info = self.GENRE_TEMPLATES.get(genre, {})
        prompt = f"""请为{genre}题材短剧设计人物设定卡。

题材特征:
- 描述: {genre_info.get('description', genre)}
- 关键元素: {", ".join(genre_info.get('key_elements', []))}
- 目标受众: {genre_info.get('target_audience', '')}
- 冲突风格: {genre_info.get('conflict_style', '')}

请设计3组不同的人物关系方案，每组包含:
1. 主角(姓名/年龄/性格/背景/动机/外貌特征/口头禅)
2. 对手/反派(姓名/与主角关系/动机)
3. 配角/盟友(姓名/功能定位)

输出JSON格式:
{{
  "series": [
    {{
      "name": "方案名称",
      "protagonist": {{ "name": "", "age": "", "personality": "", "background": "", "motivation": "", "appearance": "", "catchphrase": "" }},
      "antagonist": {{ "name": "", "relationship": "", "motivation": "" }},
      "ally": {{ "name": "", "role": "" }}
    }}
  ]
}}"""
        try:
            result = self.llm.chat_structured(prompt, self.SYSTEM_PROMPT)
            return result.get("series", [])
        except Exception:
            return self._generate_fallback_characters(genre)

    def _generate_fallback_characters(self, genre: str) -> List[Dict]:
        """Fallback character generation without LLM."""
        return [
            {
                "name": f"{genre}方案A",
                "protagonist": {
                    "name": "林夏",
                    "age": "26",
                    "personality": "坚韧、聪明、外柔内刚",
                    "background": f"普通家庭出身，在{genre}中经历成长蜕变",
                    "motivation": "改变命运，找回失去的一切",
                    "appearance": "清秀五官，气质温婉但有力量感",
                    "catchphrase": "这一次，我不会再输了",
                },
                "antagonist": {
                    "name": "赵文博",
                    "relationship": "表面盟友，实际敌人",
                    "motivation": "利益至上，不惜一切手段",
                },
                "ally": {
                    "name": "苏晴",
                    "role": "闺蜜兼盟友",
                },
            }
        ]

    def generate_episode_outline(
        self,
        genre: str,
        character_cards: List[Dict],
        total_episodes: int = 5,
    ) -> Dict:
        """Generate episode outlines for the drama.

        Args:
            genre: Drama genre.
            character_cards: Character cards from generate_character_cards.
            total_episodes: Number of episodes to outline.

        Returns:
            Dict with episode outlines.
        """
        selected_card = character_cards[0] if character_cards else {}
        hero = selected_card.get("protagonist", {})
        villain = selected_card.get("antagonist", {})

        prompt = f"""请为{genre}题材短剧生成{total_episodes}集的分集大纲。

人物设定:
- 主角: {hero.get('name', '主角')} ({hero.get('personality', '')})
  动机: {hero.get('motivation', '')}
- 反派: {villain.get('name', '反派')}
  动机: {villain.get('motivation', '')}

每集大纲格式:
{{
  "title": "第X集标题",
  "logline": "一句话说清本集核心",
  "scenes": [
    {{
      "scene_number": 1,
      "location": "场景地点",
      "time_of_day": "白天/夜晚",
      "summary": "本场景内容摘要",
      "characters_present": ["角色名"],
      "emotional_tone": "情绪",
      "duration_seconds": 30
    }}
  ],
  "cliffhanger": "本集结尾悬念",
  "hook_score": 8  # 1-10
}}

输出JSON数组格式: {{"outlines": [...]}}"""

        try:
            result = self.llm.chat_structured(prompt, self.SYSTEM_PROMPT)
            return result.get("outlines", [])
        except Exception:
            return self._generate_fallback_outlines(genre, total_episodes, selected_card)

    def _generate_fallback_outlines(
        self, genre: str, count: int, character_card: Dict
    ) -> List[Dict]:
        """Fallback outline generation without LLM."""
        hero_name = character_card.get("protagonist", {}).get("name", "主角")
        outlines = []
        for i in range(count):
            ep_num = i + 1
            if i == count - 1:
                title = f"第{ep_num}集: 高潮"
            else:
                title = f"第{ep_num}集: 发展{ep_num}"
            outlines.append({
                "title": title,
                "logline": f"{hero_name}在第{ep_num}集的故事发展",
                "scenes": [
                    {
                        "scene_number": 1,
                        "location": "室内",
                        "time_of_day": "白天",
                        "summary": "剧情发展",
                        "characters_present": [hero_name],
                        "emotional_tone": "紧张",
                        "duration_seconds": 30,
                    }
                ],
                "cliffhanger": f"第{i+1}集结尾悬念",
                "hook_score": 7 + i % 4,
            })
        return outlines

    def run(
        self,
        genre: str,
        episode_count: int = 5,
    ) -> Dict:
        """Run the full creative planning pipeline.

        Returns a complete planning package:
        - topic_analysis
        - character_cards
        - episode_outlines
        """
        print(f"  [CreativePlanner] Analyzing hot topics for {genre}...")
        topic_analysis = self.analyze_hot_topics()

        print(f"  [CreativePlanner] Generating character cards...")
        character_cards = self.generate_character_cards(genre)

        print(f"  [CreativePlanner] Generating episode outlines ({episode_count} episodes)...")
        episode_outlines = self.generate_episode_outline(
            genre, character_cards, total_episodes=episode_count
        )

        return {
            "genre": genre,
            "topic_analysis": topic_analysis,
            "character_cards": character_cards,
            "episode_outlines": episode_outlines,
        }
