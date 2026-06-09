#!/usr/bin/env python3
"""
评分规则引擎 - Scoring Engine

实现100分制内容评分，7个维度：
1. 钩子强度 20分
2. 观点清晰度 20分
3. 受众明确度 15分
4. 平台匹配度 15分
5. 素材可用度 10分
6. 转化价值 10分
7. 风险控制 10分
"""

import json
import re
from dataclasses import dataclass, field


@dataclass
class TopicScore:
    """单个选题的评分结果"""
    topic_id: int
    title: str
    scores: dict = field(default_factory=dict)
    total: float = 0.0
    rank: int = 0
    reason: str = ""
    recommendation: str = ""


DIMENSIONS = {
    "hook_strength": {"name": "钩子强度", "max": 20, "desc": "前3秒能否留住人"},
    "viewpoint_clarity": {"name": "观点清晰度", "max": 20, "desc": "一句话能说清"},
    "audience_clarity": {"name": "受众明确度", "max": 15, "desc": "谁看、为什么看"},
    "platform_fit": {"name": "平台匹配度", "max": 15, "desc": "适合哪个平台"},
    "material_availability": {"name": "素材可用度", "max": 10, "desc": "有画面/数据/案例支撑"},
    "conversion_value": {"name": "转化价值", "max": 10, "desc": "引导关注/收藏/购买"},
    "risk_control": {"name": "风险控制", "max": 10, "desc": "版权/夸大/敏感词"},
}


class ScoringEngine:
    """评分规则引擎"""
    
    def __init__(self, llm_client=None):
        self.llm_client = llm_client
    
    def score_topics(self, topics: list, top_n: int = 3) -> list:
        """评分并排序，返回Top N"""
        scored = []
        for i, topic in enumerate(topics):
            score_result = self._score_single(topic, topic_id=i+1)
            scored.append(score_result)
        
        scored.sort(key=lambda x: x.total, reverse=True)
        for rank, item in enumerate(scored, 1):
            item.rank = rank
        
        return scored[:top_n]
    
    def score_all(self, topics: list) -> list:
        """评分所有选题（不截断）"""
        return self.score_topics(topics, top_n=len(topics))
    
    def _score_single(self, topic: dict, topic_id: int) -> TopicScore:
        try:
            scores = self._llm_score(topic)
        except Exception:
            scores = self._heuristic_score(topic)
        
        total = sum(scores.values())
        return TopicScore(
            topic_id=topic_id, title=topic.get("title", ""),
            scores=scores, total=total,
            reason=self._generate_reason(scores),
            recommendation=self._recommend_platform(scores, topic.get("platform", ""))
        )
    
    def _llm_score(self, topic: dict) -> dict:
        if not self.llm_client:
            raise ValueError("LLM客户端未配置")
        
        prompt = f"""你对以下短视频选题进行100分制评分：

标题：{topic.get('title', '')}
前3秒钩子：{topic.get('hook_3sec', '')}
目标受众：{topic.get('audience', '')}
推荐平台：{topic.get('platform', '')}
预期价值：{topic.get('value', '')}
详细说明：{topic.get('description', '')}

请打分：
1. 钩子强度（0-20）：前3秒能否让人停下来
2. 观点清晰度（0-20）：能否一句话说明白
3. 受众明确度（0-15）：是否清楚谁会看
4. 平台匹配度（0-15）：是否适合推荐的平台
5. 素材可用度（0-10）：是否有足够的画面支撑
6. 转化价值（0-10）：能否引导关注/收藏
7. 风险控制（0-10）：是否有版权/敏感词问题

输出JSON：{{"hook_strength": 15, "viewpoint_clarity": 18, "audience_clarity": 12, "platform_fit": 14, "material_availability": 8, "conversion_value": 9, "risk_control": 10}}
"""
        
        response = self.llm_client.generate(
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        
        match = re.search(r'\{[^{}]*"hook_strength"[^{}]*\}', response, re.DOTALL)
        if match:
            data = json.loads(match.group(0))
            return {k: data.get(k, 0) for k in DIMENSIONS.keys()}
        
        raise ValueError(f"无法解析评分响应")
    
    def _heuristic_score(self, topic: dict) -> dict:
        """启发式评分（无LLM时回退）"""
        title = topic.get("title", "")
        hook = topic.get("hook_3sec", "")
        audience = topic.get("audience", "")
        description = topic.get("description", "")
        value = topic.get("value", "")
        
        s = {}
        
        # 钩子强度
        hook_len = len(hook.strip())
        s["hook_strength"] = 14 if 10 <= hook_len <= 50 else (8 if hook_len < 10 else 12)
        emotion_words = ['震惊', '竟然', '秘密', '真相', '为什么', '如何', '必须', '关键', '最强']
        if any(w in hook for w in emotion_words):
            s["hook_strength"] = min(s["hook_strength"] + 4, 20)
        
        # 观点清晰度
        s["viewpoint_clarity"] = 16 if len(title) <= 20 else 12
        
        # 受众明确度
        s["audience_clarity"] = 12 if audience and len(audience) > 5 else (8 if audience else 5)
        
        # 平台匹配度
        s["platform_fit"] = 13 if topic.get("platform") else 8
        
        # 素材可用度
        s["material_availability"] = 8 if description and len(description) > 50 else 5
        
        # 转化价值
        s["conversion_value"] = 8 if value and len(value) > 10 else 5
        
        # 风险控制
        s["risk_control"] = 9
        
        return s
    
    def _generate_reason(self, scores: dict) -> str:
        total = sum(scores.values())
        max_score = sum(d["max"] for d in DIMENSIONS.values())
        pct = total / max_score * 100
        level = "优秀" if pct >= 80 else ("良好" if pct >= 60 else ("一般" if pct >= 40 else "需改进"))
        
        max_dim = max(scores, key=scores.get)
        min_dim = min(scores, key=scores.get)
        
        parts = [f"整体评价：{level}（{total}/{max_score}分）"]
        if scores[max_dim] > 10:
            parts.append(f"优势：{DIMENSIONS[max_dim]['name']}得分突出")
        if scores[min_dim] < 5:
            parts.append(f"不足：{DIMENSIONS[min_dim]['name']}得分偏低")
        
        return "；".join(parts)
    
    def _recommend_platform(self, scores: dict, suggested: str) -> str:
        if scores.get("material_availability", 0) >= 8:
            return "视频平台（YouTube Shorts/TikTok）"
        if scores.get("conversion_value", 0) >= 8:
            return "社交平台（小红书/X）"
        return suggested if suggested else "根据内容类型推荐"
    
    def format_scores(self, scored_topics: list) -> str:
        """格式化评分结果为可读文本"""
        lines = []
        lines.append("=" * 40)
        lines.append("评分报告")
        lines.append("=" * 40 + "\n")
        
        for item in scored_topics:
            lines.append(f"排名 #{item.rank}: {item.title}")
            lines.append(f"总分: {item.total}/100")
            lines.append(f"理由: {item.reason}")
            lines.append(f"推荐平台: {item.recommendation}")
            for dim_name, dim_info in DIMENSIONS.items():
                score = item.scores.get(dim_name, 0)
                bar = "#" * int(score / dim_info["max"] * 10)
                lines.append(f"  {dim_info['name']:12s} [{bar:<10}] {score}/{dim_info['max']}")
            lines.append("")
        
        return "\n".join(lines)


def score_topics(topics: list, top_n: int = 3, llm_client=None) -> list:
    """便捷函数：对选题评分"""
    engine = ScoringEngine(llm_client=llm_client)
    return engine.score_topics(topics, top_n=top_n)
