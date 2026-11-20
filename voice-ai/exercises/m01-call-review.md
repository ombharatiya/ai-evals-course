# Module 1: Error analysis on real calls

Find the failures a transcript hides, code them with the failure taxonomy, and measure how well two reviewers agree.

## Data

- `data/<edition>/calls.jsonl` (200 simulated calls, two reviewers on 30 shared calls)
- `data/<edition>/traces/T01.json to T10.json`
- `world/<edition>/constants.json` (`taxonomy`)

## Tasks

1. For every human caller turn, compare `stt_entities` with `ref_entities`. List the turns where they differ and print the reference and STT text side by side. These are failures a transcript-only review cannot see.
2. Tally the first-failure code of the primary reviewer (`labeler` rv-03) per call, grouped by taxonomy category. Report counts and the share of failing calls.
3. On the 30 calls with `review_set` equal to shared-30, compute Cohen's kappa between rv-03 and rv-11 on the first-failure code, and list each disagreement.
4. For T01-T10, decide from the STT text and TTS text alone whether the failure is visible. Then check your answer against the reference text and the timeline (turn times, `barge_in`, `tags`).

## What a good answer shows

A short codebook table, the kappa with the disagreements named, and a sentence on which failure classes need listening or the timeline.

## Check your work

```bash
python3.11 solutions/m01_call_review.py
python3.11 solutions/m01_call_review.py --edition india
```

Compare with `solutions/expected/m01_call_review.txt` and `solutions/expected/m01_call_review.india.txt`.

## Read

- Global edition: https://www.aievals.co/learn/voice-ai-evals/voice-agent-traces
- India edition: https://www.aievals.co/learn/voice-ai-evals-india/voice-agent-traces
- Global edition: https://www.aievals.co/learn/voice-ai-evals/error-analysis-on-calls
- India edition: https://www.aievals.co/learn/voice-ai-evals-india/error-analysis-on-calls
- Course module: https://www.aievals.co/courses/voice-ai-advanced
