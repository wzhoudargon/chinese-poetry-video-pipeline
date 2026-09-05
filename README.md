# Chinese Poetry Video Pipeline

把一首古诗词从选题、可靠文本、意境理解、东方视觉系统、关键帧、MiniMax H3 图生视频、ChatCut 剪辑，推进到封面、发布文案和版本化标准输出包的 Codex Skill。

它沉淀的是一套可审查的创作方法，不是“一键套古风滤镜”。同一系列保持信息层级、印章品质、节奏和质量纪律；每首诗的媒介、色彩、构图和动作仍由诗意决定。

## 能复现到什么程度

- **流程与交付：**使用同一版本、明确输入、批准依据和实际验收，保持可复核。
- **视觉语言：**对照选定锚点的空间、材质与人物关系；不以未经校准的百分比承诺相似度。
- **具体人物、云纹、衣褶和逐像素画面：**生成模型具有随机性，不能承诺像素级复刻。

详细复现方法与边界见 `skills/chinese-poetry-video-pipeline/references/reproducibility.md`。

## 仓库结构

```text
skills/chinese-poetry-video-pipeline/
├── SKILL.md
├── agents/openai.yaml
├── assets/style-anchors/          # 三张用户确认的质量与关系锚点
├── references/                   # 诗意、视觉、H3、剪辑、发布和复现规则
└── scripts/                      # 项目初始化、H3 批量、环境检查和标准打包
```

## 新电脑安装

### 方式一：使用 Codex 自带的 Skill Installer

macOS / Linux：

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/.system/skill-installer/scripts/install-skill-from-github.py" \
  --repo wzhoudargon/chinese-poetry-video-pipeline \
  --path skills/chinese-poetry-video-pipeline \
  --ref v0.3.0
```

Windows PowerShell：

```powershell
python "$env:USERPROFILE\.codex\skills\.system\skill-installer\scripts\install-skill-from-github.py" `
  --repo wzhoudargon/chinese-poetry-video-pipeline `
  --path skills/chinese-poetry-video-pipeline `
  --ref v0.3.0
```

私有仓库需要目标电脑已经登录 GitHub，或配置有权读取该仓库的 `GH_TOKEN` / `GITHUB_TOKEN`。

### 方式二：手动安装

```bash
git clone https://github.com/wzhoudargon/chinese-poetry-video-pipeline.git
git -C chinese-poetry-video-pipeline checkout v0.3.0
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
cp -R chinese-poetry-video-pipeline/skills/chinese-poetry-video-pipeline \
  "${CODEX_HOME:-$HOME/.codex}/skills/"
```

安装后在下一轮对话中可用。建议先运行：

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/chinese-poetry-video-pipeline/scripts/check_environment.py"
```

## 使用

在 Codex 中直接说：

```text
使用 $chinese-poetry-video-pipeline，把《山居秋暝》制作成一条 20–30 秒东方美学短视频。
先核实原文并解释意境，进入高一致性复现模式；关键帧方向先给我审核，付费 H3 生成前必须确认参数和预计成本。
```

也可以只执行某个阶段：选诗、意境拆解、关键帧提示词、H3 批量格式、ChatCut 剪辑、封面文案或标准输出包。

## 目标环境

硬依赖：

- Codex 的 Skill 运行环境；
- Python 3.10+；
- FFmpeg / `ffprobe`。

阶段依赖：

- 可用的图像生成/编辑能力；
- MiniMax H3 访问权限；
- ChatCut 插件（完整自动剪辑时需要）；
- `Ma Shan Zheng` 或已记录的系列替代书法字体。

MiniMax 模型、计费和 WebUI 字段会变化，任何付费任务都应以当次界面为准并重新确认。

## 0.3.0 的实用改动

- 合并长篇故事脚本与人物化朗诵/可选男声预设；预设为文字特征条件，不保证锁定说话人。
- 声音路线和逐句时长在视频提交前确定，镜头数、纵深与结尾转折改为按诗意选择。
- 发布验收绑定视频、封面、印章校验和，真实解码媒体；打包不自动制造人工批准。
- 兼容旧项目状态，包和状态更新失败可恢复旧包；默认维护一个当前交付包。
- 音频增加严格解码、字幕时间检查；H3 单图批量检查镜头编号。

Git 仓库内的 `skills/chinese-poetry-video-pipeline` 是维护源；安装时固定发布标签，并核对安装后的 `VERSION`。本地多个入口应指向同一维护源，避免手工各改一份。

## 版本与发布

当前 Skill 版本见 `VERSION`。发布前应通过：

```bash
python3 -m py_compile skills/chinese-poetry-video-pipeline/scripts/*.py
python3 skills/chinese-poetry-video-pipeline/scripts/check_environment.py --json
python3 scripts/validate_repo.py
python3 -m unittest discover -s skills/chinese-poetry-video-pipeline/tests -v
```

本仓库尚未选择公开许可证；在确定公开或私有发布方式前，默认保留全部权利。
