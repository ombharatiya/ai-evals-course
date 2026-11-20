# Module 6: Turn-taking, barge-in and recovery

Draw the endpointing curve (false cutoffs against dead air) per language group and choose a silence budget per campaign and call state by expected cost.

## Data

- `data/<edition>/pauses.jsonl (1,200 labelled pauses plus T05's pause)`

## Tasks

1. For thresholds from 200 to 1,000 ms in 50 ms steps, compute the false-cutoff rate (hold pauses longer than the threshold) per language group.
2. Report the false-cutoff rate at 300 ms and 600 ms, and the shortest threshold that keeps it at or below 5%.
3. Give date and amount holds a cost of 5, dispute holds 3 and other holds 1; charge 0.2 per 100 ms of dead air on every end pause. Pick the threshold with the lowest expected cost per campaign and call state.
4. Use `model_a_hold_prob` to wait longer when the detector thinks the caller is holding, and compare its cutoffs at 300 ms with silence alone.

## What a good answer shows

A curve table, a chosen operating point per campaign and state, and one sentence on T05.

## Check your work

```bash
python3.11 solutions/m06_endpointing_barge_in.py
python3.11 solutions/m06_endpointing_barge_in.py --edition india
```

Compare with `solutions/expected/m06_endpointing_barge_in.txt` and `solutions/expected/m06_endpointing_barge_in.india.txt`.

The lab for this module is [endpointing-operating-point](../labs/endpointing-operating-point/).

## Read

- Global edition: https://www.aievals.co/learn/voice-ai-evals/turn-taking-and-barge-in
- India edition: https://www.aievals.co/learn/voice-ai-evals-india/turn-taking-and-barge-in
- Course module: https://www.aievals.co/courses/voice-ai-advanced
