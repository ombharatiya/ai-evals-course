"""Check task success against CRM state (aievals.co cookbook recipe).

Steelyard Credit is a fictional lender; its numbers are illustrative.

Scores outbound collections calls on the CRM, not on the agent's words:
  1. a gold end state per flow (F01-F10), built from the CRM snapshot before the call
  2. a checker that diffs the before and after snapshots against that gold state
     and checks the required tool order
  3. funnel metrics with their denominators (RPC, PTP per RPC, verified PTP, kept)
  4. a six-class AMD confusion matrix with per-class recall and error costs,
     and PTP per connect vs PTP per RPC for two AMD settings

Standard library only. All data is synthetic and generated here from a fixed seed.
Run:
    python collections-task-checker.py
    python collections-task-checker.py --edition india   # full file only

--edition picks the world (default global). The checker, the funnel arithmetic and
the AMD matrix are the same in both; the field names, flows' data, incidents and the
seed of the 120 synthetic calls come from the edition.
"""
from __future__ import annotations

import argparse
import math
import random
from collections import Counter


def western(n: float) -> str:
    """Western digit grouping: 130000 -> 130,000."""
    return f"{int(round(n)):,}"


# --- GLOBAL constants (WORLD-GLOBAL world-global-v1.1; fictional lender, illustrative) ---
GLOBAL = {
    "lender_note": "Steelyard Credit is a fictional lender; its numbers are illustrative.",
    "dataset": "steelyard-calls (synthetic, seed 20261121)",
    "seed": 20261121,
    "products": {"AUTO": "auto loan", "PIL": "personal installment, digital",
                 "POS": "retail point-of-sale", "SBL": "small business, guarantor",
                 "SDL": "credit-builder and small-dollar"},
    "calling_window_local": {"default": ("08:00", "21:00"), "SDL": ("09:00", "20:00")},
    "campaigns": {  # (book, silence budget ms, amount-asked / date-asked budget ms)
        "AUTO-early-nov": ("AUTO", 400, 600),
        "PIL-digital-nov": ("PIL", 400, 600),
        "POS-short-nov": ("POS", 400, 600),
        "SBL-guar-nov": ("SBL", 450, 650),
        "SDL-biwk-nov": ("SDL", 600, 800),
    },
    "languages": {"English": 0.64, "Spanish-dominant": 0.18, "Spanglish": 0.14, "other": 0.04},
    "customer_advocate": {"name": "Ms Dana Brooks", "email": "advocate@steelyard.example",
                          "phone": "(520) 555-0199",
                          "address": "1200 Example Avenue, Tucson, AZ 85701"},
    "media": {"sample_rate_hz": 8000, "codec": "G.711 mu-law", "frame_ms": 20, "frame_bytes": 160},
    "money_unit": "integer cents",
    "usd_1500_forms": ["fifteen hundred", "one thousand five hundred", "1,500", "1500",
                       "$1,500.00", "mil quinientos", "mil quinientos dolares"],  # 8th: "1.500" es-ES, R1
    "usd_1500_cents": 150000,
    # R6 task-checker data: CRM field names (WG5, WG6), flows (WG9), AMD (WG4, WG15), incidents (WG16)
    "fields": {"amount": "amount_cents", "payment_ref": "confirmation_no"},
    "sms_tool": "send_disclosure_sms", "sms_template": "disclosure_details",
    "ptp_channel": "ach", "tz": "-07:00", "world_ref": "WG1",
    "fmt_count": western,
    "voicemail_sms": False,          # WG9: the F07 voicemail is a limited-content message, no SMS
    "attempt_flags": True,           # call_attempts.counts_toward_cap and .conversation (WG6)
    "flow_product": {"F06": "SBL", "F02": "POS", "F09": "PIL", "F03": "PIL"}, "default_product": "AUTO",
    "ptp_amounts": [25000, 35000, 45000, 55000, 65000],   # $250-$650 in cents
    "misheard_short": 3500,          # "fifty" heard as "fifteen": $35.00 short (T01)
    "paid_amount": 13000, "pushed_amount": 42500, "hardship_amount": 10000,
    "dnc_phone": "+152055501{:02d}", "dnc_mod": 100,   # reserved 555-01xx numbers
    "faults": {"F07": ["sms_on_voicemail"]},
    "amd_classes": ["human", "voicemail", "call_screening", "carrier_intercept", "ivr", "silence"],
    "amd_short": {"human": "human", "voicemail": "vmail", "call_screening": "screen",
                  "carrier_intercept": "intcpt", "ivr": "ivr", "silence": "silence"},
    "t07_class": "call_screening", "f08_machines": ["call_screening", "carrier_intercept", "ivr"],
    "not_counted": ["carrier_intercept"],   # out of service: not a placed call for the 7-in-7 cap
    "incidents": {
        "T01": {"account": "A-55120931", "contact": "K-10931", "product": "AUTO",
                "attempt_id": "SY-2026-11-14-0871234", "verified_at": "2026-11-14T18:41:40-07:00",
                "stored": 21500, "confirmed": 25000, "date": "2026-11-20"},  # "two fifty" heard as "two fifteen"
        "T02": {"account": "A-55188402", "contact": "K-18402", "product": "POS",
                "payment_ref": "431187650092", "paid": 13000, "paid_on": "2026-11-03",
                "verified_at": "2026-11-16T11:20:05-07:00"},                 # paid by debit card in the app
        "T07": {"account": "A-55170712", "contact": "K-17712", "product": "AUTO",
                "true_amd": "call_screening", "conversation": True},      # logged as a conversation
    },
}
GLOBAL["gold_openings"] = dict(zip(GLOBAL["amd_classes"], [80, 40, 25, 20, 20, 15]))
# Mock classifier: P(predicted | true) for two settings. A is tuned on voicemail
# greetings (the T07 setting); B needs more evidence before it says human. Synthetic.
GLOBAL["amd_settings"] = {
    "A (current)": {
        "human":             [0.95, 0.02, 0.01, 0.00, 0.01, 0.01],
        "voicemail":         [0.07, 0.87, 0.02, 0.00, 0.02, 0.02],
        "call_screening":    [0.36, 0.08, 0.50, 0.00, 0.06, 0.00],
        "carrier_intercept": [0.18, 0.04, 0.00, 0.70, 0.00, 0.08],
        "ivr":               [0.12, 0.02, 0.06, 0.00, 0.80, 0.00],
        "silence":           [0.08, 0.04, 0.00, 0.00, 0.00, 0.88],
    },
    "B (stricter human)": {
        "human":             [0.90, 0.04, 0.02, 0.00, 0.02, 0.02],
        "voicemail":         [0.03, 0.91, 0.02, 0.00, 0.02, 0.02],
        "call_screening":    [0.10, 0.08, 0.74, 0.00, 0.08, 0.00],
        "carrier_intercept": [0.06, 0.04, 0.00, 0.82, 0.00, 0.08],
        "ivr":               [0.05, 0.02, 0.06, 0.00, 0.87, 0.00],
        "silence":           [0.04, 0.04, 0.00, 0.00, 0.00, 0.92],
    },
}
# Frozen results of the 120 seeded calls for this edition: (caught, task success, PTP rows, verified PTP)
GLOBAL["frozen"] = {"t01": ["ptps.amount_cents expected 25000 got 21500",
                            "ptps.readback_confirmed expected true got false"],
                    "t07": "call_attempts.amd_label expected call_screening got human",
                    "sample": (21, 99, 18, 11)}
