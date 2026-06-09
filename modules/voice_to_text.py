"""Faster-Whisper 语音转文字模块

集成 Faster-Whisper 实现高性能中文语音转文字（STT）。
支持：
- 本地转录（CPU/GPU）
- 热词增强（注入短剧术语提升准确率）
- VAD 过滤静音段
- 单词级时间戳（用于字幕）
- 中英混说识别
"""

import os
import json
import tempfile
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path

from faster_whisper import WhisperModel, BatchedInferencePipeline


@dataclass
class TranscriptionResult:
    """转录结果"""
    text: str                              # 完整文本
    segments: List[Dict]                   # 分段详情（含时间戳）
    words: List[Dict]                      # 单词级时间戳
    language: str                          # 检测到的语言
    language_probability: float            # 语言置信度
    duration_seconds: float                # 音频总时长（秒）
    model_size: str                        # 使用的模型
    compute_type: str                      # 计算类型


@dataclass
class VoiceProfile:
    """热词增强配置"""
    # 短剧行业术语和常见人名
    short_drama_terms: List[str] = None
    
    def __post_init__(self):
        if self.short_drama_terms is None:
            self.short_drama_terms = [
                # 短剧题材
                "重生复仇", "霸总", "逆袭", "甜宠", "战神", "悬疑",
                "总裁", "契约", "马甲", "萌宝", "马甲", "团宠",
                "修罗", "龙王", "赘婿", "闪婚", "替身", "白月光",
                "黑月光", "追妻", "火葬场", "虐恋", "爽文",
                # 短剧制作术语
                "分镜", "剧本", "旁白", "台词", "情绪提示",
                "动作描述", "场景描述", "镜头语言", "转场",
                # 角色称谓
                "顾承泽", "林婉清", "宾客", "警察", "特写",
                # 通用人名
                "张伟", "李娜", "王芳", "刘洋", "陈明",
                "赵敏", "孙红雷", "周杰", "吴京", "徐峥",
            ]


