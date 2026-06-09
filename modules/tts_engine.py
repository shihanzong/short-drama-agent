"""TTS Engine - AI voice synthesis for drama dialogue.

增强版 TTS 引擎，支持：
- 角色对话语音合成（Edge TTS）
- 全局语音播报（剧本/报告/回复）
- 情绪调节（不同语速/音调模拟情感）
- 批量合成
- 中文多音色选择
"""

import os
import asyncio
import edge_tts
import hashlib
from typing import Optional, List, Dict
from dataclasses import dataclass


@dataclass
class EmotionConfig:
    """语音情感配置"""
    happy: Dict = None       # 开心: 语速偏快、音调偏高
    sad: Dict = None         # 悲伤: 语速偏慢、音调偏低
    angry: Dict = None       # 愤怒: 语速偏快、音调高
    calm: Dict = None        # 平静: 默认
    excited: Dict = None     # 激动: 语速很快、音调高

    def __post_init__(self):
        if self.happy is None:
            self.happy = {"rate": "+20%", "pitch": "+5Hz"}
        if self.sad is None:
            self.sad = {"rate": "-15%", "pitch": "-5Hz"}
        if self.angry is None:
            self.angry = {"rate": "+25%", "pitch": "+10Hz"}
        if self.calm is None:
            self.calm = {"rate": "+0%", "pitch": "0Hz"}
        if self.excited is None:
            self.excited = {"rate": "+35%", "pitch": "+15Hz"}


# 中文可用 Edge TTS 语音表
CHINESE_VOICES = [
    # 女声
    {"name": "zh-CN-XiaoxiaoNeural", "gender": "女", "desc": "温柔女声（默认）"},
    {"name": "zh-CN-XiaoyiNeural", "gender": "女", "desc": "灵动女声"},
    {"name": "zh-CN-YunxiNeural", "gender": "男", "desc": "温暖男声"},
    {"name": "zh-CN-YunyangNeural", "gender": "男", "desc": "新闻男声"},
    {"name": "zh-CN-YunhaoNeural", "gender": "男", "desc": "少年男声"},
    {"name": "zh-CN-XiaochenNeural", "gender": "女", "desc": "活泼女声"},
    {"name": "zh-CN-XiaochenNeural", "gender": "女", "desc": "可爱女声"},
    {"name": "zh-CN-XiaomoNeural", "gender": "女", "desc": "知性女声"},
    {"name": "zh-CN-YunjianNeural", "gender": "男", "desc": "影视男声"},
    {"name": "zh-CN-guangxi-YunyeNeural", "gender": "男", "desc": "广西口音男声"},
    {"name": "zh-CN-liaoning-XiaobeiNeural", "gender": "女", "desc": "辽宁口音女声"},
    {"name": "zh-CN-shaanxi-XiaoniNeural", "gender": "女", "desc": "陕西口音女声"},
]