# --- end GLOBAL constants ---
EDITIONS = {"global": GLOBAL}

# --- India edition constants (WORLD world-v1.1; fictional lender, illustrative) ---


def inr(n: float) -> str:
    """Indian digit grouping: 130000 -> 1,30,000."""
    s = str(int(round(n)))
    if len(s) <= 3:
        return s
    head, tail = s[:-3], s[-3:]
    parts = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    return ",".join([head] + parts + [tail]) if head else ",".join(parts + [tail])


TARAZU = {
    "lender_note": "Tarazu Finance is a fictional lender; its numbers are illustrative.",
    "dataset": "tarazu-calls (synthetic, seed 20261120)",
    "seed": 20261120,
    "products": {"TW": "two-wheeler", "PL": "personal, digital", "CD": "consumer durable",
                 "SBL": "small business", "MFI": "microfinance"},
    "calling_window_local": {"default": ("08:00", "19:00"), "MFI": ("09:00", "18:00")},
    "campaigns": {  # (book, silence budget ms, amount-asked / date-asked budget ms)
        "TW-early-nov": ("TW", 400, 600),
        "PL-digital-nov": ("PL", 400, 600),
        "CD-short-nov": ("CD", 400, 600),
        "SBL-guar-nov": ("SBL", 450, 650),
        "MFI-fort-nov": ("MFI", 600, 800),
    },
    "languages": {"Hinglish": 0.58, "Hindi": 0.21, "Indian English": 0.09,
                  "Marathi": 0.07, "Kannada": 0.05},
    "grievance_officer": {"name": "Ms Neha Kulkarni", "email": "grievance@tarazu.example",
                          "phone": "020-4000-0000",
                          "address": "Tarazu House, Baner Road, Pune 411045"},
    "media": {"sample_rate_hz": 8000, "codec": "G.711 mu-law", "frame_ms": 20, "frame_bytes": 160},
    "money_unit": "integer paise",
    "rs_1_50_000_forms": ["dedh lakh", "1.5 lakh", "1,50,000", "150000", "150,000",
                          "ek lakh pachaas hazaar", "one lakh fifty thousand"],  # 8th: Devanagari, R1
    "rs_1_50_000_paise": 15000000,
    # R6 task-checker data: CRM field names (W5, W6), flows (W9), AMD (W4, W15), incidents (W16)
    "fields": {"amount": "amount_paise", "payment_ref": "utr"},
    "sms_tool": "send_grievance_sms", "sms_template": "grievance_details",
    "ptp_channel": "upi", "tz": "+05:30", "world_ref": "WORLD W1",
    "fmt_count": inr,
    "voicemail_sms": True,           # W9: the F07 voicemail carries the grievance details and an SMS
    "attempt_flags": False,
    "flow_product": {"F06": "SBL", "F02": "CD", "F09": "PL", "F03": "PL"}, "default_product": "TW",
    "ptp_amounts": [245000, 310000, 425000, 520000, 680000],   # Rs 2,450-6,800 in paise
    "misheard_short": 50000,         # "dhai hazaar" heard as "do hazaar": Rs 500 short (T01)
    "paid_amount": 130000, "pushed_amount": 420000, "hardship_amount": 100000,
    "dnc_phone": "+9198{:08d}", "dnc_mod": 10**8,
    "faults": {"F07": ["no_sms"]},
    "amd_classes": ["human", "voicemail", "operator_announcement", "caller_tune", "ivr", "silence"],
    "amd_short": {"human": "human", "voicemail": "vmail", "operator_announcement": "oper",
                  "caller_tune": "tune", "ivr": "ivr", "silence": "silence"},
    "t07_class": "operator_announcement", "f08_machines": ["operator_announcement", "ivr"],
    "not_counted": [],
    "incidents": {
        "T01": {"account": "A-55120931", "contact": "K-10931", "product": "TW",
                "attempt_id": "TZ-2026-11-14-0871234", "verified_at": "2026-11-14T18:41:40+05:30",
                "stored": 200000, "confirmed": 250000, "date": "2026-11-20"},  # dhai heard as do
        "T02": {"account": "A-55188402", "contact": "K-18402", "product": "CD",
                "payment_ref": "431187650092", "paid": 130000, "paid_on": "2026-11-03",
                "verified_at": "2026-11-16T11:20:05+05:30"},                   # paid by PhonePe
        "T07": {"account": "A-55170712", "contact": "K-17712", "product": "TW",
                "true_amd": "operator_announcement", "conversation": None},
    },
}
TARAZU["gold_openings"] = dict(zip(TARAZU["amd_classes"], [80, 40, 25, 20, 20, 15]))
# A is tuned on US-style voicemail greetings (the T07 setting); B needs more evidence. Synthetic.
TARAZU["amd_settings"] = {
    "A (current)": {
        "human":                 [0.95, 0.02, 0.01, 0.00, 0.01, 0.01],
        "voicemail":             [0.07, 0.87, 0.02, 0.00, 0.02, 0.02],
        "operator_announcement": [0.36, 0.08, 0.50, 0.00, 0.06, 0.00],
        "caller_tune":           [0.18, 0.04, 0.00, 0.70, 0.00, 0.08],
        "ivr":                   [0.12, 0.02, 0.06, 0.00, 0.80, 0.00],
        "silence":               [0.08, 0.04, 0.00, 0.00, 0.00, 0.88],
    },
    "B (stricter human)": {
        "human":                 [0.90, 0.04, 0.02, 0.00, 0.02, 0.02],
        "voicemail":             [0.03, 0.91, 0.02, 0.00, 0.02, 0.02],
        "operator_announcement": [0.10, 0.08, 0.74, 0.00, 0.08, 0.00],
        "caller_tune":           [0.06, 0.04, 0.00, 0.82, 0.00, 0.08],
        "ivr":                   [0.05, 0.02, 0.06, 0.00, 0.87, 0.00],
        "silence":               [0.04, 0.04, 0.00, 0.00, 0.00, 0.92],
    },
}
TARAZU["frozen"] = {"t01": ["ptps.amount_paise expected 250000 got 200000",
                            "ptps.readback_confirmed expected true got false"],
                    "t07": "call_attempts.amd_label expected operator_announcement got human",
                    "sample": (20, 100, 15, 11)}
