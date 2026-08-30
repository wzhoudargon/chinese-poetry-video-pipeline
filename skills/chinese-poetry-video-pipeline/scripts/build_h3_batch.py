#!/usr/bin/env python3
"""Validate MiniMax H3 prompts and build a one-physical-line-per-task batch file."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
REQUIRED_FIELDS = (
    "integrated_multimodal_description:",
    "overall_soundscape:",
    "non_diegetic_music:",
)


def natural_key(path: Path) -> list[object]:
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", path.name)]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("single", "first-last"), required=True)
    parser.add_argument("--pairing", choices=("adjacent", "pairs"), default="adjacent")
    parser.add_argument("--images-dir", required=True)
    parser.add_argument("--prompts-dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--duration-seconds", type=float, default=8.0)
    parser.add_argument("--max-chars", type=int, default=7000)
    parser.add_argument("--force", action="store_true", help="Replace an existing output file")
    return parser.parse_args()


def collect_images(directory: Path) -> list[Path]:
    return sorted(
        [path for path in directory.iterdir() if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES],
        key=natural_key,
    )


def collect_prompts(directory: Path) -> list[Path]:
    return sorted([path for path in directory.iterdir() if path.is_file() and path.suffix.lower() == ".txt"], key=natural_key)


def expected_tasks(mode: str, pairing: str, image_count: int) -> int:
    if mode == "single":
        return image_count
    if pairing == "adjacent":
        return max(0, image_count - 1)
    if image_count % 2:
        raise SystemExit("first-last pairing='pairs' requires an even number of images")
    return image_count // 2


def validate_prompt(path: Path, text: str, mode: str, duration: float, max_chars: int) -> None:
    problems: list[str] = []
    if len(text) > max_chars:
        problems.append(f"{len(text)} characters exceeds --max-chars={max_chars}")
    for field in REQUIRED_FIELDS:
        if field not in text:
            problems.append(f"missing {field}")
    if "[Shot 1]" not in text:
        problems.append("missing [Shot 1]")

    if mode == "single":
        accepted_alignments = (
            "How the reference pictures align with the target video",
            "How the reference picture aligns with the target video",
        )
        if not any(alignment in text for alignment in accepted_alignments):
            problems.append("missing compatible single-picture alignment sentence")
        if "Picture 1" not in text:
            problems.append("missing Picture 1")
    else:
        expected = "How the reference pictures align with the target video"
        if expected not in text:
            problems.append("missing first/last-picture alignment sentence")
        if "Picture 1" not in text or "Picture 2" not in text:
            problems.append("first-last prompt must name Picture 1 and Picture 2")
        duration_marker = f"{duration:.2f}-second mark"
        if duration_marker not in text:
            problems.append(f"missing Picture 2 duration marker: {duration_marker}")

    if problems:
        joined = "; ".join(problems)
        raise SystemExit(f"Prompt validation failed for {path.name}: {joined}")


def flatten(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def main() -> None:
    args = parse_args()
    if args.duration_seconds <= 0 or args.max_chars <= 0:
        raise SystemExit("Duration and max characters must be positive")

    images_dir = Path(args.images_dir).expanduser().resolve()
    prompts_dir = Path(args.prompts_dir).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    if not images_dir.is_dir():
        raise SystemExit(f"Images directory does not exist: {images_dir}")
    if not prompts_dir.is_dir():
        raise SystemExit(f"Prompts directory does not exist: {prompts_dir}")
    if output.exists() and not args.force:
        raise SystemExit(f"Refusing to overwrite existing output without --force: {output}")

    images = collect_images(images_dir)
    prompts = collect_prompts(prompts_dir)
    if not images:
        raise SystemExit("No supported images found")
    expected = expected_tasks(args.mode, args.pairing, len(images))
    if len(prompts) != expected:
        raise SystemExit(
            f"Count mismatch: mode={args.mode}, pairing={args.pairing}, images={len(images)}, "
            f"expected prompts/tasks={expected}, found prompts={len(prompts)}"
        )

    lines: list[str] = []
    for prompt_path in prompts:
        text = prompt_path.read_text(encoding="utf-8").strip()
        validate_prompt(prompt_path, text, args.mode, args.duration_seconds, args.max_chars)
        lines.append(flatten(text))

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"mode={args.mode}")
    print(f"pairing={args.pairing}")
    print(f"images={len(images)}")
    print(f"tasks={len(lines)}")
    print(f"output={output}")
    for index, prompt in enumerate(prompts, start=1):
        if args.mode == "single":
            mapping = images[index - 1].name
        elif args.pairing == "adjacent":
            mapping = f"{images[index - 1].name} -> {images[index].name}"
        else:
            mapping = f"{images[(index - 1) * 2].name} -> {images[(index - 1) * 2 + 1].name}"
        print(f"{index:02d}: {mapping} | {prompt.name}")


if __name__ == "__main__":
    main()
