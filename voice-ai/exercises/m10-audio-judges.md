# Module 10: Judges for audio

Validate a judge per language group and dimension against human labels, admit it only on the lower bound, and see the prevalence trap.

## Data

- `data/<edition>/judge_labels.jsonl` (120 calls per language group per dimension, two raters, two judges)

## Tasks

1. For each dimension, language group and judge, build the confusion matrix against `human_label`.
2. Report agreement, Cohen's kappa, violation recall and specificity with Wilson 95% intervals, and precision.
3. Admit a judge for gating only when both lower bounds reach 0.90. Which judges pass? Why does a 120-call set make that hard?
4. Show that a judge that always says compliant reaches 97% agreement and kappa 0 at 3% prevalence.
5. Compute kappa between the two human raters per language group.

## What a good answer shows

The validation table, the gate verdicts and a registry entry (templates/judge-registry-entry.json) for one judge.

## Check your work

```bash
python3.11 solutions/m10_audio_judges.py
python3.11 solutions/m10_audio_judges.py --edition india
```

Compare with `solutions/expected/m10_audio_judges.txt` and `solutions/expected/m10_audio_judges.india.txt`.

The lab for this module is [voice-judge-validation](../labs/voice-judge-validation/).

## Read

- Global edition: https://www.aievals.co/learn/voice-ai-evals/audio-judges
- India edition: https://www.aievals.co/learn/voice-ai-evals-india/audio-judges
- Course module: https://www.aievals.co/courses/voice-ai-advanced
