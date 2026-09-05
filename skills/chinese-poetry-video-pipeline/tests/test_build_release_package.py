from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "build_release_package.py"
SPEC = importlib.util.spec_from_file_location("build_release_package", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def publishing_markdown(body: str, tail: str = "置顶评论\n\n这是一条有实际内容的置顶评论。\n\n#古诗词 #AI读诗") -> str:
    return f"""# 发布资料

## 最终标题

一条完整的发布标题

## 小红书笔记

{body}

## 置顶评论与话题

{tail}

## 封面题字

核准诗句

## 诗词出处说明

可靠出处与创作边界说明。
"""


class PublishingCopyTests(unittest.TestCase):
    def test_plain_copy_preserves_prompts_and_hashtags(self) -> None:
        prompt_one = "请区分诗中的画面、声音与情绪，标出朗诵停顿、重音和易错字音，并把原文事实与创作推演分别列出。"
        prompt_two = "请把当前诗作规划成五幕竖屏短片，写清每幕动作、人物尺度、镜头方向、声音变化与最终收束状态。"
        body = f"""我先从一个真实动作进入这首诗，并解释它怎样改变画面。

接着说明构图、人物尺度和光色为什么这样安排。

```text
{prompt_one}
```

```text
{prompt_two}
```

如果由你处理最后一句，你会让镜头停住，还是继续向前？"""

        title, plain, checks = MODULE.build_plain_copy(publishing_markdown(body))

        self.assertEqual(title, "一条完整的发布标题")
        self.assertIn(prompt_one, plain)
        self.assertIn(prompt_two, plain)
        self.assertNotIn("```", plain)
        self.assertIn("#古诗词 #AI读诗", plain)
        self.assertEqual(checks["prompt_blocks"], 2)
        self.assertEqual(checks["hashtags"], 2)
        self.assertEqual(checks["semantic_preservation"], "PASS")

    def test_markdown_heading_is_removed_but_hashtag_is_preserved(self) -> None:
        plain = MODULE.markdown_to_plain("# 标题\n\n#古诗词 #东方美学\n")
        self.assertEqual(plain, "标题\n\n#古诗词 #东方美学\n")

    def test_missing_prompt_blocks_is_rejected(self) -> None:
        body = "正文解释了诗意和画面方法。你会怎样处理最后一句？"
        with self.assertRaisesRegex(SystemExit, "one or two complete fenced prompt blocks"):
            MODULE.build_plain_copy(publishing_markdown(body))

    def test_unclosed_prompt_block_is_rejected(self) -> None:
        body = "正文。\n\n```text\n这是一段没有闭合围栏的完整提示词，必须被拒绝。\n\n你会怎么处理？"
        with self.assertRaisesRegex(SystemExit, "unclosed fenced prompt block"):
            MODULE.build_plain_copy(publishing_markdown(body))

    def test_missing_hashtag_is_rejected(self) -> None:
        body = """正文说明真实制作取舍。

```text
请完成一段足够长、可直接复制、针对当前诗作的诗意拆解提示词，并区分事实与创作推演。
```

你会怎样处理最后一句？"""
        with self.assertRaisesRegex(SystemExit, "at least one complete #hashtag"):
            MODULE.build_plain_copy(publishing_markdown(body, "置顶评论\n\n这是一条完整评论。"))

    def test_unchecked_item_in_any_required_text_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "字幕与朗诵文本.md"
            path.write_text("# 字幕与朗诵文本\n\n- [ ] 人工听审仍未完成\n", encoding="utf-8")
            with self.assertRaisesRegex(SystemExit, "unchecked required items"):
                MODULE.assert_complete_text(path, "Subtitle and recitation text")


class ReleasePackageWriteModeTests(unittest.TestCase):
    def test_existing_package_requires_explicit_replace_choice(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory) / "poem_v01"
            package.mkdir()
            with self.assertRaisesRegex(SystemExit, "--replace-existing"):
                MODULE.validate_package_target(package, replace_existing=False)

    def test_replace_existing_swaps_complete_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / "poem_v01"
            building = root / ".poem_v01.building"
            package.mkdir()
            building.mkdir()
            (package / "old.txt").write_text("old package", encoding="utf-8")
            (building / "new.txt").write_text("new package", encoding="utf-8")

            MODULE.install_package(building, package, replace_existing=True)

            self.assertFalse(building.exists())
            self.assertFalse((package / "old.txt").exists())
            self.assertEqual((package / "new.txt").read_text(encoding="utf-8"), "new package")
            self.assertEqual(list(root.glob(".poem_v01.replaced-*")), [])


if __name__ == "__main__":
    unittest.main()
