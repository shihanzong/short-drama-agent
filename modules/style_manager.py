"""Style Manager - Visual style presets and consistency management."""

import os
import json
from typing import Optional, Dict, List


class StyleManager:
    """Manage visual style presets for short drama production."""

    def __init__(self, preset_dir: Optional[str] = None):
        self.preset_dir = preset_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "knowledge_base", "style_presets"
        )
        os.makedirs(self.preset_dir, exist_ok=True)
        self._presets = {}
        self._load_presets()

    def _load_presets(self):
        """Load style presets from JSON files."""
        if os.path.exists(self.preset_dir):
            for fname in os.listdir(self.preset_dir):
                if fname.endswith(".json"):
                    path = os.path.join(self.preset_dir, fname)
                    with open(path, "r", encoding="utf-8") as f:
                        preset = json.load(f)
                        self._presets[preset.get("name", fname)] = preset

    def list_presets(self) -> List[str]:
        """List available style preset names."""
        return list(self._presets.keys())

    def get_preset(self, name: str) -> Optional[Dict]:
        """Get a style preset by name."""
        return self._presets.get(name)

    def save_preset(
        self,
        name: str,
        visual_style: str,
        palette: Dict[str, str],
        lighting: str = "natural",
        camera_angle: str = "eye-level",
        mood: str = "neutral",
        aspect_ratio: str = "9:16",
    ):
        """Save a new style preset."""
        preset = {
            "name": name,
            "visual_style": visual_style,
            "palette": palette,
            "lighting": lighting,
            "camera_angle": camera_angle,
            "mood": mood,
            "aspect_ratio": aspect_ratio,
        }
        self._presets[name] = preset
        preset_file = os.path.join(self.preset_dir, f"{name}.json")
        with open(preset_file, "w", encoding="utf-8") as f:
            json.dump(preset, f, indent=2, ensure_ascii=False)

    def get_style_prompt(self, name: str) -> Optional[str]:
        """Get a ComfyUI-ready prompt string from a style preset."""
        preset = self._presets.get(name)
        if not preset:
            return None

        parts = []
        parts.append(preset.get("visual_style", "cinematic"))
        parts.append(f"lighting: {preset.get('lighting', 'natural')}")
        parts.append(f"color palette: {self._palette_to_string(preset.get('palette', {}))}")
        parts.append(f"mood: {preset.get('mood', 'neutral')}")
        if preset.get("aspect_ratio") == "9:16":
            parts.append("portrait, vertical composition, shot on smartphone")

        return ", ".join(parts)

    def get_negative_prompt(self) -> str:
        """Get a standard negative prompt for style consistency."""
        return "ugly, deformed, noisy, blurry, distorted, grainy, lowres, bad anatomy, worst quality, low quality"

    @staticmethod
    def _palette_to_string(palette: Dict[str, str]) -> str:
        """Convert palette dict to descriptive string."""
        if not palette:
            return ""
        colors = [f"{role}: {color}" for role, color in palette.items()]
        return ", ".join(colors)


# Default style presets built in
DEFAULT_PRESETS = {
    "cinematic_realistic": {
        "name": "cinematic_realistic",
        "visual_style": "cinematic realistic, film grain, depth of field",
        "palette": {"highlight": "warm gold", "shadow": "cool blue", "accent": "red"},
        "lighting": "dramatic three-point",
        "camera_angle": "cinematic wide",
        "mood": "dramatic",
        "aspect_ratio": "9:16",
    },
    "anime": {
        "name": "anime",
        "visual_style": "anime style, cel shaded, clean lines",
        "palette": {"highlight": "bright", "shadow": "soft purple", "accent": "vibrant"},
        "lighting": "soft anime lighting",
        "camera_angle": "dynamic anime angle",
        "mood": "vibrant",
        "aspect_ratio": "9:16",
    },
    "noir": {
        "name": "noir",
        "visual_style": "film noir, high contrast black and white",
        "palette": {"highlight": "white", "shadow": "deep black", "accent": "yellow"},
        "lighting": "chiaroscuro",
        "camera_angle": "low angle",
        "mood": "mysterious",
        "aspect_ratio": "9:16",
    },
    "webtoon": {
        "name": "webtoon",
        "visual_style": "Korean webtoon style, digital painting",
        "palette": {"highlight": "pastel", "shadow": "cool gray", "accent": "pink"},
        "lighting": "soft diffused",
        "camera_angle": "straight on",
        "mood": "romantic",
        "aspect_ratio": "9:16",
    },
}

for name, preset in DEFAULT_PRESETS.items():
    pass  # Will be loaded when StyleManager is instantiated
