#!/usr/bin/env python3
"""Build or refresh one verified release package for a poetry video project."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import copy
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

SENSITIVE_VALUE_RE = re.compile(
    r"(?i)(?:X-Api-Key|SEED_AUDIO_API_KEY|api[_ -]?key)\s*[\"']?\s*[:=]\s*[\"']?[A-Za-z0-9_./+\-=]{12,}"
)
SIGNED_URL_RE = re.compile(
    r"(?i)https?://\S+(?:X-Amz-Signature|X-Amz-Credential|signature=|access_token=|token=)\S*"
)
TEXT_ARCHIVE_SUFFIXES = {".json", ".md", ".txt", ".yaml", ".yml", ".log", ".csv", ".sh"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-dir", required=True, help="Poetry project directory")
    parser.add_argument("--video", help="Verified final MP4; defaults to project state export_path")
    parser.add_argument("--cover", help="Verified final cover; defaults to project state cover_path")
    parser.add_argument("--copy", dest="copy_path", help="Publishing markdown")
    parser.add_argument("--poem-source", help="Verified poem text and source markdown")
    parser.add_argument("--creative-note", help="Interpretation and visual translation markdown")
    parser.add_argument("--story-script", help="Approved script for an explicitly long-form/full-text project")
    parser.add_argument("--seal", help="Approved seal image; otherwise use the recorded asset path")
    parser.add_argument("--seal-brief", help="Seal design, approved text and generation prompt record")
    parser.add_argument("--check-only", action="store_true", help="Validate inputs without writing a package or state")
    parser.add_argument("--voice-script", help="Final subtitle and recitation markdown")
    parser.add_argument("--qa", help="Completed publishing QA markdown")
    parser.add_argument("--clean-video", help="Optional clean/no-text final MP4")
    parser.add_argument("--srt", help="Optional final subtitle file")
    parser.add_argument("--output-root", help="Defaults to <project>/07-标准输出包")
    parser.add_argument("--version", default="v01", help="Package identifier, such as v01")
    parser.add_argument(
        "--replace-existing",
        action="store_true",
        help="Refresh an existing current package in place after the new package passes all checks",
    )
    parser.add_argument("--date", default=date.today().isoformat(), help="Release date, YYYY-MM-DD")
    parser.add_argument("--title", help="Override poem title from project state")
    parser.add_argument("--author", help="Override author from project state")
    parser.add_argument("--dynasty", help="Override dynasty from project state")
    parser.add_argument("--expected-width", type=int, help="Defaults to project timeline width")
    parser.add_argument("--expected-height", type=int, help="Defaults to project timeline height")
    parser.add_argument("--expected-fps", type=float, help="Defaults to project timeline fps")
    parser.add_argument("--expected-codec", help="Defaults to project export codec")
    parser.add_argument("--expected-duration", type=float, help="Approved final duration; overrides the project planning target")
    parser.add_argument("--duration-tolerance", type=float, default=1.0, help="Allowed duration difference in seconds, default 1")
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
    if re.search(r"^\s*[-*+] \[ \]", text, re.MULTILINE):
        raise SystemExit(f"{label} still contains unchecked required items: {path}")
    if re.search(r"_{3,}|待审核", text):
        raise SystemExit(f"{label} still contains unfinished scaffold fields: {path}")
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


FENCE_LINE_RE = re.compile(r"^[ \t]*(`{3,}|~{3,})(.*)$")
HASHTAG_RE = re.compile(r"(?<!\S)#[^\s#]+")


def split_fenced_markdown(text: str) -> tuple[list[tuple[str, bool]], list[str]]:
    """Return source lines tagged as code/non-code plus complete fenced block contents."""
    classified: list[tuple[str, bool]] = []
    blocks: list[str] = []
    current: list[str] = []
    in_fence = False
    fence_character = ""
    fence_length = 0

    for raw in text.splitlines():
        match = FENCE_LINE_RE.match(raw)
        if match:
            marker, suffix = match.groups()
            if not in_fence:
                in_fence = True
                fence_character = marker[0]
                fence_length = len(marker)
                current = []
                continue
            if marker[0] == fence_character and len(marker) >= fence_length and not suffix.strip():
                blocks.append("\n".join(current).strip())
                in_fence = False
                fence_character = ""
                fence_length = 0
                current = []
                continue

        line = raw.rstrip()
        classified.append((line, in_fence))
        if in_fence:
            current.append(line)

    if in_fence:
        raise SystemExit("Publishing markdown contains an unclosed fenced prompt block")
    return classified, blocks


def markdown_to_plain(text: str) -> str:
    classified, _ = split_fenced_markdown(text)
    lines: list[tuple[str, bool]] = []
    for raw, is_code in classified:
        if is_code:
            # Code fences are formatting; the prompt inside them is publishable content.
            lines.append((raw, True))
            continue
        line = re.sub(r"!\[([^]]*)\]\([^)]+\)", r"\1", raw)
        line = re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", line)
        # CommonMark headings require whitespace after '#'. Preserve #话题标签.
        line = re.sub(r"^\s*#{1,6}(?:[ \t]+|$)", "", line)
        line = re.sub(r"^\s*(?:[-*+] |\d+[.)]\s+)", "", line)
        line = re.sub(r"^\s*- \[[ xX]\]\s*", "", line)
        line = re.sub(r"[*_`~]", "", line).strip()
        if line.startswith("|") and line.endswith("|"):
            continue
        lines.append((line, False))
    compact: list[tuple[str, bool]] = []
    for line, is_code in lines:
        if not line and compact and not compact[-1][0] and not is_code and not compact[-1][1]:
            continue
        compact.append((line, is_code))
    return "\n".join(line for line, _ in compact).strip() + "\n"


def build_plain_copy(markdown: str) -> tuple[str, str, dict[str, Any]]:
    final_title = section(markdown, ["最终标题", "发布标题"])
    final_title = final_title.splitlines()[0].strip() if final_title else ""
    if not final_title or PLACEHOLDER_RE.search(final_title):
        raise SystemExit("Publishing markdown needs a completed '## 最终标题' section")
    body = section(markdown, ["小红书笔记", "发布正文", "正文"])
    if not body:
        raise SystemExit("Publishing markdown needs a completed note/body section")
    classified_body, prompt_blocks = split_fenced_markdown(body)
    if not 1 <= len(prompt_blocks) <= 2:
        raise SystemExit(
            "Publishing note must contain one or two complete fenced prompt blocks; "
            f"found {len(prompt_blocks)}"
        )
    if any(len(re.sub(r"\s+", "", block)) < 40 for block in prompt_blocks):
        raise SystemExit("Each publishing prompt block must contain substantive, copyable text")
    body_without_prompts = "\n".join(line for line, is_code in classified_body if not is_code)
    if not re.search(r"[？?]", body_without_prompts):
        raise SystemExit("Publishing note must end with or contain a reader discussion question")
    tail = section(markdown, ["置顶评论与话题", "置顶评论与话题标签", "置顶评论", "话题标签"])
    if not tail:
        raise SystemExit("Publishing markdown needs a completed pinned-comment/topic section")
    hashtags = HASHTAG_RE.findall(tail)
    if not hashtags:
        raise SystemExit("Publishing markdown needs at least one complete #hashtag")
    comment_source = HASHTAG_RE.sub("", tail)
    comment_source = re.sub(r"(?m)^\s*置顶评论\s*$", "", comment_source)
    if len(re.sub(r"\s+", "", markdown_to_plain(comment_source))) < 10:
        raise SystemExit("Publishing markdown needs a substantive pinned comment before its hashtags")
    cover_text = section(markdown, ["封面题字", "封面标题"])
    if not cover_text:
        raise SystemExit("Publishing markdown needs a completed cover-text section")
    source_note = section(markdown, ["诗词出处说明", "出处说明"])
    if not source_note:
        raise SystemExit("Publishing markdown needs a completed poem-source note section")
    plain_body = markdown_to_plain(body).strip()
    plain_tail = markdown_to_plain(tail).strip()
    for prompt in prompt_blocks:
        if prompt.strip() not in plain_body:
            raise SystemExit("Plain publishing copy did not preserve a complete prompt block")
    for hashtag in hashtags:
        if hashtag not in plain_tail:
            raise SystemExit(f"Plain publishing copy did not preserve hashtag: {hashtag}")
    blocks = [final_title, plain_body, plain_tail]
    plain_copy = "\n\n".join(block for block in blocks if block).strip() + "\n"
    copy_checks = {
        "prompt_blocks": len(prompt_blocks),
        "discussion_question": True,
        "pinned_comment": True,
        "hashtags": len(hashtags),
        "semantic_preservation": "PASS",
    }
    return final_title, plain_copy, copy_checks


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
    strict_decode(path)
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


def strict_decode(path: Path) -> None:
    """Decode all audio/video streams; metadata alone is not media validation."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-nostdin", "-v", "error", "-xerror", "-err_detect", "explode",
             "-i", str(path), "-map", "0:v?", "-map", "0:a?", "-f", "null", "-"],
            capture_output=True, text=True,
        )
    except FileNotFoundError as exc:
        raise SystemExit("ffmpeg is required for complete media decoding") from exc
    if result.returncode or result.stderr.strip():
        raise SystemExit(f"Full decode failed for {path.name}: {result.stderr.strip()[:1000]}")


