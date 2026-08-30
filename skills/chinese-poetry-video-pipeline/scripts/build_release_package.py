#!/usr/bin/env python3
"""Build one immutable, verified release package for a poetry video project."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import uuid
from datetime import date, datetime
from fractions import Fraction
from pathlib import Path
from typing import Any


PLACEHOLDER_RE = re.compile(
    r"\b(?:PENDING|TODO|TBD)\b|待补充|待定稿|待核实|待写|待确认|待定(?:[。.]|\s*$)",
    re.IGNORECASE | re.MULTILINE,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-dir", required=True, help="Poetry project directory")
    parser.add_argument("--video", help="Verified final MP4; defaults to project state export_path")
    parser.add_argument("--cover", help="Verified final cover; defaults to project state cover_path")
    parser.add_argument("--copy", dest="copy_path", help="Publishing markdown")
    parser.add_argument("--poem-source", help="Verified poem text and source markdown")
    parser.add_argument("--creative-note", help="Interpretation and visual translation markdown")
    parser.add_argument("--voice-script", help="Final subtitle and recitation markdown")
    parser.add_argument("--qa", help="Completed publishing QA markdown")
    parser.add_argument("--clean-video", help="Optional clean/no-text final MP4")
    parser.add_argument("--srt", help="Optional final subtitle file")
    parser.add_argument("--output-root", help="Defaults to <project>/07-标准输出包")
    parser.add_argument("--version", default="v01", help="Immutable release version, such as v01")
    parser.add_argument("--date", default=date.today().isoformat(), help="Release date, YYYY-MM-DD")
    parser.add_argument("--title", help="Override poem title from project state")
    parser.add_argument("--author", help="Override author from project state")
    parser.add_argument("--dynasty", help="Override dynasty from project state")
    parser.add_argument("--expected-width", type=int, help="Defaults to project timeline width")
    parser.add_argument("--expected-height", type=int, help="Defaults to project timeline height")
    parser.add_argument("--expected-fps", type=float, help="Defaults to project timeline fps")
    parser.add_argument("--expected-codec", help="Defaults to project export codec")
    parser.add_argument("--allow-no-audio", action="store_true", help="Permit an intentionally silent final")
    parser.add_argument("--min-cover-width", type=int, default=1080)
    parser.add_argument("--min-cover-height", type=int, default=1440)
    parser.add_argument("--no-update-state", action="store_true", help="Do not update 00-project-state.json")
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Cannot read valid JSON: {path}: {exc}") from exc


def resolve_input(project: Path, value: str | None, default: str | None = None) -> Path:
    raw = value or default
    if not raw:
        raise SystemExit("A required input path is missing")
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = project / path
    path = path.resolve()
    if not path.is_file():
        raise SystemExit(f"Required file does not exist: {path}")
    return path


def safe_name(value: str) -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|\x00-\x1f]", "-", value.strip())
    cleaned = re.sub(r"\s+", "", cleaned).strip(".-_")
    if not cleaned:
        raise SystemExit("Title cannot be converted to a safe file name")
    return cleaned


def validate_version(value: str) -> str:
    normalized = value.lower()
    if not re.fullmatch(r"v\d{2,}", normalized):
        raise SystemExit("--version must look like v01, v02, or v100")
    return normalized


def validate_date(value: str) -> str:
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise SystemExit("--date must use YYYY-MM-DD") from exc


def assert_complete_text(path: Path, label: str) -> str:
    text = path.read_text(encoding="utf-8").strip()
    if len(text) < 20:
        raise SystemExit(f"{label} is empty or too short: {path}")
    match = PLACEHOLDER_RE.search(text)
    if match:
        raise SystemExit(f"{label} still contains placeholder '{match.group(0)}': {path}")
    if label == "Final QA" and re.search(r"^- \[ \]", text, re.MULTILINE):
        raise SystemExit(f"Final QA still contains unchecked items: {path}")
    return text


def section(markdown: str, names: list[str]) -> str:
    for name in names:
        pattern = re.compile(
            rf"^##+\s*{re.escape(name)}\s*$\n(.*?)(?=^##+\s|\Z)",
            re.MULTILINE | re.DOTALL,
        )
        match = pattern.search(markdown)
        if match:
            return match.group(1).strip()
    return ""


def markdown_to_plain(text: str) -> str:
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    text = re.sub(r"!\[([^]]*)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", text)
    lines: list[str] = []
    for raw in text.splitlines():
        line = re.sub(r"^\s*#{1,6}\s*", "", raw)
        line = re.sub(r"^\s*(?:[-*+] |\d+[.)]\s+)", "", line)
        line = re.sub(r"^\s*- \[[ xX]\]\s*", "", line)
        line = re.sub(r"[*_`~]", "", line).strip()
        if line.startswith("|") and line.endswith("|"):
            continue
        lines.append(line)
    compact: list[str] = []
    for line in lines:
        if not line and compact and not compact[-1]:
            continue
        compact.append(line)
    return "\n".join(compact).strip() + "\n"


def build_plain_copy(markdown: str) -> tuple[str, str]:
    final_title = section(markdown, ["最终标题", "发布标题"])
    final_title = final_title.splitlines()[0].strip() if final_title else ""
    if not final_title or PLACEHOLDER_RE.search(final_title):
        raise SystemExit("Publishing markdown needs a completed '## 最终标题' section")
    body = section(markdown, ["小红书笔记", "发布正文", "正文"])
    if not body:
        raise SystemExit("Publishing markdown needs a completed note/body section")
    tail = section(markdown, ["置顶评论与话题", "置顶评论与话题标签", "置顶评论", "话题标签"])
    if not tail:
        raise SystemExit("Publishing markdown needs a completed pinned-comment/topic section")
    cover_text = section(markdown, ["封面题字", "封面标题"])
    if not cover_text:
        raise SystemExit("Publishing markdown needs a completed cover-text section")
    source_note = section(markdown, ["诗词出处说明", "出处说明"])
    if not source_note:
        raise SystemExit("Publishing markdown needs a completed poem-source note section")
    blocks = [final_title, markdown_to_plain(body).strip()]
    blocks.append(markdown_to_plain(tail).strip())
    return final_title, "\n\n".join(block for block in blocks if block).strip() + "\n"


def run_json(command: list[str]) -> dict[str, Any]:
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise SystemExit(f"Required media inspection tool is missing: {command[0]}") from exc
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.strip() or exc.stdout.strip()
        raise SystemExit(f"Media inspection failed: {detail}") from exc
    return json.loads(result.stdout)


def parse_rate(value: str | None) -> float:
    if not value or value == "0/0":
        return 0.0
    try:
        return float(Fraction(value))
    except (ValueError, ZeroDivisionError):
        return 0.0


def probe_video(path: Path) -> dict[str, Any]:
    data = run_json([
        "ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)
    ])
    video_stream = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
    if not video_stream:
        raise SystemExit(f"No video stream found: {path}")
    audio_streams = [s for s in data.get("streams", []) if s.get("codec_type") == "audio"]
    duration_raw = data.get("format", {}).get("duration") or video_stream.get("duration") or 0
    return {
        "codec": video_stream.get("codec_name", ""),
        "width": int(video_stream.get("width", 0)),
        "height": int(video_stream.get("height", 0)),
        "fps": round(parse_rate(video_stream.get("avg_frame_rate") or video_stream.get("r_frame_rate")), 3),
        "duration_seconds": round(float(duration_raw), 3),
        "audio_streams": len(audio_streams),
        "audio_codecs": [stream.get("codec_name", "") for stream in audio_streams],
    }


def native_image_size(path: Path) -> tuple[int, int] | None:
    with path.open("rb") as handle:
        signature = handle.read(24)
        if signature.startswith(b"\x89PNG\r\n\x1a\n") and len(signature) >= 24:
            return struct.unpack(">II", signature[16:24])
        if not signature.startswith(b"\xff\xd8"):
            return None
        handle.seek(2)
        start_of_frame = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
        while True:
            byte = handle.read(1)
            if not byte:
                return None
            if byte != b"\xff":
                continue
            marker_byte = handle.read(1)
            while marker_byte == b"\xff":
                marker_byte = handle.read(1)
            if not marker_byte:
                return None
            marker = marker_byte[0]
            if marker in {0x01, 0xD8, 0xD9}:
                continue
            length_bytes = handle.read(2)
            if len(length_bytes) != 2:
                return None
            segment_length = struct.unpack(">H", length_bytes)[0]
            if segment_length < 2:
                return None
            if marker in start_of_frame:
                data = handle.read(segment_length - 2)
                if len(data) < 5:
                    return None
                height, width = struct.unpack(">HH", data[1:5])
                return width, height
            handle.seek(segment_length - 2, 1)


def probe_image(path: Path) -> dict[str, Any]:
    native_size = native_image_size(path)
    if native_size:
        width, height = native_size
        return {"width": width, "height": height, "aspect_ratio": round(width / height, 6)}
    try:
        result = subprocess.run(
            ["sips", "-g", "pixelWidth", "-g", "pixelHeight", str(path)],
            check=True,
            capture_output=True,
            text=True,
        )
        width_match = re.search(r"pixelWidth:\s*(\d+)", result.stdout)
        height_match = re.search(r"pixelHeight:\s*(\d+)", result.stdout)
        if width_match and height_match:
            width = int(width_match.group(1))
            height = int(height_match.group(1))
            return {"width": width, "height": height, "aspect_ratio": round(width / height, 6)}
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass
    try:
        from PIL import Image  # type: ignore

        with Image.open(path) as image:
            width, height = image.size
        return {"width": width, "height": height, "aspect_ratio": round(width / height, 6)}
    except (ImportError, OSError) as exc:
        raise SystemExit(f"Cannot inspect cover dimensions: {path}") from exc


def validate_media(
    video: dict[str, Any],
    cover: dict[str, Any],
    expected_width: int,
    expected_height: int,
    expected_fps: float,
    expected_codec: str,
    allow_no_audio: bool,
    min_cover_width: int,
    min_cover_height: int,
) -> list[str]:
    failures: list[str] = []
    if (video["width"], video["height"]) != (expected_width, expected_height):
        failures.append(
            f"video is {video['width']}x{video['height']}, expected {expected_width}x{expected_height}"
        )
    if abs(float(video["fps"]) - expected_fps) > 0.2:
        failures.append(f"video is {video['fps']} fps, expected {expected_fps} fps")
    if video["codec"].lower() != expected_codec.lower():
        failures.append(f"video codec is {video['codec']}, expected {expected_codec}")
    if video["duration_seconds"] <= 0:
        failures.append("video duration is zero")
    if not allow_no_audio and video["audio_streams"] < 1:
        failures.append("final video has no audio stream")
    if cover["width"] < min_cover_width or cover["height"] < min_cover_height:
        failures.append(
            f"cover is {cover['width']}x{cover['height']}, minimum is {min_cover_width}x{min_cover_height}"
        )
    if abs(float(cover["aspect_ratio"]) - 0.75) > 0.01:
        failures.append(f"cover ratio is {cover['aspect_ratio']:.4f}, expected 3:4")
    return failures


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def copy_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def copy_tree_files(source: Path, destination: Path) -> int:
    if not source.is_dir():
        return 0
    copied = 0
    for path in sorted(source.rglob("*")):
        if path.is_symlink() or not path.is_file() or any(part.startswith(".") for part in path.relative_to(source).parts):
            continue
        copy_file(path, destination / path.relative_to(source))
        copied += 1
    return copied


def optional_text_is_substantive(path: Path, kind: str) -> bool:
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8").strip()
    if not text or PLACEHOLDER_RE.search(text):
        return False
    if kind == "h3_log":
        table_lines = [line for line in text.splitlines() if line.strip().startswith("|")]
        return len(table_lines) > 2
    if kind == "chatcut":
        return bool(re.search(r"(?:Project ID|Timeline ID|Render ID|本地成片)[：:][ \t]*\S+", text))
    return len(text) >= 40


def relative_file_records(root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name not in {"manifest.json", "00-交付清单.md", "SHA256SUMS.txt"}:
            records.append({
                "path": path.relative_to(root).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            })
    return records


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def update_project_state(state_path: Path, state: dict[str, Any], package: Path, project: Path, version: str) -> None:
    state["schema_version"] = max(int(state.get("schema_version", 1)), 2)
    approvals = state.setdefault("approvals", {})
    approvals["final_export"] = True
    approvals["release_package"] = True
    artifacts = state.setdefault("artifacts", {})
    try:
        package_value = package.relative_to(project).as_posix()
    except ValueError:
        package_value = str(package)
    artifacts["release_package_path"] = package_value
    artifacts["release_package_version"] = version
    artifacts["release_package_status"] = "COMPLETE"
    state["stage"] = "publish_ready"
    state["next_step"] = "Publish the verified package or create a new immutable version for any revision."
    state.setdefault("verification", []).append({
        "stage": "publish_ready",
        "status": "PASS",
        "package": package_value,
        "version": version,
        "verified_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    })
    temporary = state_path.with_name(f".{state_path.name}.tmp-{uuid.uuid4().hex[:8]}")
    write_json(temporary, state)
    os.replace(temporary, state_path)


def main() -> None:
    args = parse_args()
    project = Path(args.project_dir).expanduser().resolve()
    state_path = project / "00-project-state.json"
    if not project.is_dir() or not state_path.is_file():
        raise SystemExit(f"Not a scaffolded poetry project: {project}")
    state = load_json(state_path)
    project_info = state.get("project", {})
    target = state.get("target", {})
    timeline = target.get("timeline", {})
    export_settings = target.get("export", {})

    title = args.title or project_info.get("title") or ""
    author = args.author if args.author is not None else project_info.get("author", "")
    dynasty = args.dynasty if args.dynasty is not None else project_info.get("dynasty", "")
    title_slug = safe_name(title)
    version = validate_version(args.version)
    release_date = validate_date(args.date)

    state_video = state.get("artifacts", {}).get("export_path") or None
    state_cover = state.get("artifacts", {}).get("cover_path") or None
    video_source = resolve_input(project, args.video, state_video)
    cover_source = resolve_input(project, args.cover, state_cover)
    copy_source = resolve_input(project, args.copy_path, "06-发布/标题与笔记.md")
    poem_source = resolve_input(project, args.poem_source, "01-诗词与意境/原文与版本.md")
    creative_note = resolve_input(project, args.creative_note, "01-诗词与意境/意境拆解.md")
    voice_script = resolve_input(project, args.voice_script, "05-ChatCut/字幕与朗诵文本.md")
    qa_source = resolve_input(project, args.qa, "06-发布/发布检查.md")

    copy_markdown = assert_complete_text(copy_source, "Publishing copy")
    assert_complete_text(poem_source, "Poem source")
    assert_complete_text(creative_note, "Creative note")
    assert_complete_text(voice_script, "Subtitle and recitation text")
    assert_complete_text(qa_source, "Final QA")
    final_title, plain_copy = build_plain_copy(copy_markdown)

    video_metadata = probe_video(video_source)
    cover_metadata = probe_image(cover_source)
    expected_width = args.expected_width or int(timeline.get("width", 1080))
    expected_height = args.expected_height or int(timeline.get("height", 1440))
    expected_fps = args.expected_fps or float(timeline.get("fps", 30))
    expected_codec = args.expected_codec or str(export_settings.get("codec", "h264"))
    failures = validate_media(
        video_metadata,
        cover_metadata,
        expected_width,
        expected_height,
        expected_fps,
        expected_codec,
        args.allow_no_audio,
        args.min_cover_width,
        args.min_cover_height,
    )
    if failures:
        raise SystemExit("Media specification check failed:\n- " + "\n- ".join(failures))

    output_root = Path(args.output_root).expanduser().resolve() if args.output_root else project / "07-标准输出包"
    output_root.mkdir(parents=True, exist_ok=True)
    package_name = f"{title_slug}_东方美学短片_{release_date}_{version}"
    package_dir = output_root / package_name
    if package_dir.exists():
        raise SystemExit(f"Refusing to overwrite immutable package: {package_dir}")
    building = output_root / f".{package_name}.building-{uuid.uuid4().hex[:8]}"
    building.mkdir(parents=False, exist_ok=False)

    video_destination = building / "01-发布成品/视频" / f"{title_slug}_3x4_1080p_{version}.mp4"
    cover_destination = building / "01-发布成品/封面" / f"{title_slug}_封面_3x4_{version}{cover_source.suffix.lower()}"
    copy_destination = building / "01-发布成品/文案/发布标题与正文.md"
    plain_destination = building / "01-发布成品/文案/发布文案-纯文本.txt"
    poem_destination = building / "02-内容依据/原文与出处.md"
    creative_destination = building / "02-内容依据/意境与创作说明.md"
    voice_destination = building / "02-内容依据/字幕与朗诵文本.md"
    qa_destination = building / "04-质量验收/最终验收.md"

    copy_file(video_source, video_destination)
    copy_file(cover_source, cover_destination)
    copy_file(copy_source, copy_destination)
    plain_destination.parent.mkdir(parents=True, exist_ok=True)
    plain_destination.write_text(plain_copy, encoding="utf-8")
    copy_file(poem_source, poem_destination)
    copy_file(creative_note, creative_destination)
    copy_file(voice_script, voice_destination)
    copy_file(qa_source, qa_destination)

    if args.clean_video:
        clean_source = resolve_input(project, args.clean_video)
        clean_metadata = probe_video(clean_source)
        clean_failures = validate_media(
            clean_metadata,
            cover_metadata,
            expected_width,
            expected_height,
            expected_fps,
            expected_codec,
            True,
            args.min_cover_width,
            args.min_cover_height,
        )
        if clean_failures:
            raise SystemExit("Clean video specification check failed:\n- " + "\n- ".join(clean_failures))
        copy_file(
            clean_source,
            building / "01-发布成品/视频" / f"{title_slug}_3x4_1080p_无字版_{version}.mp4",
        )
    if args.srt:
        srt_source = resolve_input(project, args.srt)
        copy_file(srt_source, building / "02-内容依据" / f"{title_slug}_{version}.srt")

    copy_tree_files(project / "03-关键帧/已确认", building / "03-制作归档/已确认关键帧")
    copy_tree_files(project / "04-H3/视频提示词", building / "03-制作归档/H3视频提示词")
    h3_log = project / "04-H3/批量生成/任务记录.md"
    if optional_text_is_substantive(h3_log, "h3_log"):
        copy_file(h3_log, building / "03-制作归档/H3任务记录.md")
    chatcut_record = project / "05-ChatCut/项目与导出记录.md"
    if optional_text_is_substantive(chatcut_record, "chatcut"):
        copy_file(chatcut_record, building / "03-制作归档/ChatCut项目与导出记录.md")

    asset_records = relative_file_records(building)
    video_relative = video_destination.relative_to(building).as_posix()
    cover_relative = cover_destination.relative_to(building).as_posix()
    record_by_path = {record["path"]: record for record in asset_records}
    created_at = datetime.now().astimezone().isoformat(timespec="seconds")
    manifest = {
        "schema_version": 1,
        "package_id": package_name,
        "status": "COMPLETE",
        "version": version,
        "created_at": created_at,
        "project": {
            "title": title,
            "author": author,
            "dynasty": dynasty,
            "final_publish_title": final_title,
        },
        "publishing": {
            "video": {"path": video_relative, **record_by_path[video_relative], **video_metadata},
            "cover": {"path": cover_relative, **record_by_path[cover_relative], **cover_metadata},
            "markdown_copy": copy_destination.relative_to(building).as_posix(),
            "plain_text_copy": plain_destination.relative_to(building).as_posix(),
        },
        "content_basis": {
            "poem_source": poem_destination.relative_to(building).as_posix(),
            "creative_note": creative_destination.relative_to(building).as_posix(),
            "subtitle_and_recitation": voice_destination.relative_to(building).as_posix(),
        },
        "quality": {
            "status": "PASS",
            "record": qa_destination.relative_to(building).as_posix(),
            "machine_checks": [
                "required files present",
                "video decodes and matches expected codec, dimensions, fps, duration, and audio policy",
                "cover meets minimum dimensions and 3:4 ratio",
                "required text files contain no known placeholders",
            ],
        },
        "assets": asset_records,
    }
    write_json(building / "manifest.json", manifest)

    checklist = f"""# 标准输出包交付清单

