#!/usr/bin/env python3
"""Create a non-destructive project scaffold for a Chinese poetry video."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from textwrap import dedent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, help="Parent directory for the project")
    parser.add_argument("--slug", required=True, help="New project folder name; no path separators")
    parser.add_argument("--title", required=True, help="Poem title")
    parser.add_argument("--author", default="", help="Author")
    parser.add_argument("--dynasty", default="", help="Dynasty")
    parser.add_argument("--duration", type=int, default=24, help="Target final duration in seconds")
    parser.add_argument("--long-form", "--full-text", action="store_true", help="Include a story script and full-text coverage stage")
    return parser.parse_args()


def validate_slug(slug: str) -> None:
    if not slug.strip() or slug in {".", ".."} or "/" in slug or "\\" in slug or "\x00" in slug:
        raise SystemExit("Invalid --slug: provide one safe folder name without path separators")


def write_text(path: Path, content: str) -> None:
    path.write_text(dedent(content).lstrip(), encoding="utf-8")


def main() -> None:
    args = parse_args()
    validate_slug(args.slug)
    if args.duration <= 0:
        raise SystemExit("--duration must be positive")

    root = Path(args.root).expanduser().resolve()
    if not root.is_dir():
        raise SystemExit(f"Root directory does not exist: {root}")

    project = root / args.slug
    if project.exists():
        raise SystemExit(f"Refusing to overwrite existing project: {project}")

    directories = [
        "01-诗词与意境",
        "02-视觉方案",
        "03-关键帧/候选",
        "03-关键帧/已确认",
        "04-H3/视频提示词",
        "04-H3/批量生成",
        "04-H3/输出/候选",
        "04-H3/输出/已确认",
        "05-ChatCut",
        "05-ChatCut/旁白/试听",
        "05-ChatCut/旁白/已确认",
        "06-发布/封面",
        "06-发布/印章/候选",
        "06-发布/印章/已确认",
        "06-发布/成片",
        "07-标准输出包",
    ]
    for relative in directories:
        (project / relative).mkdir(parents=True, exist_ok=False)

    state = {
        "schema_version": 4,
        "project": {
            "title": args.title,
            "author": args.author,
            "dynasty": args.dynasty,
            "folder": args.slug,
        },
        "target": {
            "final_duration_seconds": args.duration,
            "long_form": args.long_form,
            "aspect_ratio": "3:4",
            "h3_source_clip_seconds": 8,
            "timeline": {"width": 1080, "height": 1440, "fps": 30},
            "export": {"format": "mp4", "codec": "h264", "resolution": "1080p"},
        },
        "stage": "selected",
        "approvals": {
            "poem_text_verified": False,
            "story_script": False,
            "visual_direction": False,
            "keyframes": False,
            "cloud_generation_cost": False,
            "clips": False,
            "voice_persona": False,
            "voice_audition": False,
            "voice_final": False,
            "chatcut_edit": False,
            "seal_asset": False,
            "final_export": False,
            "release_package": False,
        },
        "artifacts": {
            "story_script_path": "01-诗词与意境/故事脚本.md" if args.long_form else "",
            "approved_keyframes": [],
            "h3_task_ids": [],
            "approved_clips": [],
            "approved_voice_audition": "",
            "approved_voice_segments": [],
            "chatcut_project_id": "",
            "export_path": "",
            "cover_path": "",
            "seal_design_brief": "06-发布/印章/设计说明.md",
            "approved_seal_asset": "",
            "release_package_path": "",
            "release_package_version": "",
            "release_package_status": "",
        },
        "sound_plan": {"route": "", "timing_evidence": "", "approved_existing_audio": []},
        "verification": [],
        "open_issues": [],
        "next_step": "Verify the poem text and complete the interpretation brief.",
    }
    (project / "00-project-state.json").write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    write_text(
        project / "01-诗词与意境/原文与版本.md",
        f"""
        # 《{args.title}》原文与版本

        - 作者：{args.dynasty + '·' if args.dynasty else ''}{args.author or '待核实'}
        - 可靠来源：待补充
        - 文本状态：待核实

        ## 原文

        待补充。

        ## 异文与署名说明

        无或待核实。

        ## 成片实际取句

        待定稿后填写。
        """,
    )
    write_text(
        project / "01-诗词与意境/意境拆解.md",
        """
        # 意境拆解

        - 字面事件：
        - 情绪或张力：
        - 时间结构：
        - 空间结构：
        - 核心物象或关系：
        - 结尾落点：
        - 视觉命题：通过何种关系表达何种感受。
        - 声音命题：声音从____变为____，让观众感到____。

        ## 朗诵与画面

        | 时段 | 诗句 | 停顿与重音 | 画面功能 |
        |---|---|---|---|
        """,
    )
    if args.long_form:
        write_text(
            project / "01-诗词与意境/故事脚本.md",
            f"""
            # 《{args.title}》故事脚本 v01

            > 目标时长：{args.duration} 秒
            > 适用模式：{'长片/全文' if args.long_form else '短片（按需使用）'}

            ## 导演总纲

            - 文本范围与版本：
            - 一句话故事：
            - 观众起点 → 终点：
            - 真正的主角：
            - 贯穿母题及变化：
            - 结尾落点：
            - 旁白规则：
            - 视觉与声音总弧线：

            ## 时长与章节表

            | 章 | 时段 | 原文范围/字数 | 戏剧任务 | 进入→变化→退出 | 母题变化 | 朗诵/留白 | 场数 |
            |---|---|---|---|---|---|---|---:|

            ## 场景卡

            ### C01-S01 场名｜00:00–00:00

            - 原文/旁白：
            - 画面故事：
            - 戏剧任务：
            - 主动作与结束状态：
            - 声音：
            - 转场：
            - 风险：

            ## 全文覆盖表

            | 原文段落 | 朗诵策略 | 对应章/场 | 画面功能 | 状态 |
            |---|---|---|---|---|

            ## 导演审核

            - 故事主轴：待审核
            - 全文覆盖：待审核
            - 时长预算：待审核
            - 章节推进：待审核
            - 画面可执行性：待审核
            - 声音与转场：待审核
            - 结尾落点：待审核
            - 用户批准：待审核
            """,
        )
    write_text(
        project / "02-视觉方案/风格圣经.md",
        """
        # 风格圣经

        - 主媒介：
        - 主色：
        - 唯一强调色：
        - 光线逻辑：
        - 材质逻辑：
        - 人物与服饰锚点：
        - 空间与三远：
        - 纹理上限：
        - 明确禁止项：
        - 与近期作品的差异：
        """,
    )
    write_text(
        project / "02-视觉方案/分镜与镜头变化矩阵.md",
        """
        # 分镜与镜头变化矩阵

        | 幕 | 时段 | 诗句 | 视觉命题 | 三远/空间 | 机位 | 焦段感 | 人物尺度 | 主体位置 | 前景遮挡 | 主运动 | 声音 |
        |---|---|---|---|---|---|---|---|---|---|---|---|
        """,
    )
    write_text(
        project / "03-关键帧/提示词.md",
        """
        # 关键帧提示词

        按 01、02、03… 编号。每幕记录提示词、生成版本、审核结论、失败原因和最终文件。
        """,
    )
    write_text(
        project / "04-H3/批量生成/上传顺序.md",
        """
        # H3 上传顺序

        - 模型：待确认
        - 模式：批量单图 / 首尾帧（待确认）
        - 单段时长：按声音预算确定，8 秒为默认起点
        - 分辨率：待确认
        - 原生声音：待确认
        - 预计任务数：待确认
        - 成本授权：未批准

        | 任务 | Picture 1 | Picture 2（如有） | 提示词 | 状态 |
        |---|---|---|---|---|
        """,
    )
    write_text(
        project / "04-H3/批量生成/任务记录.md",
        """
        # H3 任务记录

        | 序号 | 任务 ID | 提交时间 | 状态 | 输出文件 | 审核 | 失败原因/重试授权 |
        |---|---|---|---|---|---|---|
        """,
    )
    write_text(
        project / "05-ChatCut/旁白/诗人声音设定.md",
        """
        # 诗人声音设定

        > 本文件描述的是依据生平与作品处境进行的创作性声音设计，不是诗人真实历史声线的复原。

        ## 可核实事实

        - 创作时期与年龄区间：待核实
        - 身份、处境与地域经历：待核实
        - 作品气质的可靠依据：待核实
        - 来源与不确定性：待补充

        ## 本片创作推断

        - 年龄感：
        - 性别与声区：
        - 音色重量：
        - 呼吸与录音距离：
        - 语速、停顿与句尾：
        - 各句情绪动作：

        ## 审美美化

        - 保留：
        - 美化：
        - 禁止：年轻播音腔、新闻腔、舞台朗诵腔、故作磁性、耳语、过度苍老（按本诗修改）

        ## 发音表

        | 词 | 拼音/声调 | 分词与重音 | 人工复核 |
        |---|---|---|---|

        ## 试听范围与目标

        - 正文：
        - 目标时长：
        - 句间停顿：
        - 画面进入点与结束余韵：
        """,
    )
    write_text(
        project / "05-ChatCut/旁白/试听文本.txt",
        """
        待定稿。
        """,
    )
    write_text(
        project / "05-ChatCut/旁白/生成与质检记录.md",
        """
        # 旁白生成与质检记录

        - 模型：seed-audio-1.0
        - 生成方式：纯文本人物设定
        - 密钥来源：本机环境变量或 macOS 钥匙串；不得记录密钥值
        - 人物卡版本：
        - 付费试听授权：未批准
        - 用户批准试听：PENDING

        | 版本 | 正文 | 非敏感参数 | 实际时长 | 机器检查 | 人工听审 | 结论 |
        |---|---|---|---:|---|---|---|

        ## 人工听审

        - 年龄与身份：
        - 咬字、同音字与异读：
        - 语速、停顿、重音与气息：
        - 爆音、齿音、削波、底噪与多余声场：

        ## 最终批准

        - 批准声线：
        - 已确认分句：
        - 不得改变项：
        """,
    )
    write_text(
        project / "05-ChatCut/旁白/镜头同步表.md",
        """
        # 旁白与镜头同步表

        | 段 | 正文 | 音频文件 | 实际时长 | 镜头可用区间 | 入点 | 句内动作 | 尾部余韵 |
        |---|---|---|---:|---|---:|---|---:|
        """,
    )
    write_text(
        project / "05-ChatCut/剪辑方案.md",
        """
        # ChatCut 剪辑方案

        - 画布：1080 × 1440，30 fps
        - 主书法字体：待确认
        - 已批准的个性化 AI 印章资产：待确认
        - 印章出现方式与位置依据：待确认
        - 旁白策略：Seed Audio 已批准分句 / 人工录制 / 无旁白（待确认）

        | 成片时段 | 源片段与取段 | 诗句 | 文字动效 | 声音 | 转场 |
        |---|---|---|---|---|---|
        """,
    )
    write_text(
        project / "05-ChatCut/项目与导出记录.md",
        """
        # ChatCut 项目与导出记录

        - Project ID：
        - Timeline ID：
        - Editor URL：
        - Render ID：
        - 导出规格：1080p / H.264 / 30 fps
        - 本地成片：
        """,
    )
    write_text(
        project / "05-ChatCut/字幕与朗诵文本.md",
        """
        # 字幕与朗诵文本

        ## 成片字幕

        待定稿。

        ## 朗诵文本与停顿

        待定稿。使用 `/` 标记短停顿，使用 `//` 标记长停顿，并注明重音。
        """,
    )
    write_text(
        project / "05-ChatCut/验收.md",
        """
        # ChatCut 阶段验收

        - 结论：PENDING
        - 合成帧证据：
        - 文字与印章：
        - 声音与停顿：
        - 时间线结构：
        - 待修正：
        - 不得改变的已通过项：
        """,
    )
    write_text(
        project / "06-发布/印章/设计说明.md",
        """
        # 个性化 AI 篆刻印章设计说明

        > 这是依据诗人与本诗意境进行的 AI 视觉设计；没有可靠实物依据时，不得称为诗人的真实历史用印。

        - 核准印文：
        - 印文来源：
        - 身份说明：历史实物依据 / 创作性印文（待选择）
        - 诗人气质依据：
        - 本诗意境依据：
        - 朱文或白文：
        - 章形与字法布局：
        - 刀法、边缘与印泥状态：
        - 封面位置与层级：
        - 成片位置、出现时机与层级：
        - AI 生成／编辑模型及版本：

        ## 完整生成提示词

        待填写。必须包含准确印文、字形参考、诗人气质、本诗意境、朱白、章形、刀法、印泥和禁止项。

        ## 资产与核验

        - 候选生成原图：
        - 最终透明 PNG：
        - 原尺寸逐字核验：PENDING
        - 手机缩略图核验：PENDING
        - 封面与成片叠加核验：PENDING
        - 用户批准：PENDING
        """,
    )
    write_text(
        project / "06-发布/封面方案.md",
        """
        # 封面方案

        - 核心关系画面：
        - 主展示经典诗句（一句或两句）：
        - 小字诗名：
        - 诗句排版方向与层级：
        - 文字风格与诗意依据：
        - 背景留白与落字位置：
        - 个性化 AI 印章资产：
        - 印章位置与诗意依据：
        - 缩略图检查：PENDING
        """,
    )
    write_text(
        project / "06-发布/标题与笔记.md",
        """
        # 标题与笔记

        ## 最终标题

        待定。

        ## 备选标题

        1. 诗句直击型：
        2. 情绪解释型：
        3. AI 观看型：

        ## 小红书笔记

        待写。

        ## 置顶评论与话题

        待写。

        ## 封面题字

        - 主展示经典诗句：
        - 小字诗名：
        - 个性化 AI 印章印文：
        - 印章资产路径：

        ## 诗词出处说明

        待核实。
        """,
    )
    write_text(
        project / "06-发布/发布检查.md",
        """
        # 发布检查

        - [ ] 题名、诗句、作者、朝代无错字
        - [ ] 封面主展示为一句或两句经典诗句
        - [ ] 诗名缩小为第二视觉层
        - [ ] 排版与书写风格符合本诗意境和背景构图
        - [ ] 封面缩略图先读到诗句，随后能辨认诗名
        - [ ] 已用 AI 单独生成诗人／本诗专属印章，并经用户批准
        - [ ] 印文逐字正确且来源已记录，诗人气质与本诗意境依据完整
        - [ ] 生成原图、完整提示词和最终透明 PNG 均已保存
        - [ ] 印章没有现代字体、通用红方框、乱码或虚假历史复原表述
        - [ ] 成片可播放且首尾正常
        - [ ] 标题、笔记与视频表达同一视觉命题
        - [ ] 平台安全区无重要信息被裁切

        - 成品批准：PENDING
        - 批准依据：待补充已有用户批准的日期、范围和记录位置，不为填表重新请求批准
        - 人工听审：PENDING
        - video_sha256：待补充
        - cover_sha256：待补充
        - seal_sha256：待补充

        ## 验收结论

        PENDING
        """,
    )
    write_text(
        project / "07-标准输出包/输出包说明.md",
        """
        # 标准输出包

        全部发布素材通过验收后，运行 Skill 内的 `scripts/build_release_package.py`。

        - 默认只维护一个当前交付目录，例如 `诗名_东方美学短片_2026-08-30_v01`；
        - `01-发布成品` 只放最终视频、最终封面和可直接复制的发布文案；
        - `03-制作归档` 只保留已确认素材和可复现记录，不收纳失败候选；
        - 修正当前包时可原位更新；只有需要保留历史、审计快照或并行方案时才另建版本。
        """,
    )

    print(project)


if __name__ == "__main__":
    main()
