"""语音交互模块 - 录音、语音转文字、LLM 处理、语音播报

完整的语音交互闭环：
1. 麦克风录音 → 保存到临时文件
2. Faster-Whisper 转录为文字
3. 调用 LLM 生成回复/剧本
4. TTS 语音播报回复

支持两种模式：
- 指令模式：语音输入 → LLM 回复
- 剧本模式：语音描述剧情 → 自动生成剧本
"""

import os
import io
import tempfile
import wave
import time
import json
from typing import Optional, Callable, List, Dict
from dataclasses import dataclass, field

import edge_tts

from modules.voice_to_text import VoiceToTextEngine, TranscriptionResult
from modules.tts_engine import TTSEngine
from modules.llm_client import LLMClient


# ===== 数据结构 =====

@dataclass
class VoiceMessage:
    """语音消息"""
    role: str              # "user" 或 "assistant"
    text: str              # 文字内容
    audio_path: Optional[str] = None  # 音频路径（可选）
    duration: float = 0.0       # 语音时长（秒）
    timestamp: float = field(default_factory=time.time)


@dataclass
class VoiceInteractionState:
    """语音交互状态"""
    conversation_history: List[Dict] = field(default_factory=list)
    current_mode: str = "instruction"  # "instruction" 或 "script"
    recording: bool = False
    last_transcription: Optional[TranscriptionResult] = None


# ===== 核心引擎 =====