class VoiceToTextEngine:
    """语音转文字引擎（基于 Faster-Whisper）"""
    
    # 支持的模型尺寸
    MODEL_SIZES = {
        "tiny": {"size_mb": 75, "desc": "极速模式，适合短语音"},
        "base": {"size_mb": 140, "desc": "快速模式，通用场景"},
        "small": {"size_mb": 460, "desc": "平衡模式"},
        "medium": {"size_mb": 1500, "desc": "高精度"},
        "large-v3": {"size_mb": 3000, "desc": "最高精度，推荐"},
        "distil-large-v3": {"size_mb": 1500, "desc": "蒸馏模型，快速高精度"},
    }
    
    # 计算类型
    COMPUTE_TYPES = {
        "float16": "GPU FP16（最快）",
        "int8_float16": "GPU INT8（平衡）",
        "int8": "CPU INT8（无需GPU）",
        "float32": "CPU FP32（最准但慢）",
    }
    
    def __init__(
        self,
        model_size: str = "large-v3",
        device: str = "cpu",
        compute_type: str = "int8",
        voice_profile: Optional[VoiceProfile] = None,
    ):
        """
        Args:
            model_size: 模型尺寸（tiny/base/small/medium/large-v3）
            device: "cpu" 或 "cuda"（GPU，需安装 CUDA）
            compute_type: 计算精度
            voice_profile: 热词增强配置
        """
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.voice_profile = voice_profile or VoiceProfile()
        self.model = None
        
        # 加载模型
        print(f"[VoiceToText] 正在加载模型: {model_size} ({self.compute_type})...")
        self._load_model()
    
    def _load_model(self):
        """加载 Faster-Whisper 模型"""
        try:
            self.model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
                download_root=os.path.expanduser("~/.cache/faster-whisper"),
            )
            size_mb = self.MODEL_SIZES.get(self.model_size, {}).get("size_mb", "?")
            print(f"[VoiceToText] 模型加载完成: {self.model_size} ({size_mb}MB)")
        except Exception as e:
            print(f"[VoiceToText] 模型加载失败: {e}")
            print(f"[VoiceToText] 请确保已安装: pip install faster-whisper")
            raise
    
    def transcribe(
        self,
        audio_path: str,
        language: Optional[str] = "zh",
        vad_filter: bool = True,
        word_timestamps: bool = True,
        return_segments: bool = True,
        beam_size: int = 5,
    ) -> TranscriptionResult:
        """
        转录音频文件为文字。
        
        Args:
            audio_path: 音频文件路径（支持 wav/mp3/m4a/ogg）
            language: 语言代码（zh=中文, en=英文, None=自动检测）
            vad_filter: 是否过滤静音段
            word_timestamps: 是否返回单词级时间戳
            return_segments: 是否返回分段详情
            beam_size: 束搜索大小（越大越准但越慢）
        
        Returns:
            TranscriptionResult
        """
        # 构建热词 prompt
        initial_prompt = None
        if self.voice_profile and self.voice_profile.short_drama_terms:
            initial_prompt = " ".join(self.voice_profile.short_drama_terms)
        
        # 构建 VAD 参数
        vad_params = None
        if vad_filter:
            vad_params = {
                "min_silence_duration_ms": 500,  # 静音段最短500ms
                "threshold": 0.5,                 # 语音检测阈值
                "min_speech_duration_ms": 250,    # 语音段最短250ms
            }
        
        # 执行转录
        segments, info = self.model.transcribe(
            audio_path,
            beam_size=beam_size,
            language=language,
            vad_filter=vad_filter,
            vad_parameters=vad_params,
            word_timestamps=word_timestamps,
            initial_prompt=initial_prompt,
        )
        
        # 收集结果
        full_text = ""
        seg_list = []
        word_list = []
        total_duration = 0.0
        
        for segment in segments:
            full_text += segment.text
            total_duration = max(total_duration, segment.end)
            
            seg_entry = {
                "start": round(segment.start, 2),
                "end": round(segment.end, 2),
                "text": segment.text,
                "speaker": segment.speaker if hasattr(segment, "speaker") else None,
            }
            seg_list.append(seg_entry)
            
            if word_timestamps and hasattr(segment, "words") and segment.words:
                for word in segment.words:
                    word_list.append({
                        "start": round(word.start, 2),
                        "end": round(word.end, 2),
                        "word": word.word,
                    })
        
        result = TranscriptionResult(
            text=full_text.strip(),
            segments=seg_list,
            words=word_list,
            language=info.language,
            language_probability=info.language_probability,
            duration_seconds=round(total_duration, 2),
            model_size=self.model_size,
            compute_type=self.compute_type,
        )
        
        # 打印摘要
        lang_name = {"zh": "中文", "en": "英文"}.get(info.language, info.language)
        print(f"[VoiceToText] 转录完成: {result.duration_seconds}s "
              f"| {len(seg_list)}段 | 语言: {lang_name}({info.language_probability:.1%})")
        
        return result
    
    def transcribe_batch(
        self,
        audio_paths: List[str],
        batch_size: int = 16,
        language: str = "zh",
    ) -> List[TranscriptionResult]:
        """
        批量转录多个音频文件（性能最优）。
        
        Args:
            audio_paths: 音频文件路径列表
            batch_size: 批处理大小
            language: 语言代码
        
        Returns:
            转录结果列表
        """
        model = WhisperModel(
            self.model_size,
            device=self.device,
            compute_type=self.compute_type,
        )
        pipeline = BatchedInferencePipeline(model=model, batch_size=batch_size)
        
        results = []
        for i, audio_path in enumerate(audio_paths):
            try:
                segments, info = pipeline.transcribe(
                    audio_path,
                    language=language,
                    vad_filter=True,
                    batch_size=batch_size,
                )
                full_text = " ".join(s.text for s in segments)
                total_duration = max((s.end for s in segments), default=0)
                
                results.append(TranscriptionResult(
                    text=full_text.strip(),
                    segments=[{
                        "start": round(s.start, 2),
                        "end": round(s.end, 2),
                        "text": s.text,
                    } for s in segments],
                    words=[],
                    language=info.language,
                    language_probability=info.language_probability,
                    duration_seconds=round(total_duration, 2),
                    model_size=self.model_size,
                    compute_type=self.compute_type,
                ))
            except Exception as e:
                print(f"[VoiceToText] 文件 {audio_path} 转录失败: {e}")
                results.append(None)
        
        return results
    
    def save_srt(
        self,
        result: TranscriptionResult,
        output_path: str,
        font_size: int = 36,
    ):
        """
        保存为 SRT 字幕文件（可直接用于视频剪辑）。
        
        Args:
            result: 转录结果
            output_path: SRT 文件输出路径
            font_size: 建议字幕字号
        """
        def format_srt_time(seconds: float) -> str:
            """转换为 SRT 时间格式 HH:MM:SS,mmm"""
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            secs = int(seconds % 60)
            millis = int((seconds % 1) * 1000)
            return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
        
        with open(output_path, "w", encoding="utf-8") as f:
            for i, seg in enumerate(result.segments, 1):
                f.write(f"{i}\n")
                f.write(f"{format_srt_time(seg['start'])} --> {format_srt_time(seg['end'])}\n")
                f.write(f"{seg['text']}\n\n")
        
        print(f"[VoiceToText] SRT 字幕已保存: {output_path}")
    
    def save_json(self, result: TranscriptionResult, output_path: str):
        """保存为 JSON 格式（含完整元数据）"""
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(asdict(result), f, indent=2, ensure_ascii=False)
        print(f"[VoiceToText] JSON 结果已保存: {output_path}")
    
    def get_model_info(self) -> Dict:
        """返回当前模型配置信息"""
        return {
            "model_size": self.model_size,
            "model_info": self.MODEL_SIZES.get(self.model_size, {}),
            "device": self.device,
            "compute_type": self.compute_type,
            "compute_type_info": self.COMPUTE_TYPES.get(self.compute_type, ""),
            "available_models": {
                name: info["desc"] for name, info in self.MODEL_SIZES.items()
            },
        }
    
    def close(self):
        """释放模型资源"""
        if self.model:
            del self.model
            self.model = None
            print("[VoiceToText] 模型已释放")