EDITIONS["india"] = TARAZU
# --- end India edition constants ---

WORLD: dict = GLOBAL      # set from --edition in main()

# Shared by both editions (WG1 = W1 volumes; the gold-v7 openings draw is shared too,
# so the AMD matrix and every line computed from it are identical across editions) [W]
FUNNEL = {"dials_per_day": 250000, "connect_rate": 0.52, "human_share": 0.88,
          "rpc_share": 0.70, "ptp_per_rpc": 0.38, "kept_per_ptp": 0.62}
T07_TRUNK_S = 21          # trunk seconds T07 spent talking to a machine
AMD_SEED = 20261126       # one draw per labelled opening, the same in both editions
FAULTS = {"F01": ["amount_misheard", "write_lost", "no_link"], "F02": ["skipped_status_check"],
          "F03": ["pushed_past_dispute"], "F04": ["ptp_after_hardship"], "F05": ["third_party_as_rpc"],
          "F06": ["dues_before_verify"], "F08": ["amd_false_human"],
          "F09": ["callback_outside_window"], "F10": ["no_sms"]}   # F07 comes from the edition

PK = {"accounts": "account_id", "contacts": "contact_id", "payments": "payment_id",
      "call_attempts": "attempt_id", "ptps": "ptp_id", "callbacks": "callback_id",
      "grievances": "grievance_id", "hardship": "hardship_id", "sms_log": "sms_id",
      "dnc": "phone_e164"}
ANY = object()            # gold value meaning "any non-null value"


def fmt(v) -> str:
    if v is True:
        return "true"
    if v is False:
        return "false"
    if v is None:
        return "null"
    return str(v)


# ---------- the CRM diff ----------

def diff(before: dict, after: dict) -> dict:
    """Rows added, rows removed and fields changed, per table, keyed by primary key."""
    out = {"added": {}, "removed": {}, "changed": {}}
    for table, pk in PK.items():
        b = {r[pk]: r for r in before.get(table, [])}
        a = {r[pk]: r for r in after.get(table, [])}
        added = [a[k] for k in sorted(a) if k not in b]
        removed = [b[k] for k in sorted(b) if k not in a]
        if added:
            out["added"][table] = added
        if removed:
            out["removed"][table] = removed
        for k in sorted(set(a) & set(b)):
            for field in sorted(set(a[k]) | set(b[k])):
                if a[k].get(field) != b[k].get(field):
                    out["changed"][(table, k, field)] = (b[k].get(field), a[k].get(field))
    return out


# ---------- gold end states per flow (WG9) ----------

def gold_attempt(amd: str, rpc: bool, disp: str) -> dict:
    """The call_attempts row a flow must write. Where the edition records them, every
    placed call counts toward the 7-in-7 cap except an out-of-service intercept, and
    only a right-party call is a conversation (which starts a 7-day no-call period)."""
    row = {"amd_label": amd, "rpc": rpc, "disposition": disp}
    if WORLD["attempt_flags"]:
        row["counts_toward_cap"] = amd not in WORLD["not_counted"]
        row["conversation"] = rpc
    return row


def gold_spec(flow: str, before: dict, ctx: dict) -> dict:
    """Flow spec, plus: any flow that verifies identity must stamp contacts.verified_at."""
    spec = flow_spec(flow, before, ctx)
    if "verify_identity" in spec["tools"]:
        spec["set"][("contacts", ctx["contact_id"], "verified_at")] = ANY
    return spec


