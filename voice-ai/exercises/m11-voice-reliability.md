# Module 11: Statistics and reliability

Estimate pass^k from repeated simulated trials without the biased shortcut.

## Data

- `data/<edition>/calls.jsonl` (25 scenarios x 8 trials; `scenario.trial`)

## Tasks

1. Call a trial a pass when its task diff is empty and no deterministic check fails.
2. For each scenario with c passes in n trials, compute the unbiased pass^k = C(c,k)/C(n,k) for k = 1, 2, 4, 8.
3. Average over scenarios and compare with the plug-in (c/n)^k. Which is larger, and why?
4. Check the worked numbers: C(6,4)/C(8,4) = 0.2143, (6/8)^4 = 0.3164, 0.8^8 = 0.1678.

## What a good answer shows

A per-scenario table and the suite comparison.

## Check your work

```bash
python3.11 solutions/m11_voice_reliability.py
python3.11 solutions/m11_voice_reliability.py --edition india
```

Compare with `solutions/expected/m11_voice_reliability.txt` and `solutions/expected/m11_voice_reliability.india.txt`.

The lab for this module is [voice-pass-k-planner](../labs/voice-pass-k-planner/).

## Read

- Global edition: https://www.aievals.co/learn/voice-ai-evals/voice-reliability-statistics
- India edition: https://www.aievals.co/learn/voice-ai-evals-india/voice-reliability-statistics
- Course module: https://www.aievals.co/courses/voice-ai-advanced
