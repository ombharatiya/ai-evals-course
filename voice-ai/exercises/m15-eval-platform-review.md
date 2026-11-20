# Module 15: Capstone: design the eval platform

Collect the evidence for your capstone design: which component catches each incident, and what the program costs.

## Data

- `data/<edition>/traces/T01.json to T10.json`
- `world/<edition>/constants.json (`cost_model`)`
- your outputs from exercises 1-14 and the labs

## Tasks

1. For each of T01-T10, list the deterministic checks that fail, whether the CRM diff fails, and the gate or component that should catch it.
2. Count the incidents caught by two or more independent components.
3. Put the budget frame next to it: today's plan, the cap, and the plan at the capstone volume.
4. Write the capstone design with templates/capstone-brief.md (global edition) or templates/capstone-brief.india.md (India edition), and score it with templates/capstone-rubric.md.

## What a good answer shows

An incident coverage table you can paste into the capstone appendix.

## Check your work

```bash
python3.11 solutions/m15_eval_platform_review.py
python3.11 solutions/m15_eval_platform_review.py --edition india
```

Compare with `solutions/expected/m15_eval_platform_review.txt` and `solutions/expected/m15_eval_platform_review.india.txt`.

## Read

- Global edition: https://www.aievals.co/learn/voice-ai-evals/voice-eval-platform
- India edition: https://www.aievals.co/learn/voice-ai-evals-india/voice-eval-platform
- Course module: https://www.aievals.co/courses/voice-ai-advanced
