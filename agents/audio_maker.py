"""Audio Maker Agent - TTS dialogue, BGM generation, sound effects."""

import os
import re
import json
from typing import Optional, Dict, List
from modules.llm_client import LLMClient
from modules.tts_engine import TTSEngine


class AudioMakerAgent:
    """Generates dialogue audio, background music, and sound effects."""

    SYSTEM_PROMPT = """你是短剧音效设计专家。擅长为短剧匹配最佳BGM、设计音效、控制节奏。

设计原则:
1. 每集开场用音乐快速建立氛围(5秒内)
2. 冲突场景用快节奏音乐+低频音效
3. 情感场景用舒缓旋律
4. 转折点用突然静音制造张力
5. 每集结尾用悬念音乐"""

    BGM_MOOD_MAP = {
        "紧张": {"prompt": "tense suspense music, low strings, heartbeat rhythm, dark atmosphere", "bpm": 100},
        "悲伤": {"prompt": "melancholic piano, slow tempo, minor key, emotional", "bpm": 60},
        "甜蜜": {"prompt": "sweet romantic acoustic guitar, light piano, warm mood", "bpm": 90},
        "愤怒": {"prompt": "intense dramatic percussion, orchestral stabs, aggressive", "bpm": 130},
        "悬疑": {"prompt": "mysterious ambient, subtle synth, tension building", "bpm": 80},
        "喜悦": {"prompt": "upbeat happy pop, major key, bright melody", "bpm": 120},
        "转折": {"prompt": "surprise sting, orchestral hit, dramatic pause", "bpm": 70},
    }

    def __init__(self, llm_client: Optional[LLMClient] = None, tts_engine: Optional[TTSEngine] = None):
        self.llm = llm_client or LLMClient()
        self.tts = tts_engine or TTSEngine()

    def detect_gender_from_name(self, name: str) -> str:
        """Heuristic gender detection from Chinese character names."""
        female_chars = ["婉", "柔", "晴", "瑶", "雪", "琳", "芳", "静", "雅", "婷", "娜", "丽", "娟", "美", "萍", "霞", "燕", "蓉", "芬", "红", "艳", "婷", "欣", "怡", "悦", "涵", "萱", "梦", "若", "诗", "韵", "露", "冰", "莹", "晶", "瑶", "璇"]
        male_chars = ["承", "泽", "廷", "震", "浩", "伟", "强", "军", "磊", "峰", "刚", "勇", "明", "志", "建国", "国", "龙", "飞", "鹏", "天", "宇", "轩", "辰", "晨", "阳", "凯", "杰", "斌", "涛", "鑫", "瑞", "霖", "锋", "杰", "昊", "霆", "峻", "恒", "然", "哲", "豪", "博", "睿", "景"]
        for ch in female_chars:
            if ch in name:
                return "female"
        for ch in male_chars:
            if ch in name:
                return "male"
        return "female"  # default

    def build_voice_map(self, character_cards: List[Dict]) -> Dict[str, str]:
        """Build character name -> voice mapping from character cards."""
        voice_map = {}
        for card in character_cards:
            hero = card.get("protagonist", {})
            villain = card.get("antagonist", {})
            ally = card.get("ally", {})

            for person in [hero, villain, ally]:
                name = person.get("name", "")
                if not name:
                    continue
                gender = person.get("gender", "")
                voice_map[name] = self.tts.map_voice_for_character(name, gender)

        return voice_map

    def extract_dialogue_lines(self, script_text: str) -> List[Dict]:
        """Extract dialogue lines from a script markdown.

        Parses the standard format: [角色名]: [对白内容]
        or: 角色名: [对白内容]
        Returns list of dicts with character, text, emotion.
        """
        lines = []
        emotion_pattern = re.compile(r"\(情绪提示:\s*([^)]+)\)")

        current_char = ""
        current_line = ""
        current_emotion = ""

        for raw_line in script_text.split("\n"):
            line = raw_line.strip()
            if not line:
                continue

            # Skip section headers and rules
            if line.startswith("#") or line.startswith("---") or line.startswith("## "):
                if current_char and current_line:
                    lines.append({
                        "character": current_char,
                        "text": current_line,
                        "emotion": current_emotion or "neutral",
                    })
                    current_char = ""
                    current_line = ""
                    current_emotion = ""
                continue

            # Skip markdown bold patterns like **场景描述** or **场景描述**: xxx
            if line.startswith("**") and line.endswith("**"):
                if current_char and current_line:
                    lines.append({
                        "character": current_char,
                        "text": current_line,
                        "emotion": current_emotion or "neutral",
                    })
                    current_char = ""
                    current_line = ""
                    current_emotion = ""
                continue

            if line.startswith("**") and ":" in line:
                # Bold field like **场景描述**: 内容 -> skip, don't match as dialogue
                continue

            # Check for emotion tag
            emotion_match = emotion_pattern.search(line)
            if emotion_match:
                current_emotion = emotion_match.group(1).strip()
                continue

            # Check for action/description patterns (various formats)
            # Format: (动作描述: xxx) or [动作描述]: xxx or [动作描述]: xxx]
            action_match = re.match(r"^(\[?\s*(?:动作描述|动作)\s*\]?\s*[：:]\s*(.+))$", line)
            if action_match:
                # Extract the actual description text (group 2)
                action_text = action_match.group(2).strip()
                if current_char:
                    current_line += " [" + action_text[:20] + "]"
                continue

            # Check for (情绪提示: xxx) or (xxx) standalone on a line
            if re.match(r"^\(.*情绪提示.*\)$", line):
                continue

            # Check for standalone action: (xxx) without 情绪提示
            if re.match(r"^\(.*\)$", line) and not emotion_match and not action_match:
                # Action line - append context to current dialogue
                if current_char:
                    current_line += " [" + line.strip("()")[:20] + "]"
                continue

            # Check for dialogue pattern: [Character]: [Line] or Character: [Line]
            # Pattern 1: 角色名: (情绪提示: xxx) 对白
            # Pattern 2: 角色名: [动作描述: xxx] 对白
            # Pattern 3: 角色名: 对白内容
            # Pattern 4: [角色名]: 对白内容
            dialogue_match = re.match(r"^\[?([^\]:\(\n]+)\]?\s*[：:]\s*(.+)", line)

            if dialogue_match:
                # Flush previous line
                if current_char and current_line:
                    # Clean up the text
                    clean_text = re.sub(r"\s*\[[^\]]*\]\s*", "", current_line).strip()
                    if clean_text:
                        lines.append({
                            "character": current_char,
                            "text": clean_text,
                            "emotion": current_emotion or "neutral",
                        })

                current_char = dialogue_match.group(1).strip()
                remaining = dialogue_match.group(2).strip()

                # Remove action descriptions from the dialogue line
                clean_remaining = re.sub(r"\s*\[.*?\]\s*", "", remaining).strip()
                # Remove trailing "(情绪提示: xxx)" if already consumed above
                clean_remaining = re.sub(r"\s*\(情绪提示:[^)]*\)\s*$", "", clean_remaining).strip()

                current_line = clean_remaining
                current_emotion = ""
            else:
                # Action line or other — append as context hint
                if current_char and len(line) < 50:
                    current_line += " [" + line[:30] + "]"

        # Flush last line
        if current_char and current_line:
            clean_text = re.sub(r"\s*\[[^\]]*\]\s*", "", current_line).strip()
            if clean_text:
                lines.append({
                    "character": current_char,
                    "text": clean_text,
                    "emotion": current_emotion or "neutral",
                })

        return lines

    def generate_dialogue_audio(
        self,
        script_text: str,
        character_cards: List[Dict],
        episode_number: int = 1,
    ) -> List[str]:
        """Generate TTS audio files for all dialogue in a script.

        Returns:
            List of audio file paths.
        """
        lines = self.extract_dialogue_lines(script_text)
        if not lines:
            print("  [AudioMaker] No dialogue found in script.")
            return []

        # Build character voice mapping
        voice_map = self.build_voice_map(character_cards)

        # For any unmapped characters, use gender heuristic
        all_names = set()
        for card in character_cards:
            for role in ["protagonist", "antagonist", "ally"]:
                p = card.get(role, {})
                if p:
                    all_names.add((p.get("name", ""), p.get("gender", "")))

        print(f"  [AudioMaker] Generated voice map: {voice_map}")

        results = []
        for i, line in enumerate(lines):
            char_name = line["character"]
            gender = self.detect_gender_from_name(char_name)
            voice = voice_map.get(char_name, self.tts.map_voice_for_character(char_name, gender))

            # Skip non-dialogue items like "旁白" or "音效"
            if char_name in ("旁白", "音效", "画外音"):
                continue

            audio_path = os.path.join(
                self.tts.output_dir,
                f"ep{episode_number:03d}_c{char_name}_d{i}.mp3",
            )

            try:
                self.tts.synthesize(
                    text=line["text"],
                    voice=voice,
                    output_path=audio_path,
                )
                results.append(audio_path)
            except Exception as e:
                print(f"  [AudioMaker] TTS failed for '{char_name}' line {i}: {e}")

        print(f"  [AudioMaker] Generated {len(results)} audio files")
        return results

    def generate_bgm_plan(self, episode_script: str) -> List[Dict]:
        """Plan BGM sections for an episode based on emotional flow."""
        prompt = f"""请分析以下短剧剧本的情绪起伏，规划背景音乐。

{episode_script[:2000]}...

请规划BGM，格式:
{{
  "bgm_plan": [
    {{
      "start_time": 0,
      "end_time": 15,
      "mood": "紧张",
      "description": "开场音乐",
      "suno_prompt": "tense suspense music",
      "transition": "fade-in"
    }}
  ]
}}"""
        try:
            result = self.llm.chat_structured(prompt, self.SYSTEM_PROMPT)
            return result.get("bgm_plan", [])
        except Exception:
            return self._generate_fallback_bgm_plan(episode_script)

    def _generate_fallback_bgm_plan(self, script: str) -> List[Dict]:
        """Fallback BGM plan without LLM."""
        return [
            {"start_time": 0, "end_time": 15, "mood": "紧张", "description": "开场", "suno_prompt": self.BGM_MOOD_MAP["紧张"]["prompt"], "transition": "fade-in"},
            {"start_time": 30, "end_time": 90, "mood": "悬疑", "description": "推进", "suno_prompt": self.BGM_MOOD_MAP["悬疑"]["prompt"], "transition": "crossfade"},
            {"start_time": 120, "end_time": 160, "mood": "紧张", "description": "高潮", "suno_prompt": self.BGM_MOOD_MAP["紧张"]["prompt"], "transition": "cut"},
            {"start_time": 170, "end_time": 180, "mood": "悬疑", "description": "结尾", "suno_prompt": self.BGM_MOOD_MAP["悬疑"]["prompt"], "transition": "fade-out"},
        ]

    def run(
        self,
        script_text: str,
        character_cards: List[Dict],
        episode_number: int = 1,
    ) -> Dict:
        """Run the full audio pipeline for an episode.

        Returns dialogue audio files, BGM plan, and metadata.
        """
        print(f"  [AudioMaker] Extracting dialogue lines...")
        lines = self.extract_dialogue_lines(script_text)
        print(f"  [AudioMaker] Found {len(lines)} dialogue lines")

        print(f"  [AudioMaker] Generating TTS dialogue...")
        dialogue_audio = self.generate_dialogue_audio(
            script_text, character_cards, episode_number
        )

        print(f"  [AudioMaker] Planning BGM...")
        bgm_plan = self.generate_bgm_plan(script_text)

        return {
            "dialogue_lines": lines,
            "dialogue_audio": dialogue_audio,
            "bgm_plan": bgm_plan,
        }
