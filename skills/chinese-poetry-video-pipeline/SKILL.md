---
name: chinese-poetry-video-pipeline
description: Plan and produce complete 15–35 second Chinese-poetry aesthetic videos, from poem selection and verified interpretation through visual direction, keyframes, MiniMax H3 image-to-video prompts, ChatCut editing, export, cover, title, and social copy. Use for 古诗词意境短片、东方美学诗词视频或其中任一延续阶段；do not use for unrelated generic fantasy videos.
---

# Chinese Poetry Video Pipeline

Turn one poem into a coherent, reviewable production system. The poem determines the visual medium, motion, sound, and editing rhythm; do not begin from a reusable “古风人物＋风景” look.

## Operating modes

- **End to end:** take one poem from selection to publish-ready package.
- **Stage only:** complete only the requested stage and leave a precise next step.
- **Continue:** inspect existing project state and approved assets before doing new work. Preserve approved decisions unless the user changes them.
- **Batch series:** keep publishing identity consistent, but deliberately vary each poem’s visual medium, palette, composition, focal lengths, and motion grammar.
- **High-fidelity reproduction:** when the user asks for the same series identity across machines or projects, read [references/reproducibility.md](references/reproducibility.md), verify the target environment, use the bundled style anchors, and score conformance before delivery.

## Required routing

Read [references/quality-gates.md](references/quality-gates.md) for every use. Then read only the stage references needed now:

- Selection, source text, or interpretation: [references/poetry-interpretation.md](references/poetry-interpretation.md)
- Style, storyboard, composition, or still-image prompts: [references/visual-system.md](references/visual-system.md)
- MiniMax H3 prompts, batch files, or cloud generation: [references/minimax-h3.md](references/minimax-h3.md)
- ChatCut assembly, typography, seal, sound, or export: [references/chatcut-editing.md](references/chatcut-editing.md)
- Cover, titles, or social copy: [references/publishing.md](references/publishing.md)
- Final delivery, versioning, manifest, or handoff: [references/release-package.md](references/release-package.md)
- Cross-machine installation, style matching, or a “90% similar” request: [references/reproducibility.md](references/reproducibility.md)

When starting a new project, use `scripts/init_project.py` unless the user already has a clear folder structure. Before a MiniMax WebUI batch, use `scripts/build_h3_batch.py` to validate prompt fields and produce one physical line per task. After the final export, cover, copy, and quality record pass, use `scripts/build_release_package.py` to create the immutable standard output package.

## State machine

Track one current stage and one next action in `00-project-state.json`.

| Stage | Required result | Gate to advance |
|---|---|---|
| `selected` | verified poem candidate and production fit | text/version is reliable; poem has a visual contradiction and motion potential |
| `interpreted` | literal meaning, emotional engine, visual thesis, sound thesis | the concept explains more than a literal tableau |
| `visual_approved` | style bible, sequence arc, lens/composition matrix | consecutive shots differ meaningfully; style belongs to this poem |
| `keyframes_approved` | numbered prompts and approved 3:4 stills | every still passes composition, clarity, anatomy, gaze, continuity, and texture checks |
| `h3_prompts_ready` | readable prompts, batch text, upload order | image/task/prompt counts match; each task has executable motion and no contradictions |
| `clips_approved` | downloaded H3 clips and shot-level QC | identity, geometry, motion, camera, sound, and duration are usable |
| `chatcut_edited` | editable ChatCut timeline with text, sound, and seal | pacing, typography, narration, and overlays pass composed-frame review |
| `exported` | verified local MP4 and project export record | resolution, fps, duration, audio, and representative frames are correct |
| `publish_ready` | versioned standard output package | final video, cover, copy, source record, QA, manifest, and checksums are complete and internally consistent |

Do not jump from interpretation directly to paid video generation. A user may authorize an end-to-end run, but costly cloud submission still requires approved final parameters and expected cost unless that authorization was already explicit.

## Shared production invariants

