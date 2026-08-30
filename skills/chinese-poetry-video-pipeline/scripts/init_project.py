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
        "06-发布/封面",
        "06-发布/成片",
        "07-标准输出包",
    ]
    for relative in directories:
        (project / relative).mkdir(parents=True, exist_ok=False)

    state = {
        "schema_version": 2,
        "project": {
            "title": args.title,
            "author": args.author,
            "dynasty": args.dynasty,
            "folder": args.slug,
        },
        "target": {
            "final_duration_seconds": args.duration,
            "aspect_ratio": "3:4",
            "h3_source_clip_seconds": 8,
            "timeline": {"width": 1080, "height": 1440, "fps": 30},
            "export": {"format": "mp4", "codec": "h264", "resolution": "1080p"},
        },
        "stage": "selected",
        "approvals": {
            "poem_text_verified": False,
            "visual_direction": False,
            "keyframes": False,
            "cloud_generation_cost": False,
            "clips": False,
            "chatcut_edit": False,
            "final_export": False,
            "release_package": False,
        },
        "artifacts": {
            "approved_keyframes": [],
            "h3_task_ids": [],
            "approved_clips": [],
            "chatcut_project_id": "",
            "export_path": "",
            "cover_path": "",
            "release_package_path": "",
            "release_package_version": "",
            "release_package_status": "",
        },
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
        - 情绪发动机：____ vs ____
        - 时间结构：
        - 空间结构：
        - 核心物象及变化：
        - 末句转折：
        - 视觉命题：这不是在画____，而是在画____。
        - 声音命题：声音从____变为____，让观众感到____。

        ## 朗诵与画面

        | 时段 | 诗句 | 停顿与重音 | 画面功能 |
        |---|---|---|---|
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
        - 单段时长：8 秒
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
        project / "05-ChatCut/剪辑方案.md",
        """
        # ChatCut 剪辑方案

        - 画布：1080 × 1440，30 fps
        - 主书法字体：待确认
        - 印章文字：待确认
        - 旁白策略：统一后期旁白 / H3 原声（待确认）

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
        project / "06-发布/封面方案.md",
        """
        # 封面方案

        - 核心关系画面：
        - 主标题：
        - 小题签：
        - 书法字体：
        - 印章：
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

        待定。

        ## 诗词出处说明

        待核实。
        """,
    )
    write_text(
        project / "06-发布/发布检查.md",
        """
        # 发布检查

        - [ ] 题名、诗句、作者、朝代无错字
        - [ ] 封面缩略图可读
        - [ ] 印章文字正确
        - [ ] 成片可播放且首尾正常
        - [ ] 标题、笔记与视频表达同一视觉命题
        - [ ] 平台安全区无重要信息被裁切
        """,
    )
    write_text(
        project / "07-标准输出包/输出包说明.md",
        """
        # 标准输出包

        全部发布素材通过验收后，运行 Skill 内的 `scripts/build_release_package.py`。

        - 每个版本建立独立目录，例如 `诗名_东方美学短片_2026-08-30_v01`；
        - `01-发布成品` 只放最终视频、最终封面和可直接复制的发布文案；
        - `03-制作归档` 只保留已确认素材和可复现记录，不收纳失败候选；
        - 任何修正都新建下一版本，不覆盖既有交付包。
        """,
    )

    print(project)


if __name__ == "__main__":
    main()
