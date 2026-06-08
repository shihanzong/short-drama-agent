"""Video Editor Agent - Image-to-video, transitions, subtitles, compositing."""

import os
import json
from typing import Optional, Dict, List
from modules.llm_client import LLMClient
from modules.video_processor import VideoProcessor


class VideoEditorAgent:
    """Composites video from storyboard images, dialogue audio, and BGM."""

    SYSTEM_PROMPT = """你是短剧后期剪辑专家。精通竖屏短视频的剪辑节奏、转场特效、字幕包装。

剪辑原则:
1. 每个镜头3-5秒，节奏要快
2. 转场要干净利落，少用花哨特效
3. 字幕要大且醒目，保证手机观看清晰
4. 音画要同步，对白位置不能压字幕
5. 整体色调要统一"""

    def __init__(self, llm_client: Optional[LLMClient] = None, video_processor: Optional[VideoProcessor] = None):
        self.llm = llm_client or LLMClient()
        self.video_proc = video_processor or VideoProcessor()

    def composite_episode(
        self,
        storyboard: List[Dict],
        image_paths: List[str],
        audio_paths: List[str],
        output_path: str,
        episode_number: int = 1,
    ) -> str:
        """Composite an episode from storyboard, images, and audio.

        Returns output video path, or empty string if no images available.
        """
        if not image_paths:
            print("  [VideoEditor] No images to composite.")
            return ""

        # Filter to only valid image files
        valid_images = [p for p in image_paths if os.path.exists(p)]
        if not valid_images:
            print("  [VideoEditor] No valid images found (checking file existence)")
            return ""

        print(f"  [VideoEditor] Stitching {len(valid_images)} images to video...")
        video_path = os.path.join(
            os.path.dirname(output_path),
            f"ep{episode_number:03d}_video.mp4",
        )

        # Stitch images with Ken Burns effect
        effects = ["zoom_in", "pan_right", "zoom_in", "pan_left"] * (len(valid_images) // 4 + 1)
        result = self.video_proc.stitch_images_to_video(
            image_paths=valid_images[:10],
            output_path=video_path,
            shot_duration=4.0,
            effects=effects[:len(valid_images)],
        )

        if not result and not os.path.exists(video_path):
            print("  [VideoEditor] Failed to stitch video (ffmpeg may not be installed)")
            return ""

        # Merge with combined audio if available
        if audio_paths:
            combined = self._merge_audio_tracks(audio_paths)
            if combined and os.path.exists(combined):
                merged = self.video_proc.merge_audio_video(video_path, combined, output_path)
                if merged:
                    video_path = merged

        return video_path

    def _merge_audio_tracks(self, audio_paths: List[str]) -> Optional[str]:
        """Merge multiple audio tracks into one combined track."""
        if not audio_paths:
            return None

        valid = [p for p in audio_paths if os.path.exists(p)]
        if len(valid) == 0:
            return None
        if len(valid) == 1:
            return valid[0]

        combined = os.path.join(
            os.path.dirname(valid[0]) if valid else "output/audio",
            "_combined_audio.mp3",
        )

        try:
            result = self.video_proc.merge_audio_concat(valid, combined)
            if result and os.path.exists(result):
                return result
        except Exception as e:
            print(f"  [VideoEditor] Audio merge failed: {e}")

        return valid[0]  # Fallback to first valid

    def generate_video_prompt(
        self,
        storyboard_shot: Dict,
        style: str = "cinematic realistic",
    ) -> str:
        """Generate a prompt for ComfyUI video generation."""
        shot_type = storyboard_shot.get("shot_type", "medium")
        description = storyboard_shot.get("description", "")
        emotion = storyboard_shot.get("emotional_tone", "")

        motion_prompts = {
            "close-up": "slight zoom in, subtle head movement",
            "medium": "gentle pan, natural body movement",
            "wide": "slow dolly in, environmental movement",
            "over-shoulder": "slow tracking movement",
            "low-angle": "slow tilt up",
            "high-angle": "slow tilt down",
        }

        motion = motion_prompts.get(shot_type, "gentle camera movement")
        return f"{description}, {motion}, {emotion}, cinematic quality, smooth video, 9:16"

    def run(
        self,
        storyboard: List[Dict],
        image_paths: List[str],
        audio_paths: List[str],
        episode_number: int = 1,
        output_dir: str = "output",
    ) -> Dict:
        """Run the full video editing pipeline."""
        os.makedirs(output_dir, exist_ok=True)
        episode_dir = os.path.join(output_dir, f"ep{episode_number:03d}")
        os.makedirs(episode_dir, exist_ok=True)

        output_path = os.path.join(episode_dir, "final.mp4")

        print(f"  [VideoEditor] Compositing episode {episode_number}...")
        video_path = self.composite_episode(
            storyboard, image_paths, audio_paths, output_path, episode_number
        )

        return {
            "episode": episode_number,
            "video_path": video_path,
            "storyboard": storyboard,
        }