def flow_spec(flow: str, before: dict, ctx: dict) -> dict:
    """Required adds, required field changes, optional tables and required tool order.

    The gold state is a function of the CRM before the call: F02's branch depends on
    whether the payment the borrower claims is already in `payments`.
    """
    acc, amt, sms_tool = ctx["account_id"], WORLD["fields"]["amount"], WORLD["sms_tool"]
    note = {"template": WORLD["sms_template"]}
    attempt = gold_attempt
    if flow == "F01":
        return {"add": {"call_attempts": [attempt("human", True, "ptp")],
                        "ptps": [{amt: ctx["confirmed_amount"],
                                  "ptp_date": ctx["confirmed_date"], "readback_confirmed": True}],
                        "sms_log": [{"template": "payment_link"}, note]},
                "set": {}, "optional": set(),
                "tools": ["lookup_account", "verify_identity", "get_dues", "record_promise_to_pay",
                          "send_payment_link", sms_tool, "end_call"]}
    if flow == "F02":
        found = any(p["paid_on"] >= ctx["since"] for p in before["payments"])
        tools = ["lookup_account", "verify_identity", "get_dues", "check_payment_status"]
        if found:
            return {"add": {"call_attempts": [attempt("human", True, "paid")], "sms_log": [note]},
                    "set": {}, "optional": set(),
                    "tools": tools + [sms_tool, "end_call"]}
        return {"add": {"call_attempts": [attempt("human", True, "dispute")], "sms_log": [note],
                        "grievances": [{"category": "already_paid"}]},
                "set": {("accounts", acc, "recovery_hold"): True}, "optional": set(),
                "tools": tools + ["log_dispute", sms_tool, "end_call"]}
    if flow == "F03":
        return {"add": {"call_attempts": [attempt("human", True, "dispute")], "sms_log": [note],
                        "grievances": [{"category": "amount_wrong"}]},
                "set": {("accounts", acc, "recovery_hold"): True}, "optional": set(),
                "tools": ["lookup_account", "verify_identity", "get_dues", "log_dispute",
                          sms_tool, "end_call"]}
    if flow == "F04":
        return {"add": {"call_attempts": [attempt("human", True, "hardship")], "sms_log": [note],
                        "hardship": [{"reason": "job_loss"}]},
                "set": {("accounts", acc, "hardship_flag"): True}, "optional": set(),
                "tools": ["lookup_account", "verify_identity", "flag_hardship",
                          sms_tool, "transfer_to_human"]}
    if flow == "F05":
        return {"add": {"call_attempts": [attempt("human", False, "third_party")]},
                "set": {}, "optional": {"callbacks"},
                "tools": ["lookup_account", "mark_contact"]}
    if flow == "F06":
        return {"add": {"call_attempts": [attempt("human", True, "guarantor")], "sms_log": [note]},
                "set": {}, "optional": {"callbacks"},
                "tools": ["lookup_account", "verify_identity", "get_dues", sms_tool]}
    if flow == "F07":
        if not WORLD["voicemail_sms"]:   # limited-content message: no SMS, no disclosure
            return {"add": {"call_attempts": [attempt("voicemail", False, "voicemail")]},
                    "set": {}, "optional": set(), "tools": ["mark_contact"]}
        return {"add": {"call_attempts": [attempt("voicemail", False, "voicemail")], "sms_log": [note]},
                "set": {}, "optional": set(), "tools": [sms_tool, "mark_contact"]}
    if flow == "F08":
        return {"add": {"call_attempts": [attempt(ctx["true_amd"], False, "ivr")]},
                "set": {}, "optional": set(), "tools": ["mark_contact"]}
    if flow == "F09":
        spec = {"add": {"call_attempts": [attempt("human", True, "callback")],
                        "callbacks": [{"requested_by": "borrower", "within_window": True}]},
                "set": {}, "optional": set(), "tools": ["lookup_account", "schedule_callback"]}
        if ctx["verified"]:
            spec["add"]["sms_log"] = [note]
            spec["tools"] = ["lookup_account", "verify_identity", "schedule_callback", sms_tool]
        return spec
    if flow == "F10":
        return {"add": {"call_attempts": [attempt("human", True, "complaint")], "sms_log": [note]},
                "set": {}, "optional": {"dnc"},
                "tools": ["lookup_account", "verify_identity", sms_tool]}
    raise ValueError(flow)


# ---------- the checker ----------

def check_tools(required: list[str], log: list[dict]) -> list[str]:
    """Required tools must appear in this order (other calls may sit between them)."""
    names = [t["name"] for t in log]
    lines, pos, prev = [], 0, "call start"
    for name in required:
        try:
            pos = names.index(name, pos) + 1
            prev = name
        except ValueError:
            lines.append(f"missing tool {name} (required after {prev})")
    return lines


def check_call(call: dict) -> list[str]:
    """Return failure lines; an empty list is a task success."""
    spec = gold_spec(call["flow"], call["before"], call["ctx"])
    d = diff(call["before"], call["after"])
    lines = []
    for table, want_rows in spec["add"].items():
        got_rows = d["added"].get(table, [])
        if len(got_rows) != len(want_rows):
            lines.append(f"{table} rows added expected {len(want_rows)} got {len(got_rows)}")
        for want, got in zip(want_rows, got_rows):
            for field, v in want.items():
                if got.get(field) != v:
                    lines.append(f"{table}.{field} expected {fmt(v)} got {fmt(got.get(field))}")
    for table, rows in d["added"].items():
        if table not in spec["add"] and table not in spec["optional"]:
            lines.append(f"{table} rows added expected 0 got {len(rows)}")
    for table, rows in d["removed"].items():
        lines.append(f"{table} rows removed expected 0 got {len(rows)}")
    for (table, pk, field), want in spec["set"].items():
        old, new = d["changed"].get((table, pk, field), (None, None))
        if want is ANY:
            if new is None:
                lines.append(f"{table}.{field} expected set got null")
        elif new != want:
            lines.append(f"{table}.{field} expected {fmt(want)} got {fmt(new if (table, pk, field) in d['changed'] else old)}")
    for key, (old, new) in d["changed"].items():
        if key not in spec["set"]:
            lines.append(f"{key[0]}.{key[2]} expected unchanged got {fmt(new)}")
    return lines + check_tools(spec["tools"], call["tools"])


# ---------- synthetic calls with CRM snapshots ----------

def base_crm(acc: str, con: str, product: str, role: str = "borrower") -> dict:
    return {
        "accounts": [{"account_id": acc, "product_code": product, "recovery_hold": False,
                      "hardship_flag": False, "dnc_bot": False}],
        "contacts": [{"contact_id": con, "account_id": acc, "role": role, "verified_at": None}],
        "payments": [], "call_attempts": [], "ptps": [], "callbacks": [], "grievances": [],
        "hardship": [], "sms_log": [], "dnc": [],
    }


def copy_crm(crm: dict) -> dict:
    return {t: [dict(r) for r in rows] for t, rows in crm.items()}


