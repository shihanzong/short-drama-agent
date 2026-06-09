"""Workflow Engine - Orchestrates the full short drama production pipeline."""

import os
import json
import yaml
from datetime import datetime
from typing import Optional, Dict, List

from modules.llm_client import LLMClient
from modules.comfyui_client import ComfyUIClient
from modules.tts_engine import TTSEngine
from modules.video_processor import VideoProcessor
from modules.style_manager import StyleManager, DEFAULT_PRESETS
from modules.analytics import AnalyticsEngine

from agents.creative_planner import CreativePlannerAgent
from agents.script_writer import ScriptWriterAgent
from agents.visual_designer import VisualDesignerAgent
from agents.audio_maker import AudioMakerAgent
from agents.video_editor import VideoEditorAgent
from agents.publisher import PublisherAgent


class ShortDramaWorkflow:
    """Orchestrates the full short drama production from concept to publication."""

    def __init__(self, config_path: Optional[str] = None):
        # Load config
        if config_path and os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                self.config = yaml.safe_load(f)
        else:
            default_path = os.path.join(os.path.dirname(__file__), "config.yaml")
            if os.path.exists(default_path):
                with open(default_path, "r", encoding="utf-8") as f:
                    self.config = yaml.safe_load(f)
            else:
                self.config = {}

        # Initialize modules
        llm_cfg = self.config.get("llm", {})
        self.llm = LLMClient(config_path)

        comfy_cfg = self.config.get("comfyui", {})
        self.comfyui = ComfyUIClient(
            host=comfy_cfg.get("host", "127.0.0.1"),
            port=comfy_cfg.get("port", 8188),
            timeout=comfy_cfg.get("timeout", 900),
        )

        tts_cfg = self.config.get("tts", {})
        output_base = self.config.get("paths", {}).get("output_dir", "output")
        self.tts = TTSEngine({
            "voice_female": tts_cfg.get("voice_female", "zh-CN-XiaoxiaoNeural"),
            "voice_male": tts_cfg.get("voice_male", "zh-CN-YunxiNeural"),
            "output_dir": os.path.join(output_base, "audio"),
        })

        video_cfg = self.config.get("video", {})
        self.video_proc = VideoProcessor({
            "fps": video_cfg.get("fps", 24),
            "resolution_width": video_cfg.get("resolution_width", 1080),
            "resolution_height": video_cfg.get("resolution_height", 1920),
            "default_transition": video_cfg.get("default_transition", "fade"),
            "transition_duration": video_cfg.get("transition_duration", 0.5),
            "subtitle_font_size": video_cfg.get("subtitle_font_size", 36),
            "subtitle_margin": video_cfg.get("subtitle_margin", 20),
            "output_dir": os.path.join(output_base, "video"),
        })

        self.style_mgr = StyleManager()
        self.analytics = AnalyticsEngine(
            os.path.join(output_base, "analytics")
        )

        # Initialize agents
        self.creative_planner = CreativePlannerAgent(self.llm)
        self.script_writer = ScriptWriterAgent(self.llm)
        self.visual_designer = VisualDesignerAgent(self.llm, self.comfyui)
        self.audio_maker = AudioMakerAgent(self.llm, self.tts)
        self.video_editor = VideoEditorAgent(self.llm, self.video_proc)
        self.publisher = PublisherAgent(self.llm)

        # Runtime state
        self.drama_id = None
        self.genre = None
        self.character_cards = []
        self.episode_outlines = []
        self.scripts = []
        self.visual_data = []
        self.audio_data = []
        self.video_paths = []

    def _create_episode_dir(self, episode_num: int) -> str:
        """Create output directory for an episode."""
        output_base = self.config.get("paths", {}).get("output_dir", "output")
        episode_dir = os.path.join(output_base, f"ep{episode_num:03d}")
        os.makedirs(episode_dir, exist_ok=True)
        return episode_dir


    # ===== Kanban Workflow Handlers =====
    def _kanban_script_handler(self, task):
        """Kanban handler for script writing."""
        import json as _json
        data = _json.loads(task.body)
        ep = data["episode"]
        outline = data["outline"]
        script = self.script_writer.write_episode_script(outline, self.character_cards)
        episode_dir = self._create_episode_dir(ep)
        with open(os.path.join(episode_dir, "script.md"), "w", encoding="utf-8") as f:
            f.write(script)
        result = {"episode": ep, "script_path": os.path.join(episode_dir, "script.md")}
        self.kanban_tasks[f"script_{ep}"] = result
        return result

    def _kanban_visual_handler(self, task):
        """Kanban handler for visual design."""
        import json as _json
        data = _json.loads(task.body)
        ep = data["episode"]
        outline = data["outline"]
        episode_dir = self._create_episode_dir(ep)
        images_dir = os.path.join(episode_dir, "images")
        os.makedirs(images_dir, exist_ok=True)

        storyboard = self.visual_designer.generate_storyboard(
            "# placeholder", self.character_cards, "cinematic_realistic"
        )
        with open(os.path.join(episode_dir, "storyboard.json"), "w", encoding="utf-8") as f:
            json.dump(storyboard, f, indent=2, ensure_ascii=False)

        # Try ComfyUI
        image_paths = []
        if self.comfyui.health_check():
            for shot in storyboard[:3]:
                try:
                    img = self.comfyui.generate_from_prompt(
                        prompt=shot.get("prompt", ""),
                        negative_prompt="ugly, deformed",
                        width=576, height=1024, output_dir=images_dir,
                    )
                    if img:
                        image_paths.append(img)
                except Exception:
                    pass
        else:
            for i, shot in enumerate(storyboard[:3]):
                txt = os.path.join(images_dir, f"shot_{i+1}.txt")
                with open(txt, "w") as f:
                    f.write(shot.get("prompt", ""))
                image_paths.append(txt)

        result = {"episode": ep, "images": image_paths, "storyboard": storyboard}
        self.kanban_tasks[f"visual_{ep}"] = result
        return result

    def _kanban_audio_handler(self, task):
        """Kanban handler for audio production."""
        import json as _json
        data = _json.loads(task.body)
        ep = data["episode"]
        script_path = os.path.join(self._create_episode_dir(ep), "script.md")

        if os.path.exists(script_path):
            with open(script_path, "r", encoding="utf-8") as f:
                script_text = f.read()
        else:
            script_text = "# No script"

        audio_result = self.audio_maker.run(script_text, self.character_cards, ep)
        return {"episode": ep, "audio_files": audio_result.get("dialogue_audio", [])}

    def _kanban_video_handler(self, task):
        """Kanban handler for video compositing."""
        import json as _json
        data = _json.loads(task.body)
        ep = data["episode"]
        episode_dir = self._create_episode_dir(ep)
        video_dir = os.path.join(episode_dir, "video")
        os.makedirs(video_dir, exist_ok=True)
        final_video = os.path.join(video_dir, "final.mp4")

        visual = self.kanban_tasks.get(f"visual_{ep}", {})
        audio = self.kanban_tasks.get(f"audio_{ep}", {})

        image_paths = visual.get("images", [])
        audio_files = audio.get("audio_files", [])

        if image_paths:
            valid = [p for p in image_paths if os.path.exists(p)]
            if valid:
                self.video_editor.composite_episode(
                    visual.get("storyboard", []), valid, audio_files,
                    final_video, ep
                )

        return {"episode": ep, "video_path": final_video if os.path.exists(final_video) else ""}

    def run_single_episode(
        self,
        genre: str,
        episode_outline: dict,
        episode_number: int,
        style: str = "cinematic_realistic",
        skip_visual: bool = False,
        skip_audio: bool = False,
        skip_publish: bool = False,
        quick_mode: bool = False,
    ) -> Dict:
        """Run the full pipeline for a single episode.

        Args:
            genre: Drama genre.
            episode_outline: Outline for this episode.
            episode_number: Episode number.
            style: Visual style preset.
            skip_visual: Skip image generation.
            skip_audio: Skip audio generation.
            skip_publish: Skip publishing.

        Returns:
            Episode production result with paths and metadata.
        """
        self.drama_id = f"{genre}_ep{episode_number}"
        self.genre = genre
        episode_dir = self._create_episode_dir(episode_number)

        print(f"\n{'='*50}")
        print(f"  PRODUCING EPISODE {episode_number}")
        print(f"{'='*50}")

        # Step 1: Save outline
        outline_path = os.path.join(episode_dir, "outline.json")
        outline_data = dict(episode_outline)
        outline_data["episode_number"] = episode_number
        with open(outline_path, "w", encoding="utf-8") as f:
            json.dump(outline_data, f, indent=2, ensure_ascii=False)

        # Step 2: Script Writing
        print(f"\n[1/6] Script Writing...")
        script = self.script_writer.write_episode_script(
            episode_outline, self.character_cards
        )
        script_path = os.path.join(episode_dir, "script.md")
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(script)
        print(f"  Script saved to: {script_path}")

        # Step 3: Visual Design
        print(f"\n[2/6] Visual Design...")
        images_dir = os.path.join(episode_dir, "images")
        os.makedirs(images_dir, exist_ok=True)
        storyboard = []
        image_paths = []

        if not skip_visual:
            storyboard = self.visual_designer.generate_storyboard(
                script, self.character_cards, style
            )
            storyboard_path = os.path.join(episode_dir, "storyboard.json")
            with open(storyboard_path, "w", encoding="utf-8") as f:
                json.dump(storyboard, f, indent=2, ensure_ascii=False)

            # Generate images from storyboard (if ComfyUI is available)
            if self.comfyui.health_check():
                for shot in storyboard[:5]:  # Limit images per episode
                    try:
                        img_path = self.comfyui.generate_from_prompt(
                            prompt=shot.get("prompt", ""),
                            negative_prompt="ugly, deformed, noisy, blurry",
                            width=576,
                            height=1024,
                            output_dir=images_dir,
                        )
                        if img_path:
                            image_paths.append(img_path)
                    except Exception as e:
                        print(f"  [VisualDesigner] Image generation failed: {e}")
            else:
                print("  [VisualDesigner] ComfyUI not running - using prompt-only mode")
                # Generate fallback images
                for i, shot in enumerate(storyboard[:5]):
                    img_path = os.path.join(images_dir, f"shot_{i+1:03d}.txt")
                    with open(img_path, "w", encoding="utf-8") as f:
                        f.write(f"PO:\n{shot.get('prompt', '')}\n\nNP:\n{shot.get('negative_prompt', '')}")
                    image_paths.append(img_path)
        else:
            print("  [VisualDesign] Skipped")

        # Step 3: Audio Production
        print(f"\n[3/6] Audio Production...")
        audio_dir = os.path.join(episode_dir, "audio")
        os.makedirs(audio_dir, exist_ok=True)

        audio_files = []

        if not skip_audio:
            # Update TTS output dir for this episode
            old_output_dir = self.tts.output_dir
            self.tts.output_dir = audio_dir
            try:
                audio_result = self.audio_maker.run(
                    script, self.character_cards, episode_number
                )
                audio_files = audio_result.get("dialogue_audio", [])
            finally:
                # Restore original TTS output dir
                self.tts.output_dir = old_output_dir
        else:
            print("  [Audio] Skipped")

        # Step 5: Video Compositing
        print(f"\n[4/6] Video Compositing...")
        video_dir = os.path.join(episode_dir, "video")
        os.makedirs(video_dir, exist_ok=True)
        final_video = ""

        if image_paths:
            valid_images = [p for p in image_paths if os.path.exists(p)]
            if valid_images:
                final_video = os.path.join(video_dir, "final.mp4")
                self.video_editor.composite_episode(
                    storyboard, valid_images, audio_files, final_video, episode_number
                )
                if final_video and not os.path.exists(final_video):
                    print("  [Video] Image processing failed (ffmpeg may not be available)")
                    final_video = ""
            else:
                print("  [Video] No valid image files found (check ComfyUI or prompt-only mode)")
        else:
            print("  [Video] No images to composite")

        # Step 6: Publishing
        print(f"\n[5/6] Publishing...")
        publishing_result = {}
        if not skip_publish and not quick_mode:
            publishing_result = self.publisher.run(
                genre, [episode_outline], [final_video] if final_video else [],
                ["douyin"], self.drama_id
            )

        result = {
            "episode": episode_number,
            "genre": genre,
            "outline_path": outline_path,
            "script_path": script_path,
            "storyboard_path": os.path.join(episode_dir, "storyboard.json"),
            "images_dir": images_dir,
            "audio_files": audio_files,
            "video_path": final_video,
            "publishing": publishing_result,
        }

        # Save episode result
        result_path = os.path.join(episode_dir, "result.json")
        with open(result_path, "w", encoding="utf-8") as f:
            # Convert non-serializable types
            serializable = {}
            for k, v in result.items():
                if isinstance(v, list):
                    serializable[k] = v[:5] if len(v) > 5 else v  # Limit for readability
                elif isinstance(v, dict):
                    serializable[k] = {kk: vv for kk, vv in v.items() if not isinstance(vv, list) or len(str(vv)) < 200}
                else:
                    serializable[k] = v
            json.dump(serializable, f, indent=2, ensure_ascii=False)

        print(f"\n  Episode {episode_number} produced!")
        print(f"  Output: {episode_dir}")

        return result

    def run_series(
        self,
        genre: str,
        episode_count: int = 5,
        character_cards: Optional[List[Dict]] = None,
        style: str = "cinematic_realistic",
        output_base: str = "output",
        quick_mode: bool = False,
    ) -> Dict:
        """Run the full series production pipeline.

        Args:
            genre: Drama genre (e.g., "重生复仇", "霸总", "逆袭").
            episode_count: Number of episodes to produce.
            character_cards: Pre-generated character cards (or auto-generated).
            style: Visual style preset.
            output_base: Base output directory.
            quick_mode: Skip visual and audio generation for fast testing.

        Returns:
            Full production result with all episode outputs.
        """
        self.genre = genre
        output_base = os.path.join(output_base, genre)
        os.makedirs(output_base, exist_ok=True)

        print(f"\n{'#'*60}")
        print(f"# SHORT DRAMA PRODUCTION: {genre}")
        print(f"# Episodes: {episode_count}")
        print(f"# Style: {style}")
        print(f"# {'#'*60}")

        # Step 1: Creative Planning
        print(f"\n[1/5] Creative Planning...")
        planning = self.creative_planner.run(genre, episode_count)
        self.character_cards = planning.get("character_cards", [])
        self.episode_outlines = planning.get("episode_outlines", [])

        # Save planning result
        plan_path = os.path.join(output_base, "planning.json")
        with open(plan_path, "w", encoding="utf-8") as f:
            json.dump(planning, f, indent=2, ensure_ascii=False, default=str)

        # If outlines were fewer than requested, duplicate (fallback)
        while len(self.episode_outlines) < episode_count:
            idx = len(self.episode_outlines) + 1
            self.episode_outlines.append({
                "title": f"第{idx}集: 剧情发展",
                "logline": f"{genre}第{idx}集",
                "scenes": [
                    {
                        "scene_number": 1,
                        "location": "室内",
                        "time_of_day": "白天",
                        "summary": "剧情推进",
                        "characters_present": [],
                        "emotional_tone": "紧张",
                        "duration_seconds": 30,
                    }
                ],
                "cliffhanger": "悬念",
                "hook_score": 7,
            })

        print(f"  Planning complete: {len(self.episode_outlines)} episodes")

        # Register in analytics
        self.analytics.record_drama(
            drama_id=genre,
            genre=genre,
            episodes=episode_count,
            platforms=["douyin"],
            title=genre,
        )

        # Step 2-5: Per-episode production
        results = []
        for i, outline in enumerate(self.episode_outlines):
            if i >= episode_count:
                break

            result = self.run_single_episode(
                genre=genre,
                episode_outline=outline,
                episode_number=i + 1,
                style=style,
                skip_visual=quick_mode,
                skip_audio=quick_mode,
                skip_publish=quick_mode,
            )
            results.append(result)

        # Save overall result
        overall_path = os.path.join(output_base, "overall_result.json")
        with open(overall_path, "w", encoding="utf-8") as f:
            json.dump({
                "genre": genre,
                "total_episodes": len(results),
                "episodes": [
                    {
                        "episode": r["episode"],
                        "video_path": r.get("video_path", ""),
                        "script_path": r.get("script_path", ""),
                    }
                    for r in results
                ],
                "completed_at": datetime.now().isoformat(),
            }, f, indent=2, ensure_ascii=False)

        print(f"\n{'#'*60}")
        print(f"# PRODUCTION COMPLETE: {genre}")
        print(f"# Total episodes: {len(results)}")
        print(f"# Output directory: {output_base}")
        print(f"# {'#'*60}")

        return {
            "genre": genre,
            "episodes_produced": len(results),
            "results": results,
            "output_directory": output_base,
        }