- 包状态：**COMPLETE**
- 作品：《{title}》
- 作者：{dynasty + '·' if dynasty else ''}{author or '未署名'}
- 发布标题：{final_title}
- 版本：{version}
- 建包时间：{created_at}

## 发布成品

- [x] 最终视频：`{video_relative}`
- [x] 最终封面：`{cover_relative}`
- [x] 发布标题与正文：`{copy_destination.relative_to(building).as_posix()}`
- [x] 可直接复制的纯文本：`{plain_destination.relative_to(building).as_posix()}`

## 内容与验收

- [x] 原文与出处
- [x] 意境与创作说明
- [x] 字幕与朗诵文本
- [x] 最终验收记录
- [x] `manifest.json`
- [x] `SHA256SUMS.txt`

## 机器检查

- 视频：{video_metadata['width']}×{video_metadata['height']}，{video_metadata['fps']} fps，{video_metadata['codec']}，{video_metadata['duration_seconds']} 秒，音频流 {video_metadata['audio_streams']} 条
- 封面：{cover_metadata['width']}×{cover_metadata['height']}，比例 {cover_metadata['aspect_ratio']:.4f}
- 文件命名与版本：PASS
- 已有版本覆盖检查：PASS

任何后续修改都应创建下一版本，不覆盖本目录。
"""
    (building / "00-交付清单.md").write_text(checklist, encoding="utf-8")

    checksum_files = [path for path in sorted(building.rglob("*")) if path.is_file() and path.name != "SHA256SUMS.txt"]
    checksum_text = "\n".join(
        f"{sha256(path)}  {path.relative_to(building).as_posix()}" for path in checksum_files
    ) + "\n"
    (building / "SHA256SUMS.txt").write_text(checksum_text, encoding="utf-8")

    building.rename(package_dir)
    if not args.no_update_state:
        update_project_state(state_path, state, package_dir, project, version)
    print(package_dir)


if __name__ == "__main__":
    main()
