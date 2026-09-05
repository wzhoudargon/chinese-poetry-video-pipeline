---
name: chinese-poetry-video-pipeline
description: Produce or continue Chinese-poetry aesthetic videos, including full-text and long-form works, from verified interpretation, visual direction and narration through keyframes, MiniMax H3, ChatCut editing and a verified publishing package. Use for 古诗词意境短片、诗词或古文全篇影像化及其中任一延续阶段；not unrelated generic fantasy videos.
---

# Chinese Poetry Video Pipeline

Let the poem determine the medium, motion, sound and rhythm. A useful result expresses a specific relationship or experience from the poem; a reusable “古风人物＋风景” look is insufficient.

## Start with scope and existing work

- **End to end:** one poem through a publishable package.
- **Stage only:** complete the requested stage and record the next action; skip unrelated gates.
- **Continue:** read current state, approval evidence and actual asset paths. Preserve approved pictures, original audio, typography and timelines unless the user changes the decision. Missing JSON does not mean a project is new: inspect current-state notes and the asset index. Keep an established folder layout.
- **Batch series:** share publishing identity while choosing each poem's medium, palette and camera language deliberately.
- **Long form / full text:** use the story-script route for explicit full-text adaptation, chapters or complex narrative. Duration alone does not require another stage; a 37-second short poem can keep its simple sequence.
- **Reproduction:** compare selected style anchors and recorded creative decisions; do not promise identical pixels or invent a similarity percentage.

## Load only the current stage

Read the relevant gate in [quality-gates.md](references/quality-gates.md), then the reference needed now:

| Work | Reference |
|---|---|
| Source, selection, interpretation | [poetry-interpretation.md](references/poetry-interpretation.md) |
| Full-text coverage, chapters, scene cards | [story-script.md](references/story-script.md) |
| Style, storyboard, composition, still prompts | [visual-system.md](references/visual-system.md) |
| H3 prompts, batch files, generation | [minimax-h3.md](references/minimax-h3.md) |
| Voice route, persona, auditions, audio QA | [poetry-voice.md](references/poetry-voice.md) |
| Assembly, typography, seal placement, export | [chatcut-editing.md](references/chatcut-editing.md) |
| Cover, dedicated AI seal, titles, copy | [publishing.md](references/publishing.md) |
| Final package, acceptance, safe update | [release-package.md](references/release-package.md) |
| Environment and cross-machine reproduction | [reproducibility.md](references/reproducibility.md) |

Use `scripts/init_project.py` for a new project without an established layout; add `--long-form` when a story script is needed. Do not initialize over existing work.

## Production order

Track the active stage and next action in existing project state. These are dependencies, not a requirement to redo completed stages.

| Stage | Evidence needed |
|---|---|
| `selected` | Reliable text/version and production scope |
| `interpreted` | Literal meaning, visual thesis, sound thesis; facts separate from inference |
| `scripted` when applicable | Approved text coverage, story spine, chapter arc and scene cards |
| `sound_planned` | Sound route, actual recitation text, pronunciation and per-line time budget |
| `visual_approved` | Poem-specific medium, sequence and composition; intentional repetition is allowed |
| `keyframes_approved` | Actual frames pass geometry, gaze, continuity, clarity and sequence review |
| `h3_prompts_ready` | Correct image/task mapping, executable motion and durations that accommodate the sound plan |
| `clips_approved` | Downloaded clips pass motion, identity, geometry, sound and usable-duration checks |
| `voice_approved` when applicable | Approved existing sound or newly reviewed narration; actual timing fits the visual map |
| `chatcut_edited` | Editable timeline, composed-frame review, text/sound timing and approved dedicated seal |
| `exported` | Local export fully decodes and matches settings; actual picture and sound reviewed |
| `publish_ready` | Current files match approval evidence; package, state, manifest and checksums agree |

Before costly video production, choose **approved existing/H3 original sound, H3-generated narration, independent narration, user recording, or no narration**. Independent narration uses an approved audition or trial read to budget timing. H3-generated narration uses a spoken window planned before generation and checked afterward. Keep approved original sound without forcing another audition or persona.

## Creative and operational rules

1. Derive shots from the poem's experience: tension, accumulation, observation, absence, distance, reversal or resonance. An ending need not resolve or reverse anything.
2. Use camera variety and depth when they help meaning. Fixed-view contrasts, two-shot films, flat media and quiet close-ups are valid. Use a matrix to find accidental repetition, not to satisfy a number.
3. Keep gaze, anatomy, clothing attachment, architecture, scale and wind direction legible. Fog and texture must not conceal broken structure.
4. Specify executable motion: one main camera direction, an action path and an end state. Do not force walking without a path or replay a completed action.
5. Approve a representative frame before extending a new direction. Review the sequence together; redo only the failed shot unless the shared direction itself failed.
6. Defaults are starting points: 3:4, 20–30 seconds, often 4–7 shots, often 8-second H3 sources, 1080×1440 at 30 fps and H.264 export. Project timing, supported model settings and user choices take precedence.
7. Keep original text, spoken text and visual action distinct, including in long-form work. Never disguise bridge text as the original.
8. Dedicated AI seals remain poem/poet-specific approved assets with verified text, design rationale and generation records. Do not substitute generic stamps or claim historical authenticity.
9. A text voice preset guides character; it does not lock speaker identity. For exact reuse, prefer approved audio or an explicitly authorized, supported reference-audio workflow. The bundled generator is text-conditioned.
10. Inspect real pixels and sound. ASR, returned subtitles and loudness cannot certify pronunciation or performance. Machine packing cannot grant human approval.
11. Keep one current package by default; create another version when history or parallel delivery requires it. Check the old state format before replacement and retain the previous package until package and state both commit.

## Tools and handoffs

- Use `imagegen` for keyframes, edits and seals; use relevant ChatCut skills for editor work.
- Verify poem facts and current tool settings against reliable sources when needed. Label inference.
- Before H3 batching, run `scripts/build_h3_batch.py`; single-frame batches match leading shot IDs by default. Use `--pair-by order` only after reviewing a deliberately different upload order. Record task IDs; do not silently resubmit paid failures.
- For new Seed Audio narration, read the voice reference, preview with `scripts/generate_poetry_audio.py --dry-run`, then submit only within explicit cost authorization. Keys stay in the process environment or local Keychain, never in prompts, command arguments, logs or packages.
- On another computer, use `scripts/check_environment.py`. Missing tools change the available stage; do not silently replace the user's tool choice.
- After export and final review, run `scripts/build_release_package.py --check-only` with recorded input paths. Build or refresh only after it passes. Reuse existing user approval evidence when it applies; do not ask again merely to fill a form.
- At a handoff, give the current stage, approved assets, checks, remaining issue and one next action. Do not invent missing files, approvals or completion.