# ===== 便捷函数 =====

def transcribe_audio(
    audio_path: str,
    model_size: str = "large-v3",
    language: str = "zh",
    output_dir: str = "output/voice",
    save_srt: bool = True,
    save_json: bool = True,
    **kwargs,
) -> TranscriptionResult:
    """
    一键转录音频文件。
    
    Args:
        audio_path: 音频文件路径
        model_size: 模型尺寸
        language: 语言代码
        output_dir: 输出目录
        save_srt: 是否保存 SRT 字幕
        save_json: 是否保存 JSON 结果
        **kwargs: 传递给 transcribe() 的其他参数
    
    Returns:
        TranscriptionResult
    """
    engine = VoiceToTextEngine(model_size=model_size)
    try:
        result = engine.transcribe(audio_path, language=language, **kwargs)
        
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            base_name = Path(audio_path).stem
            
            if save_srt:
                engine.save_srt(result, os.path.join(output_dir, f"{base_name}.srt"))
            if save_json:
                engine.save_json(result, os.path.join(output_dir, f"{base_name}.json"))
        
        return result
    finally:
        engine.close()


if __name__ == "__main__":
    # 快速测试
    print("=" * 50)
    print("  VoiceToText 引擎测试")
    print("=" * 50)
    
    # 打印可用模型
    engine = VoiceToTextEngine(model_size="large-v3", device="cpu", compute_type="int8")
    info = engine.get_model_info()
    print("\n可用模型:")
    for name, desc in info["available_models"].items():
        print(f"  {name}: {desc}")
    
    print(f"\n当前配置: {info}")
    
    engine.close()
    print("\n测试完成!")
