#!/usr/bin/env python3
"""Validate the portable GitHub distribution without external Python packages."""

from __future__ import annotations

import hashlib
import json
import py_compile
import re
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
SKILL = REPO / "skills/chinese-poetry-video-pipeline"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fail(message: str) -> None:
    raise SystemExit(message)


def main() -> None:
    root_version = (REPO / "VERSION").read_text(encoding="utf-8").strip()
    skill_version = (SKILL / "VERSION").read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+", root_version) or root_version != skill_version:
        fail("Root and installed-skill versions must match semantic versioning")
    skill_md = SKILL / "SKILL.md"
    if not skill_md.is_file():
        fail("SKILL.md is missing")
    text = skill_md.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        fail("SKILL.md frontmatter is missing")
    frontmatter = text.split("---", 2)[1]
    if not re.search(r"^name:\s*chinese-poetry-video-pipeline\s*$", frontmatter, re.MULTILINE):
        fail("Unexpected skill name")
    if not re.search(r"^description:\s*\S+", frontmatter, re.MULTILINE):
        fail("Skill description is missing")

    for markdown in sorted(SKILL.rglob("*.md")):
        content = markdown.read_text(encoding="utf-8")
        for link in re.findall(r"\[[^]]+\]\(([^)]+)\)", content):
            if "://" in link or link.startswith("#"):
                continue
            target = (markdown.parent / link.split("#", 1)[0]).resolve()
            if not target.exists():
                fail(f"Broken local link in {markdown.relative_to(REPO)}: {link}")
        if re.search(r"/(?:Users|private|var/folders)/", content):
            fail(f"Private absolute path found in {markdown.relative_to(REPO)}")

    for script in sorted((SKILL / "scripts").glob("*.py")):
        py_compile.compile(str(script), doraise=True)

    manifest_path = SKILL / "assets/style-anchors/manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    anchors = manifest.get("anchors", [])
    if len(anchors) < 3:
        fail("At least three style anchors are required")
    for item in anchors:
        path = manifest_path.parent / item["file"]
        if not path.is_file():
            fail(f"Missing style anchor: {item['file']}")
        if sha256(path) != item["sha256"]:
            fail(f"Style anchor checksum mismatch: {item['file']}")
        if path.stat().st_size >= 100 * 1024 * 1024:
            fail(f"GitHub file limit exceeded: {item['file']}")

    print("Portable skill repository is valid")


if __name__ == "__main__":
    main()
