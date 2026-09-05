#!/usr/bin/env python3
"""Generate one Seed Audio poetry-recitation file without persisting the API key."""

from __future__ import annotations

import argparse
import base64
import getpass
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import uuid


ENDPOINT = "https://openspeech.bytedance.com/api/v3/tts/create"
KEYCHAIN_SERVICE = "codex-poetry-audio-api-key"
MODEL = "seed-audio-1.0"
VALID_SAMPLE_RATES = {8000, 16000, 24000, 32000, 40000, 44100, 48000}
PLACEHOLDER_RE = re.compile(r"\b(?:PENDING|TODO|TBD)\b|待核实|待补充|待定稿|待确认", re.IGNORECASE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    text_group = parser.add_mutually_exclusive_group(required=True)
    text_group.add_argument("--text", help="Canonical recitation text")
    text_group.add_argument("--text-file", type=Path, help="UTF-8 canonical recitation text")
    parser.add_argument("--persona-file", required=True, type=Path, help="UTF-8 poet voice sheet")
    parser.add_argument("--output", required=True, type=Path, help="Output WAV path")
    parser.add_argument("--metadata-output", type=Path, help="Defaults to the output path with .json")
    parser.add_argument("--speech-rate", type=int, default=0, help="-50..100")
    parser.add_argument("--loudness-rate", type=int, default=0, help="-50..100")
    parser.add_argument("--pitch-rate", type=int, default=0, help="-12..12")
    parser.add_argument("--sample-rate", type=int, default=48000)
    parser.add_argument("--dry-run", action="store_true", help="Print payload; do not load a key or call the API")
    parser.add_argument(
        "--confirm-paid-generation",
        action="store_true",
        help="Required for a real API call after the user approves the paid audition or batch",
    )
    parser.add_argument("--overwrite", action="store_true", help="Explicitly replace existing output files")
    return parser.parse_args()


def read_utf8(path: Path, label: str) -> str:
    try:
        text = path.expanduser().read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise RuntimeError(f"Cannot read {label}: {path}: {exc}") from exc
    if not text:
        raise RuntimeError(f"{label} is empty: {path}")
    return text


def load_api_key() -> str:
    env_key = os.environ.get("SEED_AUDIO_API_KEY", "").strip()
    if env_key:
        return env_key
    try:
        key = subprocess.check_output(
            [
                "security",
                "find-generic-password",
                "-a",
                getpass.getuser(),
                "-s",
                KEYCHAIN_SERVICE,
                "-w",
            ],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        key = ""
    if not key:
        raise RuntimeError(
            "No local API key is configured. Set SEED_AUDIO_API_KEY for this process or "
            f"store the key in the macOS Keychain service {KEYCHAIN_SERVICE!r}. "
            "Do not pass a key through chat or a command-line argument."
        )
    return key


def validate_config(args: argparse.Namespace) -> None:
    if not -50 <= args.speech_rate <= 100:
        raise RuntimeError("--speech-rate must be between -50 and 100")
    if not -50 <= args.loudness_rate <= 100:
        raise RuntimeError("--loudness-rate must be between -50 and 100")
    if not -12 <= args.pitch_rate <= 12:
        raise RuntimeError("--pitch-rate must be between -12 and 12")
    if args.sample_rate not in VALID_SAMPLE_RATES:
        raise RuntimeError(f"--sample-rate must be one of {sorted(VALID_SAMPLE_RATES)}")
    if not args.dry_run and not args.confirm_paid_generation:
        raise RuntimeError("Refusing a paid API call without --confirm-paid-generation")


def validate_paid_content(persona: str, text: str) -> None:
    match = PLACEHOLDER_RE.search(persona)
    if match:
        raise RuntimeError(
            f"Refusing paid generation because the persona file still contains placeholder {match.group(0)!r}"
        )
    if PLACEHOLDER_RE.search(text):
        raise RuntimeError("Refusing paid generation because the recitation text is not final")


def build_prompt(persona: str, text: str) -> str:
    prompt = f"""生成一段纯人声的中国古诗词朗诵。

以下是本片已经审核过的人物与表演设定。它是基于作品处境进行的审美化创作，不代表历史人物真实声音：

{persona}

固定制作要求：使用清楚、自然、有支点的普通话朗诵；严格遵守人物卡中的情绪动作、发音、停顿和时长。朗读范围只由下方【正文开始】与【正文结束】界定；边界内全部文字必须按原顺序完整朗读，重复句和恰好与题名相同的词句也必须保留。边界外的人物卡、题名、作者和提示语都不读；标点只表达停顿，不读出标点名称。不要增加正文以外的字。不要配乐、环境音、钟声或混响。

【正文开始】
{text}
【正文结束】"""
    if len(prompt) > 3000:
        raise RuntimeError(f"text_prompt is {len(prompt)} characters; the API limit is 3000")
    return prompt


def build_payload(args: argparse.Namespace, persona: str, text: str) -> dict:
    return {
        "model": MODEL,
        "text_prompt": build_prompt(persona, text),
        "audio_config": {
            "format": "wav",
            "sample_rate": args.sample_rate,
            "speech_rate": args.speech_rate,
            "loudness_rate": args.loudness_rate,
            "pitch_rate": args.pitch_rate,
            "enable_subtitle": True,
        },
        "watermark": {
            "aigc_watermark": False,
            "aigc_metadata": {"enable": False},
        },
    }


def post_json(payload: dict, api_key: str) -> tuple[dict, str, str | None]:
    request_id = str(uuid.uuid4())
    request = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-Api-Key": api_key,
            "X-Api-Request-Id": request_id,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            raw = response.read()
            log_id = response.headers.get("X-Tt-Logid")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:2000]
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error: {exc.reason}") from exc
    try:
        result = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("The audio service returned non-JSON data") from exc
    if result.get("code") not in (None, 0):
        raise RuntimeError(
            f"Generation failed with code {result.get('code')}: "
            f"{result.get('message', 'unknown error')}"
        )
    return result, request_id, log_id


def audio_bytes(result: dict) -> bytes:
    encoded = result.get("audio")
    if encoded:
        try:
            return base64.b64decode(encoded, validate=True)
        except (ValueError, TypeError) as exc:
            raise RuntimeError("The response contained invalid Base64 audio") from exc
    audio_url = result.get("url")
    if audio_url:
        try:
            with urllib.request.urlopen(audio_url, timeout=180) as response:
                return response.read()
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Cannot download generated audio: {exc.reason}") from exc
    raise RuntimeError("The response contained neither audio data nor an audio URL")


def atomic_write(path: Path, data: bytes, overwrite: bool) -> None:
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not overwrite:
        raise RuntimeError(f"Refusing to overwrite existing file: {path}")
    with tempfile.NamedTemporaryFile(prefix=f".{path.name}.", dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(data)
    try:
        os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def main() -> int:
    args = parse_args()
    validate_config(args)
    persona_path = args.persona_file.expanduser().resolve()
    persona = read_utf8(persona_path, "persona file")
    if args.text_file:
        text_path = args.text_file.expanduser().resolve()
        text = read_utf8(text_path, "text file")
    else:
        text_path = None
        text = (args.text or "").strip()
        if not text:
            raise RuntimeError("Recitation text is empty")
    payload = build_payload(args, persona, text)
    if args.dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    output = args.output.expanduser().resolve()
    metadata_output = (
        args.metadata_output.expanduser().resolve()
        if args.metadata_output
        else output.with_suffix(".json")
    )
    if output.suffix.lower() != ".wav":
        raise RuntimeError("--output must use a .wav suffix because this workflow requests WAV audio")
    if metadata_output == output:
        raise RuntimeError("--metadata-output must differ from --output")
    validate_paid_content(persona, text)
    for candidate in (output, metadata_output):
        if candidate.exists() and not args.overwrite:
            raise RuntimeError(f"Refusing to overwrite existing file: {candidate}")

    result, request_id, log_id = post_json(payload, load_api_key())
    atomic_write(output, audio_bytes(result), args.overwrite)
    metadata = {
        "schema_version": 1,
        "model": MODEL,
        "request_id": request_id,
        "log_id": log_id,
        "duration": result.get("duration"),
        "original_duration": result.get("original_duration"),
        "subtitle": result.get("subtitle"),
        "subtitle_time_unit": "milliseconds",
        "audio_config": payload["audio_config"],
        "text_sha256": sha256_text(text),
        "persona_sha256": sha256_text(persona),
        "persona_file": persona_path.name,
        "text_file": text_path.name if text_path else None,
        "output_file": output.name,
        "credential_source": "local environment or macOS Keychain; value never persisted",
    }
    atomic_write(
        metadata_output,
        (json.dumps(metadata, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
        args.overwrite,
    )
    print(output)
    print(metadata_output)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
