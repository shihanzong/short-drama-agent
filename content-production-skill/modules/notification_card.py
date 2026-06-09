#!/usr/bin/env python3
"""
团队推送卡片 - Team Notification Card
"""

import json
import urllib.request
from pathlib import Path
from datetime import datetime

SKILL_ROOT = Path(__file__).parent.parent


class NotificationCard:
    """团队推送卡片生成器"""
    
    def generate_action_card(self, topic_info: dict, score_info: dict,
                              material_list: list = None,
                              next_steps: list = None) -> dict:
        card = {
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M'),
            "raw_material": topic_info.get("raw_material", "未指定"),
            "raw_source": topic_info.get("raw_source", ""),
            "raw_url": topic_info.get("raw_url", ""),
            "top_topics": score_info.get("top_topics", []),
            "material_needed": material_list or [],
            "next_steps": next_steps or [],
            "risk_reminders": topic_info.get("risk_reminders", [])
        }
        return card
    
    def format_human_readable(self, card_data: dict) -> str:
        """生成人类可读的文本格式"""
        lines = []
        lines.append(f"📋 内容生产日报 - {card_data.get('timestamp', '')}")
        lines.append(f"📺 素材：{card_data.get('raw_material', 'N/A')}")
        if card_data.get('raw_url'):
            lines.append(f"   链接：{card_data['raw_url']}")
        lines.append("")
        
        for i, topic in enumerate(card_data.get("top_topics", []), 1):
            lines.append(f"🏆 Top {i}: {topic.get('title', 'N/A')}")
            lines.append(f"   评分：{topic.get('score', 'N/A')}")
            lines.append(f"   推荐平台：{topic.get('platform', 'N/A')}")
            lines.append(f"   理由：{topic.get('reason', 'N/A')}")
            lines.append("")
        
        if card_data.get("material_needed"):
            lines.append("📦 素材需求：")
            for item in card_data["material_needed"]:
                lines.append(f"  - {item}")
            lines.append("")
        
        if card_data.get("next_steps"):
            lines.append("🎯 下一步行动：")
            for step in card_data["next_steps"]:
                lines.append(f"  → {step}")
        
        return "\n".join(lines)
    
    def to_dingtalk_card(self, card_data: dict) -> dict:
        """转换为钉钉卡片格式"""
        topics_str = ""
        for i, topic in enumerate(card_data.get("top_topics", []), 1):
            topics_str += f"Top {i}: {topic.get('title', 'N/A')}\n"
            topics_str += f"评分：{topic.get('score', 'N/A')} | 平台：{topic.get('platform', 'N/A')}\n"
            topics_str += f"理由：{topic.get('reason', 'N/A')}\n\n"
        
        material_str = "\n".join([f"- {m}" for m in card_data.get("material_needed", [])])
        steps_str = "\n".join([f"→ {s}" for s in card_data.get("next_steps", [])])
        
        text = f"### 素材：{card_data.get('raw_material', 'N/A')}\n\n{topics_str}\n### 素材需求\n{material_str}\n\n### 下一步\n{steps_str}"
        
        return {
            "msgtype": "actionCard",
            "actionCard": {
                "title": f"📋 内容生产日报 - {card_data.get('timestamp', '')}",
                "text": text,
                "singleTitle": "查看详情",
                "singleURL": card_data.get("raw_url", "")
            }
        }
    
    def to_feishu_card(self, card_data: dict) -> dict:
        """转换为飞书卡片格式"""
        topics_text = "\n\n".join(
            [f"**Top {i+1}**: {t.get('title', 'N/A')}\n评分：{t.get('score', 'N/A')} | 平台：{t.get('platform', 'N/A')}"
             for i, t in enumerate(card_data.get("top_topics", []))]
        )
        
        return {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text",
                              "content": f"📋 内容生产日报 - {card_data.get('timestamp', '')}"},
                    "template": "blue"
                },
                "elements": [
                    {"tag": "div", "text": {"tag": "lark_md",
                             "content": f"**素材**：{card_data.get('raw_material', 'N/A')}"}},
                    {"tag": "hr"},
                    {"tag": "div", "text": {"tag": "lark_md", "content": f"**选题\n{topics_text}"}},
                    {"tag": "hr"},
                    {"tag": "div", "text": {"tag": "lark_md",
                             "content": f"**素材需求**\n{chr(10).join(['- ' + m for m in card_data.get('material_needed', [])])}"}},
                    {"tag": "hr"},
                    {"tag": "action", "actions": [{
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "查看详情"},
                        "type": "default",
                        "url": card_data.get("raw_url", "")
                    }]}
                ]
            }
        }
    
    def send_dingtalk(self, webhook_url: str, card_data: dict, timeout: int = 10) -> bool:
        """发送到钉钉"""
        try:
            card = self.to_dingtalk_card(card_data)
            data = json.dumps(card).encode('utf-8')
            req = urllib.request.Request(webhook_url, data=data,
                                        headers={'Content-Type': 'application/json'},
                                        method='POST')
            resp = urllib.request.urlopen(req, timeout=timeout)
            result = json.loads(resp.read().decode('utf-8'))
            return result.get("errcode") == 0
        except Exception as e:
            print(f"钉钉发送失败：{e}")
            return False
    
    def send_feishu(self, webhook_url: str, card_data: dict, timeout: int = 10) -> bool:
        """发送到飞书"""
        try:
            card = self.to_feishu_card(card_data)
            data = json.dumps(card).encode('utf-8')
            req = urllib.request.Request(webhook_url, data=data,
                                        headers={'Content-Type': 'application/json'},
                                        method='POST')
            resp = urllib.request.urlopen(req, timeout=timeout)
            result = json.loads(resp.read().decode('utf-8'))
            return result.get("code") == 0
        except Exception as e:
            print(f"飞书发送失败：{e}")
            return False


def create_notification_card(topic_info: dict, score_info: dict,
                              material_list: list = None,
                              next_steps: list = None) -> dict:
    card = NotificationCard()
    return card.generate_action_card(topic_info, score_info, material_list, next_steps)
