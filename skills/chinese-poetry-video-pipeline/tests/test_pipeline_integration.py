"""Offline regression cases using real small media, never a generation API."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

SKILL = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL / "scripts"


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


release = load("build_release_package")
audio = load("check_poetry_audio")
generation = load("generate_poetry_audio")
h3 = load("build_h3_batch")


def run(*args):
    return subprocess.run([str(a) for a in args], capture_output=True, text=True)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg required")
class PipelineIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.media_dir = tempfile.TemporaryDirectory()
        cls.media = Path(cls.media_dir.name)
        commands = [
            ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=blue:s=108x144:r=30",
             "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000", "-t", "1",
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-movflags", "+faststart", str(cls.media / "video.mp4")],
            ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=red:s=108x144", "-frames:v", "1", str(cls.media / "cover.png")],
            ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000", "-t", "2", "-c:a", "pcm_s16le", str(cls.media / "voice.wav")],
        ]
        for command in commands:
            result = run(*command)
            if result.returncode:
                raise RuntimeError(result.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.media_dir.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        result = run(sys.executable, SCRIPTS / "init_project.py", "--root", self.root,
                     "--slug", "poem", "--title", "测试诗", "--duration", "1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.project = self.root / "poem"
        for src, name in [("video.mp4", "video.mp4"), ("cover.png", "cover.png"), ("cover.png", "seal.png")]:
            shutil.copy2(self.media / src, self.project / name)
        for relative in ["01-诗词与意境/原文与版本.md", "01-诗词与意境/意境拆解.md", "05-ChatCut/字幕与朗诵文本.md"]:
            (self.project / relative).write_text("# 已确认记录\n\n测试使用的独立合成资料，内容与当前演示范围一致，已记录检查依据。\n")
        (self.project / "06-发布/印章/设计说明.md").write_text("# 印章设计\n\n测试资产已确认；此处保存生成提示词，不代表真实印章审查。\n\n```text\nCreate the test seal with a plain red field.\n```\n")
        (self.project / "06-发布/标题与笔记.md").write_text("""# 发布资料
## 最终标题
测试诗的发布标题
## 小红书笔记
我们根据本次诗意确定画面与声音的关系。
```text
请针对本首诗确定取句与停顿，再写出画面关系、人物尺度和可执行动作，保留结尾余韵并核实易错字音。
```
你会如何处理这首诗的结尾？
## 置顶评论与话题
这是可以交流具体声音和画面选择的评论。
#古诗词 #意境
## 封面题字
已确认的诗句
## 诗词出处说明
这是完全离线的合成测试资料。
""")
        self.state_path = self.project / "00-project-state.json"
        state = json.loads(self.state_path.read_text())
        state["artifacts"].update(export_path="video.mp4", cover_path="cover.png", approved_seal_asset="seal.png")
        self.state_path.write_text(json.dumps(state))
        self.qa = self.project / "06-发布/发布检查.md"
        self.write_qa()
        self.command = [sys.executable, SCRIPTS / "build_release_package.py", "--project-dir", self.project,
                        "--expected-width", "108", "--expected-height", "144", "--min-cover-width", "108",
                        "--min-cover-height", "144", "--date", "2026-09-05"]
        self.package = self.project / "07-标准输出包/测试诗_东方美学短片_2026-09-05_v01"

    def write_qa(self, status="PASS", approval="APPROVED"):
        self.qa.write_text(f"""# 当前发布验收
