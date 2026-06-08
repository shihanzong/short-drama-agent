"""Visual Designer Agent - Character consistency, scene generation, storyboard creation."""

import os
import json
from typing import Optional, Dict, List
from modules.llm_client import LLMClient
from modules.comfyui_client import ComfyUIClient


class VisualDesignerAgent:
    """Generates character images, scene images, and storyboards."""

    SYSTEM_PROMPT = """你是短剧视觉设计专家。精通角色形象设计、场景构图、分镜设计。

设计原则:
1. 角色一致性是最重要的 - 同一角色所有画面必须保持同一张脸
2. 竖屏9:16构图
3. 画面要有电影感，光影层次丰富
4. 每个场景的情绪要能通过画面传达
5. 分镜要考虑镜头语言和观众视角"""

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        comfyui_client: Optional[ComfyUIClient] = None,
    ):
        self.llm = llm_client or LLMClient()
        self.comfyui = comfyui_client or ComfyUIClient()

    def generate_character_prompt(
        self,
        character: Dict,
        style: str = "cinematic realistic",
    ) -> Dict:
        """Generate ComfyUI-ready prompts for a character.

        Returns positive prompt, negative prompt, and style tags.
        """
        name = character.get("name", "character")
        appearance = character.get("appearance", {})
        personality = character.get("personality", {})

        # Build appearance description
        traits = ", ".join(personality.get("traits", []))
        face = appearance.get("face_description", "")
        hair = appearance.get("hair", "")
        clothing = appearance.get("clothing_style", "")

        positive = f"1person, {name}, {face}, {hair}, {clothing}, {traits}, looking at camera, portrait"
        negative = "ugly, deformed, noisy, blurry, extra limbs, bad anatomy"

        # Style-specific prompt parts
        style_prompts = {
            "cinematic_realistic": "cinematic lighting, film grain, realistic skin texture, depth of field, 85mm portrait lens",
            "anime": "anime style, cel shading, clean lines, vibrant colors",
            "noir": "film noir, high contrast, black and white, dramatic shadows",
            "webtoon": "Korean webtoon style, digital art, soft colors, clean illustration",
        }
        style_part = style_prompts.get(style, style_prompts["cinematic_realistic"])

        return {
            "positive": f"{positive}, {style_part}",
            "negative": negative,
            "style_tags": style,
            "reference_description": f"Portrait of {name}: {face}, {hair}, {clothing}. Personality: {traits}.",
        }

    def generate_scene_description(
        self,
        scene_outline: Dict,
        style: str = "cinematic realistic",
    ) -> Dict:
        """Convert a scene outline into a detailed image generation prompt."""
        location = scene_outline.get("location", "")
        time_of_day = scene_outline.get("time_of_day", "白天")
        summary = scene_outline.get("summary", "")
        emotion = scene_outline.get("emotional_tone", "")

        time_mapping = {
            "白天": "bright daylight, clear sky",
            "夜晚": "night time, moonlight, dark atmosphere",
            "黄昏": "golden hour, sunset, warm lighting",
            "黎明": "dawn, soft morning light, misty",
        }
        time_desc = time_mapping.get(time_of_day, time_mapping["白天"])

        emotion_mapping = {
            "紧张": "tense atmosphere, dramatic lighting, shadows",
            "悲伤": "melancholic, cool tones, rain, somber mood",
            "甜蜜": "warm lighting, soft focus, pink and gold tones",
            "愤怒": "intense red lighting, sharp shadows, aggressive angle",
            "悬疑": "mysterious, dimly lit, fog, noir atmosphere",
        }
        emotion_desc = emotion_mapping.get(emotion, "")

        style_prompts = {
            "cinematic_realistic": "cinematic shot, realistic photography, film lighting",
            "anime": "anime scene, beautiful background art, vibrant colors",
            "webtoon": "webtoon panel style, clean illustration, digital art",
        }
        style_desc = style_prompts.get(style, style_prompts["cinematic_realistic"])

        positive = f"{summary}, {location}, {time_desc}, {emotion_desc}, {style_desc}, vertical composition, 9:16"
        negative = "ugly, deformed, noisy, blurry, horizontal, watermark, text"

        return {
            "positive": positive,
            "negative": negative,
            "scene_summary": summary,
            "scene_location": location,
        }

    def generate_storyboard(
        self,
        script_text: str,
        character_cards: List[Dict],
        style: str = "cinematic_realistic",
    ) -> Dict:
        """Create a storyboard from a script.

        Args:
            script_text: The script markdown text.
            character_cards: Character cards.
            style: Visual style preset.

        Returns:
            Storyboard dict with shot descriptions and prompts.
        """
        prompt = f"""请根据以下短剧剧本生成详细的分镜脚本。

剧本:
{script_text[:3000]}...

角色:
{json.dumps([c.get("protagonist", {}) for c in character_cards], ensure_ascii=False, indent=2)}

视觉风格: {style}

请生成{style}风格的竖屏分镜，每个镜头包含:
- 镜头编号
- 镜头类型 (特写/close-up/中景/全景/俯拍/仰拍)
- 画面描述
- 对应的ComfyUI生成提示词
- 运镜方向
- 时长(秒)
- 情绪

输出JSON格式: {{"storyboard": [{"shot_number": 1, "shot_type": "", "description": "", "prompt": "", "duration_seconds": 4, "emotional_tone": ""}]}}"""

        try:
            result = self.llm.chat_structured(prompt, self.SYSTEM_PROMPT)
            return result.get("storyboard", [])
        except Exception:
            return self._generate_fallback_storyboard(script_text, character_cards)

    def _generate_fallback_storyboard(
        self, script: str, chars: List[Dict]
    ) -> List[Dict]:
        """Fallback storyboard without LLM."""
        hero_name = (chars[0].get("protagonist", {}).get("name", "主角") if chars else "主角")
        return [
            {
                "shot_number": 1,
                "shot_type": "close-up",
                "description": f"{hero_name}的面部特写，表情坚定",
                "prompt": "1person, close-up portrait, determined expression, cinematic lighting, 9:16 vertical",
                "duration_seconds": 4,
                "emotional_tone": "坚定",
            },
            {
                "shot_number": 2,
                "shot_type": "medium",
                "description": "中景，{hero_name}与对手对话",
                "prompt": "medium shot, 2people talking, dramatic lighting, 9:16 vertical",
                "duration_seconds": 6,
                "emotional_tone": "紧张",
            },
        ]

    def generate_character_consistency_set(
        self,
        character: Dict,
        outputs_dir: str,
        variations: int = 4,
    ) -> List[str]:
        """Generate a set of character consistency reference images.

        Generates multiple poses/expressions to maintain character consistency
        across all scenes. Uses ComfyUI for image generation.
        """
        prompts = self.generate_character_prompt(character)
        os.makedirs(outputs_dir, exist_ok=True)

        generated_files = []
        try:
            for i in range(variations):
                variation_prompts = {
                    "prompt": prompts["positive"],
                    "negative_prompt": prompts["negative"],
                    "seed": -1,
                    "steps": 20,
                    "cfg": 7.0,
                    "width": 576,
                    "height": 1024,
                }
                result = self.comfyui.generate_from_prompt(
                    prompt=prompts["positive"],
                    negative_prompt=prompts["negative"],
                    output_dir=outputs_dir,
                    **variation_prompts,
                )
                if result:
                    generated_files.append(result)
        except Exception as e:
            print(f"  [VisualDesigner] ComfyUI generation failed: {e}")
            print("  [VisualDesigner] Skipping image generation. Character reference will use text prompts only.")

        return generated_files

    def run(
        self,
        episode_script: str,
        character_cards: List[Dict],
        style: str = "cinematic_realistic",
        output_dir: str = "output",
    ) -> Dict:
        """Run full visual design pipeline for an episode.

        Returns storyboard, character reference images, and scene images.
        """
        print(f"  [VisualDesigner] Generating storyboard...")
        storyboard = self.generate_storyboard(episode_script, character_cards, style)

        # Generate character consistency references
        char_ref_dir = os.path.join(output_dir, "character_refs")
        ref_images = []
        for card in character_cards:
            char_data = card.get("protagonist", card)
            ref_dir = os.path.join(char_ref_dir, char_data.get("name", "char"))
            refs = self.generate_character_consistency_set(char_data, ref_dir)
            ref_images.extend(refs)

        return {
            "storyboard": storyboard,
            "character_references": ref_images,
            "style": style,
        }
