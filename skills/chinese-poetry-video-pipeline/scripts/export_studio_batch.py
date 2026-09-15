#!/usr/bin/env python3
"""Export explicit per-task durations for the H3 Studio batch input adapter."""
import argparse
import math
import re
from pathlib import Path


def studio_line(text, duration):
    if not math.isfinite(duration) or not 2 <= duration <= 15:
        raise ValueError("Studio duration must be between 2 and 15 seconds, inclusive.")
    text = text.strip()
    if not text:
        raise ValueError("Empty prompt.")
    if re.match(r"^\d+(?:\.\d+)?\s*秒", text):
        raise ValueError("Input already has a duration prefix; use the model prompt source.")
    # Check explicit English total-shot declarations used by existing sources.
    # Action timestamps are not used to infer a duration.
    declared = re.findall(r"(?i)\b(\d+(?:\.\d+)?)-second\s+(?:continuous\s+)?shot\b", text)
    single_shot = len(set(re.findall(r'\[Shot (\d+)\]', text))) <= 1
    if single_shot and declared and any(abs(float(n)-duration)>1e-8 for n in declared):
        raise ValueError("Explicit total-shot duration conflicts with the requested duration.")
    for start, end in re.findall(r"From ([0-9.]+) to ([0-9.]+) seconds", text):
        if not 0 <= float(start) < float(end) <= duration:
            raise ValueError("A spoken/action window exceeds the requested duration.")
    return f"{duration:g}秒，" + re.sub(r"\s+", " ", text)


def export_lines(prompts, durations):
    if not prompts or len(prompts) != len(durations):
        raise ValueError("Provide exactly one explicit duration for every prompt.")
    return [studio_line(text, duration) for text, duration in zip(prompts, durations)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prompts', nargs='+', type=Path, required=True)
    parser.add_argument('--durations', nargs='+', type=float, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--force', action='store_true')
    args = parser.parse_args()
    if args.output.resolve() in [p.resolve() for p in args.prompts]:
        parser.error('Output must not overwrite a model prompt source.')
    try:
        lines = export_lines([p.read_text(encoding='utf-8-sig') for p in args.prompts], args.durations)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('w' if args.force else 'x', encoding='utf-8') as out:
            out.write('\n'.join(lines)+'\n')
    except (ValueError, OSError) as exc:
        parser.exit(1, f'{exc}\n')
    print('Studio task durations: '+', '.join(f'{d:g}s' for d in args.durations))
    print('Only line-prefix duration is configured; actual model output is not verified.')


if __name__ == '__main__':
    main()
