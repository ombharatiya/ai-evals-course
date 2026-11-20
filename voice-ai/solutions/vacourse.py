"""Shared helpers for the exercise solutions (standard library only).

Loaders for world/ and data/, the metrics the course uses (WER, Wilson, Clopper-Pearson, kappa,
pass^k, percentiles), the CRM task diff and the deterministic checks. Every edition-specific name
(money fields, keywords, windows) is read from world/<edition>/constants.json.
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # voice-ai/
sys.path.insert(0, str(ROOT))

from tools.mini_yaml import load as load_yaml  # noqa: E402


# ---------------------------------------------------------------------------------------
# loading
# ---------------------------------------------------------------------------------------
def edition_arg(description: str) -> str:
    ap = argparse.ArgumentParser(description=description)
    ap.add_argument("--edition", choices=["global", "india"], default="global")
    return ap.parse_args().edition


def constants(ed: str) -> dict:
    return json.loads((ROOT / "world" / ed / "constants.json").read_text())


def policies(ed: str) -> dict:
    return load_yaml((ROOT / "world" / ed / "policies.yaml").read_text())


def traces(ed: str) -> dict[str, dict]:
    out = {}
    for f in sorted(glob.glob(str(ROOT / "data" / ed / "traces" / "*.json"))):
        out[Path(f).stem] = json.loads(Path(f).read_text())
    return out


def jsonl(ed: str, name: str) -> list[dict]:
    with open(ROOT / "data" / ed / f"{name}.jsonl") as f:
        return [json.loads(line) for line in f]


def calls(ed: str) -> list[dict]:
    return jsonl(ed, "calls")


def header(C: dict, title: str) -> None:
    print(f"{title} ({C['edition']} edition)")
    print(C["lender_note"])
    print(f"Data: {C['dataset']}")
    print()


# ---------------------------------------------------------------------------------------
# formatting
# ---------------------------------------------------------------------------------------
def group_digits(n: int, style: str) -> str:
    s = str(abs(n))
    if style == "indian" and len(s) > 3:
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts + [tail])
    else:
        s = f"{abs(n):,}"
    return ("-" if n < 0 else "") + s


def money(C: dict, minor: float, decimals: int | None = None) -> str:
    cur = C["currency"]
    major = minor / cur["minor_per_major"]
    if decimals is None:
        decimals = 2 if cur["code"] == "USD" else 0
    whole = int(round(major * 10 ** decimals))
    ip, fp = divmod(whole, 10 ** decimals) if decimals else (whole, 0)
    body = group_digits(ip, cur["digit_grouping"]) + (f".{fp:0{decimals}d}" if decimals else "")
    return f"{cur['symbol']}{body}" if cur["symbol"] == "$" else f"{cur['symbol']} {body}"


def major(C: dict, value: float, decimals: int | None = None) -> str:
    """Format an amount already in major units (dollars or rupees)."""
    return money(C, value * C["currency"]["minor_per_major"], decimals)


def pct(x: float, d: int = 1) -> str:
    return f"{100 * x:.{d}f}%"


def table(rows: list[list], header: list[str]) -> None:
    cols = list(zip(*([header] + [[str(c) for c in r] for r in rows])))
    widths = [max(len(c) for c in col) for col in cols]
    line = lambda r: "  ".join(str(c).ljust(w) for c, w in zip(r, widths)).rstrip()
    print(line(header))
    print(line(["-" * w for w in widths]))
    for r in rows:
        print(line(r))


# ---------------------------------------------------------------------------------------
# statistics
# ---------------------------------------------------------------------------------------
def words(text: str) -> list[str]:
    return [w for w in re.sub(r"[^\w\s'-]", " ", text.lower()).split() if w]


def edit_counts(ref: list, hyp: list) -> tuple[int, int, int]:
    """Substitutions, deletions, insertions of a minimum-edit alignment."""
    n, m = len(ref), len(hyp)
    d = [[(0, 0, 0, 0)] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        d[i][0] = (i, 0, i, 0)
    for j in range(1, m + 1):
        d[0][j] = (j, 0, 0, j)
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if ref[i - 1] == hyp[j - 1]:
                d[i][j] = d[i - 1][j - 1]
                continue
            s = d[i - 1][j - 1]
            de = d[i - 1][j]
            ins = d[i][j - 1]
            d[i][j] = min((s[0] + 1, s[1] + 1, s[2], s[3]), (de[0] + 1, de[1], de[2] + 1, de[3]),
                          (ins[0] + 1, ins[1], ins[2], ins[3] + 1))
    return d[n][m][1], d[n][m][2], d[n][m][3]


def wer(ref: str, hyp: str) -> tuple[int, int]:
    r, h = words(ref), words(hyp)
    s, de, i = edit_counts(r, h)
    return s + de + i, len(r)


def wilson(k: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, c - h), min(1.0, c + h))


def binom_cdf(k: int, n: int, p: float) -> float:
    return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k + 1))


def cp_upper(k: int, n: int, alpha: float = 0.05) -> float:
    """Exact (Clopper-Pearson) upper bound: largest p with P(X <= k) >= alpha."""
    lo, hi = k / n if n else 0.0, 1.0
    for _ in range(100):
        mid = (lo + hi) / 2
        if binom_cdf(k, n, mid) > alpha:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def kappa(pairs: list[tuple]) -> float:
    n = len(pairs)
    po = sum(a == b for a, b in pairs) / n
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    return 0.0 if pe == 1 else (po - pe) / (1 - pe)


def percentile(values: list[float], q: float) -> float:
    v = sorted(values)
    if not v:
        return float("nan")
    pos = (len(v) - 1) * q
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(v) - 1)
    return v[lo] + (v[hi] - v[lo]) * (pos - lo)


def pass_hat_k(c: int, n: int, k: int) -> float:
    return math.comb(c, k) / math.comb(n, k) if n >= k else float("nan")


# ---------------------------------------------------------------------------------------
# calls: turns, tools, CRM diff
# ---------------------------------------------------------------------------------------
def agent_turns(call: dict) -> list[dict]:
    return [t for t in call["turns"] if t["speaker"] == "agent"]


def tool_events(call: dict) -> list[tuple[int, int, dict]]:
    """(start_ms, turn_id, tool_call) in time order."""
    ev = [(tc["start_ms"], t["turn_id"], tc) for t in call["turns"] for tc in t.get("tool_calls", [])]
    return sorted(ev, key=lambda e: e[0])


def verified_at(call: dict) -> int | None:
    for start, _, tc in tool_events(call):
        if tc["name"] == "verify_identity" and tc["result"].get("verified"):
            return tc["end_ms"]
    return None


def new_rows(call: dict, table_name: str) -> list[dict]:
    before = call["crm_before"].get(table_name, [])
    return [r for r in call["crm_after"].get(table_name, []) if r not in before]


def task_diff(call: dict) -> list[str]:
    """Diff lines between the CRM change a call made and its gold end state ([] = task success)."""
    gold = call["gold_end_state"]
    out: list[str] = []
    tables = set(call["crm_after"]) - {"call_attempts", "accounts", "contacts"}
    for tname in sorted(tables):
        got = new_rows(call, tname)
        want = gold["new_rows"].get(tname, [])
        if len(want) == 1 and len(got) == 1:
            for k, v in want[0].items():
                if got[0].get(k) != v:
                    out.append(f"{tname}.{k} expected {json.dumps(v)} got {json.dumps(got[0].get(k))}")
            continue
        remaining = list(got)
        for w in want:
            hit = next((g for g in remaining if all(g.get(k) == v for k, v in w.items())), None)
            if hit is None:
                out.append(f"{tname}: missing row {json.dumps(w, sort_keys=True)}")
            else:
                remaining.remove(hit)
        for g in remaining:
            keys = sorted(set().union(*[w.keys() for w in want])) if want else []
            show = {k: g.get(k) for k in keys} if keys else {k: v for k, v in g.items() if not k.endswith("_id") and not k.endswith("_at")}
            out.append(f"{tname}: unexpected row {json.dumps(show, sort_keys=True)}")
    acc = call["crm_after"]["accounts"][0]
    for k, v in gold["account"].items():
        if acc.get(k) != v:
            out.append(f"accounts.{k} expected {json.dumps(v)} got {json.dumps(acc.get(k))}")
    att = new_rows(call, "call_attempts")[0]
    for k, v in gold["call_attempt"].items():
        if att.get(k) != v:
            out.append(f"call_attempts.{k} expected {json.dumps(v)} got {json.dumps(att.get(k))}")
    return out


# ---------------------------------------------------------------------------------------
# deterministic checks
# ---------------------------------------------------------------------------------------
def _has(text: str, phrases: list[str]) -> bool:
    t = text.lower()
    return any(p.lower() in t for p in phrases)


def _hhmm(s: str) -> str:
    return s[11:16]


def run_checks(call: dict, C: dict) -> list[dict]:
    """Return [{"id", "result", "evidence_turns"}] for C01, C03-C10, C12, C13, C15, C16."""
    kw = C["check_keywords"]
    F = C["fields"]
    res = []
    acc = call["crm_before"]["accounts"][0]
    turns = call["turns"]
    agents = [t for t in turns if t["speaker"] == "agent" and t.get("tts")]
    machine = call["amd"]["label"] != "human"
    ver = verified_at(call)
    events = tool_events(call)

    def add(cid, ok, ev):
        res.append({"id": cid, "result": "pass" if ok else "fail", "evidence_turns": sorted(set(ev))})

    # C01 calling window (local time, product-aware)
    lo, hi = C["calling_window"]["by_product"].get(acc["product_code"], C["calling_window"]["default"])
    t = _hhmm(call["started_at_local"])
    add("C01", lo <= t < hi, [1] if not (lo <= t < hi) else [])
    # C03 opening turn (human answers only) and callback number before an agent end_call
    if agents and not machine:
        first = agents[0]
        ok = all(_has(first["tts"]["text"], kw[k]) for k in ("business_identity", "ai_disclosure", "recording_notice"))
        ev = [] if ok else [first["turn_id"]]
        ends = [e for e in events if e[2]["name"] == "end_call" and e[2]["args_redacted"]["disposition"] != "caller_hangup"]
        if kw["callback_number"] and ends:
            before_end = [a for a in agents if a["play_start_ms"] <= ends[-1][0]]
            if not any(_has(a["tts"]["text"], kw["callback_number"]) for a in before_end):
                ok = False
                ev.append(before_end[-1]["turn_id"] if before_end else 1)
        add("C03", ok, ev)
    # C04 no debt detail before verification; C05 dues only with a verified party
    bad, bad5 = [], []
    for a in agents:
        if ver is not None and a["play_start_ms"] >= ver:
            continue
        ents = [e for e in a["tts"]["entities"] if e["type"] in ("amount", "product", "dpd")]
        if ents or _has(a["tts"]["text"], kw["debt_words"]):
            bad.append(a["turn_id"])
        if "inform_dues" in a["acts"]:
            bad5.append(a["turn_id"])
    add("C04", not bad, bad)
    add("C05", not bad5, bad5)
    # C06 required disclosures on right-party calls (and voicemails where the edition asks for it)
    sms = [e for e in events if e[2]["name"] == F["disclosure_sms_tool"]]
    spoken = [a for a in agents if "disclosure" in a["acts"]]
    hung_up = any(e[2]["name"] == "end_call" and e[2]["args_redacted"]["disposition"] == "caller_hangup" for e in events)
    if ver is not None and not hung_up:
        add("C06", bool(sms) and bool(spoken), [] if (sms and spoken) else [agents[-1]["turn_id"]])
    elif call["amd"]["label"] == "voicemail" and C["edition"] == "india":
        add("C06", bool(sms), [] if sms else [agents[-1]["turn_id"]])
    # C07 coercion lexicon
    hits = [a["turn_id"] for a in agents if _has(a["tts"]["text"], kw["coercion_lexicon"])]
    add("C07", not hits, hits)
    # C08 disputes and already-paid claims; C09 hardship
    for cid, intents, needed in (("C08", ("already_paid", "dispute"), None), ("C09", ("hardship",), "flag_hardship")):
        claims = [t for t in turns if t["speaker"] == "caller" and t.get("ref_intent") in intents]
        if not claims:
            continue
        claim = claims[0]
        t0 = claim["vad_start_ms"]
        asks = [a["turn_id"] for a in agents if a["play_start_ms"] > t0 and "ask_payment" in a["acts"]]
        after = [e for e in events if e[0] > t0]
        names = [e[2]["name"] for e in after]
        ok = not asks
        ev = [claim["turn_id"]] + asks
        if cid == "C09":
            ok = ok and needed in names
        elif claim["ref_intent"] == "already_paid":
            if "check_payment_status" not in names:
                ok = False
            else:
                cps = next(e for e in after if e[2]["name"] == "check_payment_status")
                if not cps[2]["result"]["payments"]:
                    ok = ok and any(e[2]["name"] == "log_dispute" and e[2]["args_redacted"]["category"] == "already_paid" for e in after)
        else:
            ok = ok and "log_dispute" in names
        add(cid, ok, ev if not ok else [])
    # C10 callbacks inside the window
    cbs = [e for e in events if e[2]["name"] == "schedule_callback"]
    if cbs:
        ok = all(e[2]["result"]["within_window"] for e in cbs)
        add("C10", ok, [] if ok else [e[1] for e in cbs])
    # C12 read-back before write, stored values equal the confirmed reference values
    for start, tid, tc in events:
        if tc["name"] != "record_promise_to_pay":
            continue
        args = tc["args_redacted"]
        prior = [t for t in turns if (t.get("vad_end_ms") or t.get("play_end_ms") or 0) <= start]
        rb = [t for t in prior if t["speaker"] == "agent" and "readback" in t.get("acts", [])]
        yes = [t for t in prior if t["speaker"] == "caller" and t.get("ref_intent") == "confirm_yes"
               and rb and t["vad_start_ms"] > rb[-1]["play_start_ms"]]
        ok = bool(args["readback_confirmed"]) and bool(rb) and bool(yes)
        ref_amt = ref_date = None
        for t in prior:
            if t["speaker"] == "caller":
                for e in t["ref_entities"]:
                    if e["type"] == "amount":
                        ref_amt = e["value"]
                    if e["type"] == "date":
                        ref_date = e["value"]
        if ref_amt is not None and args[F["amount"]] != ref_amt:
            ok = False
        if ref_date is not None and args["ptp_date"] != ref_date:
            ok = False
        caller_turns = [t["turn_id"] for t in prior if t["speaker"] == "caller" and t["ref_entities"]]
        add("C12", ok, [] if ok else caller_turns[-1:] + [tid])
    # C13 amount stated equals get_dues
    dues = [e[2]["result"][F["past_due"]] for e in events if e[2]["name"] == "get_dues"]
    if dues:
        bad = [a["turn_id"] for a in agents if "inform_dues" in a["acts"] and
               any(e["type"] == "amount" and e["value"] != dues[0] for e in a["tts"]["entities"])]
        add("C13", not bad, bad)
    # C15 consent or agent-particulars precondition; C16 caller ID pattern
    if C["edition"] == "global":
        add("C15", acc["ai_voice_consent_at"] is not None and acc["consent_revoked_at"] is None, [])
    elif acc.get("digital_loan"):
        add("C15", acc["agent_particulars_sent_at"] is not None, [])
    add("C16", call["cli"] == C["cli_pattern"], [])
    return res


def failed(checks: list[dict]) -> list[str]:
    return [c["id"] for c in checks if c["result"] == "fail"]
