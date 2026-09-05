#!/usr/bin/env python3
"""Check whether a machine can run each stage of the poetry-video workflow."""

from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


KEYCHAIN_SERVICE = "codex-poetry-audio-api-key"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    return parser.parse_args()


def command_version(command: str, args: list[str]) -> dict[str, Any]:
    executable = shutil.which(command)
    if not executable:
        return {"available": False, "path": "", "version": ""}
    try:
        result = subprocess.run(
            [executable, *args], check=False, capture_output=True, text=True, timeout=8
        )
        output = (result.stdout or result.stderr).strip().splitlines()
        version = output[0] if output else "available"
    except (OSError, subprocess.TimeoutExpired):
        version = "available; version query failed"
    return {"available": True, "path": executable, "version": version}


def find_chatcut_skills(codex_home: Path) -> list[str]:
    cache = codex_home / "plugins/cache/chatcut-inc/chatcut"
    if not cache.is_dir():
        return []
    matches = []
    for skill in cache.glob("*/skills/chatcut-plugin-basics/SKILL.md"):
        matches.append(str(skill.parent.parent.parent.name))
    return sorted(set(matches))


def font_status() -> dict[str, Any]:
    fc_match = shutil.which("fc-match")
    if not fc_match:
        return {"available": None, "detail": "fc-match unavailable; verify Ma Shan Zheng in the editor"}
    try:
        result = subprocess.run(
            [fc_match, "-f", "%{family}", "Ma Shan Zheng"],
            check=False,
            capture_output=True,
            text=True,
            timeout=8,
        )
        family = result.stdout.strip()
        return {"available": "Ma Shan Zheng".lower() in family.lower(), "detail": family}
    except (OSError, subprocess.TimeoutExpired):
        return {"available": None, "detail": "font check failed; verify in the editor"}


def seed_audio_credential_status() -> dict[str, Any]:
    if os.environ.get("SEED_AUDIO_API_KEY", "").strip():
        return {"available": True, "source": "process environment", "secret_read": False}
    security = shutil.which("security")
    if not security:
        return {"available": False, "source": "not configured", "secret_read": False}
    try:
        result = subprocess.run(
            [
                security,
                "find-generic-password",
                "-a",
                getpass.getuser(),
                "-s",
                KEYCHAIN_SERVICE,
            ],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=8,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {"available": None, "source": "check failed", "secret_read": False}
    return {
        "available": result.returncode == 0,
        "source": "macOS Keychain" if result.returncode == 0 else "not configured",
        "secret_read": False,
    }


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_anchors(skill_root: Path) -> dict[str, Any]:
    anchor_root = skill_root / "assets/style-anchors"
    manifest_path = anchor_root / "manifest.json"
    if not manifest_path.is_file():
        return {"available": False, "valid": False, "count": 0, "files": [], "errors": ["manifest missing"]}
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"available": False, "valid": False, "count": 0, "files": [], "errors": [str(exc)]}
    errors: list[str] = []
    files: list[str] = []
    for item in manifest.get("anchors", []):
        name = str(item.get("file", ""))
        path = anchor_root / name
        files.append(name)
        if not path.is_file():
            errors.append(f"missing: {name}")
        elif sha256(path) != item.get("sha256"):
            errors.append(f"checksum mismatch: {name}")
    return {
        "available": bool(files),
        "valid": not errors and len(files) >= 3,
        "count": len(files),
        "files": files,
        "errors": errors,
    }


def main() -> None:
    args = parse_args()
    skill_root = Path(__file__).resolve().parent.parent
    version_path = skill_root / "VERSION"
    skill_version = version_path.read_text(encoding="utf-8").strip() if version_path.is_file() else "unknown"
    codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()
    anchors = verify_anchors(skill_root)
    ffmpeg = command_version("ffmpeg", ["-version"])
    ffprobe = command_version("ffprobe", ["-version"])
    python_ok = sys.version_info >= (3, 10)
    chatcut_versions = find_chatcut_skills(codex_home)
    seed_audio = seed_audio_credential_status()
    report: dict[str, Any] = {
        "status": "PASS",
        "skill_version": skill_version,
        "hard_requirements": {
            "python": {
                "available": python_ok,
                "version": ".".join(map(str, sys.version_info[:3])),
                "minimum": "3.10",
            },
            "ffprobe": ffprobe,
            "ffmpeg": ffmpeg,
            "skill_structure": {
                "available": (skill_root / "SKILL.md").is_file(),
                "path": str(skill_root),
            },
        },
        "stage_capabilities": {
            "ffmpeg": ffmpeg,
            "chatcut_plugin_versions": chatcut_versions,
            "chatcut_available": bool(chatcut_versions),
            "ma_shan_zheng": font_status(),
            "style_anchors": anchors,
            "image_generation": "MANUAL_CHECK",
            "minimax_h3_access": "MANUAL_CHECK",
            "seed_audio_credential": seed_audio,
        },
        "notes": [
            "Image generation and MiniMax H3 access require account/UI checks.",
            "A missing ChatCut plugin permits planning and prompt production, but not the documented edit stage.",
            "The Seed Audio credential check only tests presence; it never reads or prints the secret value.",
        ],
    }
    hard_failures = [
        name
        for name, item in report["hard_requirements"].items()
        if not item.get("available")
    ]
    if hard_failures:
        report["status"] = "BLOCKED"
        report["hard_failures"] = hard_failures
    elif (
        not chatcut_versions
        or not anchors["valid"]
        or report["stage_capabilities"]["ma_shan_zheng"]["available"] is not True
    ):
        report["status"] = "PARTIAL"

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Poetry video workflow environment: {report['status']}")
        print(f"Skill version: {skill_version}")
        print(f"Python: {report['hard_requirements']['python']['version']} ({'PASS' if python_ok else 'FAIL'})")
        print(f"ffprobe: {'PASS' if ffprobe['available'] else 'FAIL'}")
        print(f"ChatCut plugin: {'PASS' if chatcut_versions else 'MANUAL/UNAVAILABLE'}")
        anchor_label = "PASS" if anchors["valid"] else "FAIL"
        print(f"Style anchors: {anchor_label} ({anchors['count']}/3)")
        font = report["stage_capabilities"]["ma_shan_zheng"]
        font_label = "PASS" if font["available"] is True else "CHECK"
        print(f"Ma Shan Zheng: {font_label} ({font['detail']})")
        print("Image generation: MANUAL CHECK")
        print("MiniMax H3 access and current cost: MANUAL CHECK")
        seed_label = "READY" if seed_audio["available"] is True else "NOT CONFIGURED"
        print(f"Seed Audio local credential: {seed_label} ({seed_audio['source']})")
    raise SystemExit(1 if report["status"] == "BLOCKED" else 0)


if __name__ == "__main__":
    main()