class VoiceInteractionEngine:
    """语音交互引擎

    整合录音、语音转文字、LLM、语音播报于一体。
    """

    def __init__(
        self,
        stt_model_size: str = "large-v3",
        stt_device: str = "cpu",
        stt_compute_type: str = "int8",
        tts_config: Optional[dict] = None,
        llm_client: Optional[LLMClient] = None,
    ):
        """
        Args:
            stt_model_size: Faster-Whisper 模型尺寸
            stt_device: 设备（cpu/cuda）
            stt_compute_type: 计算类型（int8/float16）
            tts_config: TTS 配置
            llm_client: LLM 客户端
        """
        # 语音转文字引擎
        self.stt = VoiceToTextEngine(
            model_size=stt_model_size,
            device=stt_device,
            compute_type=stt_compute_type,
        )

        # TTS 引擎
        self.tts = TTSEngine(config=tts_config or {})

        # LLM 客户端
        self.llm = llm_client or LLMClient()

        # 交互状态
        self.state = VoiceInteractionState()
        self.callbacks = {
            "on_recording_start": [],
            "on_recording_end": [],
            "on_transcription": [],
            "on_llm_response": [],
            "on_speech_play": [],
        }

    def _register_callback(self, event: str, callback: Callable):
        """注册回调函数"""
        if event in self.callbacks:
            self.callbacks[event].append(callback)

    def _emit(self, event: str, *args, **kwargs):
        """触发回调"""
        for cb in self.callbacks.get(event, []):
            try:
                cb(*args, **kwargs)
            except Exception:
                pass

    # ===== 录音功能 =====

    def record_audio(
        self,
        duration: float = 10.0,
        output_path: Optional[str] = None,
        sample_rate: int = 16000,
    ) -> str:
        """
        从麦克风录音指定时长。
        
        Args:
            duration: 录音时长（秒），默认 10 秒
            output_path: 输出 WAV 文件路径
            sample_rate: 采样率

        Returns:
            输出的 WAV 文件路径
        """
        if output_path is None:
            output_path = os.path.join(
                tempfile.gettempdir(),
                f"voice_{int(time.time())}.wav"
            )

        # 尝试使用 pyaudio 录音
        try:
            import pyaudio
            audio = pyaudio.PyAudio()
            
            # 获取默认麦克风设备
            device_index = None
            for i in range(audio.get_device_count()):
                dev_info = audio.get_device_info_by_index(i)
                if dev_info.get("maxInputChannels", 0) > 0:
                    device_index = i
                    break

            if device_index is None:
                raise RuntimeError("未找到麦克风设备")

            stream = audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=sample_rate,
                input=True,
                input_device_index=device_index,
            )

            print(f"[VoiceInteraction] 开始录音 ({duration}秒)...")
            frames = []

            # 播放提示音（蜂鸣声）
            self._play_beep(audio, sample_rate, 0.1)

            import numpy as np
            for _ in range(int(sample_rate * duration / 100)):  # 10ms 一帧
                data = stream.read(1024)
                frames.append(data)

            # 结束提示音
            self._play_beep(audio, sample_rate, 0.1, freq=880)

            stream.stop_stream()
            stream.close()
            audio.terminate()

            # 保存 WAV
            with wave.open(output_path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)  # 16-bit
                wf.setframerate(sample_rate)
                wf.writeframes(b"".join(frames))

            file_size = os.path.getsize(output_path)
            print(f"[VoiceInteraction] 录音完成: {output_path} ({file_size / 1024:.1f}KB)")
            self.state.recording = False
            self._emit("on_recording_end", output_path, duration)

            return output_path

        except ImportError:
            print("[VoiceInteraction] 未安装 pyaudio，跳过录音")
            print("[VoiceInteraction] 跳过此步骤，直接提供音频文件路径")
            return ""
        except Exception as e:
            print(f"[VoiceInteraction] 录音失败: {e}")
            return ""

    def _play_beep(self, audio, sample_rate: int, duration: float, freq: int = 440):
        """播放蜂鸣提示音"""
        try:
            import numpy as np
            t = np.linspace(0, duration, int(sample_rate * duration), False)
            data = (np.sin(2 * np.pi * freq * t) * 32767).astype(np.int16).tobytes()
            
            stream = audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=sample_rate,
                output=True,
            )
            stream.write(data)
            stream.stop_stream()
            stream.close()
        except Exception:
            pass

    def record_to_file(self, audio_bytes: bytes, output_path: str):
        """将音频字节保存到文件"""
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(audio_bytes)
        return output_path

    # ===== 核心交互流程 =====

    def voice_to_instruction(
        self,
        audio_path: str,
        mode: str = "instruction",
    ) -> VoiceMessage:
        """
        语音指令处理：录音 → 转录 → LLM 回复 → 可选语音播报
        
        Args:
            audio_path: 录音文件路径
            mode: 交互模式 ("instruction" 或 "script")

        Returns:
            VoiceMessage - 包含 LLM 回复的文字和 TTS 音频
        """
        self.state.current_mode = mode

        # 1. 转录
        print("\n[VoiceInteraction] 正在转录语音...")
        transcription = self.stt.transcribe(audio_path, language="zh")
        self.state.last_transcription = transcription
        self._emit("on_transcription", transcription)

        user_text = transcription.text
        print(f"[VoiceInteraction] 识别结果: {user_text}")

        if not user_text.strip():
            return VoiceMessage(
                role="assistant",
                text="没听清，请再说一遍。",
                audio_path=self.tts.synthesize("没听清，请再说一遍。"),
            )

        # 2. 调用 LLM
        print("[VoiceInteraction] 正在生成回复...")
        assistant_text = self._generate_response(user_text, mode)
        print(f"[VoiceInteraction] 回复: {assistant_text[:200]}...")

        # 3. 语音播报
        print("[VoiceInteraction] 正在合成语音...")
        audio_path = self.tts.synthesize_with_emotion(
            assistant_text,
            character_gender="male",
            emotion="calm",
        )

        msg = VoiceMessage(
            role="assistant",
            text=assistant_text,
            audio_path=audio_path,
            timestamp=time.time(),
        )

        self._emit("on_llm_response", msg)
        self._emit("on_speech_play", audio_path)

        return msg

    def voice_to_script(
        self,
        audio_path: str,
        genre: str = "重生复仇",
        episode_count: int = 1,
    ) -> Dict:
        """
        语音生成剧本：语音描述剧情 → 自动生成剧本
        
        Args:
            audio_path: 录音文件路径
            genre: 短剧题材
            episode_count: 集数

        Returns:
            包含剧本、角色卡、大纲的字典
        """
        # 1. 转录
        print("\n[VoiceInteraction] 正在转录语音描述...")
        transcription = self.stt.transcribe(audio_path, language="zh")
        self.state.last_transcription = transcription

        user_text = transcription.text
        print(f"[VoiceInteraction] 剧情描述: {user_text}")

        # 2. 调用 creative planner + script writer
        print("[VoiceInteraction] 正在生成剧本...")

        # 构建 prompt
        prompt = f"""请根据以下语音描述，生成短剧剧本。

题材：{genre}
集数：{episode_count} 集

用户语音描述：
"{user_text}"

请生成：
1. 角色卡片（至少3个角色）
2. 分集大纲
3. 第一集完整剧本

格式使用 JSON，包含：
- character_cards: 角色列表
- episode_outlines: 分集大纲
- script: 第一集剧本"""

        try:
            result = self.llm.chat(prompt, max_tokens=4096)
            # 尝试解析 JSON
            try:
                data = json.loads(result)
            except json.JSONDecodeError:
                # 提取 JSON 代码块
                import re
                match = re.search(r'\{[\s\S]*\}', result)
                if match:
                    data = json.loads(match.group())
                else:
                    data = {"text": result, "script": result}

            print("[VoiceInteraction] 剧本生成完成！")
            return data

        except Exception as e:
            print(f"[VoiceInteraction] 剧本生成失败: {e}")
            return {
                "error": str(e),
                "user_description": user_text,
            }

    def chat_with_voice(
        self,
        audio_path: str,
        conversation_history: Optional[List[Dict]] = None,
    ) -> VoiceMessage:
        """
        多轮语音对话。
        
        Args:
            audio_path: 录音文件路径
            conversation_history: 对话历史

        Returns:
            VoiceMessage
        """
        # 转录
        transcription = self.stt.transcribe(audio_path, language="zh")
        user_text = transcription.text
        self.state.last_transcription = transcription

        # 更新对话历史
        if conversation_history is None:
            conversation_history = self.state.conversation_history

        conversation_history.append({
            "role": "user",
            "content": user_text,
        })

        # LLM 生成回复
        # 构建系统提示
        system_prompt = """你是一个短剧智能助手。
你的任务是帮助规划和创作短剧。
请简洁、专业地回答用户的问题。
用中文回答。"""

        messages = [
            {"role": "system", "content": system_prompt},
        ] + conversation_history[-10:]  # 最近10轮

        try:
            assistant_text = self.llm.chat_with_messages(messages, max_tokens=2048)
        except Exception as e:
            assistant_text = f"抱歉，出了点问题: {e}"

        # 保存对话历史
        conversation_history.append({
            "role": "assistant",
            "content": assistant_text,
        })

        self.state.conversation_history = conversation_history

        # 语音播报
        audio_path_out = self.tts.synthesize(
            assistant_text,
            voice=self.tts.default_voice_male,
            rate="+5%",
        )

        return VoiceMessage(
            role="assistant",
            text=assistant_text,
            audio_path=audio_path_out,
        )

    # ===== 辅助方法 =====

    def _generate_response(self, user_text: str, mode: str = "instruction") -> str:
        """根据模式生成 LLM 回复"""
        if mode == "script":
            prompt = f"""用户想要创作短剧，描述如下：
"{user_text}"

请给出专业的剧本创作建议。包括：
1. 题材推荐
2. 角色设定建议
3. 故事大纲建议
4. 下一步操作"""
        else:
            prompt = f"""用户语音输入：
"{user_text}"

请简短、友好地回复用户。如果用户想要创作短剧，引导用户提供更多细节。"""

        try:
            return self.llm.chat(prompt, max_tokens=1024)
        except Exception as e:
            return f"无法处理请求: {e}"

    def play_audio(self, audio_path: str):
        """播放音频文件"""
        if not audio_path or not os.path.exists(audio_path):
            print(f"[VoiceInteraction] 音频文件不存在: {audio_path}")
            return

        import subprocess
        try:
            subprocess.Popen(["start", audio_path], shell=True)
        except Exception as e:
            print(f"[VoiceInteraction] 播放失败: {e}")

    def get_status(self) -> Dict:
        """获取当前状态"""
        return {
            "mode": self.state.current_mode,
            "recording": self.state.recording,
            "conversation_count": len(self.state.conversation_history),
            "stt_model": self.stt.model_size,
            "stt_device": self.stt.device,
            "tts_voices": self.tts.get_available_voices_summary()[:5],
            "model_info": self.stt.get_model_info(),
        }

    def close(self):
        """释放资源"""
        self.stt.close()


