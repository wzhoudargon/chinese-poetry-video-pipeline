#!/usr/bin/env python3
"""Inspect generated poetry audio and report decode, timing, subtitle, peak, and loudness checks."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audio", required=True, type=Path)
    parser.add_argument("--metadata", type=Path, help="JSON written by generate_poetry_audio.py")
    expected = parser.add_mutually_exclusive_group()
    expected.add_argument("--expected-text")
    expected.add_argument("--expected-text-file", type=Path)
    parser.add_argument("--min-duration", type=float)
    parser.add_argument("--max-duration", type=float)
    parser.add_argument("--strict", action="store_true", help="Return nonzero for warnings as well as failures")
    return parser.parse_args()


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(command, check=False, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise RuntimeError(f"Required tool is missing: {command[0]}") from exc


def normalize_words(value: str) -> str:
    return re.sub(r"[\W_]+", "", value, flags=re.UNICODE).casefold()


def read_expected(args: argparse.Namespace) -> str | None:
    if args.expected_text_file:
        return args.expected_text_file.expanduser().read_text(encoding="utf-8").strip()
    return args.expected_text.strip() if args.expected_text else None


def probe(audio: Path) -> dict[str, Any]:
    result = run([
        "ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(audio)
    ])
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "ffprobe failed")
    data = json.loads(result.stdout)
    audio_streams = [stream for stream in data.get("streams", []) if stream.get("codec_type") == "audio"]
    if not audio_streams:
        raise RuntimeError("No audio stream found")
    stream = audio_streams[0]
    duration = data.get("format", {}).get("duration") or stream.get("duration") or 0
    return {
        "audio_stream_count": len(audio_streams),
        "codec": stream.get("codec_name"),
        "sample_rate": int(stream.get("sample_rate") or 0),
        "channels": int(stream.get("channels") or 0),
        "duration_seconds": round(float(duration), 3),
    }


def decode_check(audio: Path) -> tuple[bool, str]:
    result = run(["ffmpeg", "-nostdin", "-v", "error", "-xerror", "-err_detect", "explode", "-i", str(audio), "-map", "0:a", "-f", "null", "-"])
    return result.returncode == 0 and not result.stderr.strip(), result.stderr.strip()


def loudness(audio: Path) -> dict[str, float | None]:
    result = run([
        "ffmpeg", "-hide_banner", "-nostats", "-i", str(audio),
        "-filter_complex", "ebur128=peak=true", "-f", "null", "-"
    ])
    detail = result.stderr
    integrated = re.findall(r"I:\s*(-?\d+(?:\.\d+)?)\s*LUFS", detail)
    peaks = re.findall(r"Peak:\s*(-?\d+(?:\.\d+)?)\s*dBFS", detail)
    return {
        "integrated_lufs": float(integrated[-1]) if integrated else None,
        "true_peak_dbfs": float(peaks[-1]) if peaks else None,
    }


def subtitle_text(metadata: dict[str, Any]) -> str | None:
    subtitle = metadata.get("subtitle")
    if isinstance(subtitle, dict) and isinstance(subtitle.get("text"), str):
        return subtitle["text"]
    if isinstance(subtitle, str):
        return subtitle
    return None


def validate_subtitle_timing(metadata: dict[str, Any], duration: float) -> tuple[list[str], bool]:
    subtitle = metadata.get("subtitle")
    if not isinstance(subtitle, dict) or not subtitle.get("sentences"):
        return [], False
    unit = metadata.get("subtitle_time_unit", "milliseconds")
    if unit not in ("milliseconds", "seconds"):
        return ["unknown subtitle_time_unit"], False
    scale = 1000.0 if unit == "milliseconds" else 1.0
    errors: list[str] = []
    def check(rows: Any, low: float, high: float, label: str) -> None:
        if not isinstance(rows, list):
            errors.append(f"{label} must be a list")
            return
        previous = low
        for index, row in enumerate(rows):
            try:
                raw_start, raw_end = row["start_time"], row["end_time"]
                if isinstance(raw_start, bool) or isinstance(raw_end, bool):
                    raise ValueError("boolean timestamp")
                start, end = float(raw_start) / scale, float(raw_end) / scale
                if not (math.isfinite(start) and math.isfinite(end)):
                    raise ValueError("nonfinite timestamp")
                if start < low or end <= start or start < previous - 0.02 or end > high + 0.05:
                    raise ValueError("out-of-order or out-of-bounds timestamp")
                if "words" in row:
                    check(row["words"], start, end, f"{label}[{index}].words")
                previous = end
            except (KeyError, TypeError, ValueError):
                errors.append(f"invalid timing in {label}[{index}]")
    check(subtitle["sentences"], 0.0, duration, "subtitle.sentences")
    return errors, not errors


def main() -> int:
    args = parse_args()
    if not shutil.which("ffprobe") or not shutil.which("ffmpeg"):
        raise RuntimeError("ffprobe and ffmpeg are required")
    audio = args.audio.expanduser().resolve()
    if not audio.is_file():
        raise RuntimeError(f"Audio file does not exist: {audio}")
    metadata: dict[str, Any] = {}
    if args.metadata:
        metadata = json.loads(args.metadata.expanduser().read_text(encoding="utf-8"))

    failures: list[str] = []
    warnings: list[str] = []
    media = probe(audio)
    decoded, decode_detail = decode_check(audio)
    if not decoded:
        failures.append(f"full decode failed: {decode_detail}")
    if media["audio_stream_count"] != 1:
        warnings.append(f"expected one audio stream, found {media['audio_stream_count']}")
    duration = float(media["duration_seconds"])
    if args.min_duration is not None and duration < args.min_duration:
        failures.append(f"duration {duration}s is shorter than {args.min_duration}s")
    if args.max_duration is not None and duration > args.max_duration:
        failures.append(f"duration {duration}s is longer than {args.max_duration}s")

    if not math.isfinite(duration) or duration <= 0:
        failures.append("audio duration must be positive and finite")
    configured_rate = metadata.get("audio_config", {}).get("sample_rate")
    if configured_rate is not None and configured_rate != media["sample_rate"]:
        failures.append("sample rate does not match generation metadata")
    timing_failures, timing_checked = validate_subtitle_timing(metadata, duration)
    failures.extend(timing_failures)
    if metadata.get("subtitle") and not timing_checked and not timing_failures:
        warnings.append("subtitle timing is unavailable; content matching does not verify synchronization")
    levels = loudness(audio)
    peak = levels["true_peak_dbfs"]
    lufs = levels["integrated_lufs"]
    if peak is None:
        warnings.append("true peak could not be measured")
    elif peak > -1.0:
        warnings.append(f"true peak {peak} dBFS is above the preferred -1 dBFS ceiling")
    if lufs is None:
        warnings.append("integrated loudness could not be measured")
    elif not -24.0 <= lufs <= -14.0:
        warnings.append(f"integrated loudness {lufs} LUFS is outside the review range -24..-14 LUFS")

    expected = read_expected(args)
    returned_subtitle = subtitle_text(metadata)
    subtitle_match: bool | None = None
    if expected is not None:
        if returned_subtitle is None:
            warnings.append("expected text was supplied but metadata has no returned subtitle")
        else:
            subtitle_match = normalize_words(expected) == normalize_words(returned_subtitle)
            if not subtitle_match:
                failures.append("returned subtitle content does not match the canonical text")

    status = "FAIL" if failures else "WARN" if warnings else "PASS"
    report = {
        "status": status,
        "audio": audio.name,
        "media": media,
        "decode_pass": decoded,
        "levels": levels,
        "subtitle_match": subtitle_match,
        "subtitle_timing_pass": timing_checked if metadata.get("subtitle") else None,
        "failures": failures,
        "warnings": warnings,
        "manual_checks_required": [
            "poet age and identity feel",
            "pronunciation, homophones, historical readings, and names",
            "natural pauses, emphasis, breath, and emotional action",
            "artifacts, clipping, sibilance, plosives, noise, and unwanted ambience",
        ],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if failures or (args.strict and warnings):
        return 1
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