def probe_image(path: Path) -> dict[str, Any]:
    strict_decode(path)
    data = run_json(["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(path)])
    stream = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
    if not stream or not stream.get("width") or not stream.get("height"):
        raise SystemExit(f"Cannot decode cover pixels: {path}")
    width, height = int(stream["width"]), int(stream["height"])
    return {"width": width, "height": height, "aspect_ratio": round(width / height, 6)}


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
    expected_duration: float | None = None,
    duration_tolerance: float = 1.0,
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
    if not math.isfinite(video["duration_seconds"]) or video["duration_seconds"] <= 0:
        failures.append("video duration is zero")
    if not math.isfinite(duration_tolerance) or duration_tolerance < 0:
        failures.append("duration tolerance must be finite and nonnegative")
    if expected_duration is not None:
        if not math.isfinite(expected_duration) or expected_duration <= 0:
            failures.append("expected duration must be positive and finite")
        elif abs(video["duration_seconds"] - expected_duration) > duration_tolerance:
            failures.append(f"video duration is {video['duration_seconds']}s, expected {expected_duration}s +/- {duration_tolerance}s")
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


def assert_no_sensitive_text(path: Path) -> None:
    if path.suffix.lower() not in TEXT_ARCHIVE_SUFFIXES:
        return
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise SystemExit(f"Cannot safely inspect archive text: {path}: {exc}") from exc
    if SENSITIVE_VALUE_RE.search(text):
        raise SystemExit(f"Refusing to package a possible API credential: {path}")
    if SIGNED_URL_RE.search(text):
        raise SystemExit(f"Refusing to package a signed or temporary URL: {path}")


def assert_no_sensitive_tree(root: Path) -> None:
    for path in sorted(root.rglob("*")):
        if path.is_file():
            assert_no_sensitive_text(path)


def copy_tree_files(source: Path, destination: Path, reject_sensitive: bool = False) -> int:
    if not source.is_dir():
        return 0
    copied = 0
    for path in sorted(source.rglob("*")):
        if path.is_symlink() or not path.is_file() or any(part.startswith(".") for part in path.relative_to(source).parts):
            continue
        if reject_sensitive:
            assert_no_sensitive_text(path)
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


def validate_package_target(package: Path, replace_existing: bool) -> None:
    if package.exists() and not package.is_dir():
        raise SystemExit(f"Package target exists and is not a directory: {package}")
    if package.exists() and not replace_existing:
        raise SystemExit(
            f"Package already exists: {package}\n"
            "Use --replace-existing to refresh the current package in place, "
            "or choose another --version only when a separate snapshot is needed."
        )


def normalize_state(state: dict[str, Any]) -> dict[str, Any]:
    """Accept existing list/dict evidence without discarding legacy project fields."""
    if not isinstance(state, dict):
        raise SystemExit("Project state must be a JSON object")
    result = copy.deepcopy(state)
    for key in ("project", "target", "approvals", "artifacts"):
        if not isinstance(result.get(key, {}), dict):
            raise SystemExit(f"Project state {key} must be an object")
    target = result.get("target", {})
    for key in ("timeline", "export"):
        if not isinstance(target.get(key, {}), dict):
            raise SystemExit(f"Project target {key} must be an object")
    if not isinstance(result.get("verification", []), (list, dict)):
        raise SystemExit("Project verification must be a list or object")
    if isinstance(result.get("verification"), dict):
        if not isinstance(result["verification"].get("package_history", []), list):
            raise SystemExit("Project verification.package_history must be a list")
    result.setdefault("stage", result.get("current_stage", "selected"))
    result.setdefault("next_step", result.get("next_action", ""))
    return result


def qa_field(text: str, name: str) -> str:
    match = re.search(rf"^\s*(?:-\s*)?{re.escape(name)}[：:]\s*(.+)$", text, re.MULTILINE)
    return match.group(1).strip().strip("`") if match else ""


def validate_acceptance(text: str, video: Path, cover: Path, seal: Path, has_audio: bool) -> dict[str, str]:
    # This is a current-release record, not a history of rejected candidates.
    if re.search(r"\b(?:FAIL|REVISE|BLOCKED|PENDING)\b", text, re.IGNORECASE):
        raise SystemExit("Final QA contains an unresolved failure or pending review")
    conclusion = section(text, ["验收结论", "最终验收结论"])
    if not re.match(r"PASS(?:\b|[。．])", conclusion):
        raise SystemExit("Final QA needs an explicit '## 验收结论' beginning with PASS")
    if qa_field(text, "成品批准") != "APPROVED" or len(qa_field(text, "批准依据")) < 8:
        raise SystemExit("Final QA needs 成品批准: APPROVED and a concrete 批准依据; packaging cannot approve assets")
    hearing = qa_field(text, "人工听审")
    if hearing != "PASS" and not (not has_audio and hearing == "N/A" and qa_field(text, "不适用原因")):
        raise SystemExit("Final QA needs 人工听审: PASS (N/A with a reason is allowed only for a silent export)")
    hashes = {"video_sha256": sha256(video), "cover_sha256": sha256(cover), "seal_sha256": sha256(seal)}
    for name, digest in hashes.items():
        if qa_field(text, name).lower() != digest:
            raise SystemExit(f"Final QA {name} does not match the current approved file")
    return {**hashes, "approval_evidence": qa_field(text, "批准依据"), "human_audio_review": hearing}


def prepare_project_state(state: dict[str, Any], package: Path, project: Path,
                          version: str, write_mode: str) -> dict[str, Any]:
    result = normalize_state(state)
    try:
        package_value = package.relative_to(project).as_posix()
    except ValueError:
        package_value = str(package)
    result.setdefault("artifacts", {}).update({
        "release_package_path": package_value, "release_package_version": version,
        "release_package_status": "COMPLETE", "release_package_write_mode": write_mode,
    })
    result["stage"] = "publish_ready"
    if "current_stage" in result:
        result["current_stage"] = "publish_ready"
    # Preserve an existing next action (e.g. a separate pending audition).
    evidence = {"stage": "publish_ready", "status": "PASS", "package": package_value,
                "version": version, "write_mode": write_mode,
                "verified_at": datetime.now().astimezone().isoformat(timespec="seconds")}
    verification = result.setdefault("verification", [])
    if isinstance(verification, dict):
        verification.setdefault("package_history", []).append(evidence)
    else:
        verification.append(evidence)
    # Never create human approvals as a side effect of copying files.
    return result


def install_package(building: Path, package: Path, replace_existing: bool,
                    state_path: Path | None = None, new_state: dict[str, Any] | None = None,
                    expected_state: bytes | None = None) -> None:
    """Commit the package and prepared state together; restore the old package on failure."""
    validate_package_target(package, replace_existing)
    state_temp = None
    backup = None
    installed = False
    try:
        if state_path is not None:
            if new_state is None:
                raise ValueError("A prepared state is required")
            state_temp = state_path.with_name(f".{state_path.name}.tmp-{uuid.uuid4().hex[:8]}")
            write_json(state_temp, new_state)
            if expected_state is not None and state_path.read_bytes() != expected_state:
                raise SystemExit("Project state changed during validation; rerun with current evidence")
        if package.exists():
            backup = package.with_name(f".{package.name}.replaced-{uuid.uuid4().hex[:8]}")
            package.rename(backup)
        building.rename(package)
        installed = True
        if state_temp is not None:
            os.replace(state_temp, state_path)
    except BaseException:
        if installed:
            package.rename(building)
        if backup is not None and backup.exists():
            backup.rename(package)
        raise
    finally:
        if state_temp is not None:
            state_temp.unlink(missing_ok=True)
    if backup is not None:
        shutil.rmtree(backup)


def main() -> None:
    args = parse_args()
    project = Path(args.project_dir).expanduser().resolve()
    state_path = project / "00-project-state.json"
    if not project.is_dir() or not state_path.is_file():
        raise SystemExit(f"Not a scaffolded poetry project: {project}")
    state_bytes = state_path.read_bytes()
    state = normalize_state(load_json(state_path))
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

    legacy = state.get("verification", {}) if isinstance(state.get("verification"), dict) else {}
    artifacts = state.get("artifacts", {})
    state_video = artifacts.get("export_path") or legacy.get("export_file")
    state_cover = artifacts.get("cover_path") or legacy.get("cover_file")
    video_source = resolve_input(project, args.video, state_video)
    cover_source = resolve_input(project, args.cover, state_cover)
    copy_source = resolve_input(project, args.copy_path, "06-发布/标题与笔记.md")
    poem_source = resolve_input(project, args.poem_source, "01-诗词与意境/原文与版本.md")
    creative_note = resolve_input(project, args.creative_note, "01-诗词与意境/意境拆解.md")
    story_script = None
    if args.story_script or target.get("long_form") or target.get("full_text"):
        story_script = resolve_input(project, args.story_script, artifacts.get("story_script_path") or "01-诗词与意境/故事脚本.md")
    seal = resolve_input(project, args.seal, artifacts.get("approved_seal_asset") or legacy.get("seal_final"))
    seal_brief = resolve_input(project, args.seal_brief, artifacts.get("seal_design_brief") or "06-发布/印章/设计说明.md")
    voice_script = resolve_input(project, args.voice_script, "05-ChatCut/字幕与朗诵文本.md")
    qa_source = resolve_input(project, args.qa, "06-发布/发布检查.md")

    copy_markdown = assert_complete_text(copy_source, "Publishing copy")
    assert_complete_text(poem_source, "Poem source")
    assert_complete_text(creative_note, "Creative note")
    assert_complete_text(voice_script, "Subtitle and recitation text")
    qa_text = assert_complete_text(qa_source, "Final QA")
    assert_complete_text(seal_brief, "Seal design and prompt record")
    if "```" not in seal_brief.read_text(encoding="utf-8"):
        raise SystemExit("Seal brief must preserve its generation prompt in a fenced block")
    if story_script:
        assert_complete_text(story_script, "Story script")
    final_title, plain_copy, copy_checks = build_plain_copy(copy_markdown)

    video_metadata = probe_video(video_source)
    cover_metadata = probe_image(cover_source)
    probe_image(seal)
    acceptance = validate_acceptance(qa_text, video_source, cover_source, seal, bool(video_metadata["audio_streams"]))
    expected_width = args.expected_width or int(timeline.get("width", 1080))
    expected_height = args.expected_height or int(timeline.get("height", 1440))
    expected_fps = args.expected_fps or float(timeline.get("fps", 30))
    expected_codec = args.expected_codec or str(export_settings.get("codec", "h264"))
    duration_value = args.expected_duration if args.expected_duration is not None else target.get("final_duration_seconds", legacy.get("export_duration_seconds"))
    expected_duration = float(duration_value) if duration_value is not None else None
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
        expected_duration,
        args.duration_tolerance,
    )
    if failures:
        raise SystemExit("Media specification check failed:\n- " + "\n- ".join(failures))

    if args.check_only:
        print(json.dumps({"status": "PASS", "video": video_metadata, "acceptance": acceptance}, ensure_ascii=False))
        return
    output_root = Path(args.output_root).expanduser().resolve() if args.output_root else project / ("99_交付包" if (project / "99_交付包").is_dir() else "07-标准输出包")
    output_root.mkdir(parents=True, exist_ok=True)
    package_name = f"{title_slug}_东方美学短片_{release_date}_{version}"
    package_dir = output_root / package_name
    validate_package_target(package_dir, args.replace_existing)
    write_mode = "UPDATE_IN_PLACE" if package_dir.exists() else "CREATE"
    new_state = None if args.no_update_state else prepare_project_state(state, package_dir, project, version, write_mode)
    building = output_root / f".{package_name}.building-{uuid.uuid4().hex[:8]}"
    building.mkdir(parents=False, exist_ok=False)

    video_label = "3x4_1080p" if (expected_width, expected_height) == (1080, 1440) else f"{expected_width}x{expected_height}"
    video_destination = building / "01-发布成品/视频" / f"{title_slug}_{video_label}_{version}.mp4"
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
    seal_destination = building / "03-制作归档/印章" / f"已批准印章{seal.suffix.lower()}"
    copy_file(seal, seal_destination)
    copy_file(seal_brief, building / "03-制作归档/印章/设计与提示词.md")
    story_destination = building / "02-内容依据/故事脚本.md" if story_script else None
    if story_script:
        copy_file(story_script, story_destination)

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
            expected_duration,
            args.duration_tolerance,
        )
        if clean_failures:
            raise SystemExit("Clean video specification check failed:\n- " + "\n- ".join(clean_failures))
        copy_file(
            clean_source,
            building / "01-发布成品/视频" / f"{title_slug}_{video_label}_无字版_{version}.mp4",
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

    voice_archive_count = 0
    voice_root = project / "05-ChatCut/旁白"
    voice_destination_root = building / "03-制作归档/旁白"
    approved_voice_count = copy_tree_files(
        voice_root / "已确认", voice_destination_root / "已确认", reject_sensitive=True,
    )
    for source_name, destination_name in [
        ("诗人声音设定.md", "诗人声音设定.md"),
        ("生成与质检记录.md", "生成与质检记录.md"),
        ("镜头同步表.md", "镜头同步表.md"),
    ]:
        source = voice_root / source_name
        if approved_voice_count and optional_text_is_substantive(source, "voice"):
            assert_no_sensitive_text(source)
            copy_file(source, voice_destination_root / destination_name)
            voice_archive_count += 1
    voice_archive_count += approved_voice_count

    assert_no_sensitive_tree(building)

    asset_records = relative_file_records(building)
    video_relative = video_destination.relative_to(building).as_posix()
    cover_relative = cover_destination.relative_to(building).as_posix()
    record_by_path = {record["path"]: record for record in asset_records}
    for name, destination in (("video_sha256", video_destination),
                              ("cover_sha256", cover_destination),
                              ("seal_sha256", seal_destination)):
        copied_hash = record_by_path[destination.relative_to(building).as_posix()]["sha256"]
        if copied_hash != acceptance[name]:
            raise SystemExit(f"Approved source changed while copying: {name}; package was not installed")
    if qa_destination.read_text(encoding="utf-8").strip() != qa_text:
        raise SystemExit("Final QA changed while copying; package was not installed")
    created_at = datetime.now().astimezone().isoformat(timespec="seconds")
    manifest = {
        "schema_version": 1,
        "package_id": package_name,
        "status": "COMPLETE",
        "version": version,
        "write_mode": write_mode,
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
            "copy_checks": copy_checks,
        },
        "content_basis": {
            "poem_source": poem_destination.relative_to(building).as_posix(),
            "creative_note": creative_destination.relative_to(building).as_posix(),
            **({"story_script": story_destination.relative_to(building).as_posix()} if story_destination else {}),
            "subtitle_and_recitation": voice_destination.relative_to(building).as_posix(),
        },
        "production_archive": {
            "approved_voice_files": voice_archive_count,
            "approved_seal": seal_destination.relative_to(building).as_posix(),
        },
        "quality": {
            "status": "PASS",
            "record": qa_destination.relative_to(building).as_posix(),
            "acceptance": acceptance,
            "duration_target_seconds": expected_duration,
            "duration_tolerance_seconds": args.duration_tolerance,
            "machine_checks": [
                "required files present",
                "video fully decodes; codec, dimensions, fps, positive duration, configured duration target and audio policy checked",
                "cover meets minimum dimensions and 3:4 ratio",
                "required text files contain no known placeholders",
                "plain publishing copy preserves complete prompts, discussion question, pinned comment, and hashtags",
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
- 写入方式：{"原位更新当前包" if write_mode == "UPDATE_IN_PLACE" else "新建当前包"}
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
- [x] 已批准专属印章及设计提示词
{f'- [x] 故事脚本：`{story_destination.relative_to(building).as_posix()}`' if story_destination else '- [x] 故事脚本：本项目不适用'}
- [x] `manifest.json`
- [x] `SHA256SUMS.txt`

## 机器检查

- 视频：{video_metadata['width']}×{video_metadata['height']}，{video_metadata['fps']} fps，{video_metadata['codec']}，{video_metadata['duration_seconds']} 秒，音频流 {video_metadata['audio_streams']} 条
- 封面：{cover_metadata['width']}×{cover_metadata['height']}，比例 {cover_metadata['aspect_ratio']:.4f}
- 发布文案：提示词 {copy_checks['prompt_blocks']} 段，话题标签 {copy_checks['hashtags']} 个，交流问题 / 置顶评论 / 语义保留 PASS
- 文件命名与版本：PASS
- 当前交付包写入检查：PASS

本目录可以作为当前交付包原位更新；只有需要保留历史、审计快照或并行方案时才另建版本。
"""
    (building / "00-交付清单.md").write_text(checklist, encoding="utf-8")

    checksum_files = [path for path in sorted(building.rglob("*")) if path.is_file() and path.name != "SHA256SUMS.txt"]
    checksum_text = "\n".join(
        f"{sha256(path)}  {path.relative_to(building).as_posix()}" for path in checksum_files
    ) + "\n"
    (building / "SHA256SUMS.txt").write_text(checksum_text, encoding="utf-8")

    install_package(building, package_dir, args.replace_existing,
                    None if args.no_update_state else state_path, new_state, state_bytes)
    print(package_dir)


if __name__ == "__main__":
    main()
