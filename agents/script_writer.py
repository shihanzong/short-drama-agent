"""Script Writer Agent - Converts episode outlines into standard short drama scripts."""

import os
import json
from typing import Optional, Dict, List
from modules.llm_client import LLMClient


class ScriptWriterAgent:
    """Writes and formats short drama scripts from episode outlines."""

    SYSTEM_PROMPT = """你是资深短剧编剧。精通竖屏短剧的剧本写作，深谙3分钟一集的节奏控制。

创作原则:
1. 每集开场3秒必须有钩子吸引观众
2. 对白简短口语化，每句不超过15字
3. 每集约600-800字，3-5个场景
4. 每集至少1个强冲突或反转
5. 每集结尾必须留悬念钩子
6. 多用动作和表情描述，少用旁白
7. 对白要有人物性格特征

输出格式: 标准短剧剧本格式"""

    SCRIPT_SYSTEM_PROMPT = """你是短剧剧本写作AI。严格按以下格式输出:

# 第X集: [标题]

## 场景[编号]: [地点] [白天/夜晚]
**场景描述**: [画面描述，1-2句]

[角色名]: [对白内容]
(情绪提示: [愤怒/委屈/得意...])

[动作描述]: [角色动作或表情]

---

每集控制在600-800字。对白要口语化、有冲突感。"""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm = llm_client or LLMClient()

    def write_episode_script(
        self,
        episode_outline: Dict,
        character_cards: List[Dict],
        previous_scripts: Optional[List[str]] = None,
    ) -> str:
        """Write a script for a single episode from its outline.

        Args:
            episode_outline: Episode outline dict.
            character_cards: Character cards.
            previous_scripts: Previous episode scripts for continuity.

        Returns:
            Formatted script text.
        """
        hero = (character_cards[0].get("protagonist", {}) if character_cards else {})
        villain = (character_cards[0].get("antagonist", {}) if character_cards else {})

        characters_info = f"""- 主角: {hero.get('name', '?')} ({hero.get('personality', '')}) - 口头禅: {hero.get('catchphrase', '')}
- 反派: {villain.get('name', '?')} - 动机: {villain.get('motivation', '')}"""

        scenes = episode_outline.get("scenes", [])
        scenes_info = "\n".join([
            f"- 场景{i+1}: [{s.get('location', '?')}] {s.get('time_of_day', '')} - {s.get('summary', '')}"
            for i, s in enumerate(scenes)
        ])

        # Previous episodes reference
        prev_ref = ""
        if previous_scripts:
            prev_ref = "上一集内容参考(保持连贯):\n" + "\n".join(previous_scripts[-2:])
        else:
            prev_ref = "无"

        prompt = f"""请为以下大纲编写完整的短剧剧本。

第{episode_outline.get('episode_number', '?')}集: {episode_outline.get('title', '')}
核心冲突: {episode_outline.get('conflict', '')}
结局悬念: {episode_outline.get('cliffhanger', '')}

人物:
{characters_info}

场景:
{scenes_info}

要求:
1. 每集3分钟，约600-800字
2. 开场3秒必须有钩子
3. 对白简短口语化(每句不超过15字)
4. 至少1个强冲突/反转
5. 每句对白后标注情绪提示
6. 包含动作和表情描述
7. 结尾留悬念

{prev_ref}

请输出完整剧本，使用标准短剧格式。"""

        try:
            return self.llm.generate_script(prompt, self.SCRIPT_SYSTEM_PROMPT)
        except Exception:
            return self._write_fallback_script(episode_outline, character_cards)

    def _write_fallback_script(self, outline: Dict, chars: List[Dict]) -> str:
        """Fallback script without LLM."""
        hero_name = (chars[0].get("protagonist", {}).get("name", "主角") if chars else "主角")
        scenes = outline.get("scenes", [])

        lines = [f"# 第{outline.get('episode_number', 0)}集: {outline.get('title', '')}"]
        lines.append("")

        for i, scene in enumerate(scenes):
            lines.append(f"## 场景{i+1}: {scene.get('location', '室内')} {scene.get('time_of_day', '白天')}")
            lines.append(f"**场景描述**: {scene.get('summary', '')}")
            lines.append("")
            lines.append(f"{hero_name}: (内心独白) 事情不会这么简单结束。")
            lines.append("(情绪提示: 坚定)")
            lines.append("")
            lines.append("---")
            lines.append("")

        lines.append(f"悬念钩子: {outline.get('cliffhanger', '悬念')}")
        return "\n".join(lines)

    def write_batch_scripts(
        self,
        outlines: List[Dict],
        character_cards: List[Dict],
        output_dir: Optional[str] = None,
    ) -> List[str]:
        """Write scripts for multiple episodes.

        Returns:
            List of script texts.
        """
        scripts = []
        prev_scripts = []

        for i, outline in enumerate(outlines):
            outline = dict(outline)
            outline["episode_number"] = i + 1
            print(f"  [ScriptWriter] Writing episode {i+1}...")

            script = self.write_episode_script(outline, character_cards, prev_scripts)
            scripts.append(script)
            prev_scripts.append(script)

            if output_dir:
                script_path = os.path.join(output_dir, f"ep{i+1:03d}_script.md")
                with open(script_path, "w", encoding="utf-8") as f:
                    f.write(script)

        return scripts

    def review_script_quality(self, script: str, outline: Dict) -> Dict:
        """Review a script for quality issues.

        Returns quality metrics and suggestions.
        """
        prompt = f"""请审查以下剧本质量:

剧本:
{script[:2000]}...

大纲:
{json.dumps(outline, ensure_ascii=False, indent=2)}

请检查:
1. 对白是否口语化(是否有书面语)
2. 是否有足够的冲突/反转
3. 每句对白是否超过15字
4. 结尾是否有悬念钩子
5. 字数是否在600-800范围

输出JSON:
{{
  "score": 8,
  "issues": ["问题1", "问题2"],
  "suggestions": ["建议1", "建议2"]
}}"""

        try:
            return self.llm.chat_structured(prompt, self.SYSTEM_PROMPT)
        except Exception:
            return {"score": 6, "issues": ["无法审查，使用默认设置"], "suggestions": []}
