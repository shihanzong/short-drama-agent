#!/usr/bin/env python3
"""
长视频转录模块 - Video Transcription Module
支持YouTube链接和本地文件转录
"""

import json
import os
import re
from pathlib import Path
from typing import Optional

SKILL_ROOT = Path(__file__).parent.parent


class VideoTranscriber:
    """长视频转录器"""
    
    def __init__(self, whisper_model: str = "base"):
        self.whisper_model = whisper_model
    
    def transcribe(self, source: str, source_type: str = "youtube") -> dict:
        if source_type == "youtube":
            return self._transcribe_youtube(source)
        elif source_type == "video":
            return self._transcribe_local_video(source)
        elif source_type == "audio":
            return self._transcribe_local_audio(source)
        elif source_type == "transcript":
            return self._load_transcript(source)
        else:
            return {"error": f"不支持的源类型：{source_type}"}
    
    def _transcribe_youtube(self, url: str) -> dict:
        """使用yt-dlp提取YouTube字幕"""
        result = {"source": url, "source_type": "youtube", "text": "", "method": "unknown"}
        
        try:
            import subprocess
            # 获取视频信息
            info = subprocess.run(
                ["yt-dlp", "--skip-download", "--print",
                 "title:%(title)s\nduration:%(duration)s", url],
                capture_output=True, text=True, timeout=30
            )
            
            if info.returncode == 0:
                title = ""
                duration = 0
                for line in info.stdout.strip().split('\n'):
                    if line.startswith('title:'):
                        title = line[6:].strip()
                    elif line.startswith('duration:'):
                        try:
                            duration = int(line[9:].strip())
                        except:
                            pass
                
                result["title"] = title
                result["duration_seconds"] = duration
                
                # 尝试提取字幕
                subprocess.run(
                    ["yt-dlp", "--skip-download",
                     "--write-sub", "--write-auto-sub",
                     "--sub-lang", "zh,zh-Hans,zh-Hant,en",
                     "-o", "/tmp/yt_sub", url],
                    capture_output=True, text=True, timeout=60
                )
                
                subtitle_text = self._read_subtitle_file("/tmp/yt_sub")
                if subtitle_text:
                    result["text"] = subtitle_text
                    result["method"] = "official_captions"
                    return result
            
            # 回退：使用本地whisper
            result["method"] = "local_whisper"
            
        except Exception as e:
            result["error"] = f"YouTube转录失败：{str(e)}"
        
        return result
    
    def _read_subtitle_file(self, base_path: str) -> str:
        """读取字幕文件"""
        for ext in ['.srt', '.vtt', '.ttml', '.xml']:
            fp = base_path + ext
            if os.path.exists(fp):
                with open(fp, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                if ext == '.srt':
                    lines = content.strip().split('\n')
                    text_lines = []
                    for line in lines:
                        if '-->' in line:
                            continue
                        if re.match(r'^\d+$', line.strip()):
                            continue
                        if line.strip():
                            text_lines.append(line.strip())
                    return ' '.join(text_lines)
                
                elif ext == '.vtt':
                    lines = content.strip().split('\n')
                    text_lines = []
                    skip_header = True
                    for line in lines:
                        if skip_header and line.startswith('WEBVTT'):
                            continue
                        elif skip_header:
                            skip_header = False
                            continue
                        if '-->' in line or not line.strip():
                            continue
                        clean = re.sub(r'<[^>]+>', '', line).strip()
                        if clean:
                            text_lines.append(clean)
                    return ' '.join(text_lines)
                
                elif ext in ['.ttml', '.xml']:
                    matches = re.findall(r'>([^<]+)<', content)
                    return ' '.join([t.strip() for t in matches if t.strip() and len(t.strip()) > 1])
        
        return ""
    
    def _transcribe_local_video(self, filepath: str) -> dict:
        if not os.path.exists(filepath):
            return {"error": f"文件不存在：{filepath}"}
        
        try:
            import subprocess
            audio_path = filepath.rsplit('.', 1)[0] + '_audio.wav'
            subprocess.run(
                ["ffmpeg", "-y", "-i", filepath,
                 "-vn", "-acodec", "pcm_s16le", "-ar", "16000",
                 "-ac", "1", audio_path],
                capture_output=True, text=True, timeout=300
            )
            if os.path.exists(audio_path):
                return self._transcribe_audio_file(audio_path)
            return {"error": "音频提取失败"}
        except Exception as e:
            return {"error": f"视频转录失败：{str(e)}"}
    
    def _transcribe_local_audio(self, filepath: str) -> dict:
        if not os.path.exists(filepath):
            return {"error": f"文件不存在：{filepath}"}
        return self._transcribe_audio_file(filepath)
    
    def _load_transcript(self, filepath: str) -> dict:
        if not os.path.exists(filepath):
            return {"error": f"文件不存在：{filepath}"}
        with open(filepath, 'r', encoding='utf-8') as f:
            text = f.read()
        return {"source": filepath, "source_type": "transcript", "text": text,
                "character_count": len(text)}
    
    def _transcribe_audio_file(self, audio_path: str) -> dict:
        result = {"source": audio_path, "method": "faster_whisper"}
        try:
            from modules.voice_to_text import VoiceToTextEngine
            engine = VoiceToTextEngine(model_size=self.whisper_model)
            transcribed = engine.transcribe(audio_path)
            if transcribed:
                result["text"] = transcribed.get("text", "")
                result["segments"] = transcribed.get("segments", [])
                result["duration_seconds"] = transcribed.get("duration", 0)
                result["language"] = transcribed.get("language", "unknown")
            else:
                result["error"] = "转录结果为空"
        except ImportError:
            result["error"] = "Faster-Whisper未安装"
        except Exception as e:
            result["error"] = f"转录失败：{str(e)}"
        return result


def transcribe_video(source: str, source_type: str = "youtube",
                     whisper_model: str = "base") -> dict:
    t = VideoTranscriber(whisper_model=whisper_model)
    return t.transcribe(source, source_type=source_type)
