"""角色语音绑定模块 - 为短剧角色绑定固定 TTS 音色

解决多集短剧中同一角色声音不一致的问题。
支持从角色卡片自动提取语音偏好、手动绑定、优先级管理。
"""

import os
import json
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass, field


@dataclass
class VoiceBinding:
    """角色语音绑定"""
    character_name: str        # 角色名
    voice: str                 # TTS 语音名
    gender: str                # 性别（male/female/unknown）
    source: str                # 来源：auto / manual / template
    confidence: float = 1.0    # 置信度


# 性别指示词映射表
FEMALE_INDICATORS = [
    "婉清", "柔", "晴", "夏", "瑶", "雪", "琳", "芳", "静", "雅",
    "浅", "苏", "柔柔", "小蛮", "月儿", "灵儿", "芷若", "梦璃",
    "小蛮", "婉婉", "浅浅", "阿瑶",
]

MALE_INDICATORS = [
    "承泽", "廷深", "震东", "泽", "浩", "伟", "强", "军", "磊", "峰",
    "尘", "逸尘", "沉", "默", "野", "霸", "天", "龙", "萧",
]


class VoiceBinder:
    """角色语音绑定管理器"""

    def __init__(
        self,
        default_female: str = "zh-CN-XiaoxiaoNeural",
        default_male: str = "zh-CN-YunxiNeural",
        binding_file: Optional[str] = None,
    ):
        """
        Args:
            default_female: 默认女声
            default_male: 默认男声
            binding_file: 绑定配置文件路径（持久化）
        """
        self.default_female = default_female
        self.default_male = default_male
        self.binding_file = binding_file
        self._bindings: Dict[str, VoiceBinding] = {}

        # 加载持久化的绑定
        if self.binding_file and os.path.exists(self.binding_file):
            self._load_bindings()

    def _load_bindings(self):
        """从文件加载绑定"""
        try:
            with open(self.binding_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            for name, info in data.items():
                self._bindings[name] = VoiceBinding(
                    character_name=name,
                    voice=info["voice"],
                    gender=info.get("gender", "unknown"),
                    source=info.get("source", "manual"),
                )
        except Exception as e:
            print(f"[VoiceBinder] 加载绑定失败: {e}")

    def save_bindings(self):
        """保存绑定到文件"""
        if not self.binding_file:
            return
        data = {
            name: asdict(b) for name, b in self._bindings.items()
        }
        with open(self.binding_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _detect_gender(self, name: str) -> str:
        """根据名字检测性别"""
        for indicator in FEMALE_INDICATORS:
            if indicator in name:
                return "female"
        for indicator in MALE_INDICATORS:
            if indicator in name:
                return "male"
        return "unknown"

    def _detect_voice(self, name: str, gender: str) -> str:
        """根据性别选择语音"""
        if gender == "female":
            return self.default_female
        elif gender == "male":
            return self.default_male
        return self.default_female  # 默认女声

    def bind_character(
        self,
        character_name: str,
        voice: str,
        gender: str = "unknown",
        source: str = "manual",
    ):
        """手动绑定角色语音"""
        self._bindings[character_name] = VoiceBinding(
            character_name=character_name,
            voice=voice,
            gender=gender,
            source=source,
        )
        self.save_bindings()

    def auto_bind_from_cards(
        self,
        character_cards: List[Dict],
    ):
        """
        从角色卡片自动绑定语音。
        
        Args:
            character_cards: 角色卡片列表，每个卡片包含 protagonist/antagonist/ally
        """
        for card in character_cards:
            for role_key in ("protagonist", "antagonist", "ally"):
                role = card.get(role_key)
                if not role:
                    continue
                name = role.get("name", "")
                if not name:
                    continue

                # 已有绑定则跳过
                if name in self._bindings:
                    continue

                gender = self._detect_gender(name)
                voice = self._detect_voice(name, gender)

                self._bindings[name] = VoiceBinding(
                    character_name=name,
                    voice=voice,
                    gender=gender,
                    source="auto",
                )

        self.save_bindings()

    def get_voice(self, character_name: str) -> str:
        """获取角色对应的语音"""
        if character_name in self._bindings:
            return self._bindings[character_name].voice
        # 未绑定则自动检测
        gender = self._detect_gender(character_name)
        return self._detect_voice(character_name, gender)

    def get_binding(self, character_name: str) -> Optional[VoiceBinding]:
        """获取角色的绑定信息"""
        return self._bindings.get(character_name)

    def get_all_bindings(self) -> List[VoiceBinding]:
        """获取所有绑定"""
        return list(self._bindings.values())

    def print_bindings(self):
        """打印所有绑定"""
        print("\n  角色语音绑定:")
        print("  " + "-" * 70)
        if not self._bindings:
            print("  (暂无绑定)")
        for name, binding in sorted(self._bindings.items()):
            gender_icon = {"male": "👨", "female": "👩", "unknown": "👤"}.get(
                binding.gender, "👤"
            )
            source_tag = {"auto": "[自动]", "manual": "[手动]", "template": "[模板]"}[
                binding.source
            ]
            print(f"    {gender_icon} {binding.voice:30s} | {name:15s} | {binding.gender:8s} | {source_tag}")
        print("  " + "-" * 70)
        print()

    def apply_to_dialogue(
        self,
        dialogues: List[Dict],
    ) -> List[Dict]:
        """
        为对话列表自动添加语音字段。
        
        Args:
            dialogues: 对话列表，每个对话包含 "character" 或 "role" 字段
        
        Returns:
            添加了 "voice" 字段的对话列表
        """
        for d in dialogues:
            char_name = d.get("character", d.get("role", ""))
            if char_name:
                d["voice"] = self.get_voice(char_name)
        return dialogues

    def export_bindings_json(self, output_path: str):
        """导出绑定为 JSON"""
        data = {
            name: asdict(b) for name, b in self._bindings.items()
        }
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"  语音绑定已导出: {output_path}")


def asdict(obj):
    """简单的 dataclass 转 dict 函数"""
    import dataclasses
    if dataclasses.is_dataclass(obj):
        return {f.name: asdict(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
    return obj
