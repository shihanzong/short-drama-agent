# 短剧一条龙智能体 (Short Drama Agent)

一个基于多 Agent 协作的 AI 短剧全自动生产系统。从创意策划到多平台发布，全程自动化。

```
创意策划 -> 剧本创作 -> 视觉设计 -> 音频制作 -> 后期合成 -> 发布运营
```

## 核心功能

| Agent | 功能 | 依赖 |
|-------|------|------|
| CreativePlanner | 热点分析、角色设计、分集大纲 | LLM |
| ScriptWriter | 剧本生成、质量审查 | LLM |
| VisualDesigner | 分镜脚本、ComfyUI 图像生成 | LLM + ComfyUI |
| AudioMaker | TTS 配音、BGM 规划 | LLM + Edge TTS |
| VideoEditor | 图片转视频、字幕、剪辑 | ffmpeg + moviepy |
| Publisher | 标题文案、平台适配、发布 | LLM |

## 快速开始

### 1. 安装

**Windows:**
```bash
# 一键安装
cd short-drama-agent
setup.bat
```

**Linux/macOS:**
```bash
cd short-drama-agent
pip install -r requirements.txt
```

### 2. 配置

编辑 `config.yaml`：

```yaml
llm:
  provider: "agnes"        # agnes / openai / anthropic
  model: "agnes-2.0-flash"
  api_key: "your-api-key"  # 或设置环境变量 AGNES_API_KEY
```

### 3. 使用

```bash
# 快速模式（只生成策划+剧本，无需 ComfyUI）
python main.py --genre "重生复仇" --episodes 5 --mode quick

# 完整版（需要 ComfyUI + ffmpeg）
python main.py --genre "霸总" --episodes 3 --mode full

# 只生成策划方案
python main.py --genre "逆袭" --episodes 5 --mode planning-only

# 使用 Kanban 并行生产
python main.py --genre "悬疑" --episodes 5 --mode kanban

# 指定输出目录
python main.py --genre "甜宠" --episodes 3 -o my_drama

# 查看可用题材
python main.py --list-genres
```

## 可用题材

| 题材 | 适合人群 | 特点 |
|------|----------|------|
| 重生复仇 | 女频 25-40 岁 | 爽感强，每集打脸 |
| 霸总甜宠 | 女频 18-35 岁 | 甜度拉满，先婚后爱 |
| 逆袭爽文 | 男频 20-45 岁 | 打脸碾压，节奏快 |
| 悬疑反转 | 全年龄 20-45 | 烧脑反转，每集悬念 |
| 战神龙王 | 男频 25-50 岁 | 身份反转，极致爽感 |
| 甜宠日常 | 女频 16-30 岁 | 纯甜无虐，撒糖日常 |

## 输出结构

```
output/
  重生复仇/
    planning.json          # 创意策划方案
    ep001/
      outline.json         # 分集大纲
      script.md            # 剧本
      storyboard.json      # 分镜
      images/              # 场景图片
      audio/               # 音频文件
      video/
        final.mp4          # 成品视频
    ep002/
      ...
    overall_result.json    # 总结果
```

## 三种运行模式

| 模式 | 说明 | 需要 | 速度 |
|------|------|------|------|
| quick | 策划+剧本+分镜 | LLM | 快 |
| full | 全流程 | LLM+ComfyUI+ffmpeg | 慢 |
| planning-only | 只出策划方案 | LLM | 最快 |

## ComfyUI 集成

完整版需要运行 ComfyUI：

```bash
# 1. 安装 ComfyUI
pip install comfy-cli
comfy install --nvidia

# 2. 启动
comfy launch --background

# 3. 下载模型
comfy model download --url <flux-model-url> --relative-path models/checkpoints

# 4. 安装自定义节点
comfy node install ip-adapter
```

## 项目结构

```
short-drama-agent/
|-- agents/              # 六大 Agent 实现
|   |-- creative_planner.py
|   |-- script_writer.py
|   |-- visual_designer.py
|   |-- audio_maker.py
|   |-- video_editor.py
|   |-- publisher.py
|-- modules/             # 公共模块
|   |-- llm_client.py    # LLM 统一接口
|   |-- comfyui_client.py # ComfyUI 客户端
|   |-- tts_engine.py    # TTS 引擎
|   |-- video_processor.py # 视频处理
|   |-- style_manager.py # 风格管理
|   |-- analytics.py     # 数据分析
|-- kanban_orchestrator.py # 多 Agent 编排引擎
|-- workflow.py          # 主编排引擎
|-- config.yaml          # 配置文件
|-- main.py              # CLI 入口
|-- sd_agent.py          # 快捷入口
|-- requirements.txt     # Python 依赖
|-- templates/           # JSON 模板
|-- workflows/           # ComfyUI 工作流
|-- knowledge_base/      # 知识库
|-- setup.bat            # Windows 一键安装
|-- run_quick.bat        # 快速运行脚本
|-- README.md
```

## 扩展方向

- [ ] 真人短剧辅助（拍摄脚本+分镜表输出）
- [ ] 互动短剧（分支剧情选择）
- [ ] 多语言版本（自动翻译+字幕）
- [ ] 创作者 SaaS（Web 界面）
- [ ] 批量出海（多平台自动发布）

## License

MIT