# ===== 便捷函数 =====

def quick_voice_transcribe(
    audio_path: str,
    model_size: str = "large-v3",
) -> str:
    """
    快速转录语音文件为文字。
    
    Args:
        audio_path: 音频文件路径
        model_size: 模型尺寸
    
    Returns:
        转录文字
    """
    engine = VoiceToTextEngine(model_size=model_size)
    try:
        result = engine.transcribe(audio_path, language="zh")
        return result.text
    finally:
        engine.close()


def quick_tts(text: str, output_path: str) -> str:
    """
    快速将文字转为语音。
    
    Args:
        text: 要合成的文字
        output_path: 输出 MP3 路径
    
    Returns:
        音频文件路径
    """
    tts = TTSEngine()
    return tts.synthesize(text, voice=tts.default_voice_male, output_path=output_path)


if __name__ == "__main__":
    # 快速测试
    print("=" * 50)
    print("  语音交互引擎测试")
    print("=" * 50)

    engine = VoiceInteractionEngine()
    status = engine.get_status()
    print("\n当前配置:")
    print(f"  模式: {status['mode']}")
    print(f"  STT 模型: {status['stt_model']} ({status['stt_device']})")
    print(f"  TTS 音色: {status['tts_voices'][:2]}")
    print(f"  对话轮数: {status['conversation_count']}")

    print("\n可用中文语音:")
    engine.tts.print_chinese_voices()

    engine.close()
    print("\n测试完成!")