class TTSEngine:
    """Edge TTS 语音合成引擎（增强版）"""

    def __init__(self, config: Optional[dict] = None):
        self._config = config or {}
        self.default_voice = self._config.get(
            "voice_female", "zh-CN-XiaoxiaoNeural"
        )
        self.default_voice_male = self._config.get(
            "voice_male", "zh-CN-YunxiNeural"
        )
        self.rate = self._config.get("rate", "+0%")
        self.output_dir = self._config.get(
            "output_dir", os.path.join("output", "audio")
        )
        os.makedirs(self.output_dir, exist_ok=True)

        # 情感配置
        self.emotion = EmotionConfig()

    # ===== 基础合成 =====

    def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        rate: Optional[str] = None,
        pitch: Optional[str] = None,
        output_path: Optional[str] = None,
    ) -> str:
        """
        将文本合成为语音。

        Args:
            text: 要合成的文本
            voice: 语音名称（默认女声）
            rate: 语速（如 "+10%", "-5%"）
            pitch: 音调（如 "+5Hz", "-5Hz"）
            output_path: 输出文件路径

        Returns:
            生成的音频文件路径
        """
        if not text or not text.strip():
            return ""

        if not output_path:
            ts = hashlib.md5(text.encode()).hexdigest()[:8]
            output_path = os.path.join(self.output_dir, f"tts_{ts}.mp3")

        voice_name = voice or self.default_voice

        # 构建 edge_tts 参数
        voice_args = [f"voice={voice_name}"]
        if rate:
            voice_args.append(f"rate={rate}")
        if pitch:
            voice_args.append(f"pitch={pitch}")

        settings = " ".join(voice_args)
        # 分离出 voice name 和额外参数
        parts = settings.split()
        vn = None
        extra = []
        for p in parts:
            if p.startswith("voice="):
                vn = p.split("=", 1)[1]
            else:
                extra.append(p)

        communicate = edge_tts.Communicate(text, vn, rate=rate, pitch=pitch)
        try:
            asyncio.run(communicate.save(output_path))
        except Exception as e:
            print(f"  [TTS] 合成失败: {e}")
            return ""

        return output_path

    def synthesize_with_emotion(
        self,
        text: str,
        character_gender: str = "female",
        emotion: str = "calm",
        output_path: Optional[str] = None,
    ) -> str:
        """
        带情感的语音合成。

        Args:
            text: 要合成的文本
            character_gender: 角色性别 ("female"/"male")
            emotion: 情感 ("happy"/"sad"/"angry"/"calm"/"excited")
            output_path: 输出文件路径

        Returns:
            音频文件路径
        """
        voice = self.default_voice if character_gender in ("female", "女") else self.default_voice_male
        emo_config = getattr(self.emotion, emotion, self.emotion.calm)

        return self.synthesize(
            text=text,
            voice=voice,
            rate=emo_config["rate"],
            pitch=emo_config["pitch"],
            output_path=output_path,
        )

    def synthesize_report(self, report_text: str) -> str:
        """
        合成报告/摘要/回复的语音播报。

        使用男声、平静语速，适合播报长篇内容。

        Args:
            report_text: 报告文本

        Returns:
            音频文件路径
        """
        return self.synthesize(
            text=report_text,
            voice=self.default_voice_male,
            rate="+5%",  # 报告播报语速稍快
            output_path=os.path.join(self.output_dir, "report.mp3"),
        )

    # ===== 批量合成 =====

    def synthesize_batch(
        self,
        dialogues: list,
        output_prefix: str = "ep",
    ) -> list:
        """批量合成多个对话。"""
        results = []
        for i, d in enumerate(dialogues):
            text = d.get("text", "").strip()
            if not text:
                continue
            voice = d.get("voice") or self.default_voice
            rate = d.get("rate", self.rate)
            path = os.path.join(
                self.output_dir,
                f"{output_prefix}_ep{d.get('episode', 0)}_"
                f"c{d.get('character', i)}_d{i}.mp3",
            )
            try:
                results.append(
                    self.synthesize(text=text, voice=voice, rate=rate, output_path=path)
                )
            except Exception as e:
                print(f"  [TTS] 合成失败 {i}: {e}")
        return results

    # ===== 角色映射 =====

    def map_voice_for_character(self, character_name: str, gender: str = "") -> str:
        """根据角色名和性别映射 TTS 语音。"""
        g = gender.lower().strip() if gender else ""
        female_indicators = ["婉清", "柔", "晴", "夏", "瑶", "雪", "琳", "芳", "静", "雅"]
        male_indicators = ["承泽", "廷深", "震东", "泽", "浩", "伟", "强", "军", "磊", "峰"]

        if g in ("female", "f", "女"):
            return self.default_voice
        if g in ("male", "m", "男"):
            return self.default_voice_male

        for name in female_indicators:
            if name in character_name:
                return self.default_voice
        for name in male_indicators:
            if name in character_name:
                return self.default_voice_male

        return self.default_voice

    # ===== 语音列表 =====

    def list_voices(self) -> list:
        """列出所有可用的 Edge TTS 语音。"""
        async def _list():
            return await edge_tts.list_voices()
        return asyncio.run(_list())

    def get_available_voices_summary(self) -> list:
        """返回可用的中文语音列表。"""
        try:
            voices = self.list_voices()
            cn_voices = [
                {
                    "name": v["ShortName"],
                    "gender": "女" if v["Gender"] == "Female" else "男",
                    "locale": v["Locale"],
                }
                for v in voices
                if v["Locale"].startswith("zh-")
            ]
            return cn_voices
        except Exception:
            return []

    def print_chinese_voices(self):
        """打印所有中文语音的列表（含说明）。"""
        print("\n  可用中文语音:")
        print("  " + "-" * 60)
        for v in CHINESE_VOICES:
            print(f"    {v['name']}  |  {v['gender']}  |  {v['desc']}")
        print("  " + "-" * 60)
        print()
