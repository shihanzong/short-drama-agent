"""Publisher Agent - Multi-platform publishing,封面生成, data tracking."""

import os
import json
from typing import Optional, Dict, List
from modules.llm_client import LLMClient


class PublisherAgent:
    """Handles publishing to multiple platforms and data tracking."""

    SYSTEM_PROMPT = """你是短视频运营专家。精通抖音、快手、视频号等平台的发布规则、流量玩法、爆款公式。

运营原则:
1. 标题要有数字+悬念+利益点
2. 封面要吸睛，人物面部要清晰
3. 发布时间: 抖音6-8pm、快手7-9pm、视频号9-11am
4. 标签: 3-5个精准标签，不要堆砌
5. 描述要引导评论互动"""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm = llm_client or LLMClient()

    def generate_cover_prompt(
        self,
        episode_title: str,
        characters: List[Dict],
    ) -> Dict:
        """Generate a prompt for creating an eye-catching cover image.

        Returns ComfyUI-ready prompt and text overlay info.
        """
        hero_name = (characters[0].get("protagonist", {}).get("name", "主角") if characters else "")
        genre = characters[0].get("genre", "") if characters else ""

        cover_text = f"第1集\n{episode_title}"

        prompt = f"""Generate a short drama cover image.
Title overlay: {cover_text}
Main character: {hero_name}
Genre: {genre}

Requirements:
- Vertical 9:16 format
- Main character face clearly visible and prominent
- Bold title text at top or bottom
- Dramatic lighting, high contrast
- Eye-catching composition for short video platform

Positive prompt:
portrait, {hero_name}, dramatic lighting, high contrast, vertical composition, short drama cover, bold title text area at bottom, 9:16, cinematic quality

Negative prompt:
ugly, deformed, noisy, blurry, horizontal, landscape"""

        return {
            "prompt": prompt,
            "cover_text": cover_text,
            "character_name": hero_name,
        }

    def generate_titles_and_captions(
        self,
        genre: str,
        episode_outlines: List[Dict],
        platform: str = "douyin",
    ) -> Dict:
        """Generate titles, captions, and tags for each episode.

        Returns a dict with titles, descriptions, and tags per episode.
        """
        prompt = f"""请为{genre}题材短剧生成每集的标题、文案和标签。

共{len(episode_outlines)}集，每集输出:
{{
  "titles": ["爆款标题1", "爆款标题2", "爆款标题3"],
  "description": "引流描述文案(50-100字)",
  "tags": ["标签1", "标签2", "标签3", "标签4"],
  "cover_text": "封面文字(简短有力，2-6字)"
}}

标题公式: 数字+悬念+情绪+利益点
示例: "重生回到订婚宴，我反手甩了她一巴掌！"

请为每一集生成3个标题选项、1个描述、4个标签。

输出JSON: {{"episodes": [...]}}"""

        try:
            result = self.llm.chat_structured(prompt)
            return result.get("episodes", [])
        except Exception:
            return self._generate_fallback_captions(genre, episode_outlines)

    def _generate_fallback_captions(
        self, genre: str, outlines: List[Dict]
    ) -> List[Dict]:
        """Fallback captions without LLM."""
        results = []
        for i, outline in enumerate(outlines):
            results.append({
                "episode": i + 1,
                "titles": [
                    f"{outline.get('title', '短剧')} | {genre}",
                    f"第{i+1}集 {genre}高能场面",
                    f"{genre}第{i+1}集 - 太爽了！",
                ],
                "description": f"推荐这部{genre}短剧第{i+1}集！{outline.get('cliffhanger', '')}",
                "tags": [genre, "短剧", "追剧", f"第{i+1}集"],
                "cover_text": f"第{i+1}集",
            })
        return results

    def get_platform_adaptation(
        self,
        video_path: str,
        platform: str = "douyin",
    ) -> Dict:
        """Get platform-specific adaptation requirements.

        Returns resolution, duration limits, format requirements.
        """
        platform_configs = {
            "douyin": {
                "resolution": "1080x1920",
                "max_duration": 600,
                "format": "mp4",
                "codec": "h264",
                "max_file_size_mb": 500,
                "thumbnail": "9:16 portrait",
            },
            "kuaishou": {
                "resolution": "1080x1920",
                "max_duration": 300,
                "format": "mp4",
                "codec": "h264",
                "max_file_size_mb": 200,
                "thumbnail": "9:16 portrait",
            },
            "wechat_video": {
                "resolution": "1080x1920",
                "max_duration": 600,
                "format": "mp4",
                "codec": "h264",
                "max_file_size_mb": 1000,
                "thumbnail": "9:16 portrait",
            },
            "youtube_shorts": {
                "resolution": "1080x1920",
                "max_duration": 60,
                "format": "mp4",
                "codec": "h264",
                "max_file_size_mb": 100,
                "thumbnail": "9:16 portrait",
            },
        }
        return platform_configs.get(platform, platform_configs["douyin"])

    def generate_publish_report(
        self,
        drama_id: str,
        genre: str,
        total_episodes: int,
        platforms: List[str],
        video_paths: List[str],
    ) -> str:
        """Generate a publishing checklist and schedule report."""
        titles = []
        for platform in platforms:
            config = self.get_platform_adaptation(None, platform)
            titles.append(f"- {platform}: {config['resolution']} | 最大{config['max_duration']}秒 | {config['format']}")

        report = f"""# 短剧发布报告

## 基本信息
- 剧名: {drama_id}
- 题材: {genre}
- 总集数: {total_episodes}
- 视频路径: {", ".join(video_paths)}

## 平台适配
{chr(10).join(titles)}

## 发布时间建议
- 抖音: 18:00 - 20:00
- 快手: 19:00 - 21:00
- 视频号: 09:00 - 11:00
- YouTube Shorts: 12:00 - 14:00

## 发布清单
- [ ] 确认视频格式符合要求
- [ ] 准备封面图
- [ ] 准备标题文案
- [ ] 准备标签
- [ ] 按时间表发布
- [ ] 发布后30分钟内回复评论
"""
        return report

    def run(
        self,
        genre: str,
        episode_outlines: List[Dict],
        video_paths: List[str],
        platforms: List[str] = None,
        drama_id: str = "episode_001",
    ) -> Dict:
        """Run the full publishing pipeline."""
        platforms = platforms or ["douyin"]

        print(f"  [Publisher] Generating titles and captions...")
        captions = self.generate_titles_and_captions(genre, episode_outlines, platforms[0])

        print(f"  [Publisher] Generating publishing report...")
        report = self.generate_publish_report(
            drama_id, genre, len(episode_outlines), platforms, video_paths
        )

        return {
            "captions": captions,
            "publishing_report": report,
            "platforms": platforms,
            "video_paths": video_paths,
        }
