"""Module 8 (outbound-task-success) solution: CRM diffs and the AMD matrix. Run: python3.11 solutions/m08_outbound_task_success.py [--edition india]"""
from collections import Counter, defaultdict

import vacourse as v

ed = v.edition_arg(__doc__)
C = v.constants(ed)
calls = v.calls(ed)
v.header(C, "Task success against CRM state")

t01 = v.traces(ed)["T01"]
print("T01 against its gold end state:")
for line in v.task_diff(t01):
    print(f"  {line}")
print()
by_flow = defaultdict(lambda: [0, 0])
for c in calls:
    f = c["scenario"]["flow"]
    by_flow[f][1] += 1
    by_flow[f][0] += not v.task_diff(c)
rows = [[f, C["flows"][f], f"{ok}/{n}", v.pct(ok / n)] for f, (ok, n) in sorted(by_flow.items())]
v.table(rows, ["flow", "name", "task success", "rate"])
print()
def diff_label(line: str) -> str:
    """'<table>.<field>' for a field difference, '<table> missing row' or '<table> unexpected row' for a row."""
    head = line.split(" ")[0]
    if head.endswith(":"):
        return head[:-1] + (" missing row" if ": missing row " in line else " unexpected row")
    return head


fails = Counter(diff_label(line) for c in calls for line in v.task_diff(c))
print("Most common diff fields:", ", ".join(f"{k} ({n})" for k, n in fails.most_common(5)))
print()
prod = v.jsonl(ed, "production_sample")
classes = C["amd_classes"]
conf = Counter((r["amd_true"], r["amd_pred"]) for r in prod if r["connected"])
print("AMD confusion on connected attempts (rows: true class, columns: predicted):")
rows = []
for t in classes:
    n = sum(conf[(t, p)] for p in classes)
    rows.append([t] + [conf[(t, p)] for p in classes] + [f"{conf[(t, t)] / n:.2f}" if n else "-"])
v.table(rows, ["true \\ pred"] + classes + ["recall"])
recalls = {t: conf[(t, t)] / max(1, sum(conf[(t, p)] for p in classes)) for t in classes}
low = min(recalls, key=recalls.get)
false_human = sum(conf[(t, "human")] for t in classes if t != "human")
false_machine = sum(conf[("human", p)] for p in classes if p != "human")
print(f"Lowest recall: {low} ({recalls[low]:.2f}).")
print(f"Cost-weighted error: {false_human} false humans x 21 s of trunk time = {21 * false_human} s; "
      f"{false_machine} false machines = {false_machine} lost human contacts.")
