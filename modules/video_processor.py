"""Video Processor - ffmpeg + moviepy based video editing engine."""

import os
import subprocess
from typing import Optional, List


class VideoProcessor:
    """Video processing engine using ffmpeg and moviepy."""

    def __init__(self, config: Optional[dict] = None):
        self._config = config or {}
        self.fps = self._config.get("fps", 24)
        self.width = self._config.get("resolution_width", 1080)
        self.height = self._config.get("resolution_height", 1920)
        self.default_transition = self._config.get("default_transition", "fade")
        self.transition_duration = self._config.get("transition_duration", 0.5)
        self.output_dir = self._config.get("output_dir", "output")
        self.font_size = self._config.get("subtitle_font_size", 36)
        self.subtitle_margin = self._config.get("subtitle_margin", 20)
        self._ffmpeg_available = None

    @property
    def ffmpeg_available(self) -> bool:
        """Check if ffmpeg is available on the system."""
        if self._ffmpeg_available is None:
            try:
                subprocess.run(
                    ["ffmpeg", "-version"],
                    capture_output=True,
                    check=True,
                    timeout=5,
                )
                self._ffmpeg_available = True
            except Exception:
                self._ffmpeg_available = False
        return self._ffmpeg_available

    def ken_burns_effect(
        self,
        image_path: str,
        output_path: str,
        duration: float = 4.0,
        direction: str = "zoom_in",
    ) -> str:
        """Apply Ken Burns pan/zoom effect to a static image.

        Args:
            image_path: Source image file.
            output_path: Output video file (MP4).
            duration: Duration in seconds.
            direction: zoom_in, zoom_out, pan_left, pan_right, pan_up, pan_down.

        Returns:
            Output path, or empty string if ffmpeg not available.
        """
        if not self.ffmpeg_available:
            print(f"  [VideoProcessor] ffmpeg not available - skipping ken burns for {os.path.basename(image_path)}")
            return ""

        if not os.path.exists(image_path):
            print(f"  [VideoProcessor] Image not found: {image_path}")
            return ""

        cmd = [
            "ffmpeg", "-y",
            "-loop", "1",
            "-i", image_path,
            "-vf", self._ken_burns_filter(direction),
            "-t", str(duration),
            "-r", str(self.fps),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-s", f"{self.width}x{self.height}",
            "-preset", "fast",
            output_path,
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if result.returncode != 0:
                print(f"  [VideoProcessor] ffmpeg error: {result.stderr[:200]}")
                return ""
        except subprocess.TimeoutExpired:
            print(f"  [VideoProcessor] ffmpeg timeout for {image_path}")
            return ""
        except Exception as e:
            print(f"  [VideoProcessor] ffmpeg failed: {e}")
            return ""

        return output_path

    def _ken_burns_filter(self, direction: str) -> str:
        """Build ffmpeg zoompan filter for Ken Burns effect."""
        zoom = "1.0"
        x = "0"
        y = "0"

        if direction == "zoom_in":
            zoom = "min(zoom+0.0015,1.2)"
        elif direction == "zoom_out":
            zoom = "max(zoom-0.0015,1)"
        elif direction == "pan_right":
            x = "min(on*w,(w/1.5)*if(lte(zoom,1.0),((1.5*W)/(w*1.0)),0))"
        elif direction == "pan_left":
            x = "max(on*w-(w*0.5),0)"
        elif direction == "pan_up":
            y = "max(on*h-(h*0.5),0)"
        elif direction == "pan_down":
            y = "min(on*h,(h/1.5)*if(lte(zoom,1.0),((1.5*H)/(h*1.0)),0))"

        return f"zoompan=z={zoom}:x={x}:y={y}:d={int(60*4)}:s={self.width}x{self.height}:fps={self.fps}"

    def stitch_images_to_video(
        self,
        image_paths: List[str],
        output_path: str,
        shot_duration: float = 4.0,
        effects: Optional[List[str]] = None,
    ) -> str:
        """Stitch a sequence of images into a video with Ken Burns effects.

        Args:
            image_paths: Ordered list of image file paths.
            output_path: Output MP4 path.
            shot_duration: Seconds per shot.
            effects: Optional list of direction strings (one per image).

        Returns:
            Output video path, or empty string on failure.
        """
        if not self.ffmpeg_available:
            print("  [VideoProcessor] ffmpeg not available - skipping video stitch")
            return ""

        # Filter to only existing files
        valid_images = [p for p in image_paths if os.path.exists(p)]
        if not valid_images:
            print("  [VideoProcessor] No valid images to stitch")
            return ""

        if not effects:
            effects = ["zoom_in"] * len(valid_images)

        # Build ffmpeg concat input file list
        list_file = os.path.join(self.output_dir, "_concat_list.txt")
        shot_videos = []

        for i, img_path in enumerate(valid_images):
            shot_out = os.path.join(
                self.output_dir, f"_shot_{i:03d}.mp4"
            )
            effect = effects[i] if i < len(effects) else "zoom_in"
            self.ken_burns_effect(img_path, shot_out, shot_duration, effect)
            if os.path.exists(shot_out):
                shot_videos.append(shot_out)

        if not shot_videos:
            print("  [VideoProcessor] No shot videos generated")
            return ""

        # Build concat list
        with open(list_file, "w") as f:
            for v in shot_videos:
                f.write(f"file '{v}'\n")

        # Concatenate
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", list_file,
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            output_path,
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode != 0:
                print(f"  [VideoProcessor] concat error: {result.stderr[:200]}")
                return ""
        except Exception as e:
            print(f"  [VideoProcessor] concat failed: {e}")
            return ""

        # Cleanup shot videos and list file
        for v in shot_videos:
            if os.path.exists(v):
                os.remove(v)
        if os.path.exists(list_file):
            os.remove(list_file)

        return output_path

    def add_subtitles(
        self,
        video_path: str,
        srt_path: str,
        output_path: str,
        font_size: Optional[int] = None,
    ) -> str:
        """Add SRT subtitles to video using ffmpeg hardsub."""
        if not self.ffmpeg_available:
            return ""

        if not os.path.exists(video_path):
            return ""

        fs = font_size or self.font_size
        margin = self.subtitle_margin
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-vf", f"subtitles={srt_path}:force_style='FontSize={fs},MarginV={margin}'",
            "-c:a", "copy",
            output_path,
        ]
        try:
            subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        except Exception:
            return ""
        return output_path

    def merge_audio_video(
        self,
        video_path: str,
        audio_path: str,
        output_path: str,
    ) -> str:
        """Merge an audio file with a video file."""
        if not self.ffmpeg_available:
            return ""

        if not os.path.exists(video_path) or not os.path.exists(audio_path):
            return ""

        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", audio_path,
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            output_path,
        ]
        try:
            subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        except Exception:
            return ""
        return output_path

    def merge_audio_concat(self, audio_paths: List[str], output_path: str) -> str:
        """Concatenate multiple audio files into one."""
        if not self.ffmpeg_available or len(audio_paths) < 2:
            if len(audio_paths) == 1:
                return audio_paths[0]
            return ""

        valid = [p for p in audio_paths if os.path.exists(p)]
        if not valid:
            return ""
        if len(valid) == 1:
            return valid[0]

        concat_list = output_path.replace(".mp3", "_concat.txt")
        with open(concat_list, "w") as f:
            for p in valid:
                f.write(f"file '{p}'\n")

        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_list,
            "-c:a", "aac",
            "-b:a", "192k",
            "-map_metadata", "-1",
            output_path,
        ]
        try:
            subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        except Exception:
            return ""
        finally:
            if os.path.exists(concat_list):
                os.remove(concat_list)

        return output_path if os.path.exists(output_path) else ""

    def create_srt(
        self,
        dialogues: List[dict],
        output_path: str,
    ) -> str:
        """Create an SRT subtitle file from dialogue data.

        Args:
            dialogues: List of dicts with keys: time_start, time_end, text, speaker
            output_path: Output .srt file path
        """
        with open(output_path, "w", encoding="utf-8") as f:
            for i, d in enumerate(dialogues):
                start = self._seconds_to_srt_time(d["time_start"])
                end = self._seconds_to_srt_time(d["time_end"])
                f.write(f"{i + 1}\n")
                f.write(f"{start} --> {end}\n")
                f.write(f"[{d.get('speaker', '')}] {d['text']}\n\n")
        return output_path

    @staticmethod
    def _seconds_to_srt_time(seconds: float) -> str:
        """Convert seconds to SRT timestamp format."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        ms = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"
