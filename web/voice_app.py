#!/usr/bin/env python3
"""短剧智能体桌面版 APP - 语音交互界面

功能：
1. 语音录制 → 转文字 → LLM 回复 → 语音播报
2. 语音生成剧本（描述剧情 → 自动生成）
3. 对话历史查看
4. 设置面板（STT 模型、TTS 音色、题材选择）

使用 CustomTkinter 构建现代化桌面 UI。
"""

import os
import sys
import json
import time
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path
from datetime import datetime

# CustomTkinter for modern UI
import customtkinter

# 设置主题
customtkinter.set_appearance_mode("dark")
customtkinter.set_default_color_theme("blue")


class VoiceApp(customtkinter.CTk):
    """短剧智能体桌面版主窗口"""

    def __init__(self):
        super().__init__()

        self.title("AI 短剧智能体 v2.0")
        self.geometry("900x700")
        self.minsize(800, 600)

        # 加载模块
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from modules.llm_client import LLMClient
        from modules.voice_interact import VoiceInteractionEngine
        from modules.tts_engine import TTSEngine
        from modules.voice_to_text import VoiceToTextEngine

        # 初始化引擎
        self.llm = LLMClient()
        self.tts = TTSEngine()
        self.stt = VoiceToTextEngine(model_size="large-v3", device="cpu", compute_type="int8")
        self.voice_engine = VoiceInteractionEngine(
            llm_client=self.llm,
            tts_config={
                "voice_female": "zh-CN-XiaoxiaoNeural",
                "voice_male": "zh-CN-YunxiNeural",
                "output_dir": os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output", "voice"),
            },
        )

        # 状态
        self.recording = False
        self.conversation_history = []
        self.current_genre = "重生复仇"
        self.genre_list = ["重生复仇", "霸总", "逆袭", "悬疑", "战神", "甜宠"]

        # 构建界面
        self._build_ui()
        self._print_voice_list()

    def _build_ui(self):
        """构建界面"""
        # 主框架
        main_frame = customtkinter.CTkFrame(self, corner_radius=0)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # ===== 顶部栏 =====
        top_frame = customtkinter.CTkFrame(main_frame)
        top_frame.pack(fill="x", pady=(0, 10))

        title = customtkinter.CTkLabel(
            top_frame, text="AI 短剧智能体",
            font=customtkinter.CTkFont(size=20, weight="bold"),
        )
        title.pack(side="left", padx=15, pady=10)

        # 题材选择
        genre_label = customtkinter.CTkLabel(top_frame, text="题材:")
        genre_label.pack(side="left", padx=(10, 5), pady=10)

        genre_var = customtkinter.StringVar(value=self.current_genre)
        genre_combo = customtkinter.CTkComboBox(
            top_frame, values=self.genre_list,
            variable=genre_var, width=120,
            command=self._on_genre_change,
        )
        genre_combo.pack(side="left", padx=5, pady=10)
        self.genre_var = genre_var

        # ===== 内容区域 =====
        content_frame = customtkinter.CTkFrame(main_frame)
        content_frame.pack(fill="both", expand=True, padx=0, pady=0)

        # 左侧：对话区
        left_frame = customtkinter.CTkFrame(content_frame)
        left_frame.pack(side="left", fill="both", expand=True, padx=(0, 10), pady=10)

        # 对话文本区
        self.chat_text = customtkinter.CTkTextbox(
            left_frame, width=500, height=400,
            corner_radius=10, font=customtkinter.CTkFont(size=14),
        )
        self.chat_text.pack(fill="both", expand=True, padx=10, pady=10)
        self.chat_text.insert("1.0", "欢迎使用 AI 短剧智能体！\n\n语音交互已就绪。\n点击下方麦克风按钮开始对话。\n\n")

        # 底部输入区
        input_frame = customtkinter.CTkFrame(left_frame)
        input_frame.pack(fill="x", padx=10, pady=(0, 10))

        self.input_var = customtkinter.StringVar()
        self.input_entry = customtkinter.CTkEntry(
            input_frame, textvariable=self.input_var,
            placeholder_text="输入文字指令...", height=40,
        )
        self.input_entry.pack(side="left", fill="x", expand=True, padx=(0, 5), pady=5)
        self.input_entry.bind("<Return>", lambda e: self._send_text_message())

        # 发送按钮
        send_btn = customtkinter.CTkButton(
            input_frame, text="发送", width=80, height=40,
            fg_color="#2ECC71", hover_color="#27AE60",
            command=self._send_text_message,
        )
        send_btn.pack(side="right", pady=5)

        # ===== 右侧：控制面板 =====
        right_frame = customtkinter.CTkFrame(content_frame, width=280)
        right_frame.pack(side="right", fill="y", padx=(10, 0), pady=10)
        right_frame.pack_propagate(False)

        # 录音按钮（大圆形）
        self.record_btn_frame = customtkinter.CTkFrame(right_frame)
        self.record_btn_frame.pack(pady=20)

        self.record_btn = customtkinter.CTkButton(
            self.record_btn_frame,
            text="🎤",
            width=100, height=100,
            font=customtkinter.CTkFont(size=40),
            fg_color="#E74C3C",
            hover_color="#C0392B",
            corner_radius=50,
            command=self._toggle_recording,
        )
        self.record_btn.pack()

        self.record_label = customtkinter.CTkLabel(
            right_frame, text="点击录音",
            font=customtkinter.CTkFont(size=12),
        )
        self.record_label.pack(pady=(5, 0))

        # 语音播报按钮
        self.play_btn = customtkinter.CTkButton(
            right_frame, text="🔊 播放最后回复",
            width=240, height=40,
            fg_color="#3498DB",
            hover_color="#2980B9",
            command=self._play_last_response,
        )
        self.play_btn.pack(pady=10)

        # 录音状态
        self.status_var = customtkinter.StringVar(value="就绪")
        status_label = customtkinter.CTkLabel(
            right_frame, textvariable=self.status_var,
            font=customtkinter.CTkFont(size=11),
        )
        status_label.pack(pady=10)

        # 分离标签页（对话历史 / 设置）
        self.tabview = customtkinter.CTkTabview(
            right_frame, width=260, height=200,
        )
        self.tabview.pack(pady=10, padx=10)

        # 对话历史标签
        history_tab = self.tabview.add("对话历史")
        self.history_listbox = customtkinter.CTkTextbox(
            history_tab, height=160,
            font=customtkinter.CTkFont(size=10),
        )
        self.history_listbox.pack(fill="both", expand=True, padx=5, pady=5)

        # 设置标签
        settings_tab = self.tabview.add("设置")

        stt_label = customtkinter.CTkLabel(settings_tab, text="STT 模型:")
        stt_label.pack(anchor="w", padx=5, pady=(5, 0))
        self.stt_model_var = customtkinter.StringVar(value="large-v3")
        stt_combo = customtkinter.CTkComboBox(
            settings_tab,
            values=["tiny", "base", "small", "medium", "large-v3"],
            variable=self.stt_model_var, width=200,
        )
        stt_combo.pack(pady=2)

        tts_label = customtkinter.CTkLabel(settings_tab, text="播报音色:")
        tts_label.pack(anchor="w", padx=5, pady=(10, 0))
        self.tts_voice_var = customtkinter.StringVar(value="male")
        tts_combo = customtkinter.CTkComboBox(
            settings_tab, values=["male (男声)", "female (女声)"],
            variable=self.tts_voice_var, width=200,
        )
        tts_combo.pack(pady=2)

        # 按钮区域
        btn_frame = customtkinter.CTkFrame(right_frame)
        btn_frame.pack(pady=10, padx=10, fill="x")

        script_btn = customtkinter.CTkButton(
            btn_frame, text="🎬 语音生成剧本",
            height=40, fg_color="#9B59B6",
            hover_color="#8E44AD",
            command=self._voice_generate_script,
        )
        script_btn.pack(pady=2)

        clear_btn = customtkinter.CTkButton(
            btn_frame, text="🗑 清空对话",
            height=40, fg_color="#95A5A6",
            hover_color="#7F8C8D",
            command=self._clear_chat,
        )
        clear_btn.pack(pady=2)

        settings_btn = customtkinter.CTkButton(
            btn_frame, text="⚙ 完整设置",
            height=40,
            fg_color="#34495E",
            hover_color="#2C3E50",
            command=self._open_settings,
        )
        settings_btn.pack(pady=2)

    def _print_voice_list(self):
        """打印可用语音"""
        voices = self.tts.get_available_voices_summary()
        for v in voices[:5]:
            print(f"  {v['name']} ({v['gender']})")

    def _on_genre_change(self, value):
        """题材切换回调"""
        self.current_genre = value
        self._add_chat_message("系统", f"题材已切换为: {value}")

    def _toggle_recording(self):
        """切换录音状态"""
        if self.recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self):
        """开始录音"""
        self.recording = True
        self.record_btn.configure(fg_color="#E67E22")
        self.record_label.configure(text="录音中... 点击停止")
        self.status_var.set("录音中...")

        # 在后台线程录音
        thread = threading.Thread(target=self._do_recording, daemon=True)
        thread.start()

    def _do_recording(self):
        """执行录音"""
        audio_path = self.voice_engine.record_audio(duration=10.0)
        if audio_path and os.path.exists(audio_path):
            self.after(0, lambda: self._process_audio(audio_path))
        else:
            self.after(0, self._recording_failed)

    def _stop_recording(self):
        """停止录音"""
        self.recording = False
        self.record_btn.configure(fg_color="#E74C3C")
        self.record_label.configure(text="点击录音")

    def _recording_failed(self):
        """录音失败"""
        self.status_var.set("录音失败")
        self._add_chat_message("系统", "❌ 录音失败，请检查麦克风设置。")

    def _process_audio(self, audio_path):
        """处理录音文件"""
        self.status_var.set("正在处理...")
        self._add_chat_message("🎤 语音", f"[音频: {os.path.basename(audio_path)}]")

        try:
            # 转录
            self._add_chat_message("🔄 转录中...", "")

            transcription = self.stt.transcribe(audio_path, language="zh")
            user_text = transcription.text
            duration = transcription.duration_seconds

            self._add_chat_message("🗣 识别", user_text or "(未识别到文字)")

            if not user_text.strip():
                self._add_chat_message("系统", "没听清，请再说一遍。")
                self.status_var.set("就绪")
                return

            # 添加到对话历史
            self.conversation_history.append({
                "role": "user",
                "content": user_text,
            })

            # 生成回复
            self._add_chat_message("🤖 思考中...", "")
            response = self._generate_response(user_text)

            # 保存到历史
            self.conversation_history.append({
                "role": "assistant",
                "content": response,
            })

            # 语音播报
            audio_path_out = self.tts.synthesize(
                response,
                voice=self.tts.default_voice_male,
                rate="+5%",
            )

            self._add_chat_message("🤖 回复", response)
            self._add_chat_message("🔊 语音", f"[音频: {os.path.basename(audio_path_out) if audio_path_out else '无'}]")

            # 更新设置
            self._update_history_list()
            self.status_var.set("就绪")

        except Exception as e:
            self._add_chat_message("系统", f"❌ 处理失败: {e}")
            self.status_var.set("错误")

    def _send_text_message(self):
        """发送文字消息"""
        text = self.input_var.get().strip()
        if not text:
            return

        self.input_var.set("")
        self._add_chat_message("💬 文字", text)

        self.conversation_history.append({"role": "user", "content": text})

        self._add_chat_message("🤖 思考中...", "")
        response = self._generate_response(text)

        self.conversation_history.append({"role": "assistant", "content": response})
        self._add_chat_message("🤖 回复", response)
        self._update_history_list()

    def _generate_response(self, user_text: str) -> str:
        """生成 LLM 回复"""
        system_prompt = """你是一个短剧创作智能助手。
你的职责是帮助用户创作和规划短剧。
用中文回答，简洁专业。

常用题材：重生复仇、霸总、逆袭、甜宠、战神、悬疑
常用功能：
- 创意策划：生成角色卡、分集大纲
- 剧本写作：完整剧本和分镜
- 视觉设计：画面描述和分镜脚本
- 音频制作：配音和 BGM
- 视频剪辑：合成最终视频
- 平台发布：抖音、快手、YouTube Shorts"""

        messages = [
            {"role": "system", "content": system_prompt},
        ] + self.conversation_history[-10:]

        try:
            return self.llm.chat_with_messages(messages, max_tokens=2048)
        except Exception as e:
            return f"抱歉，无法生成回复: {e}"

    def _voice_generate_script(self):
        """语音生成剧本"""
        genre = self.current_genre
        audio_path = self.voice_engine.record_audio(duration=15.0)

        if not audio_path or not os.path.exists(audio_path):
            self._add_chat_message("系统", "❌ 录音失败，请重试。")
            return

        self._add_chat_message("🎬 语音生成剧本", f"[录音: {os.path.basename(audio_path)}]")
        self.status_var.set("生成剧本中...")

        try:
            transcription = self.stt.transcribe(audio_path, language="zh")
            description = transcription.text
            self._add_chat_message("🗣 识别", description)

            if not description.strip():
                self._add_chat_message("系统", "没听清，请再说一遍。")
                self.status_var.set("就绪")
                return

            self._add_chat_message("🤖 正在生成剧本...", f"题材: {genre}")

            prompt = f"""请根据以下描述，生成短剧剧本。

题材：{genre}
语音描述："{description}"

请生成：
1. 角色卡片（3-5 个角色）
2. 分集大纲（5 集）
3. 第一集完整剧本

使用 JSON 格式输出。"""

            result = self.llm.chat(prompt, max_tokens=4096)
            self._add_chat_message("🎬 剧本", result[:1000] + ("..." if len(result) > 1000 else ""))
            self.status_var.set("就绪")

        except Exception as e:
            self._add_chat_message("系统", f"❌ 剧本生成失败: {e}")
            self.status_var.set("错误")

    def _play_last_response(self):
        """播放最后回复"""
        if self.conversation_history:
            last = self.conversation_history[-1]
            if last.get("role") == "assistant":
                audio_path = self.tts.synthesize(
                    last["content"],
                    voice=self.tts.default_voice_male,
                )
                self.voice_engine.play_audio(audio_path)

    def _add_chat_message(self, sender: str, text: str):
        """添加对话消息"""
        time_str = datetime.now().strftime("%H:%M:%S")
        tag = f"msg_{len(self.chat_text.get('1.0', 'end-1c').splitlines())}"

        self.chat_text.configure(state="normal")
        self.chat_text.insert("end", f"\n[{time_str}] {sender}\n")

        if text:
            # 限制显示长度
            display_text = text if len(text) < 500 else text[:500] + "..."
            self.chat_text.insert("end", display_text + "\n")

        self.chat_text.see("end")
        self.chat_text.configure(state="disabled")

    def _update_history_list(self):
        """更新对话历史列表"""
        self.history_listbox.configure(state="normal")
        self.history_listbox.delete("1.0", "end")

        for i, msg in enumerate(self.conversation_history[-20:], 1):
            role_icon = "🙋" if msg["role"] == "user" else "🤖"
            preview = msg["content"][:50] + ("..." if len(msg["content"]) > 50 else "")
            self.history_listbox.insert("end", f"{i}. {role_icon} {preview}\n")

        self.history_listbox.configure(state="disabled")

    def _clear_chat(self):
        """清空对话"""
        if messagebox.askyesno("确认", "确定清空所有对话？"):
            self.chat_text.configure(state="normal")
            self.chat_text.delete("1.0", "end")
            self.chat_text.insert("1.0", "对话已清空。\n")
            self.chat_text.configure(state="disabled")
            self.conversation_history.clear()
            self._update_history_list()

    def _open_settings(self):
        """打开设置窗口"""
        settings_win = customtkinter.CTkToplevel(self)
        settings_win.title("设置")
        settings_win.geometry("400x500")

        frame = customtkinter.CTkFrame(settings_win)
        frame.pack(fill="both", expand=True, padx=20, pady=20)

        customtkinter.CTkLabel(frame, text="STT 模型", font=customtkinter.CTkFont(size=14, weight="bold")).pack(anchor="w", pady=(10, 5))
        stt_combo = customtkinter.CTkComboBox(
            frame, values=["tiny", "base", "small", "medium", "large-v3"],
            variable=self.stt_model_var,
        )
        stt_combo.pack(fill="x", pady=5)

        customtkinter.CTkLabel(frame, text="TTS 播报音色", font=customtkinter.CTkFont(size=14, weight="bold")).pack(anchor="w", pady=(15, 5))
        tts_combo = customtkinter.CTkComboBox(
            frame, values=["male (男声)", "female (女声)"],
            variable=self.tts_voice_var,
        )
        tts_combo.pack(fill="x", pady=5)

        customtkinter.CTkLabel(frame, text="录音时长（秒）", font=customtkinter.CTkFont(size=14, weight="bold")).pack(anchor="w", pady=(15, 5))
        dur_var = customtkinter.StringVar(value="10")
        entry = customtkinter.CTkEntry(frame, textvariable=dur_var)
        entry.pack(fill="x", pady=5)

        def save():
            messagebox.showinfo("提示", "设置已保存（重启生效）")
            settings_win.destroy()

        save_btn = customtkinter.CTkButton(frame, text="保存", command=save)
        save_btn.pack(pady=20)

        # 显示当前模型信息
        info = self.stt.get_model_info()
        customtkinter.CTkLabel(
            frame,
            text=f"当前模型: {info['model_size']}\n设备: {info['device']}\n精度: {info['compute_type']}",
            font=customtkinter.CTkFont(size=11),
        ).pack(pady=10)

    def on_close(self):
        """关闭时清理资源"""
        self.stt.close()
        self.destroy()


def main():
    """启动应用"""
    app = VoiceApp()

    # 窗口关闭事件
    app.protocol("WM_DELETE_WINDOW", app.on_close)

    app.mainloop()


if __name__ == "__main__":
    main()
