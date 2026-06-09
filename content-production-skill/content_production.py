#!/usr/bin/env python3
"""
内容生产主程序 - Content Production Pipeline

固定SOP流程：
1. 读取素材（YouTube/本地/文字稿）
2. 提取内容信号
3. 生成选题（5-10个）
4. 评分筛选Top 3
5. 生成脚本/配音稿/分镜
6. 生成多平台文案
7. 人工确认
8. 生成推送卡片
"""

import json
from pathlib import Path
from datetime import datetime

SKILL_ROOT = Path(__file__).parent
MODULES_DIR = SKILL_ROOT / 'modules'

# 确保modules在路径中
import sys
if str(MODULES_DIR.parent) not in sys.path:
    sys.path.insert(0, str(MODULES_DIR.parent))


class ContentProductionPipeline:
    """内容生产流水线
    
    按固定流程处理长内容素材，生成可发布的内容资产。
    """
    
    def __init__(self, llm_client=None, approval_dir: str = None):
        """
        Args:
            llm_client: LLM客户端
            approval_dir: 确认记录目录
        """
        self.llm_client = llm_client
        self.approval_dir = approval_dir
        
        # 初始化子模块
        from modules.signal_extractor import ContentSignalExtractor
        from modules.scoring_engine import ScoringEngine
        from modules.platform_copy_generator import PlatformCopyGenerator
        from modules.approval_workflow import ApprovalWorkflow
        from modules.video_transcriber import VideoTranscriber
        from modules.notification_card import NotificationCard
        
        self.signal_extractor = ContentSignalExtractor(llm_client=llm_client)
        self.scoring_engine = ScoringEngine(llm_client=llm_client)
        self.copy_generator = PlatformCopyGenerator(llm_client=llm_client)
        self.approval_workflow = ApprovalWorkflow(approval_dir=approval_dir)
        self.transcriber = VideoTranscriber()
        self.notification = NotificationCard()
        
        # 产出目录
        self.output_dir = SKILL_ROOT / 'outputs'
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def run(self, text: str, topic: str = "", source: str = "",
            target_platforms: list = None, top_n: int = 3) -> dict:
        """
        执行完整的内容生产流水线
        
        Args:
            text: 原始长文本素材
            topic: 素材主题
            source: 素材来源
            target_platforms: 目标平台列表，None=全部
            top_n: 保留Top N个选题
            
        Returns:
            完整产出结果
        """
        print("=" * 50)
        print("内容生产流水线启动")
        print(f"主题: {topic or '未指定'}")
        print(f"来源: {source or '未指定'}")
        print(f"输入长度: {len(text)} 字符")
        print("=" * 50)
        
        result = {
            "topic": topic,
            "source": source,
            "timestamp": datetime.now().isoformat(),
            "status": "running",
            "steps": {}
        }
        
        # Step 1: 提取内容信号
        print("\n[Step 1/6] 提取内容信号...")
        signals = self.signal_extractor.extract(text, topic=topic, source=source)
        result["steps"]["signals"] = signals
        signal_count = signals.get("meta", {}).get("signal_count", 0)
        print(f"  提取到 {signal_count} 条内容信号")
        
        # Step 2: 保存信号
        signals_file = self.signal_extractor.save_results(signals)
        result["steps"]["signals_file"] = signals_file
        
        # Step 3: 生成选题
        print("\n[Step 2/6] 生成选题...")
        topics = self._generate_topics(signals, topic)
        result["steps"]["topics"] = topics
        print(f"  生成 {len(topics)} 个选题")
        
        # Step 4: 评分筛选
        print("\n[Step 3/6] 评分筛选...")
        scored_topics = self.scoring_engine.score_topics(topics, top_n=top_n)
        result["steps"]["scored_topics"] = [
            {"title": t.title, "total": t.total, "rank": t.rank,
             "scores": t.scores, "reason": t.reason,
             "recommendation": t.recommendation}
            for t in scored_topics
        ]
        print(f"  Top {top_n} 选题已筛选")
        for t in scored_topics:
            print(f"    #{t.rank} {t.title} ({t.total}/100)")
        
        # Step 5: 生成脚本/分镜/文案
        print("\n[Step 4/6] 生成脚本和文案...")
        copy_results = {}
        scripts = {}
        
        for topic_item in scored_topics:
            title = topic_item.title
            print(f"\n  处理选题: {title}")
            
            # 生成脚本
            script = self._generate_script(topic_item, text)
            scripts[title] = script
            
            # 生成多平台文案
            copies = self.copy_generator.generate_for_platforms(
                {"title": title, "description": topic_item.reason},
                scripts=script,
                platforms=target_platforms
            )
            copy_results[title] = copies
        
        result["steps"]["scripts"] = scripts
        result["steps"]["copies"] = copy_results
        
        # Step 6: 保存产出
        print("\n[Step 5/6] 保存产出...")
        output_file = self._save_output(result)
        result["output_file"] = output_file
        
        # Step 7: 创建确认会话
        print("\n[Step 6/6] 创建确认流程...")
        session = self.approval_workflow.create_session(topic=topic or "未指定", source=source)
        result["approval_session"] = session["session_id"]
        
        result["status"] = "completed"
        result["message"] = "内容生产流水线完成，等待人工确认"
        
        # 生成推送卡片
        card_data = self.notification.generate_action_card(
            topic_info={"raw_material": topic, "raw_source": source},
            score_info={"top_topics": [
                {"title": t.title, "score": f"{t.total}/100",
                 "platform": t.recommendation, "reason": t.reason}
                for t in scored_topics
            ]},
            material_list=["素材截图", "封面图"],
            next_steps=["人工确认选题", "撰写脚本", "录制配音", "发布"]
        )
        result["notification_card"] = card_data
        print("\n" + self.notification.format_human_readable(card_data))
        
        print("\n" + "=" * 50)
        print("流水线完成！产出已保存到:", output_file)
        print("确认会话ID:", session["session_id"])
        print("=" * 50)
        
        return result
    
    def _generate_topics(self, signals: dict, topic: str) -> list:
        """基于内容信号生成选题"""
        if self.llm_client:
            prompt = f"""基于以下内容信号，生成6个短视频选题。

主题：{topic}

内容信号：
- 核心观点：{signals.get('core_viewpoints', [])}
- 关键案例：{signals.get('key_cases', [])}
- 金句：{signals.get('golden_quotes', [])}
- 冲突点：{signals.get('conflict_points', [])}
- 数字数据：{signals.get('key_numbers', [])}

每个选题必须包含：
- title（标题，不超过20字）
- audience（目标受众）
- hook_3sec（前3秒钩子）
- platform（推荐平台：小红书/X/YouTube/TikTok/公众号）
- value（预期价值）
- description（选题说明，100字内）
- signal_source（引用的信号类型）

输出JSON数组：[{{"title": "...", "audience": "...", "hook_3sec": "...", "platform": "...", "value": "...", "description": "...", "signal_source": []}}]

要求：每个选题角度不同，标题要吸引人。"""
            
            try:
                response = self.llm_client.generate(
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"}
                )
                import re
                match = re.search(r'\[[^]]*\]', response, re.DOTALL)
                if match:
                    return json.loads(match.group(0))
            except:
                pass
        
        # 回退：生成基础选题
        return [
            {"title": f"{topic}：核心观点解读", "audience": "对{topic}感兴趣的人",
             "hook_3sec": "你知道吗？关于这件事，90%的人都搞错了",
             "platform": "小红书", "value": "帮助理解核心观点",
             "description": f"解读{topic}的核心观点，提供实用建议",
             "signal_source": ["核心观点"]},
            {"title": f"{topic}：案例深度分析", "audience": "行业从业者",
             "hook_3sec": "一个真实案例告诉你为什么这个很重要",
             "platform": "YouTube", "value": "深度案例分析",
             "description": f"通过具体案例深入分析{topic}",
             "signal_source": ["关键案例"]},
            {"title": f"{topic}：争议话题讨论", "audience": "关注争议的读者",
             "hook_3sec": "这件事引发了巨大争议，你站在哪一边",
             "platform": "X", "value": "引发讨论和转发",
             "description": f"围绕{topic}的争议点进行讨论",
             "signal_source": ["冲突点"]}
        ]
    
    def _generate_script(self, topic_item, source_text: str) -> dict:
        """生成脚本、配音稿、分镜"""
        if self.llm_client:
            prompt = f"""为选题【{topic_item.title}】生成：

1. 60秒短视频脚本（表格格式：时间码|画面描述|配音文本|素材需求|音效）
2. 配音稿（口语化，标注语气和停顿）
3. 分镜表（镜号|时间码|画面|景别|运镜|字幕|素材类型|音效）

选题信息：{topic_item.reason}
相关内容信号：{topic_item.scores}

输出JSON：{{"script": "脚本内容", "voiceover": "配音稿内容", "storyboard": "分镜内容"}}"""
            
            try:
                response = self.llm_client.generate(
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"}
                )
                import re
                match = re.search(r'\{[^{}]*"script"[^{}]*\}', response, re.DOTALL)
                if match:
                    return json.loads(match.group(0))
            except:
                pass
        
        return {
            "script": f"[脚本] {topic_item.title}\n\n（需要LLM支持才能生成完整脚本）",
            "voiceover": f"[配音稿] {topic_item.title}\n\n（需要LLM支持）",
            "storyboard": f"[分镜表] {topic_item.title}\n\n（需要LLM支持）"
        }
    
    def _save_output(self, result: dict) -> str:
        """保存完整产出到文件"""
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"content_production_{ts}.json"
        filepath = self.output_dir / filename
        filepath.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        return str(filepath)


def run_content_production(text: str, topic: str = "", source: str = "",
                            llm_client=None, target_platforms: list = None,
                            top_n: int = 3, approval_dir: str = None) -> dict:
    """便捷函数：运行内容生产流水线"""
    pipeline = ContentProductionPipeline(llm_client=llm_client, approval_dir=approval_dir)
    return pipeline.run(text, topic=topic, source=source,
                       target_platforms=target_platforms, top_n=top_n)
