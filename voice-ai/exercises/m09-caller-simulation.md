# Module 9: Simulating callers

Check that the simulated callers cover every gated segment, and compare simulated pass rates with production on the same checks.

## Data

- `data/<edition>/calls.jsonl (`scenario`)`
- `data/<edition>/production_sample.jsonl (`checks`)`
- `world/<edition>/constants.json (`flow_groups`, `language_groups`)`

## Tasks

1. Count scenarios per gated segment (4 flow groups x 3 language groups). Name any segment without a scenario.
2. Run C04, C08, C09 and C12 on every simulated call (exercise 14 has the checks).
3. Compare the simulated pass rate with the production pass rate for each check, in points.

## What a good answer shows

A coverage table and a sim-minus-real table, with one sentence on what you would audit before trusting the simulator.

## Check your work

```bash
python3.11 solutions/m09_caller_simulation.py
python3.11 solutions/m09_caller_simulation.py --edition india
```

Compare with `solutions/expected/m09_caller_simulation.txt` and `solutions/expected/m09_caller_simulation.india.txt`.

The lab for this module is [caller-simulator-validator](../labs/caller-simulator-validator/).

## Read

- Global edition: https://www.aievals.co/learn/voice-ai-evals/voice-simulation
- India edition: https://www.aievals.co/learn/voice-ai-evals-india/voice-simulation
- Course module: https://www.aievals.co/courses/voice-ai-advanced
