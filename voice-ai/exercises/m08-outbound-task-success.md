# Module 8: Task success and outbound outcomes

Score task success as a diff of CRM state against a gold end state per flow, and cost the AMD confusion matrix.

## Data

- `data/<edition>/calls.jsonl` (`crm_before`, `crm_after`, `gold_end_state`)
- `data/<edition>/traces/T01.json`
- `data/<edition>/production_sample.jsonl` (`amd_true`, `amd_pred`)

## Tasks

1. Write `task_diff(call)`: the rows a call added to each CRM table, matched against `gold_end_state.new_rows`, plus the account fields and the call-attempt fields in the gold state. Print one line per difference in the form `<table>.<field> expected <gold value> got <stored value>`. When a whole row is wrong, print `<table>: missing row <gold row>` for a gold row with no match, or `<table>: unexpected row <stored row>` for an added row the gold state does not list. Read the money field name from `fields.amount`.
2. Run it on T01 and on all 200 calls. Report task success per flow.
3. Build the six-class AMD confusion matrix from the production sample, with per-class recall. Name the class with the lowest recall.
4. Price the errors: 21 s of trunk time per false human, one lost contact per false machine.

## What a good answer shows

The T01 diff lines, the per-flow table, the AMD matrix and the cost line.

## Check your work

```bash
python3.11 solutions/m08_outbound_task_success.py
python3.11 solutions/m08_outbound_task_success.py --edition india
```

Compare with `solutions/expected/m08_outbound_task_success.txt` and `solutions/expected/m08_outbound_task_success.india.txt`.

The lab for this module is [collections-task-checker](../labs/collections-task-checker/).

## Read

- Global edition: https://www.aievals.co/learn/voice-ai-evals/task-success-and-outbound
- India edition: https://www.aievals.co/learn/voice-ai-evals-india/task-success-and-outbound
- Course module: https://www.aievals.co/courses/voice-ai-advanced