def attempt_row(att: str, acc: str, amd: str, rpc: bool, disp: str,
                conversation: bool | None = None) -> dict:
    """What the dialer logged. `conversation` defaults to the RPC flag; T07 overrides it."""
    row = {"attempt_id": att, "account_id": acc, "amd_label": amd, "rpc": rpc, "disposition": disp}
    if WORLD["attempt_flags"]:
        row["counts_toward_cap"] = amd not in WORLD["not_counted"]
        row["conversation"] = rpc if conversation is None else conversation
    return row


class Ids:
    def __init__(self):
        self.n = 0

    def next(self, prefix: str) -> str:
        self.n += 1
        return f"{prefix}-{self.n:05d}"


def simulate(flow: str, i: int, rng: random.Random, ids: Ids, fault: str | None) -> dict:
    """What the agent did: a tool log and the CRM after the call (written independently of gold_spec)."""
    W, amt, ref = WORLD, WORLD["fields"]["amount"], WORLD["fields"]["payment_ref"]
    sms_tool, note = W["sms_tool"], W["sms_template"]
    acc, con, att = f"A-{55120000 + i}", f"K-{20000 + i}", f"AT-{i:05d}"
    product = W["flow_product"].get(flow, W["default_product"])
    before = base_crm(acc, con, product, "guarantor" if flow == "F06" else "borrower")
    ctx = {"account_id": acc, "contact_id": con, "since": "2026-11-01", "verified": True}
    if flow == "F02":
        if rng.random() < 0.7:  # P02 paid on 3 Nov; sometimes the payment is not posted yet
            before["payments"].append({"payment_id": ids.next("PM"), "account_id": acc,
                                       ref: str(rng.randrange(10**11, 10**12)),
                                       amt: W["paid_amount"], "paid_on": "2026-11-03"})
    after = copy_crm(before)
    tools: list[dict] = []
    T = lambda name, **kw: tools.append({"name": name, "result": "ok", **kw})

    def attempt(amd, rpc, disp, conversation=None):
        after["call_attempts"].append(attempt_row(att, acc, amd, rpc, disp, conversation))

    def sms(template):
        after["sms_log"].append({"sms_id": ids.next("SMS"), "account_id": acc, "template": template})

    def ptp(amount, date, readback):
        after["ptps"].append({"ptp_id": ids.next("PTP"), "account_id": acc, "attempt_id": att,
                              amt: amount, "ptp_date": date,
                              "channel": W["ptp_channel"], "readback_confirmed": readback})

    def verify():
        T("verify_identity")
        for c in after["contacts"]:
            c["verified_at"] = "2026-11-14T10:05:00" + W["tz"]

    if flow in ("F01", "F02", "F03", "F04", "F06", "F09", "F10"):
        T("lookup_account")
    if flow == "F01":
        amount = rng.choice(W["ptp_amounts"])
        ctx["confirmed_amount"] = amount
        ctx["confirmed_date"] = f"2026-11-{rng.randint(16, 28)}"
        verify(); T("get_dues")
        stored, readback = amount, True
        if fault == "amount_misheard":
            stored, readback = amount - W["misheard_short"], False
        T("record_promise_to_pay", **{amt: stored})
        if fault != "write_lost":  # the tool returned ok; the row never reached the CRM
            ptp(stored, ctx["confirmed_date"], readback)
        if fault != "no_link":
            T("send_payment_link"); sms("payment_link")
        T(sms_tool); sms(note); T("end_call")
        attempt("human", True, "ptp")
    elif flow == "F02":
        verify(); T("get_dues")
        if fault == "skipped_status_check":
            attempt("human", True, "no_ptp"); T("end_call")
        else:
            T("check_payment_status")
            if before["payments"]:
                attempt("human", True, "paid")
            else:
                T("log_dispute")
                after["grievances"].append({"grievance_id": ids.next("G"), "account_id": acc,
                                            "category": "already_paid", "status": "open"})
                after["accounts"][0]["recovery_hold"] = True
                attempt("human", True, "dispute")
            T(sms_tool); sms(note); T("end_call")
    elif flow == "F03":
        verify(); T("get_dues")
        if fault == "pushed_past_dispute":
            T("record_promise_to_pay")
            ptp(W["pushed_amount"], "2026-11-25", True)
            attempt("human", True, "ptp")
        else:
            T("log_dispute")
            after["grievances"].append({"grievance_id": ids.next("G"), "account_id": acc,
                                        "category": "amount_wrong", "status": "open"})
            after["accounts"][0]["recovery_hold"] = True
            attempt("human", True, "dispute")
        T(sms_tool); sms(note); T("end_call")
    elif flow == "F04":
        verify(); T("flag_hardship")
        after["hardship"].append({"hardship_id": ids.next("H"), "account_id": acc, "reason": "job_loss"})
        after["accounts"][0]["hardship_flag"] = True
        if fault == "ptp_after_hardship":
            T("record_promise_to_pay")
            ptp(W["hardship_amount"], "2026-11-21", True)
        T(sms_tool); sms(note); T("transfer_to_human")
        attempt("human", True, "hardship")
    elif flow == "F05":
        T("lookup_account"); T("mark_contact")
        attempt("human", fault == "third_party_as_rpc", "third_party")
        if rng.random() < 0.5:
            T("schedule_callback")
            after["callbacks"].append({"callback_id": ids.next("CB"), "account_id": acc,
                                       "requested_by": "agent", "within_window": True})
    elif flow == "F06":
        if fault != "dues_before_verify":
            verify()
        T("get_dues")
        if fault == "dues_before_verify":
            verify()
        T(sms_tool); sms(note)
        attempt("human", True, "guarantor")
    elif flow == "F07":
        sends = W["voicemail_sms"]
        if fault == "no_sms":
            sends = False
        if fault == "sms_on_voicemail":  # an SMS to whoever holds the phone
            sends = True
        if sends:
            T(sms_tool); sms(note)
        T("mark_contact"); attempt("voicemail", False, "voicemail")
    elif flow == "F08":
        ctx["true_amd"] = rng.choice(W["f08_machines"])
        if fault == "amd_false_human":  # a T07-like miss: opener played to a machine
            attempt("human", False, "no_response", conversation=True); T("end_call")
        else:
            T("mark_contact"); attempt(ctx["true_amd"], False, "ivr")
    elif flow == "F09":
        ctx["verified"] = rng.random() < 0.6
        if ctx["verified"]:
            verify()
        T("schedule_callback")
        late = fault == "callback_outside_window"
        after["callbacks"].append({"callback_id": ids.next("CB"), "account_id": acc,
                                   "requested_by": "agent" if late else "borrower",
                                   "within_window": not late})
        if ctx["verified"]:
            T(sms_tool); sms(note)
        attempt("human", True, "callback")
    elif flow == "F10":
        verify()
        if fault != "no_sms":
            T(sms_tool); sms(note)
        if rng.random() < 0.3:
            T("set_do_not_call")
            phone = W["dnc_phone"].format(i % W["dnc_mod"])
            after["dnc"].append({"phone_e164": phone, "account_id": acc, "scope": "bot"})
        attempt("human", True, "complaint")
    return {"id": f"SYN-{i:03d}", "flow": flow, "fault": fault, "ctx": ctx,
            "before": before, "after": after, "tools": tools}