1. **Begin with the poem’s conflict.** Examples of useful structures include繁华与孤独、天上与人间、盛时与迟暮、物是与人非、路阻与心行. Do not treat these examples as a fixed catalog.
2. **Translate, do not illustrate mechanically.** Every shot needs a visual proposition: a relationship, transformation, delay, absence, weight, distance, or reversal.
3. **Choose a fresh visual language per poem.** Series continuity should come mainly from editorial typography, seal logic, pacing discipline, and quality—not identical scenery, color grading, or character framing.
4. **Vary camera grammar.** Never use the same view, focal-length family, subject scale, and composition in consecutive shots. Consider high distance, deep distance, and level distance from Chinese painting where they strengthen meaning.
5. **Build depth structurally.** Use foreground occlusion, scale, paths, bridges, water, cloth, bamboo, architecture, or light to connect foreground–midground–background. Fog may separate planes but must not hide structure.
6. **Keep images clear.** No smear, repeated fractured texture, texture proliferation, indiscriminate glow, heavy fog, soft-focus masking, malformed hands, duplicated figures, unreadable architecture, accidental text, or watermark.
7. **Keep movement physically executable.** Describe a countable action path, consistent wind direction, object attachment, camera direction, and end state. Do not force walking when the composition gives the character nowhere to go.
8. **Regenerate structural failures.** Repeated inpainting often creates blur and broken texture. Preserve approved elements in a new generation prompt and regenerate the whole frame when composition or geometry is wrong.
9. **Default delivery shape.** Unless the user specifies otherwise: 3:4 vertical; 20–30 second final; 4–7 shots; 8-second H3 source clips with editable head/tail handles; ChatCut timeline 1080×1440 at 30 fps; H.264 1080p export.
10. **Verify pixels, not descriptions.** Inspect actual stills, generated clips, composed ChatCut frames, and exported files before reporting completion.
11. **Package, do not dump.** Keep publish-ready assets separate from production archives. A final package is versioned and immutable; a correction creates `v02` instead of silently replacing `v01`.
12. **Define similarity before claiming it.** A score near 90 means the same creative decisions, visual discipline, prompt grammar, edit identity, and delivery contract—not identical generated pixels. Exact frames cannot be guaranteed across model versions or random generations.

## Tool coordination

- Use the `imagegen` skill for keyframe creation or image editing.
- For current poem text, authorship, variants, or historical interpretation, use reliable primary or authoritative sources when verification is needed; distinguish source facts from creative inference.
- For ChatCut work, load the relevant ChatCut skills. Commonly needed: `chatcut:chatcut-plugin-basics`, `chatcut:asset-import`, `chatcut:create-motion-graphics`, `chatcut:verification`, and `chatcut:export`.
- For a user-operated MiniMax H3 WebUI, prepare files and exact input order first. Use browser/computer control only when requested or authorized. Record task IDs and do not silently resubmit failed paid tasks.
- On a new computer, run `scripts/check_environment.py` before beginning end-to-end production. Missing ChatCut or H3 access changes the available stage; it is not silently replaced by another tool.

## Review rhythm

- Present poem interpretation and the visual thesis together.
- Present the sequence plan before generating all keyframes when the direction is new.
- Generate or approve a representative first frame before batching a style-sensitive sequence.
- Review stills as a sequence, not only one by one.
- Fix only the failing shot once the sequence style is approved.
- At each handoff, state: current stage, approved artifacts, verification evidence, remaining risk, and the single next action.

## Deliverables

A complete project should contain:

- verified poem and interpretation;
- style bible, storyboard, and shot-variation matrix;
- numbered keyframe prompts and approved images;
- per-shot H3 prompts, batch prompt file, upload order, and task log;
- approved generated clips;
- ChatCut project/timeline record and visual QC;
- verified export;
- cover, title options, note copy, and hashtags.
- a versioned standard output package containing publish-ready assets, production archive, manifest, checksums, and final QA.

Do not fabricate missing files, task IDs, exports, approvals, or verification. Mark them pending in project state.
