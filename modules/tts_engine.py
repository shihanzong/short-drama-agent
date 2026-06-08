"""TTS Engine - AI voice synthesis for drama dialogue."""

import os
import asyncio
import edge_tts
from typing import Optional, List


class TTSEngine:
    """Edge TTS wrapper for generating character dialogue audio."""

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

    def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        rate: Optional[str] = None,
        output_path: Optional[str] = None,
    ) -> str:
        """Synthesize text to speech and save to file.

        Uses asyncio.run() internally since edge_tts.Communicate.save()
        is a coroutine.

        Args:
            text: The dialogue text to synthesize.
            voice: TTS voice name (zh-CN-YunxiNeural for male, etc.).
            rate: Speech rate adjustment (e.g., "+10%", "-5%").
            output_path: Where to save the MP3 file.

        Returns:
            Path to the generated audio file.
        """
        if not text or not text.strip():
            return ""

        if not output_path:
            import time
            name = f"tts_{int(time.time())}_{hash(text) % 10000}"
            output_path = os.path.join(self.output_dir, f"{name}.mp3")

        voice_name = voice or self.default_voice
        rate_val = rate or self.rate

        async def _synthesize():
            communicate = edge_tts.Communicate(text, voice_name, rate=rate_val)
            await communicate.save(output_path)

        try:
            asyncio.run(_synthesize())
        except Exception as e:
            print(f"  [TTS] Async error: {e}")
            return ""

        return output_path

    def synthesize_batch(
        self,
        dialogues: list,
        output_prefix: str = "ep",
    ) -> list:
        """Synthesize multiple dialogues into separate audio files."""
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
                print(f"  [TTS] Failed to synthesize dialogue {i}: {e}")
        return results

    def map_voice_for_character(self, character_name: str, gender: str = "") -> str:
        """Map a character name and gender to a TTS voice."""
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

    def list_voices(self) -> list:
        """List available TTS voices."""
        async def _list():
            return await edge_tts.list_voices()
        return asyncio.run(_list())

    def get_available_voices_summary(self) -> list:
        """Return a compact summary of available Chinese voices."""
        try:
            voices = self.list_voices()
            cn_voices = [
                {"name": v["ShortName"], "gender": v["Gender"], "locale": v["Locale"]}
                for v in voices
                if v["Locale"].startswith("zh-")
            ]
            return cn_voices
        except Exception:
            return []