def incident_calls() -> list[dict]:
    """T01, T02 and T07 from the edition's incident log as CRM snapshots and tool logs."""
    W, amt, ref, out = WORLD, WORLD["fields"]["amount"], WORLD["fields"]["payment_ref"], []
    # T01: amount misheard; PTP written before read-back
    t = W["incidents"]["T01"]
    before = base_crm(t["account"], t["contact"], t["product"])
    after = copy_crm(before)
    after["contacts"][0]["verified_at"] = t["verified_at"]
    after["call_attempts"].append(attempt_row(t["attempt_id"], t["account"], "human", True, "ptp"))
    after["ptps"].append({"ptp_id": "PTP-T01", "account_id": t["account"],
                          "attempt_id": t["attempt_id"], amt: t["stored"],
                          "ptp_date": t["date"], "channel": W["ptp_channel"], "readback_confirmed": False})
    after["sms_log"] += [{"sms_id": "SMS-T01a", "account_id": t["account"], "template": "payment_link"},
                         {"sms_id": "SMS-T01b", "account_id": t["account"], "template": W["sms_template"]}]
    tools = [{"name": n, "result": "ok"} for n in
             ["lookup_account", "verify_identity", "get_dues", "record_promise_to_pay",
              "send_payment_link", W["sms_tool"], "end_call"]]
    out.append({"id": "T01", "flow": "F01", "fault": "amount_misheard", "before": before, "after": after,
                "tools": tools, "ctx": {"account_id": t["account"], "contact_id": t["contact"],
                                        "confirmed_amount": t["confirmed"], "confirmed_date": t["date"]}})
    # T02: barge-in ignored; no check_payment_status, no log_dispute, a PTP request instead
    t = W["incidents"]["T02"]
    before = base_crm(t["account"], t["contact"], t["product"])
    before["payments"].append({"payment_id": "PM-T02", "account_id": t["account"], ref: t["payment_ref"],
                               amt: t["paid"], "paid_on": t["paid_on"]})
    after = copy_crm(before)
    after["contacts"][0]["verified_at"] = t["verified_at"]
    after["call_attempts"].append(attempt_row("AT-T02", t["account"], "human", True, "no_ptp"))
    tools = [{"name": n, "result": "ok"} for n in ["lookup_account", "verify_identity", "get_dues", "end_call"]]
    out.append({"id": "T02", "flow": "F02", "fault": "skipped_status_check", "before": before,
                "after": after, "tools": tools,
                "ctx": {"account_id": t["account"], "contact_id": t["contact"], "since": "2026-11-01"}})
    # T07: a machine labelled human; opener played; no mark_contact
    t = W["incidents"]["T07"]
    before = base_crm(t["account"], t["contact"], t["product"])
    after = copy_crm(before)
    after["call_attempts"].append(attempt_row("AT-T07", t["account"], "human", False, "no_response",
                                              t["conversation"]))
    out.append({"id": "T07", "flow": "F08", "fault": "amd_false_human", "before": before, "after": after,
                "tools": [{"name": "end_call", "result": "ok"}],
                "ctx": {"account_id": t["account"], "contact_id": t["contact"],
                        "true_amd": t["true_amd"]}})
    return out


def build_calls(seed: int, n_total: int = 120, fault_rate: float = 0.15) -> list[dict]:
    rng, ids = random.Random(seed), Ids()
    faults = {**FAULTS, **WORLD["faults"]}
    calls = incident_calls()
    flows = [f"F{k:02d}" for k in range(1, 11)]
    i = 0
    while len(calls) < n_total:
        flow = flows[i % 10]
        fault = rng.choice(faults[flow]) if rng.random() < fault_rate else None
        calls.append(simulate(flow, i, rng, ids, fault))
        i += 1
    return calls


# ---------- funnel metrics with denominators ----------

def verified_ptp(call: dict) -> bool:
    """Stored amount and date equal what the borrower confirmed, after an explicit yes."""
    ctx, amt = call["ctx"], WORLD["fields"]["amount"]
    rows = diff(call["before"], call["after"])["added"].get("ptps", [])
    return any(r["readback_confirmed"] and r[amt] == ctx.get("confirmed_amount")
               and r["ptp_date"] == ctx.get("confirmed_date") for r in rows)


def sample_funnel(calls: list[dict]) -> dict:
    attempts = [r for c in calls for r in diff(c["before"], c["after"])["added"].get("call_attempts", [])]
    ptp_calls = [c for c in calls if diff(c["before"], c["after"])["added"].get("ptps")]
    return {"calls": len(calls), "amd_human": sum(a["amd_label"] == "human" for a in attempts),
            "rpc": sum(a["rpc"] for a in attempts), "ptp": len(ptp_calls),
            "verified_ptp": sum(verified_ptp(c) for c in ptp_calls),
            "task_success": sum(not check_call(c) for c in calls)}


