# Module 13: Production monitoring

Size production samples for rare violations and see why a uniform sample misses them.

## Data

- `data/<edition>/production_sample.jsonl (`stratum`)`
- `world/<edition>/constants.json (`world_rates`, `volumes`)`

## Tasks

1. Estimate each risk stratum's share of human-answered calls with a Wilson interval.
2. Compute the calls needed to see a 1-in-1,000 violation with 95% probability, P(at least one) for 1,000 calls at 1 in 2,000, and the upper bounds for 0 violations in 300 audited calls.
3. Replay T09: at the world's threat rate and a uniform 2% judge sample, how likely was it to see at least one threat in three days? What changes if the judge reads every angry-path call?

## What a good answer shows

The strata table and the sizing numbers.

## Check your work

```bash
python3.11 solutions/m13_voice_monitoring.py
python3.11 solutions/m13_voice_monitoring.py --edition india
```

Compare with `solutions/expected/m13_voice_monitoring.txt` and `solutions/expected/m13_voice_monitoring.india.txt`.

The lab for this module is [rare-violation-sampling](../labs/rare-violation-sampling/).

## Read

- Global edition: https://www.aievals.co/learn/voice-ai-evals/voice-production-monitoring
- India edition: https://www.aievals.co/learn/voice-ai-evals-india/voice-production-monitoring
- Course module: https://www.aievals.co/courses/voice-ai-advanced
