# Module 2: Metric design, layers and trade-offs

Build a collections funnel where every rate names its denominator, and see how an AMD error moves one metric and not another.

## Data

- `data/<edition>/production_sample.jsonl` (4,000 dial attempts from one day)

## Tasks

1. Count dials, connects (`connected`), true human answers (`human_answer`), right-party contacts (`rpc`), promises (`ptp`), verified promises (`ptp_verified`) and kept promises (`kept`).
2. Report PTP per dial, per connect, per human answer and per RPC, and kept PTP per dial.
3. Count false humans (AMD said human on a machine) and false machines (AMD said machine on a human). Price the false humans at 21 s of trunk time each.
4. Explain in two sentences why PTP per connect moves when only the AMD error rate changes, while PTP per RPC does not.

## What a good answer shows

A funnel table with named denominators and the AMD paragraph.

## Check your work

```bash
python3.11 solutions/m02_metric_layers.py
python3.11 solutions/m02_metric_layers.py --edition india
```

Compare with `solutions/expected/m02_metric_layers.txt` and `solutions/expected/m02_metric_layers.india.txt`.

## Read

- Global edition: https://www.aievals.co/learn/voice-ai-evals/voice-metric-layers
- India edition: https://www.aievals.co/learn/voice-ai-evals-india/voice-metric-layers
- Course module: https://www.aievals.co/courses/voice-ai-advanced