- 成品批准：{approval}
- 批准依据：隔离测试中的明确批准记录，仅用于验证程序行为。
- 人工听审：PASS
- video_sha256：{digest(self.project / 'video.mp4')}
- cover_sha256：{digest(self.project / 'cover.png')}
- seal_sha256：{digest(self.project / 'seal.png')}
## 验收结论
{status}。当前合成素材符合本次测试要求。
""")

    def test_valid_package_archives_seal_and_preserves_approvals(self):
        before = json.loads(self.state_path.read_text())["approvals"]
        result = run(*self.command)
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = json.loads((self.package / "manifest.json").read_text())
        self.assertEqual(manifest["status"], "COMPLETE")
        self.assertEqual(manifest["production_archive"]["approved_voice_files"], 0)
        self.assertFalse((self.package / "03-制作归档/旁白").exists())
        self.assertIn("108x144", manifest["publishing"]["video"]["path"])
        self.assertEqual(digest(self.package / manifest["production_archive"]["approved_seal"]), digest(self.project / "seal.png"))
        self.assertEqual(json.loads(self.state_path.read_text())["approvals"], before)
        for line in (self.package / "SHA256SUMS.txt").read_text().splitlines():
            expected, relative = line.split("  ", 1)
            self.assertEqual(digest(self.package / relative), expected)

    def test_failed_or_unapproved_qa_cannot_replace_package(self):
        self.package.mkdir(parents=True)
        (self.package / "old.txt").write_text("approved package")
        before = self.state_path.read_bytes()
        for status, approval in [("REVISE", "APPROVED"), ("PASS", "PENDING")]:
            with self.subTest(status=status, approval=approval):
                self.write_qa(status, approval)
                result = run(*self.command, "--replace-existing")
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual((self.package / "old.txt").read_text(), "approved package")
                self.assertEqual(self.state_path.read_bytes(), before)

    def test_changed_asset_invalidates_approval_hash(self):
        self.qa.write_text(self.qa.read_text().replace(digest(self.project / "video.mp4"), "0" * 64))
        result = run(*self.command)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("video_sha256", result.stderr)
        self.assertFalse(self.package.exists())

    def test_header_only_cover_is_rejected(self):
        (self.project / "cover.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 8 + struct.pack(">II", 108, 144))
        self.write_qa()
        result = run(*self.command)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("decode", result.stderr.lower())
        self.assertFalse(self.package.exists())

    def test_corrupt_video_payload_is_rejected(self):
        video = self.project / "video.mp4"
        data = bytearray(video.read_bytes())
        position = 0
        while position + 8 <= len(data):
            size, kind = struct.unpack(">I4s", data[position:position + 8])
            if kind == b"mdat":
                data[position + 8:position + size] = bytes(size - 8)
                break
            position += size
        else:
            self.fail("No mdat in generated fixture")
        video.write_bytes(data)
        self.write_qa()
        result = run(*self.command)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.package.exists())

    def test_legacy_state_preserves_evidence_and_next_action(self):
        state = json.loads(self.state_path.read_text())
        state.pop("stage")
        state.pop("next_step")
        state["current_stage"] = "exported"
        state["next_action"] = "Review a separate optional audition."
        state["verification"] = {"export_file": "video.mp4", "seal_final": "seal.png", "prior_evidence": "retain"}
        state["artifacts"].pop("export_path")
        state["artifacts"].pop("approved_seal_asset")
        self.state_path.write_text(json.dumps(state))
        self.package.mkdir(parents=True)
        (self.package / "old.txt").write_text("old")
        result = run(*self.command, "--replace-existing")
        self.assertEqual(result.returncode, 0, result.stderr)
        after = json.loads(self.state_path.read_text())
        self.assertEqual(after["stage"], after["current_stage"])
        self.assertEqual(after["verification"]["prior_evidence"], "retain")
        self.assertEqual(after["next_action"], state["next_action"])
        self.assertEqual(len(after["verification"]["package_history"]), 1)

    def test_invalid_state_fails_before_replacement(self):
        state = json.loads(self.state_path.read_text())
        state["verification"] = "invalid"
        self.state_path.write_text(json.dumps(state))
        self.package.mkdir(parents=True)
        (self.package / "old.txt").write_text("old")
        result = run(*self.command, "--replace-existing")
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue((self.package / "old.txt").exists())

    def test_check_only_does_not_write_package_or_state(self):
        before = self.state_path.read_bytes()
        result = run(*self.command, "--check-only")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.package.exists())
        self.assertEqual(before, self.state_path.read_bytes())

    def test_duration_target_is_checked_and_approved_override_is_explicit(self):
        state = json.loads(self.state_path.read_text())
        state["target"]["final_duration_seconds"] = 37
        self.state_path.write_text(json.dumps(state))
        result = run(*self.command, "--check-only")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("expected 37", result.stderr)
        result = run(*self.command, "--check-only", "--expected-duration", "1", "--duration-tolerance", "0.1")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_long_form_script_is_required_and_archived(self):
        state = json.loads(self.state_path.read_text())
        state["target"]["long_form"] = True
        self.state_path.write_text(json.dumps(state))
        self.assertNotEqual(run(*self.command).returncode, 0)
        story = self.project / "01-诗词与意境/故事脚本.md"
        story.write_text("# 已批准故事脚本\n\n原文覆盖完整，分章与朗诵时间已确认，声音和画面分别标明，结尾保留余韵。")
        result = run(*self.command)
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = json.loads((self.package / "manifest.json").read_text())
        self.assertEqual(digest(self.package / manifest["content_basis"]["story_script"]), digest(story))

    def test_truncated_audio_is_rejected_in_strict_mode(self):
        voice = self.root / "broken.wav"
        voice.write_bytes((self.media / "voice.wav").read_bytes()[:-19001])
        result = run(sys.executable, SCRIPTS / "check_poetry_audio.py", "--audio", voice, "--strict")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(json.loads(result.stdout)["decode_pass"])

    def test_subtitle_timing_and_sample_rate_must_match_audio(self):
        metadata = self.root / "metadata.json"
        metadata.write_text(json.dumps({"subtitle": {"text": "春眠不觉晓", "sentences": [
            {"text": "春眠不觉晓", "start_time": 90000, "end_time": -1000}]}, "audio_config": {"sample_rate": 8000}}))
        result = run(sys.executable, SCRIPTS / "check_poetry_audio.py", "--audio", self.media / "voice.wav",
                     "--metadata", metadata, "--expected-text", "春眠不觉晓", "--strict")
        self.assertNotEqual(result.returncode, 0)
        failures = json.loads(result.stdout)["failures"]
        self.assertTrue(any("timing" in f for f in failures))
        self.assertTrue(any("sample rate" in f for f in failures))

    def test_valid_audio_and_timing_pass(self):
        metadata = self.root / "metadata.json"
        metadata.write_text(json.dumps({"subtitle": {"text": "春眠不觉晓", "sentences": [
            {"text": "春眠不觉晓", "start_time": 100, "end_time": 1800}]}, "audio_config": {"sample_rate": 48000}}))
        result = run(sys.executable, SCRIPTS / "check_poetry_audio.py", "--audio", self.media / "voice.wav",
                     "--metadata", metadata, "--expected-text", "春眠不觉晓", "--strict")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(json.loads(result.stdout)["subtitle_timing_pass"])


class FailureRecoveryTests(unittest.TestCase):
    def test_state_commit_failure_restores_old_package(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package, building, state = root / "package", root / ".building", root / "state.json"
            package.mkdir(); building.mkdir()
            (package / "old.txt").write_text("old")
            (building / "new.txt").write_text("new")
            state.write_text('{"old": true}')
            original = state.read_bytes()
            with mock.patch.object(release.os, "replace", side_effect=OSError("simulated state write failure")):
                with self.assertRaises(OSError):
                    release.install_package(building, package, True, state, {"new": True}, original)
            self.assertEqual((package / "old.txt").read_text(), "old")
            self.assertEqual(state.read_bytes(), original)
            self.assertTrue((building / "new.txt").exists())

    def test_changed_state_aborts_before_install(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package, building, state = root / "package", root / ".building", root / "state.json"
            package.mkdir(); building.mkdir()
            state.write_text('{"newer": true}')
            with self.assertRaisesRegex(SystemExit, "changed during validation"):
                release.install_package(building, package, True, state, {}, b"{}")
            self.assertTrue(package.exists())
            self.assertTrue(building.exists())

    def test_h3_missing_shot_id_is_not_silently_paired(self):
        with self.assertRaisesRegex(SystemExit, "do not match"):
            h3.validate_shot_ids([Path("01.png"), Path("03.png")], [Path("01.txt"), Path("02.txt")])
        h3.validate_shot_ids([Path("S01-image.png"), Path("S03-image.png")], [Path("01-prompt.txt"), Path("03-prompt.txt")])

    def test_audio_dry_run_never_loads_credentials_or_calls_network(self):
        with tempfile.TemporaryDirectory() as directory:
            persona = Path(directory) / "persona.md"
            persona.write_text("明确的测试声线和停顿设定。")
            args = ["generate_poetry_audio.py", "--text", "行路难，行路难。", "--persona-file", str(persona),
                    "--output", str(Path(directory) / "voice.wav"), "--dry-run"]
            with mock.patch.object(sys, "argv", args), mock.patch.object(generation, "load_api_key") as key, \
                    mock.patch.object(generation, "post_json") as post, mock.patch("builtins.print"):
                self.assertEqual(generation.main(), 0)
                key.assert_not_called(); post.assert_not_called()
            self.assertFalse((Path(directory) / "voice.wav").exists())


if __name__ == "__main__":
    unittest.main()