def daily_funnel(f: dict = FUNNEL) -> list[tuple[str, float, str]]:
    connects = f["dials_per_day"] * f["connect_rate"]
    human = connects * f["human_share"]
    rpc = human * f["rpc_share"]
    ptp = rpc * f["ptp_per_rpc"]
    kept = ptp * f["kept_per_ptp"]
    return [("dials", f["dials_per_day"], "-"), ("connects", connects, "52% of dials"),
            ("human answers", human, "88% of connects"), ("RPC", rpc, "70% of human answers"),
            ("PTP", ptp, "38% of RPC"), ("kept PTP", kept, "62% of PTP")]


# ---------- six-class AMD confusion matrix ----------

def classify(probs: list[float], u: float) -> str:
    acc = 0.0
    classes = WORLD["amd_classes"]
    for cls, p in zip(classes, probs):
        acc += p
        if u < acc:
            return cls
    return classes[-1]


def amd_matrices() -> dict[str, dict[str, Counter]]:
    """One uniform draw per opening, shared by both settings, so the comparison is paired."""
    classes, gold = WORLD["amd_classes"], WORLD["gold_openings"]
    rng = random.Random(AMD_SEED)
    openings = [cls for cls in classes for _ in range(gold[cls])]
    draws = [rng.random() for _ in openings]
    out = {}
    for name, table in WORLD["amd_settings"].items():
        m = {cls: Counter() for cls in classes}
        for true, u in zip(openings, draws):
            m[true][classify(table[true], u)] += 1
        out[name] = m
    return out


