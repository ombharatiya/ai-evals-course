# Module 12: Evals under load, and their cost

Find the load knee in the simulated calls and rebuild the monthly eval budget from unit costs.

## Data

- `data/<edition>/calls.jsonl (`concurrency_at_start`, `timings_summary`)`
- `world/<edition>/constants.json (`cost_model`, `volumes`, `ci`, `world_rates`)`

## Tasks

1. Band the calls by concurrency at start (below 1,500, 1,500 to 1,799, 1,800 and above) and report P50 and P95 of the tool-turn gap per band.
2. Recompute every line of the baseline budget from the unit costs and volumes, and compare with the world bible.
3. Scale the volume-driven lines (checks, judges, STT) to the capstone volume and compare with the capstone cap.

## What a good answer shows

The load table, the budget table and the cap verdicts.

## Check your work

```bash
python3.11 solutions/m12_voice_load_cost.py
python3.11 solutions/m12_voice_load_cost.py --edition india
```

Compare with `solutions/expected/m12_voice_load_cost.txt` and `solutions/expected/m12_voice_load_cost.india.txt`.

The lab for this module is [voice-load-ramp-plan](../labs/voice-load-ramp-plan/).

## Read

- Global edition: https://www.aievals.co/learn/voice-ai-evals/voice-load-and-cost
- India edition: https://www.aievals.co/learn/voice-ai-evals-india/voice-load-and-cost
- Course module: https://www.aievals.co/courses/voice-ai-advanced