def wilson(k: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    p = k / n
    den = 1 + z * z / n
    mid = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return mid - half, mid + half


def amd_costs(m: dict[str, Counter]) -> dict:
    """Errors in their own units. A false machine on a human loses an RPC 70% of the time (WG1);
    a false human on a machine wastes T07's 21 s of trunk time and plays the opener to a machine."""
    classes = WORLD["amd_classes"]
    false_machine = sum(m["human"][c] for c in classes if c != "human")
    false_human = sum(m[c]["human"] for c in classes if c != "human")
    machine_swap = sum(m[t][p] for t in classes[1:] for p in classes[1:] if t != p)
    return {"false_machine": false_machine, "false_human": false_human, "machine_swap": machine_swap,
            "lost_rpc": false_machine * FUNNEL["rpc_share"], "trunk_s": false_human * T07_TRUNK_S}


def amd_daily(m: dict[str, Counter]) -> dict:
    """Project one setting onto a day: true mix of connects from WG1, machine mix from the gold set."""
    classes, gold = WORLD["amd_classes"], WORLD["gold_openings"]
    connects = FUNNEL["dials_per_day"] * FUNNEL["connect_rate"]
    humans = connects * FUNNEL["human_share"]
    n_mach = sum(gold[c] for c in classes[1:])
    true_mix = {"human": humans}
    for c in classes[1:]:
        true_mix[c] = (connects - humans) * gold[c] / n_mach
    rate = lambda t, p: m[t][p] / gold[t]
    engaged_h = humans * rate("human", "human")
    engaged_m = sum(true_mix[c] * rate(c, "human") for c in classes[1:])
    rpc = engaged_h * FUNNEL["rpc_share"]
    ptp = rpc * FUNNEL["ptp_per_rpc"]
    return {"agent_connects": engaged_h + engaged_m, "machines_engaged": engaged_m, "rpc": rpc,
            "ptp": ptp, "ptp_per_connect": ptp / (engaged_h + engaged_m), "ptp_per_rpc": ptp / rpc,
            "trunk_hours": engaged_m * T07_TRUNK_S / 3600}


def main() -> None:
    global WORLD
    ap = argparse.ArgumentParser()
    ap.add_argument("--edition", choices=sorted(EDITIONS), default="global",
                    help="which world's field names, incidents and seed to use (default global)")
    args = ap.parse_args()
    WORLD = EDITIONS[args.edition]
    seed, group, frozen = WORLD["seed"], WORLD["fmt_count"], WORLD["frozen"]
    classes, short = WORLD["amd_classes"], WORLD["amd_short"]
    print(WORLD["lender_note"])
    print(f"Edition: {args.edition}. Dataset: {WORLD['dataset']}")

    # [1] incidents against their gold end states
    print("\n[1] Incident calls against their gold end states")
    incidents = {c["id"]: c for c in incident_calls()}
    for cid in ("T01", "T02", "T07"):
        lines = check_call(incidents[cid])
        print(f"  {cid} {incidents[cid]['flow']}: {'PASS' if not lines else 'FAIL'}")
        for line in lines:
            print(f"    {line}")
    t01, t02, t07 = (check_call(incidents[k]) for k in ("T01", "T02", "T07"))
    assert t01 == frozen["t01"] and "ptps.ptp_date" not in " ".join(t01)
    assert any(l.startswith("missing tool check_payment_status") for l in t02)
    assert frozen["t07"] in t07
    if WORLD["attempt_flags"]:  # T07 was logged as a conversation: a week of contact lost
        assert "call_attempts.conversation expected false got true" in t07

    # [2] 120 calls
    calls = build_calls(seed)
    assert len(calls) == 120
    print(f"\n[2] Task success on {len(calls)} synthetic calls (3 incidents + 117 seeded, 15% fault rate)")
    print("  flow  calls  pass  fail  first failure line of failed calls (top 2)")
    by_flow: dict[str, list] = {}
    for c in calls:
        by_flow.setdefault(c["flow"], []).append(c)
    caught = missed = false_alarm = 0
    for flow in sorted(by_flow):
        cs = by_flow[flow]
        fails = [(c, check_call(c)) for c in cs]
        n_fail = sum(bool(l) for _, l in fails)
        reasons = Counter(l[0] for _, l in fails if l)
        top = "; ".join(f"{r} (x{k})" if k > 1 else r for r, k in reasons.most_common(2)) or "-"
        print(f"  {flow}  {len(cs):5d}  {len(cs) - n_fail:4d}  {n_fail:4d}  {top}")
        for c, l in fails:
            caught += bool(c["fault"]) and bool(l)
            missed += bool(c["fault"]) and not l
            false_alarm += (not c["fault"]) and bool(l)
    print(f"  injected faults caught {caught}, missed {missed}; clean calls flagged {false_alarm}")
    assert missed == 0 and false_alarm == 0

    lost = [c for c in calls if c["fault"] == "write_lost"]
    if lost:
        c = lost[0]
        ok = [t for t in c["tools"] if t["name"] == "record_promise_to_pay"][0]["result"]
        print(f"  {c['id']}: record_promise_to_pay returned {ok!r}; checker says {check_call(c)[0]}")
    assert lost, "seed should produce a write_lost call"

    # [3] funnel
    s = sample_funnel(calls)
    print(f"\n[3] Funnel on the {s['calls']} calls (each denominator named)")
    print(f"  AMD said human               {s['amd_human']:4d}")
    print(f"  right-party contacts (RPC)   {s['rpc']:4d}")
    print(f"  PTP rows written             {s['ptp']:4d}   PTP per RPC {s['ptp'] / s['rpc']:.3f}")
    print(f"  verified PTP                 {s['verified_ptp']:4d}   verified PTP per RPC "
          f"{s['verified_ptp'] / s['rpc']:.3f}; per PTP {s['verified_ptp'] / s['ptp']:.3f}")
    print(f"  task success                 {s['task_success']:4d}   per call {s['task_success'] / s['calls']:.3f}")
    print("  kept PTP: not known at call time; checked at ptp_date plus grace (ptps.kept)")
    assert s["verified_ptp"] < s["ptp"]
    assert (caught, s["task_success"], s["ptp"], s["verified_ptp"]) == frozen["sample"]

    print(f"\n  Daily funnel from {WORLD['world_ref']} (26 calling days a month)")
    rows = daily_funnel()
    for name, n, den in rows:
        print(f"  {name:15s} {group(n):>9s}   {den}")
    vals = {name: n for name, n, _ in rows}
    assert vals["connects"] == 130000 and round(vals["human answers"]) == 114400
    assert round(vals["RPC"]) == 80080 and round(vals["PTP"]) == 30430 and round(vals["kept PTP"]) == 18867
    print(f"  PTP per connect {vals['PTP'] / vals['connects']:.4f}; PTP per RPC "
          f"{vals['PTP'] / vals['RPC']:.2f}; kept PTP per dial {vals['kept PTP'] / vals['dials']:.4f}")
    assert abs(vals["PTP"] / vals["connects"] - 0.234080) < 1e-9
    assert abs(vals["kept PTP"] / vals["dials"] - 0.075467392) < 1e-9

    # [4] AMD matrix (identical counts in both editions; only the class names differ)
    mats = amd_matrices()
    for name, m in mats.items():
        print(f"\n[4] AMD setting {name}: 200 labelled openings, rows = true, columns = predicted")
        print("  " + " " * 22 + "".join(f"{short[c]:>8s}" for c in classes) + "   recall [Wilson 95%]")
        recalls = {}
        for t in classes:
            n = WORLD["gold_openings"][t]
            k = m[t][t]
            lo, hi = wilson(k, n)
            recalls[t] = k / n
            print(f"  {t:22s}" + "".join(f"{m[t][p]:8d}" for p in classes)
                  + f"   {k / n:.2f} [{lo:.2f}, {hi:.2f}]")
        cost = amd_costs(m)
        print(f"  false machine on a human: {cost['false_machine']} -> {cost['lost_rpc']:.1f} expected lost RPCs")
        print(f"  false human on a machine: {cost['false_human']} -> {cost['trunk_s']} s of trunk time, "
              f"{cost['false_human']} openers played to a machine")
        print(f"  machine taken for another machine class: {cost['machine_swap']}")
        if name.startswith("A"):
            low = min(recalls, key=recalls.get)
            print(f"  lowest recall: {low}")
            assert low == WORLD["t07_class"]
            assert sum(m[t][t] for t in classes) < 200
            assert [m[c]["human"] for c in classes] == [77, 6, 8, 1, 3, 2]   # frozen [C]
            assert (cost["false_machine"], cost["false_human"], cost["machine_swap"]) == (3, 20, 14)

    # [5] AMD settings and the conversation metric
    print("\n[5] Daily projection: same agent, two AMD settings (machine mix taken from the gold set)")
    print("  setting               agent connects  machines engaged   RPC     PTP   PTP/connect  PTP/RPC  trunk h")
    proj = {}
    for name, m in mats.items():
        d = amd_daily(m)
        proj[name] = d
        print(f"  {name:20s} {group(d['agent_connects']):>15s} {group(d['machines_engaged']):>17s} "
              f"{group(d['rpc']):>7s} {group(d['ptp']):>7s} {d['ptp_per_connect']:12.4f} "
              f"{d['ptp_per_rpc']:8.2f} {d['trunk_hours']:8.1f}")
    a, b = proj["A (current)"], proj["B (stricter human)"]
    assert abs(a["ptp_per_rpc"] - b["ptp_per_rpc"]) < 1e-12
    assert b["ptp_per_connect"] > a["ptp_per_connect"] and b["ptp"] < a["ptp"]
    print(f"  PTP per connect moves {a['ptp_per_connect']:.4f} -> {b['ptp_per_connect']:.4f} "
          f"while PTP per RPC stays {a['ptp_per_rpc']:.2f}: the agent did not change, the denominator did")
    d_rpc = a["rpc"] - b["rpc"]
    d_trunk_s = (a["trunk_hours"] - b["trunk_hours"]) * 3600
    print(f"  B loses {group(d_rpc)} RPCs and {group(a['ptp'] - b['ptp'])} PTPs a day and saves "
          f"{a['trunk_hours'] - b['trunk_hours']:.1f} trunk hours")
    print(f"  break-even: B pays only if one lost RPC is worth less than {d_trunk_s / d_rpc:.0f} trunk seconds")
    assert (round(a["agent_connects"]), round(b["agent_connects"])) == (112710, 108420)
    assert (round(d_rpc), round(a["ptp"] - b["ptp"]), round(d_trunk_s / d_rpc)) == (2002, 761, 15)
    print("\nAll checks passed.")


if __name__ == "__main__":
    main()
