"""Generate the synthetic course data for one edition of the Voice AI Evaluation course.

    python3.11 data/generate.py --edition global          # writes data/global/
    python3.11 data/generate.py --edition india           # writes data/india/
    python3.11 data/generate.py --edition global --check  # regenerate in memory, compare with disk

Standard library only. The same edition and seed always give byte-identical files.
Everything about the lenders, agents, people and calls is fictional and synthetic.
This file holds no language text: names, numbers and utterances come from
world/<edition>/constants.json and world/<edition>/phrases.json.
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import math
import random
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
GENERATOR_VERSION = "1.0.0"
SCHEMA_VERSION = "voice-trace/1.3"
HOP = 10  # orchestration hop, ms
REDACTED = ("account_id", "contact_id", "phone_e164", "value", "statement")

# Scenario cards for the 200 generated calls: 25 scenarios x 8 simulated trials.
# (scenario id, flow, persona, language role, variant)
SCENARIOS = [
    ("S01", "F01", "P01", "english", ""), ("S02", "F01", "P01", "native", ""),
    ("S03", "F01", "P12", "mixed", ""), ("S04", "F01", "P13", "native", ""),
    ("S05", "F09", "P10", "english", ""), ("S06", "F09", "P10", "mixed", ""),
    ("S07", "F02", "P02", "native", "found"), ("S08", "F02", "P02", "english", "not_found"),
    ("S09", "F03", "P03", "english", ""), ("S10", "F03", "P03", "mixed", ""),
    ("S11", "F04", "P04", "mixed", ""), ("S12", "F04", "P04", "english", ""),
    ("S13", "F10", "P11", "english", ""), ("S14", "F10", "P11", "mixed", ""),
    ("S15", "F05", "P05", "english", ""), ("S16", "F05", "P06", "mixed", "wrong_number"),
    ("S17", "F06", "P07", "english", ""), ("S18", "F06", "P07", "native", ""),
    ("S19", "F07", "P08", "mixed", ""), ("S20", "F08", "P09", "native", ""),
    ("S21", "F01", "P01", "mixed", ""), ("S22", "F02", "P02", "mixed", "found"),
    ("S23", "F04", "P04", "native", ""), ("S24", "F10", "P11", "native", ""),
    ("S25", "F03", "P03", "native", ""),
]
TRIALS = 8
FAULT_LEVELS = [0.0, 0.05, 0.1, 0.15, 0.25, 0.4]
FAULT_BY_FLOW = {"F01": "ENT.AMOUNT", "F02": "TURN.BARGEIN", "F03": "POL.DISPUTE", "F04": "POL.HARDSHIP",
                 "F05": "POL.DISCLOSE", "F06": "POL.DISCLOSE", "F07": "POL.DISCLOSE", "F08": "OUT.AMD",
                 "F09": "POL.WINDOW", "F10": "POL.COERCE"}


# ---------------------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------------------
def load_world(edition: str) -> tuple[dict, dict]:
    w = ROOT / "world" / edition
    return (json.loads((w / "constants.json").read_text()), json.loads((w / "phrases.json").read_text()))


def text_of(v) -> tuple[str, str | None]:
    if isinstance(v, dict):
        return v["text"], v.get("gloss")
    return v, None


def fill(template: str, **kw) -> str:
    out = template
    for k, v in kw.items():
        out = out.replace("{" + k + "}", str(v))
    return re.sub(r"\s+", " ", out).strip()


def words(text: str) -> list[str]:
    return [w for w in re.sub(r"[^\w\s'-]", " ", text.lower()).split() if w]


def syllables(text: str) -> int:
    n = 0
    for w in words(text):
        groups, prev = 0, False
        for ch in w:
            v = ch in "aeiouy"
            if v and not prev:
                groups += 1
            prev = v
        n += max(1, groups)
    return n


def lognorm(rng: random.Random, median: float, p95: float, lo: int = 1, hi: int | None = None) -> int:
    sigma = math.log(p95 / median) / 1.645
    v = int(round(median * math.exp(rng.gauss(0, sigma))))
    v = max(lo, v)
    return min(v, hi) if hi is not None else v


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------------------
# world wrapper
# ---------------------------------------------------------------------------------------
class World:
    def __init__(self, edition: str):
        self.C, self.P = load_world(edition)
        self.edition = edition
        self.F = self.C["fields"]
        self.persona = {p["id"]: p for p in self.C["personas"]}
        self.book_campaign = {v["book"]: k for k, v in self.C["campaigns"].items()}
        self.sms_tool = self.F["disclosure_sms_tool"]
        self.sms_template = "disclosure" if edition == "global" else "grievance"
        self.global_ed = edition == "global"
        tags = self.P["lang_tags"]
        self.tag_default, self.tag_other = tags["default"], tags["other"]
        self.other_words = set(tags["other_words"])

    def group(self, role: str, persona_id: str) -> str:
        return self.C["group_roles"][role]

    def agent_lang(self, group: str) -> str:
        return self.P["agent_language_for_group"][group]

    @staticmethod
    def _render(text: str, gloss: str | None, kw: dict) -> tuple[str, str | None]:
        tkw = {k: (v[0] if isinstance(v, tuple) else v) for k, v in kw.items()}
        gkw = {k: (v[1] if isinstance(v, tuple) else v) for k, v in kw.items()}
        for k, v in kw.items():
            if isinstance(v, tuple):
                gkw.setdefault(k + "_gloss", v[1])
        t = fill(text, **tkw)
        g = fill(gloss, **gkw) if gloss else None
        return t, g

    def agent_line(self, group: str, key: str, **kw) -> tuple[str, str | None]:
        text, gloss = text_of(self.P["agent"][self.agent_lang(group)][key])
        return self._render(text, gloss, kw)

    def caller_line(self, group: str, key: str, **kw) -> tuple[str, str | None]:
        text, gloss = text_of(self.P["caller"][group][key])
        return self._render(text, gloss, kw)

    def lang_tags(self, text: str) -> list[str]:
        return [self.tag_other if w in self.other_words else self.tag_default for w in words(text)]

    def digits_words(self, group: str, digits: str) -> str:
        lang = self.P["digit_language_for_group"][group]
        names = self.P["digits"][lang]
        return " ".join(names[int(c)] for c in digits)


# ---------------------------------------------------------------------------------------
# one call on one clock
# ---------------------------------------------------------------------------------------
class Call:
    """Builds one call. Every time is in ms since media start at the agent's ingress."""

    def __init__(self, W: World, rng: random.Random, call_id: str, account: dict, contact: dict,
                 campaign: str, started: dt.datetime, tz: str, budget: int, budget_asked: int,
                 load: float, prompt: str = "collections-v17", threshold: float | None = None):
        self.W, self.rng, self.call_id = W, rng, call_id
        self.account, self.contact = account, contact
        self.campaign, self.started, self.tz = campaign, started, tz
        self.budget, self.budget_asked, self.load = budget, budget_asked, load
        self.turns: list[dict] = []
        self.t = 0
        self.crm = {t: [] for t in ("accounts", "contacts", "payments", "ptps", "callbacks", "grievances",
                                    "hardship", "dnc", "sms_log", "call_attempts")}
        if W.global_ed:
            self.crm["revocations"] = []
        self.crm["accounts"].append(account)
        self.crm["contacts"].append(contact)
        self.verified = False
        self.disposition = None
        self.marked = None
        self.faults: list[tuple[int, str, str, int]] = []
        self.prompt = prompt
        thr = threshold if threshold is not None else W.C["campaigns"][campaign]["threshold"]
        self.threshold = thr
        self.n_ptp = 0
        self.amd = None
        self.extra_gap = 0.0
        self.n_callers = 0
        self.mark = None

    # --- time helpers -------------------------------------------------------------
    def ts(self, t_ms: int) -> str:
        return (self.started + dt.timedelta(milliseconds=t_ms)).isoformat(timespec="seconds")

    def speech_ms(self, text: str, rate: float) -> int:
        return int(round(syllables(text) / rate * 1000 / 10.0)) * 10 + 200

    # --- turns --------------------------------------------------------------------
    def caller(self, text: str, gloss: str | None = None, stt: str | None = None, start: int | None = None,
               gap: tuple[int, int] = (350, 900), dur: int | None = None, eot: int | None = None,
               intent: str | None = None, ref_entities=(), stt_entities=None, tags=(), source: str = "human",
               pauses=(), rate: float = 3.8, hangover: int = 200, stt_conf: float | None = None,
               lang_tags: list | None = None) -> dict:
        if start is None:
            start = self.t + self.rng.randint(*gap) + int(self.extra_gap)
        self.n_callers += 1
        if dur is None:
            dur = self.speech_ms(text, rate) + sum(p["end_ms"] - p["start_ms"] for p in pauses)
        vad_end = start + dur
        if eot is None:
            eot = vad_end + self.budget + self.rng.randint(-20, 90)
        stt_text = stt if stt is not None else text
        turn = {"turn_id": len(self.turns) + 1, "speaker": "caller", "source": source,
                "vad_start_ms": start, "vad_end_ms": vad_end, "vad_hangover_ms": hangover}
        if source == "human":
            first = " ".join(stt_text.split()[:2])
            turn["stt_partials"] = [{"t_ms": start + min(490, dur // 2), "text": first}]
            turn["stt_final"] = {"t_ms": vad_end + self.rng.randint(150, 260), "text": stt_text,
                                 "lang_tags": lang_tags if lang_tags is not None else self.W.lang_tags(stt_text),
                                 "confidence": stt_conf if stt_conf is not None else round(self.rng.uniform(0.80, 0.96), 2)}
            turn["eot_commit_ms"] = eot
        else:
            turn["stt_partials"] = []
            turn["stt_final"] = {"t_ms": vad_end + 200, "text": stt_text, "lang_tags": self.W.lang_tags(stt_text),
                                 "confidence": 0.9}
            turn["eot_commit_ms"] = None
        turn["reference_text"] = text
        if gloss:
            turn["gloss"] = gloss
        turn["ref_intent"] = intent
        turn["ref_entities"] = list(ref_entities)
        turn["stt_entities"] = list(ref_entities) if stt_entities is None else list(stt_entities)
        turn["tags"] = list(tags)
        turn["pauses"] = list(pauses)
        self.turns.append(turn)
        self.t = max(self.t, vad_end)
        return turn

    def agent(self, turn_type: str, text: str | None, gloss: str | None = None, acts=(), tools=(),
              post_tools=(), entities=(), responds_to: dict | None = "last", rate: float = 4.4,
              stages: dict | None = None, play_start: int | None = None, start_after: int | None = None,
              barge: dict | None = None, audio_reading: str | None = None) -> dict:
        """tools run between the LLM's first token and the TTS request; post_tools run after playback."""
        rng = self.rng
        st = dict(stages or {})
        if responds_to == "last":
            responds_to = next((t for t in reversed(self.turns) if t["speaker"] == "caller"), None)
        turn = {"turn_id": len(self.turns) + 1, "speaker": "agent", "turn_type": turn_type,
                "responds_to": responds_to["turn_id"] if responds_to else None}
        slow = self.load > 1800
        hop = st.get("hop", HOP)
        if responds_to and responds_to.get("eot_commit_ms") is not None:
            t0 = responds_to["eot_commit_ms"]
        else:
            t0 = start_after if start_after is not None else self.t + 200
        tool_turn = bool(tools)
        if st.get("scripted"):
            turn["llm"] = None
            cursor = t0
        else:
            req = st.get("request_ms", t0 + hop)
            ttft = st.get("ttft", lognorm(rng, 560 if tool_turn else 500, 900 if tool_turn else 800, 180, 2600)
                          * (1.8 if slow else 1.0))
            ttft = int(round(ttft))
            first = st.get("first_token_ms", req + ttft)
            turn["llm"] = {"request_ms": req, "first_token_ms": first, "first_answer_token_ms": first,
                           "cached_tokens": st.get("cached_tokens", rng.choice([0, 1840, 1840, 1840, 2210]))}
            if req < t0:
                turn["llm"]["speculative"] = True
            cursor = first
        calls = []
        for i, (name, args) in enumerate(tools):
            h = st.get("tool_hops", [hop] * len(tools))[i]
            dur = st.get("tool_ms", [None] * len(tools))[i]
            if dur is None:
                dur = lognorm(rng, 260, 480, 60, 2500) * (2.2 if slow else 1)
            start = cursor + h
            end = start + int(dur)
            calls.append(self.tool(name, args, start, end))
            cursor = end
        if text is None:
            turn["tool_calls"] = calls
            turn["tts"] = None
            turn["play_start_ms"] = None
            turn["play_end_ms"] = None
            turn["barge_in"] = None
            turn["acts"] = list(acts)
            self.turns.append(turn)
            self.t = max(self.t, cursor)
            for name, args in post_tools:
                s = self.t + HOP
                turn["tool_calls"].append(self.tool(name, args, s, s + lognorm(rng, 60, 140, 10)))
                self.t = s + 60
            return turn
        tts_req = st.get("tts_request_ms", cursor + st.get("tts_hop", hop))
        ttfb = st.get("ttfb", lognorm(rng, 200, 320, 90, 900))
        fb = st.get("first_byte_ms", tts_req + ttfb)
        playout = st.get("playout", rng.randint(35, 60))
        ps = play_start if play_start is not None else fb + playout
        pe = ps + self.speech_ms(text, rate)
        if barge:
            pe = barge["tts_stop_ms"]
        turn["tool_calls"] = calls
        turn["tts"] = {"text": text, "request_ms": tts_req, "first_byte_ms": fb, "entities": list(entities)}
        if gloss:
            turn["tts"]["gloss"] = gloss
        if audio_reading:
            turn["tts"]["audio_reading"] = audio_reading
        turn["play_start_ms"] = ps
        turn["play_end_ms"] = pe
        turn["speaking_rate_sps"] = rate
        turn["barge_in"] = barge
        turn["acts"] = list(acts)
        self.turns.append(turn)
        self.t = max(self.t, pe)
        for name, args in post_tools:
            s = self.t + HOP
            d = lognorm(rng, 90, 200, 20)
            turn["tool_calls"].append(self.tool(name, args, s, s + d))
            self.t = s + d
        return turn

    # --- tools and the CRM --------------------------------------------------------
    def tool(self, name: str, args: dict, start: int, end: int) -> dict:
        W, F = self.W, self.W.F
        acc = self.account
        aid = acc["account_id"]
        full = dict(args)
        if name not in ("transfer_to_human", "end_call") and "account_id" not in full:
            full = {"account_id": aid, **full}
        res: dict
        if name == "lookup_account":
            res = {"account_id": aid, "contact_id": self.contact["contact_id"], "first_name": self.contact["first_name"],
                   "product_code": acc["product_code"], "preferred_language": acc["preferred_language"],
                   "contact_role": self.contact["role"], "masked_loan_no": "XXXX" + acc["loan_last4"]}
            if W.global_ed:
                res["jurisdiction"] = acc["jurisdiction"]
        elif name == "verify_identity":
            ok = full["value"] == self.contact[F["postal_code"]] or full["value"] == acc["loan_last4"]
            self.verified = self.verified or ok
            res = {"verified": ok, "attempts": 1, "locked": False}
        elif name == "get_dues":
            res = {F["past_due"]: acc[F["past_due"]], F["payment"]: acc[F["payment"]],
                   "next_due_date": acc["next_due_date"], "dpd": acc["dpd"],
                   F["late_fee"]: self.extra["late_fee"], F["payoff"]: self.extra["payoff"]}
        elif name == "check_payment_status":
            res = {"payments": [{F["payment_ref"]: p[F["payment_ref"]], F["amount"]: p[F["amount"]],
                                 "paid_on": p["paid_on"], "channel": p["channel"]}
                                for p in self.crm["payments"] if p["paid_on"] >= full["since"]]}
        elif name == "record_promise_to_pay":
            self.n_ptp += 1
            pid = f"PTP-{self.rng.randint(100000, 999999)}"
            self.crm["ptps"].append({"ptp_id": pid, "account_id": aid, "attempt_id": self.attempt_id,
                                     F["amount"]: full[F["amount"]], "ptp_date": full["ptp_date"],
                                     "channel": full["channel"], "readback_confirmed": full["readback_confirmed"],
                                     "created_at": self.ts(end), "kept": None, "kept_checked_at": None})
            res = {"ptp_id": pid}
        elif name == "send_payment_link":
            sid = f"SMS-{self.rng.randint(100000, 999999)}"
            self.crm["sms_log"].append({"sms_id": sid, "account_id": aid, "template": "payment_link", "sent_at": self.ts(end)})
            res = {"link_id": f"LNK-{self.rng.randint(100000, 999999)}"}
        elif name == "schedule_callback":
            cid = f"CB-{self.rng.randint(100000, 999999)}"
            local = full["callback_at"][11:16]
            lo, hi = self.window()
            within = lo <= local <= hi
            self.crm["callbacks"].append({"callback_id": cid, "account_id": aid, "callback_at_local": full["callback_at"],
                                          "requested_by": full["requested_by"], "status": "scheduled"})
            res = {"callback_id": cid, "within_window": within}
        elif name == "log_dispute":
            gid = f"GRV-{self.rng.randint(100000, 999999)}"
            self.crm["grievances"].append({"grievance_id": gid, "account_id": aid, "category": full["category"],
                                           "statement": full["statement"], "opened_at": self.ts(end), "status": "open"})
            acc["recovery_hold"] = True
            res = {"grievance_id": gid}
        elif name == "flag_hardship":
            hid = f"HS-{self.rng.randint(100000, 999999)}"
            self.crm["hardship"].append({"hardship_id": hid, "account_id": aid, "reason": full["reason"], "opened_at": self.ts(end)})
            acc["hardship_flag"] = True
            res = {"hardship_id": hid}
        elif name == "mark_contact":
            self.marked = full["outcome"]
            res = {"ok": True}
        elif name == "set_do_not_call":
            self.crm["dnc"].append({"account_id": aid, "phone_e164": full["phone_e164"], "scope": full["scope"],
                                    "reason": full["reason"], "set_at": self.ts(end)})
            if full["scope"] == "bot":
                acc["dnc_bot"] = True
            res = {"ok": True}
        elif name == W.sms_tool:
            sid = f"SMS-{self.rng.randint(100000, 999999)}"
            self.crm["sms_log"].append({"sms_id": sid, "account_id": aid, "template": W.sms_template, "sent_at": self.ts(end)})
            res = {"sms_id": sid}
        elif name == "transfer_to_human":
            res = {"transfer_id": f"TR-{self.rng.randint(100000, 999999)}"}
            self.disposition = self.disposition or f"transfer_{full['queue']}"
        elif name == "end_call":
            res = {"ok": True}
            self.disposition = self.disposition or full["disposition"]
        else:
            raise ValueError(name)
        red = {k: v for k, v in full.items() if k not in REDACTED}
        return {"name": name, "args_redacted": red, "start_ms": start, "end_ms": end, "result": res}

    def window(self) -> tuple[str, str]:
        cw = self.W.C["calling_window"]
        return tuple(cw["by_product"].get(self.account["product_code"], cw["default"]))

    def fault(self, t_ms: int, code: str, note: str, turn_id: int) -> None:
        self.faults.append((t_ms, code, note, turn_id))

    # --- finish -------------------------------------------------------------------
    def finish(self, meta: dict, crm_before: dict, gold: dict, checks=(), judge_scores=(), labels=None,
               dial: dict | None = None) -> dict:
        W = self.W
        rpc = self.verified
        disp = self.marked or self.disposition or "unknown"
        attempt = {"attempt_id": self.attempt_id, "account_id": self.account["account_id"],
                   "phone_e164": self.contact["phone_e164"], "cli": W.C["cli_pattern"],
                   "started_at_local": self.started.isoformat(timespec="seconds"), "tz": self.tz}
        if W.global_ed:
            attempt.update({"location_signals": meta["location_signals"],
                            "connect_outcome": dial["connect_outcome"], "counts_toward_cap": dial["counts_toward_cap"],
                            "conversation": dial["conversation"]})
        attempt.update({"amd_label": self.amd["label"], "rpc": rpc, "disposition": disp,
                        "recording_uri": f"s3://recordings/{self.call_id}.wav",
                        "retain_until": (self.started.date() + dt.timedelta(days=30 * W.C["recording_retention"]["months"] + 5)).isoformat()})
        self.crm["call_attempts"].append(attempt)
        gaps, eot, ttft, tool_ms, ttfb, playout, ids, types = [], [], [], [], [], [], [], []
        byid = {t["turn_id"]: t for t in self.turns}
        for t in self.turns:
            if t["speaker"] != "agent" or t["play_start_ms"] is None or t["responds_to"] is None:
                continue
            c = byid[t["responds_to"]]
            if c.get("eot_commit_ms") is None:
                continue
            ids.append(t["turn_id"])
            types.append(t["turn_type"])
            gaps.append(t["play_start_ms"] - c["vad_end_ms"])
            eot.append(c["eot_commit_ms"] - c["vad_end_ms"])
            ttft.append(t["llm"]["first_token_ms"] - t["llm"]["request_ms"] if t["llm"] else None)
            pre = [x for x in t["tool_calls"] if x["start_ms"] < t["tts"]["request_ms"]]
            tool_ms.append(sum(x["end_ms"] - x["start_ms"] for x in pre))
            ttfb.append(t["tts"]["first_byte_ms"] - t["tts"]["request_ms"])
            playout.append(t["play_start_ms"] - t["tts"]["first_byte_ms"])
        if labels is None:
            labels = []
            if self.faults:
                t_ms, code, note, tid = sorted(self.faults)[0]
                labels.append({"labeler": meta.get("labeler", "rv-03"), "taxonomy": W.C["taxonomy"]["version"],
                               "code": code, "note": note, "turn_id": tid})
        out = {"call_id": self.call_id, "schema_version": SCHEMA_VERSION, "edition": W.edition,
               "dataset": W.C["dataset"], "campaign": self.campaign, "account_id": self.account["account_id"],
               "persona_or_real": meta["persona_or_real"], "scenario": meta["scenario"],
               "started_at_local": self.started.isoformat(timespec="seconds"), "tz": self.tz}
        if W.global_ed:
            out["location_signals"] = meta["location_signals"]
        out["dial"] = dial
        out["cli"] = W.C["cli_pattern"]
        if W.global_ed:
            out["attestation"] = "A"
        out.update({"carrier": meta["carrier"], "codec_chain": meta["codec_chain"], "pipeline": "cascade",
                    "concurrency_at_start": int(self.load),
                    "versions": {**{k: v for k, v in W.C["versions"].items() if k != "gold"},
                                 "prompt": self.prompt, "turn_detector": f"td-1.1@thr{self.threshold:.2f}",
                                 "gold": None},
                    "silence_budget_ms": {"default": self.budget, "amount_or_date_asked": self.budget_asked},
                    "audio": {"agent_channel_uri": f"s3://recordings/{self.call_id}/agent.wav",
                              "caller_channel_uri": f"s3://recordings/{self.call_id}/caller.wav",
                              "sample_rate_hz": 8000, "redacted_uri": f"s3://recordings/{self.call_id}/caller.redacted.wav",
                              "carrier_offset_ms": meta.get("carrier_offset_ms", 212)},
                    "amd": self.amd, "turns": self.turns,
                    "timings_summary": {"agent_turn_ids": ids, "turn_types": types, "turn_gap_ms": gaps,
                                        "stage_ms": {"eot_delay": eot, "llm_ttft": ttft, "tool": tool_ms,
                                                     "tts_ttfb": ttfb, "playout": playout}},
                    "crm_before": crm_before, "crm_after": self.crm, "gold_end_state": gold,
                    "checks": list(checks), "judge_scores": list(judge_scores), "labels": labels})
        return out


# ---------------------------------------------------------------------------------------
# accounts
# ---------------------------------------------------------------------------------------
def make_account(W: World, rng: random.Random, persona: dict, group: str, dues: int, call_date: dt.date,
                 account_id: str | None = None, postal: str | None = None) -> tuple[dict, dict, dict]:
    F, C = W.F, W.C
    prod = persona["product"]
    first, _, last = persona["name"].partition(" ")
    if persona["role"] in ("machine", "stranger", "third_party"):
        owner = W.persona["P01"] if persona["id"] == "P05" else None
        if owner:
            first, _, last = owner["name"].partition(" ")
        else:
            first, last = (("Ryan", "Mitchell") if W.global_ed else ("Rahul", "Verma"))
    aid = account_id or f"A-{rng.randint(10000000, 99999999)}"
    postal = postal or rng.choice(W.P["postal_codes"])
    dob = dt.date(rng.randint(1958, 2000), rng.randint(1, 12), rng.randint(1, 28)).isoformat()
    dpd = rng.randint(*C["campaigns"][W.book_campaign[prod]]["dpd"]) if persona["id"] != "P01" else 6
    acc = {"account_id": aid, "product_code": prod, "first_name": first, "last_name": last, "dob": dob,
           F["postal_code"]: postal}
    if W.global_ed:
        acc["state"] = persona["state"]
        acc["jurisdiction"] = "us"
    acc.update({"loan_last4": f"{rng.randint(0, 9999):04d}", "preferred_language": group, "dpd": dpd,
                F["past_due"]: dues, F["payment"]: dues, "next_due_date": (call_date + dt.timedelta(days=rng.randint(10, 25))).isoformat(),
                "recovery_hold": False, "hardship_flag": False, "dnc_bot": False})
    digital = prod in ("PIL", "PL")
    if W.global_ed:
        acc.update({"digital_origination": digital, "ai_voice_consent_at": "2026-03-02T10:15:00-07:00", "consent_revoked_at": None})
    else:
        acc.update({"digital_loan": digital, "agent_particulars_sent_at": "2026-10-28T11:00:00+05:30" if digital else None})
    if W.global_ed:
        phone = f"+1555{rng.randint(1000000, 9999999)}"
    else:
        phone = f"+910000{rng.randint(100000, 999999)}"
    if persona["role"] == "guarantor":
        gfirst, _, glast = persona["name"].partition(" ")
        contact = {"contact_id": f"K-{rng.randint(10000, 99999)}", "account_id": aid, "phone_e164": phone,
                   "role": "guarantor", "first_name": gfirst, "last_name": glast,
                   "dob": dt.date(rng.randint(1960, 1990), rng.randint(1, 12), rng.randint(1, 28)).isoformat(),
                   F["postal_code"]: postal, "verified_at": None}
        acc_postal = rng.choice([p for p in W.P["postal_codes"] if p != postal])
        acc[F["postal_code"]] = acc_postal
    else:
        contact = {"contact_id": f"K-{rng.randint(10000, 99999)}", "account_id": aid, "phone_e164": phone,
                   "role": "borrower", "first_name": first, "last_name": last, "dob": dob,
                   F["postal_code"]: postal, "verified_at": None}
    extra = {"late_fee": 2500 if W.global_ed else 50000, "payoff": dues * 9}
    return acc, contact, extra


def snapshot(crm: dict) -> dict:
    return copy.deepcopy(crm)


# ---------------------------------------------------------------------------------------
# generated calls (200)
# ---------------------------------------------------------------------------------------
def opener_turn(c: Call, group: str, first: str, last: str, v16: bool = False, dpd: int = 4):
    W = c.W
    if v16:
        text, gloss = W.agent_line(group, "third_party_opener_v16", first=first, last=last,
                                   dpd_words=dpd, dpd_words_gloss=dpd)
        acts = ["business_identity", "debt_detail"]
    else:
        text, gloss = W.agent_line(group, "opener", first=first, last=last)
        acts = ["business_identity", "ai_disclosure", "recording_notice", "identity_question"]
    c.amd = {"label": "human", "confidence": round(c.rng.uniform(0.86, 0.97), 2), "decided_at_ms": c.rng.randint(2300, 2460),
             "true_label": "human"}
    return c.agent("greeting", text, gloss, acts=acts, tools=[("lookup_account", {"phone_e164": c.contact["phone_e164"]})],
                   responds_to=None, start_after=c.amd["decided_at_ms"], stages={"scripted": True})


def amount_words(W: World, group: str, opt: dict) -> tuple[str, str]:
    lang = W.agent_lang(group)
    en = "en"
    return opt["agent"][lang], opt["agent"].get(en, opt["agent"][lang])


def date_words(W: World, group: str, opt: dict) -> tuple[str, str]:
    lang = W.agent_lang(group)
    return opt["agent"][lang], opt["agent"].get("en", opt["agent"][lang])


def verify_prefix(c: Call, group: str, dues_opt: dict, guarantor: bool = False, fault_unverified: bool = False):
    """Greeting, identity answer, verification and the dues statement (turns 1-5)."""
    W, F = c.W, c.W.F
    first = c.contact["first_name"]
    opener_turn(c, group, first, c.contact["last_name"])
    key = "guarantor_q" if guarantor else "identity_yes"
    t, gl = W.caller_line(group, key, first=first)
    c.caller(t, gl, intent="identity_confirmed")
    if fault_unverified:
        amt = amount_words(W, group, dues_opt)
        t, gl = W.agent_line(group, "dues_unverified", amount=amt)
        turn = c.agent("amount-quote", t, gl, acts=["inform_dues", "ask_payment"],
                       entities=[{"type": "amount", "value": dues_opt["value"]}])
        c.fault(turn["play_start_ms"], "POL.DISCLOSE", "dues stated before identity verification", turn["turn_id"])
        t, gl = W.caller_line(group, "backchannel")
        c.caller(t, gl, intent="backchannel")
    t, gl = W.agent_line(group, "verify_ask")
    c.agent("verification", t, gl, acts=["verify_ask"])
    postal = c.contact[F["postal_code"]]
    spoken = W.digits_words(group, postal)
    c.caller(spoken, None, intent="verify_answer", ref_entities=[{"type": "postal_code", "value": postal}])
    amt = amount_words(W, group, dues_opt)
    notice = text_of(W.P["agent"][W.agent_lang(group)]["notice"])
    nt = (notice[0], notice[1] or notice[0])
    tools = [("verify_identity", {"contact_id": c.contact["contact_id"], "method": F["postal_code"], "value": postal}),
             ("get_dues", {})]
    if guarantor:
        t, gl = W.agent_line(group, "guarantor_dues", first=first, amount=amt, notice=nt[0], notice_gloss=nt[1])
    else:
        t, gl = W.agent_line(group, "dues", first=first, amount=amt, notice=nt[0], notice_gloss=nt[1])
    acts = (["debt_notice"] if W.global_ed else []) + ["inform_dues", "ask_payment"]
    return c.agent("amount-quote", t, gl, acts=acts, tools=tools,
                   entities=[{"type": "amount", "value": dues_opt["value"]}])


def closing(c: Call, group: str, disposition: str, sms: bool = True, extra_post=()):
    W = c.W
    t, gl = W.caller_line(group, "bye")
    c.caller(t, gl, intent="closing")
    t, gl = W.agent_line(group, "closing")
    acts = ["callback_number", "goodbye"] if W.global_ed else ["goodbye"]
    post = list(extra_post) + [("end_call", {"disposition": disposition})]
    return c.agent("closing", t, gl, acts=acts, post_tools=post)


def disclosure_turn(c: Call, group: str, prefix_key: str | None, ptype: str, tools=(), acts=(), entities=(), rate=4.4, **kw):
    W = c.W
    parts, glosses = [], []
    if prefix_key:
        t, gl = W.agent_line(group, prefix_key, **kw)
        parts.append(t)
        glosses.append(gl)
    t, gl = W.agent_line(group, "disclosure")
    parts.append(t)
    glosses.append(gl)
    gloss = " ".join(g for g in glosses if g) or None
    return c.agent(ptype, " ".join(parts), gloss, acts=list(acts) + ["disclosure"], tools=tools,
                   post_tools=[(W.sms_tool, {"jurisdiction": "us"} if W.global_ed else {})], entities=entities, rate=rate)


def flow_call(W: World, sid: str, flow: str, pid: str, role: str, variant: str, trial: int, p_fault: float,
              seq: int) -> dict:
    rng = random.Random(f"{W.C['seed']}-{sid}-{trial}")
    persona = W.persona[pid]
    group = W.C["group_roles"][role]
    campaign = W.book_campaign[persona["product"]]
    cinfo = W.C["campaigns"][campaign]
    call_date = dt.date(2026, 11, 18) + dt.timedelta(days=trial % 2)
    lo, hi = W.C["calling_window"]["by_product"].get(persona["product"], W.C["calling_window"]["default"])
    lo_m = int(lo[:2]) * 60 + int(lo[3:]) + 30
    hi_m = int(hi[:2]) * 60 + int(hi[3:]) - 45
    minute = rng.randint(lo_m, hi_m)
    window_fault = rng.random() < 0.012
    if window_fault:
        minute = int(hi[:2]) * 60 + int(hi[3:]) + rng.randint(5, 40)
    state = persona["state"]
    tz = W.C["timezones"][state]
    off = W.C["utc_offsets"][tz]
    sign = 1 if off[0] == "+" else -1
    tzinfo = dt.timezone(sign * dt.timedelta(hours=int(off[1:3]), minutes=int(off[4:6])))
    started = dt.datetime(call_date.year, call_date.month, call_date.day, minute // 60, minute % 60,
                          rng.randint(0, 59), tzinfo=tzinfo)
    u = rng.random()
    load = rng.randint(300, 1500) if u < 0.7 else (rng.randint(1500, 1800) if u < 0.88 else rng.randint(1801, 2400))
    dues_opt = rng.choice(W.P["dues_amounts"])
    acc, contact, extra = make_account(W, rng, persona, group, dues_opt["value"], call_date)
    call_id = f"{W.C['call_id_prefix']}-{call_date.isoformat()}-{9000000 + seq:07d}"
    c = Call(W, rng, call_id, acc, contact, campaign, started, tz, cinfo["budget_ms"], cinfo["budget_asked_ms"], load)
    c.extra = extra
    c.attempt_id = f"AT-{rng.randint(10000000, 99999999)}"
    if flow == "F02" and variant == "found":
        c.crm["payments"].append({"payment_id": f"PAY-{rng.randint(100000, 999999)}", "account_id": acc["account_id"],
                                  W.F["payment_ref"]: f"{rng.randint(10**11, 10**12 - 1)}", W.F["amount"]: dues_opt["value"],
                                  "paid_on": W.P["paid_on"]["iso"], "channel": "debit_card" if W.global_ed else "upi",
                                  "posted_at": f"{W.P['paid_on']['iso']}T21:10:00{off}"})
    before = snapshot(c.crm)
    faulty = rng.random() < p_fault
    fcode = FAULT_BY_FLOW[flow]
    if window_fault:
        c.fault(0, "POL.WINDOW", "call placed outside the calling window", 1)
    amtF = W.F["amount"]
    gold: dict = {"new_rows": {}, "account": {}, "call_attempt": {}}
    sms_row = {"template": W.sms_template}
    meta_conn = {"connect_outcome": "answered", "counts_toward_cap": True, "conversation": True}
    first = contact["first_name"]

    if flow in ("F01",):
        verify_prefix(c, group, dues_opt)
        popts = [o for o in W.P["promise_amounts"] if o["value"] <= dues_opt["value"]] or W.P["promise_amounts"]
        popt = rng.choice(popts)
        dopt = rng.choice(W.P["promise_dates"])
        loop = faulty and pid == "P12" and group in W.P.get("loop_stt", {})
        cutoff = (not faulty) and rng.random() < 0.12
        misheard = faulty and not loop
        say_amt = popt["say"][group]
        say_amt_gloss = popt["agent"].get("en")
        say_date = dopt["say"][group]
        ent_ref = [{"type": "amount", "value": popt["value"]}, {"type": "date", "value": dopt["iso"]}]
        if loop:
            t, gl = W.caller_line(group, "promise", amount=say_amt, date=say_date, amount_gloss=say_amt_gloss, date_gloss=dopt["gloss"])
            stt = fill(W.P["loop_stt"][group], amount=popt["confusable"]["say"][group])
            c.caller(t, gl, stt=stt, intent="promise", ref_entities=ent_ref,
                     stt_entities=[{"type": "amount", "value": popt["confusable"]["value"]}],
                     lang_tags=[W.tag_default] * len(words(stt)), stt_conf=0.52)
            turn = c.agent("objection", *W.agent_line(group, "clarify"), acts=["clarify"])
            c.fault(turn["play_start_ms"], "STT.LID", "language locked to one language mid-utterance; clarification loop", turn["turn_id"] - 1)
            t, gl = W.caller_line(group, "loop_answer", date=say_date, date_gloss=dopt["gloss"])
            c.caller(t, gl, stt=" ".join(words(t)[:-2]), intent="promise", ref_entities=[ent_ref[1]], stt_entities=[], stt_conf=0.55)
            c.agent("objection", *W.agent_line(group, "clarify_again"), acts=["clarify"])
            t, gl = W.caller_line(group, "loop_hangup", date=say_date, date_gloss=dopt["gloss"])
            c.caller(t, gl, intent="hangup", ref_entities=[ent_ref[1]], stt_entities=[])
            c.agent("closing", None, acts=[], post_tools=[("end_call", {"disposition": "caller_hangup"})], responds_to=None)
        else:
            if cutoff:
                t1, g1 = W.caller_line(group, "promise_part1")
                t2, g2 = W.caller_line(group, "promise_part2", date=say_date, date_gloss=dopt["gloss"])
                hold = rng.randint(c.budget + 120, c.budget + 450)
                part1 = c.caller(t1, g1, intent="promise_partial", eot=None)
                part1["eot_commit_ms"] = part1["vad_end_ms"] + c.budget
                part1["pauses"] = [{"start_ms": part1["vad_end_ms"], "end_ms": part1["vad_end_ms"] + hold,
                                    "label": "hold", "content_tag": "date"}]
                t, gl = W.agent_line(group, "push_same_day")
                agent_t = c.agent("objection", t, gl, acts=["ask_payment"], responds_to=part1)
                cstart = part1["vad_end_ms"] + hold
                p2 = c.caller(t2, g2, start=cstart, intent="promise", ref_entities=[ent_ref[1]])
                if p2["vad_start_ms"] < agent_t["play_end_ms"]:
                    agent_t["barge_in"] = {"t_ms": cstart + 380, "tts_stop_ms": cstart + 440, "stop_latency_ms": 440}
                    agent_t["play_end_ms"] = cstart + 440
                c.t = max(p2["vad_end_ms"], agent_t["play_end_ms"])
                c.fault(agent_t["play_start_ms"], "TURN.CUTOFF", "turn closed during a hold pause before the date", agent_t["turn_id"])
                t, gl = W.caller_line(group, "promise", amount=say_amt, date=say_date, amount_gloss=say_amt_gloss, date_gloss=dopt["gloss"])
                c.caller(t, gl, intent="promise", ref_entities=ent_ref)
            else:
                stt_text = None
                stt_ent = ent_ref
                t, gl = W.caller_line(group, "promise", amount=say_amt, date=say_date, amount_gloss=say_amt_gloss, date_gloss=dopt["gloss"])
                if misheard:
                    conf = popt["confusable"]
                    stt_text, _ = W.caller_line(group, "promise", amount=conf["say"][group], date=say_date,
                                                amount_gloss="", date_gloss="")
                    stt_ent = [{"type": "amount", "value": conf["value"]}, ent_ref[1]]
                c.caller(t, gl, stt=stt_text, intent="promise", ref_entities=ent_ref, stt_entities=stt_ent)
            heard = popt["confusable"] if misheard else popt
            a_amt = amount_words(W, group, heard)
            a_date = date_words(W, group, dopt)
            if misheard:
                args = {amtF: heard["value"], "ptp_date": dopt["iso"], "channel": "link", "readback_confirmed": False}
                t, gl = W.agent_line(group, "noted_no_readback", amount=a_amt, date=a_date)
                turn = c.agent("tool", t, gl, acts=["inform_ptp"], tools=[("record_promise_to_pay", args)],
                               entities=[{"type": "amount", "value": heard["value"]}, {"type": "date", "value": dopt["iso"]}])
                c.fault(turn["play_start_ms"], "ENT.AMOUNT", "amount misheard; PTP written before read-back", turn["turn_id"])
                t, gl = W.caller_line(group, "backchannel")
                c.caller(t, gl, intent="backchannel")
                disclosure_turn(c, group, "ptp_done", "tool", acts=["inform_link"],
                                tools=[("send_payment_link", {amtF: heard["value"], "channel": "sms"})])
            else:
                t, gl = W.agent_line(group, "readback", amount=a_amt, date=a_date)
                c.agent("readback", t, gl, acts=["readback"],
                        entities=[{"type": "amount", "value": popt["value"]}, {"type": "date", "value": dopt["iso"]}])
                t, gl = W.caller_line(group, "yes")
                c.caller(t, gl, intent="confirm_yes")
                args = {amtF: popt["value"], "ptp_date": dopt["iso"], "channel": "link", "readback_confirmed": True}
                disclosure_turn(c, group, "ptp_done", "tool", acts=["inform_link"],
                                tools=[("record_promise_to_pay", args), ("send_payment_link", {amtF: popt["value"], "channel": "sms"})])
            closing(c, group, "ptp")
        gold["new_rows"] = {"ptps": [{amtF: popt["value"], "ptp_date": dopt["iso"], "readback_confirmed": True}],
                            "sms_log": [{"template": "payment_link"}, sms_row]}
        gold["call_attempt"] = {"rpc": True, "disposition": "ptp"}

    elif flow == "F09":
        opener_turn(c, group, first, contact["last_name"])
        t, gl = W.caller_line(group, "callback_req")
        c.caller(t, gl, intent="callback_request")
        cb = rng.choice(W.P["callback_times"])
        cb_local = cb["local"]
        by = "borrower"
        if faulty:
            hh = int(W.C["calling_window"]["default"][1][:2])
            cb_local = f"{hh}:30"
            by = "agent"
        cb_at = f"{started.date().isoformat()}T{cb_local}{off}"
        lang = W.agent_lang(group)
        tt = (cb["agent"][lang], cb["agent"].get("en", cb["agent"][lang]))
        t, gl = W.agent_line(group, "callback_ok", time=tt, time_gloss=tt[1])
        turn = c.agent("tool", t, gl, acts=["confirm_callback"],
                       tools=[("schedule_callback", {"callback_at": cb_at, "requested_by": by, "reason": "driving"})])
        if faulty:
            c.fault(turn["play_start_ms"], "POL.WINDOW", "callback booked outside the calling window by the agent", turn["turn_id"])
        closing(c, group, "callback")
        gold["new_rows"] = {"callbacks": [{"requested_by": "borrower", "status": "scheduled"}]}
        gold["call_attempt"] = {"rpc": False, "disposition": "callback"}

    elif flow == "F02":
        dues_t = verify_prefix(c, group, dues_opt)
        t, gl = W.caller_line(group, "already_paid")
        start = dues_t["play_start_ms"] + (dues_t["play_end_ms"] - dues_t["play_start_ms"]) // 2
        stop_lat = 900 if faulty else rng.randint(180, 340)
        dues_t["barge_in"] = {"t_ms": start + stop_lat - 60, "tts_stop_ms": start + stop_lat, "stop_latency_ms": stop_lat}
        dues_t["play_end_ms"] = start + stop_lat
        c.t = dues_t["play_end_ms"]
        c.caller(t, gl, start=start, intent="already_paid")
        paid = W.P["paid_on"]
        if faulty:
            t, gl = W.agent_line(group, "push_after_claim")
            turn = c.agent("objection", t, gl, acts=["ask_payment"])
            c.fault(dues_t["barge_in"]["t_ms"], "TURN.BARGEIN", "900 ms talk-over, plan not revised after already-paid claim", dues_t["turn_id"])
            t, gl = W.caller_line(group, "already_paid")
            c.caller(t, gl, intent="already_paid")
            disclosure_turn(c, group, None, "closing", acts=[])
            closing(c, group, "refused")
        elif variant == "found":
            a = amount_words(W, group, dues_opt)
            d = date_words(W, group, paid)
            disclosure_turn(c, group, "paid_found", "tool", acts=["confirm_payment"],
                            tools=[("check_payment_status", {"since": "2026-10-20"})], amount=a, date=d)
            closing(c, group, "paid")
        else:
            disclosure_turn(c, group, "paid_not_found", "tool", acts=["inform_review"],
                            tools=[("check_payment_status", {"since": "2026-10-20"}),
                                   ("log_dispute", {"category": "already_paid", "statement": "caller says paid on the 3rd"})])
            closing(c, group, "dispute")
        if variant == "found":
            gold["new_rows"] = {"sms_log": [sms_row]}
            gold["account"] = {"recovery_hold": False}
            gold["call_attempt"] = {"rpc": True, "disposition": "paid"}
        else:
            gold["new_rows"] = {"grievances": [{"category": "already_paid"}], "sms_log": [sms_row]}
            gold["account"] = {"recovery_hold": True}
            gold["call_attempt"] = {"rpc": True, "disposition": "dispute"}

    elif flow == "F03":
        verify_prefix(c, group, dues_opt)
        t, gl = W.caller_line(group, "dispute")
        c.caller(t, gl, intent="dispute")
        if faulty:
            small = W.P["small_amounts"][0]
            a = amount_words(W, group, small)
            t, gl = W.agent_line(group, "dispute_push", amount=a)
            turn = c.agent("objection", t, gl, acts=["ask_payment"], entities=[{"type": "amount", "value": small["value"]}])
            c.fault(turn["play_start_ms"], "POL.DISPUTE", "payment requested after a dispute", turn["turn_id"])
            t, gl = W.caller_line(group, "dispute")
            c.caller(t, gl, intent="dispute")
        disclosure_turn(c, group, "dispute_logged", "tool", acts=["inform_dispute"],
                        tools=[("log_dispute", {"category": "amount_wrong", "statement": "late fee disputed"})])
        closing(c, group, "dispute")
        gold["new_rows"] = {"grievances": [{"category": "amount_wrong"}], "sms_log": [sms_row]}
        gold["account"] = {"recovery_hold": True}
        gold["call_attempt"] = {"rpc": True, "disposition": "dispute"}

    elif flow == "F04":
        verify_prefix(c, group, dues_opt)
        t, gl = W.caller_line(group, "hardship")
        c.caller(t, gl, intent="hardship", tags=["crying, 4 s"], rate=2.6)
        if faulty:
            small = W.P["small_amounts"][0]
            a = amount_words(W, group, small)
            t, gl = W.agent_line(group, "hardship_push", amount=a)
            last = c.turns[-1]
            turn = c.agent("objection", t, gl, acts=["ask_payment"], rate=5.9,
                           entities=[{"type": "amount", "value": small["value"]}],
                           stages={"request_ms": last["vad_end_ms"] - 600, "first_token_ms": last["vad_end_ms"] - 100,
                                   "tts_request_ms": last["vad_end_ms"] + 60, "first_byte_ms": last["vad_end_ms"] + 140,
                                   "playout": 40})
            last["eot_commit_ms"] = last["vad_end_ms"] + 150
            c.fault(turn["play_start_ms"], "POL.HARDSHIP", "payment requested after hardship, rushed, over crying", turn["turn_id"])
            t, gl = W.caller_line(group, "hardship")
            c.caller(t, gl, intent="hardship", rate=2.8)
        disclosure_turn(c, group, "hardship_ack", "tool", acts=["acknowledge_hardship"],
                        tools=[("flag_hardship", {"reason": "job_loss"})])
        t, gl = W.caller_line(group, "backchannel")
        c.caller(t, gl, intent="backchannel")
        t, gl = W.agent_line(group, "connecting")
        c.agent("closing", t, gl, acts=["transfer"], post_tools=[("transfer_to_human", {"queue": "hardship", "reason": "job loss"})])
        gold["new_rows"] = {"hardship": [{"reason": "job_loss"}], "sms_log": [sms_row]}
        gold["account"] = {"hardship_flag": True}
        gold["call_attempt"] = {"rpc": True, "disposition": "transfer_hardship"}

    elif flow == "F10":
        verify_prefix(c, group, dues_opt)
        t, gl = W.caller_line(group, "angry")
        c.caller(t, gl, intent="complaint", rate=4.6)
        coerce = rng.random() < min(p_fault, 0.1)
        if coerce:
            t, gl = W.agent_line(group, "threat")
            turn = c.agent("objection", t, gl, acts=["consequence_statement"])
            c.fault(turn["play_start_ms"], "POL.COERCE", "coercive consequence statement", turn["turn_id"])
            t, gl = W.caller_line(group, "angry_after_threat")
            c.caller(t, gl, intent="complaint")
        disclosure_turn(c, group, "angry_ok", "objection", acts=["deescalate"])
        t, gl = W.caller_line(group, "angry_after_ok")
        c.caller(t, gl, intent="closing")
        t, gl = W.agent_line(group, "closing")
        c.agent("closing", t, gl, acts=["goodbye"], post_tools=[("end_call", {"disposition": "complaint"})])
        gold["new_rows"] = {"sms_log": [sms_row]}
        gold["call_attempt"] = {"rpc": True, "disposition": "complaint"}

    elif flow == "F05":
        opener_turn(c, group, acc["first_name"], acc["last_name"])
        wrong = variant == "wrong_number"
        t, gl = W.caller_line(group, "wrong_number" if wrong else "third_party")
        c.caller(t, gl, intent="wrong_number" if wrong else "third_party")
        if faulty:
            a = amount_words(W, group, dues_opt)
            t, gl = W.agent_line(group, "third_party_disclose", amount=a)
            turn = c.agent("objection", t, gl, acts=["inform_dues"], entities=[{"type": "amount", "value": dues_opt["value"]}],
                           post_tools=[("end_call", {"disposition": "info"})])
            c.fault(turn["play_start_ms"], "POL.DISCLOSE", "dues stated to a third party before verification", turn["turn_id"])
        elif wrong:
            t, gl = W.agent_line(group, "wrong_number_ok")
            c.agent("closing", t, gl, acts=["goodbye"],
                    tools=[("mark_contact", {"outcome": "wrong_number", "relation": None}),
                           ("set_do_not_call", {"phone_e164": contact["phone_e164"], "scope": "all", "reason": "wrong number"})],
                    post_tools=[("end_call", {"disposition": "wrong_number"})])
        else:
            t, gl = W.agent_line(group, "third_party_ok")
            c.agent("closing", t, gl, acts=["goodbye"],
                    tools=[("mark_contact", {"outcome": "third_party", "relation": "family"})],
                    post_tools=[("end_call", {"disposition": "third_party"})])
        meta_conn = {"connect_outcome": "answered", "counts_toward_cap": True, "conversation": False}
        if wrong:
            gold["new_rows"] = {"dnc": [{"scope": "all"}]}
            gold["call_attempt"] = {"rpc": False, "disposition": "wrong_number"}
        else:
            gold["call_attempt"] = {"rpc": False, "disposition": "third_party"}

    elif flow == "F06":
        verify_prefix(c, group, dues_opt, guarantor=True, fault_unverified=faulty)
        t, gl = W.caller_line(group, "backchannel")
        c.caller(t, gl, intent="backchannel")
        disclosure_turn(c, group, None, "closing", acts=[])
        closing(c, group, "guarantor_informed")
        gold["new_rows"] = {"sms_log": [sms_row]}
        gold["call_attempt"] = {"rpc": True, "disposition": "guarantor_informed"}

    elif flow == "F07":
        c.amd = {"label": "voicemail", "confidence": round(rng.uniform(0.85, 0.97), 2), "decided_at_ms": rng.randint(2300, 2480),
                 "true_label": "voicemail"}
        greet = W.P["machine"]["voicemail"]
        c.caller(greet, None, start=600, dur=8400, source="machine", intent="voicemail_greeting")
        key = "voicemail_bad" if faulty else "voicemail_ok"
        a = amount_words(W, group, dues_opt)
        t, gl = W.agent_line(group, key, first=acc["first_name"], amount=a)
        post = [] if W.global_ed else [(W.sms_tool, {})]
        post += [("mark_contact", {"outcome": "voicemail", "relation": None}), ("end_call", {"disposition": "voicemail"})]
        ents = [{"type": "amount", "value": dues_opt["value"]}] if faulty else []
        turn = c.agent("greeting", t, gl, acts=["voicemail_message"] + (["inform_dues"] if faulty else []),
                       responds_to=None, start_after=9600, stages={"scripted": True}, post_tools=post, entities=ents)
        if faulty:
            c.fault(turn["play_start_ms"], "POL.DISCLOSE", "debt detail in a voicemail", turn["turn_id"])
        meta_conn = {"connect_outcome": "voicemail", "counts_toward_cap": True, "conversation": False}
        gold["new_rows"] = {} if W.global_ed else {"sms_log": [sms_row]}
        gold["call_attempt"] = {"rpc": False, "disposition": "voicemail"}

    elif flow == "F08":
        kind = rng.choice(["screening", "intercept", "ivr"])
        true = {"screening": W.C["amd_classes"][3], "intercept": W.C["amd_classes"][2], "ivr": "ivr"}[kind]
        greet = W.P["machine"][kind]
        mt = c.caller(greet, None, start=900, source="machine", intent="machine_prompt", rate=4.0)
        if faulty:
            c.amd = {"label": "human", "confidence": 0.71, "decided_at_ms": 2380, "true_label": true}
            t, gl = W.agent_line(group, "opener", first=acc["first_name"], last=acc["last_name"])
            turn = c.agent("greeting", t, gl, acts=["business_identity", "ai_disclosure", "recording_notice", "identity_question"],
                           responds_to=None, start_after=2390, stages={"scripted": True},
                           tools=[("lookup_account", {"phone_e164": contact["phone_e164"]})])
            c.fault(turn["play_start_ms"], "OUT.AMD", "machine answer treated as a human; opener played to it", turn["turn_id"])
            t, gl = W.agent_line(group, "amd_repeat")
            c.agent("greeting", t, gl, acts=["repeat"], responds_to=None, start_after=c.t + 1500, stages={"scripted": True},
                    post_tools=[("end_call", {"disposition": "no_response"})])
            meta_conn = {"connect_outcome": "answered", "counts_toward_cap": True, "conversation": True}
        else:
            c.amd = {"label": "ivr", "confidence": round(rng.uniform(0.8, 0.95), 2), "decided_at_ms": 2380, "true_label": true}
            c.agent("closing", None, acts=["hang_up"], responds_to=None, start_after=2400,
                    tools=[("mark_contact", {"outcome": "ivr", "relation": None})], stages={"scripted": True},
                    post_tools=[("end_call", {"disposition": "ivr"})])
            meta_conn = {"connect_outcome": "answered", "counts_toward_cap": True, "conversation": False}
        gold["call_attempt"] = {"rpc": False, "disposition": "ivr"}
    else:
        raise ValueError(flow)

    # latency tail label when a tool turn breaches its SLO (budget + 2,200 ms)
    slo_tool = c.budget + W.C["slo"]["turn_gap_add_ms"]["tool"]
    byid = {t["turn_id"]: t for t in c.turns}
    for t in c.turns:
        if t["speaker"] == "agent" and t.get("tool_calls") and t["play_start_ms"] and t["responds_to"]:
            ct = byid[t["responds_to"]]
            if ct.get("eot_commit_ms") and t["play_start_ms"] - ct["vad_end_ms"] > slo_tool:
                c.fault(t["play_start_ms"], "LAT.TAIL", f"tool-turn gap over {slo_tool} ms", t["turn_id"])
    carrier = rng.choice(W.C["carriers"])
    loc = {"area_code": tz, "address": tz}
    if W.global_ed:
        dial = {"attempts_7d_before": rng.randint(0, 5), **meta_conn}
    else:
        dial = {"connected_calls_today_before": rng.randint(0, 1), "connected_calls_week_before": rng.randint(0, 4),
                "connect_outcome": meta_conn["connect_outcome"]}
    meta = {"persona_or_real": "sim", "location_signals": loc, "carrier": carrier, "codec_chain": W.C["codec_chains"][carrier],
            "scenario": {"scenario_id": sid, "trial": trial, "flow": flow, "persona": pid, "language_group": group,
                         "variant": variant or None},
            "labeler": "rv-03"}
    return c.finish(meta, before, gold, dial=dial)


def generate_calls(W: World) -> list[dict]:
    rng = random.Random(W.C["seed"])
    levels = {sid: rng.choice(FAULT_LEVELS) for sid, *_ in SCENARIOS}
    calls = []
    seq = 0
    for sid, flow, pid, role, variant in SCENARIOS:
        for trial in range(1, TRIALS + 1):
            seq += 1
            calls.append(flow_call(W, sid, flow, pid, role, variant, trial, levels[sid], seq))
    # a second reviewer labels 30 calls (shared calls for reviewer agreement)
    r2 = random.Random(W.C["seed"] + 7)
    shared = r2.sample(range(len(calls)), 30)
    swap = {"TURN.BARGEIN": "TURN.TALKOVER", "POL.HARDSHIP": "TONE.PACE", "ENT.AMOUNT": "ENT.CONFIRM",
            "LAT.TAIL": None, "TURN.CUTOFF": "TURN.TALKOVER"}
    for i in sorted(shared):
        call = calls[i]
        first = call["labels"][0] if call["labels"] else None
        code = first["code"] if first else None
        if r2.random() < 0.2 and code in swap:
            code = swap[code]
        elif r2.random() < 0.04 and code is None:
            code = "TURN.TALKOVER"
        lab = {"labeler": "rv-11", "taxonomy": W.C["taxonomy"]["version"], "code": code or "NONE",
               "note": "second reviewer, shared calibration set", "turn_id": first["turn_id"] if first and code else None}
        if first is None:
            call["labels"].append({"labeler": "rv-03", "taxonomy": W.C["taxonomy"]["version"], "code": "NONE",
                                   "note": "no failure found", "turn_id": None})
        call["labels"].append(lab)
        call["review_set"] = "shared-30"
    for call in calls:
        if not call["labels"]:
            call["labels"].append({"labeler": "rv-03", "taxonomy": W.C["taxonomy"]["version"], "code": "NONE",
                                   "note": "no failure found", "turn_id": None})
        call.setdefault("review_set", "single")
    return calls


# ---------------------------------------------------------------------------------------
# incident traces T01-T10, S1, S2a, S2b (fixed times, identical in both editions)
# ---------------------------------------------------------------------------------------
INCIDENT_META = {
    # id: (date, local time, persona, flow, prompt, budget override, concurrency)
    "T01": ("2026-11-14", "18:41:07", "P01", "F01", "collections-v17", 300, 1150),
    "T02": ("2026-11-16", "12:20:44", "P02", "F02", "collections-v17", None, 900),
    "T03": ("2026-11-12", "11:05:12", "P05", "F05", "collections-v16", 300, 700),
    "T04": ("2026-11-13", "17:52:30", "P01", "F01", "collections-v17", 300, 2150),
    "T05": (None, "13:15:09", "P01", "F01", "collections-v17", 300, 1300),
    "T06": ("2026-11-11", "16:02:51", "P10", "F01", "collections-v16", None, 800),
    "T07": ("2026-11-10", "10:12:03", "P09", "F08", "collections-v16", 300, 600),
    "T08": ("2026-11-16", "15:40:18", "P12", "F01", "collections-v17", None, 1000),
    "T09": ("2026-11-18", "18:55:41", "P11", "F10", "collections-v17-p1", None, 1700),
    "T10": ("2026-11-17", "14:30:27", "P04", "F04", "collections-v17", None, 950),
    "S1": ("2026-11-17", "11:42:10", "P07", "F06", "collections-v17", None, 650),
    "S2a": ("2026-11-17", "10:05:00", "P08", "F07", "collections-v17", None, 500),
    "S2b": ("2026-11-12", "10:07:00", "P08", "F07", "collections-v16", None, 500),
}


ANCHORS = {"T02": ("start", None), "T04": ("start", 38710), "T05": ("start", 51200), "T08": ("end", 70500)}


def incident_call(W: World, iid: str, seq: int) -> dict:
    """Incidents with anchored times are built twice: once to measure, once with the slack
    spread evenly over the caller gaps, so the anchored events land on the bible's clock."""
    if iid not in ANCHORS:
        return _incident(W, iid, seq)[0]
    kind, target = ANCHORS[iid]
    margin = 700 if kind == "start" else 0
    k = None
    while True:
        _, c = _incident(W, iid, seq, k_fill=k)
        end, n = c.mark
        target = getattr(c, "target", None) or ANCHORS[iid][1]
        if end + margin <= target:
            break
        k = c.k_used - 1
        if k < 0:
            raise RuntimeError(f"{iid}: prefix too long for its anchor")
    eg = (target - margin - end) / max(1, n)
    rec, c2 = _incident(W, iid, seq, k_fill=c.k_used, extra_gap=eg)
    assert target - margin - 60 <= c2.mark[0] <= target - margin + 5, (iid, c2.mark, target)
    return rec


def _incident(W: World, iid: str, seq: int, k_fill: int | None = None, extra_gap: float = 0.0):
    date_s, time_s, pid, flow, prompt, budget_over, load = INCIDENT_META[iid]
    if date_s is None:  # T05: a Monday in the global log; the India twin's date is a Sunday
        date_s = "2026-11-16" if W.global_ed else "2026-11-15"
    rng = random.Random(f"{W.C['seed']}-{iid}")
    persona = W.persona[pid]
    group = persona["language_group"]
    campaign = W.book_campaign[persona["product"]]
    cinfo = W.C["campaigns"][campaign]
    budget = budget_over or cinfo["budget_ms"]
    thr = cinfo.get("threshold_before_fix", cinfo["threshold"]) if budget_over == 300 else cinfo["threshold"]
    tz = W.C["timezones"][persona["state"]]
    if iid == "T09" and W.global_ed:
        tz = "America/Chicago"
    off = W.C["utc_offsets"][tz]
    sign = 1 if off[0] == "+" else -1
    tzinfo = dt.timezone(sign * dt.timedelta(hours=int(off[1:3]), minutes=int(off[4:6])))
    d = dt.date.fromisoformat(date_s)
    hh, mm, ss = (int(x) for x in time_s.split(":"))
    started = dt.datetime(d.year, d.month, d.day, hh, mm, ss, tzinfo=tzinfo)
    inc = W.P["incidents"][iid[:2] if iid.startswith("S2") else iid]
    dues_value = inc.get("dues_value", W.P["dues_amounts"][0]["value"])
    dues_opt = next((o for o in W.P["dues_amounts"] if o["value"] == dues_value), None) or {
        "value": dues_value, "agent": {k: "" for k in W.P["agent"]}}
    acc, contact, extra = make_account(W, rng, persona, group, dues_value, d, account_id="A-55120931" if pid in ("P01", "P05", "P08") else None,
                                       postal=inc.get("zip"))
    if pid == "P01":
        acc["dpd"] = 4 if d.day <= 12 else 6
    if pid == "P07":
        contact["contact_id"] = "K-20417"
    call_id = f"{W.C['call_id_prefix']}-{date_s}-{'0871234' if iid == 'T01' else f'{8000000 + seq:07d}'}"
    c = Call(W, rng, call_id, acc, contact, campaign, started, tz, budget, cinfo["budget_asked_ms"], load,
             prompt=prompt, threshold=thr)
    c.extra = extra
    c.extra_gap = extra_gap
    c.k_used = 0
    c.attempt_id = f"AT-{70000000 + seq}"
    amtF, F = W.F["amount"], W.F
    sms_row = {"template": W.sms_template}
    gold = {"new_rows": {}, "account": {}, "call_attempt": {}}
    checks, judge_scores, labels = [], [], []
    conn = {"connect_outcome": "answered", "counts_toward_cap": True, "conversation": True}
    lab = lambda code, note, tid, who="rv-07": {"labeler": who, "taxonomy": W.C["taxonomy"]["version"], "code": code, "note": note, "turn_id": tid}
    before = None

    def fill_until(anchor: int):
        """Repeat-the-amount exchanges until the next anchored event is near."""
        while (c.t + 11000 < anchor) if k_fill is None else (c.k_used < k_fill):
            c.k_used += 1
            t, gl = W.caller_line(group, "repeat_ask")
            c.caller(t, gl, intent="repeat_request")
            a = amount_words(W, group, dues_opt)
            t, gl = W.agent_line(group, "dues", first=contact["first_name"], amount=a, notice="", notice_gloss="")
            c.agent("amount-quote", t, gl, acts=["inform_dues", "ask_payment"], entities=[{"type": "amount", "value": dues_value}])

    def prefix_to(anchor: int, dues_line: bool = True):
        verify_prefix(c, group, dues_opt)
        fill_until(anchor)

    if iid == "T01":
        before = snapshot(c.crm)
        opener_turn(c, group, contact["first_name"], contact["last_name"])
        c.turns[-1]["play_end_ms"] = 6400
        c.t = 6400
        t, gl = W.caller_line(group, "identity_yes")
        c.caller(t, gl, start=6800, dur=700, eot=7870, intent="identity_confirmed")
        t, gl = W.agent_line(group, "verify_ask")
        c.agent("verification", t, gl, acts=["verify_ask"], stages={"ttft": 520, "ttfb": 190, "playout": 50})
        c.turns[-1]["play_end_ms"] = 10900
        c.t = 10900
        postal = contact[F["postal_code"]]
        c.caller(W.digits_words(group, postal), start=11300, dur=1200, eot=12870, intent="verify_answer",
                 ref_entities=[{"type": "postal_code", "value": postal}])
        c.agent("amount-quote", inc["dues"], None, acts=(["debt_notice"] if W.global_ed else []) + ["inform_dues", "ask_payment"],
                tools=[("verify_identity", {"contact_id": contact["contact_id"], "method": F["postal_code"], "value": postal}),
                       ("get_dues", {})],
                entities=[{"type": "amount", "value": dues_value}],
                stages={"ttft": 470, "tool_ms": [200, 250], "ttfb": 210, "playout": 60})
        c.turns[-1]["play_end_ms"] = 17800
        c.t = 17800
        ent_ref = [{"type": "amount", "value": inc["said"]}, {"type": "date", "value": inc["date"]}]
        c.caller(inc["ref"], start=18220, dur=21940 - 18220, eot=22310, stt=inc["stt"], intent="promise",
                 ref_entities=ent_ref, stt_entities=[{"type": "amount", "value": inc["stored"]}, ent_ref[1]], stt_conf=0.78)
        c.turns[-1]["stt_final"]["t_ms"] = 22180
        c.turns[-1]["stt_partials"] = [{"t_ms": 18710, "text": " ".join(inc["stt"].split()[:3])}]
        t7 = c.agent("tool", inc["noted"], None, acts=["inform_ptp"],
                     tools=[("record_promise_to_pay", {amtF: inc["stored"], "ptp_date": inc["date"], "channel": "link", "readback_confirmed": False})],
                     entities=[{"type": "amount", "value": inc["stored"]}, {"type": "date", "value": inc["date"]}],
                     stages={"request_ms": 22320, "first_token_ms": 22990, "cached_tokens": 1840, "tool_hops": [20], "tool_ms": [470],
                             "tts_hop": 20, "first_byte_ms": 23690, "playout": 50})
        t7["play_end_ms"] = 27900
        c.t = 27900
        c.caller(inc["backchannel"], start=28120, dur=780, intent="backchannel")
        disclosure_turn(c, group, "ptp_done", "tool", acts=["inform_link"],
                        tools=[("send_payment_link", {amtF: inc["stored"], "channel": "sms"})])
        closing(c, group, "ptp")
        checks = [{"id": "C12", "result": "fail", "evidence_turns": [6, 7]}]
        labels = [lab("ENT.AMOUNT", "amount word substituted; PTP written before read-back", 6)]
        gold["new_rows"] = {"ptps": [{amtF: inc["said"], "ptp_date": inc["date"], "readback_confirmed": True}],
                            "sms_log": [{"template": "payment_link"}, sms_row]}
        gold["call_attempt"] = {"rpc": True, "disposition": "ptp"}

    elif iid == "T02":
        before = snapshot(c.crm)
        opener_turn(c, group, contact["first_name"], contact["last_name"])
        c.caller(*W.caller_line(group, "identity_yes"), intent="identity_confirmed")
        c.agent("verification", *W.agent_line(group, "verify_ask"), acts=["verify_ask"])
        postal = contact[F["postal_code"]]
        spoken = W.digits_words(group, postal)
        zdur = c.speech_ms(spoken, 3.8)
        c.target = 29350 - zdur
        c.mark = (c.t, c.n_callers)
        c.extra_gap = 0.0
        c.caller(spoken, None, start=29350 - zdur, dur=zdur, eot=29800, intent="verify_answer",
                 ref_entities=[{"type": "postal_code", "value": postal}])
        txt, gl = text_of(inc["dues"])
        t5 = c.agent("amount-quote", txt, gl, acts=["inform_dues", "ask_payment"], entities=[{"type": "amount", "value": dues_value}],
                     tools=[("verify_identity", {"contact_id": contact["contact_id"], "method": F["postal_code"], "value": postal}),
                            ("get_dues", {})],
                     stages={"request_ms": 29810, "first_token_ms": 30000, "tool_ms": [190, 170], "tts_hop": 10,
                             "first_byte_ms": 30450, "playout": 50},
                     barge={"t_ms": 33000, "tts_stop_ms": 33060, "stop_latency_ms": 900})
        c.t = 33060
        txt, gl = text_of(inc["claim"])
        ct = c.caller(txt, gl, start=32160, dur=34980 - 32160, eot=35280, intent="already_paid")
        txt, gl = text_of(inc["push"])
        c.agent("objection", txt, gl, acts=["ask_payment"],
                stages={"request_ms": 34300, "first_token_ms": 34900, "tts_request_ms": 35290, "first_byte_ms": 35370, "playout": 50})
        c.caller(*W.caller_line(group, "already_paid"), intent="already_paid")
        disclosure_turn(c, group, None, "closing", acts=[])
        closing(c, group, "refused")
        checks = [{"id": "C08", "result": "fail", "evidence_turns": [ct["turn_id"], ct["turn_id"] + 1]}]
        labels = [lab("TURN.BARGEIN", "900 ms talk-over; plan not revised after the already-paid claim", t5["turn_id"])]
        gold["new_rows"] = {"grievances": [{"category": "already_paid"}], "sms_log": [sms_row]}
        gold["account"] = {"recovery_hold": True}
        gold["call_attempt"] = {"rpc": True, "disposition": "dispute"}

    elif iid == "T03":
        before = snapshot(c.crm)
        c.amd = {"label": "human", "confidence": 0.93, "decided_at_ms": 2380, "true_label": "human"}
        t1 = c.agent("greeting", inc["opener_v16"], None, acts=["business_identity", "debt_detail"],
                     tools=[("lookup_account", {"phone_e164": contact["phone_e164"]})], responds_to=None, start_after=2380,
                     stages={"scripted": True, "tool_ms": [120], "ttfb": 40, "playout": 50}, play_start=2600,
                     entities=[{"type": "product", "value": acc["product_code"]}, {"type": "dpd", "value": 4}])
        t1["play_end_ms"] = 8400
        c.t = 8400
        c.caller(inc["reply"], start=9100, dur=1300, eot=10700, intent="third_party")
        t3 = c.agent("objection", inc["disclose"], None, acts=["inform_dues", "ask_payment"],
                     entities=[{"type": "amount", "value": dues_value}],
                     stages={"ttft": 260, "ttfb": 60, "playout": 20}, play_start=11050,
                     post_tools=[("end_call", {"disposition": "info"})])
        checks = [{"id": "C03", "result": "fail", "evidence_turns": [1]}, {"id": "C04", "result": "fail", "evidence_turns": [1, 3]},
                  {"id": "C05", "result": "fail", "evidence_turns": [1, 3]}]
        labels = [lab("POL.DISCLOSE", "debt details told to a family member before verification; no AI or recording notice", 1)]
        conn["conversation"] = False
        gold["call_attempt"] = {"rpc": False, "disposition": "third_party"}

    elif iid == "T04":
        before = snapshot(c.crm)
        verify_prefix(c, group, dues_opt)
        fill_until(38710)
        c.mark = (c.t, c.n_callers)
        c.extra_gap = 0.0
        ask = c.caller(inc["ask"], None, start=40210 - 1500, dur=1500, eot=40590, intent="total_request")
        t_main = c.agent("tool", inc["reply"], None, acts=["inform_dues"], entities=[{"type": "amount", "value": dues_value}],
                         tools=[("get_dues", {}), ("check_payment_status", {"since": "2026-10-01"})],
                         stages={"request_ms": 40600, "first_token_ms": 41820, "tool_hops": [10, 10], "tool_ms": [860, 1250],
                                 "tts_hop": 10, "first_byte_ms": 44150, "playout": 50})
        hello = c.caller(inc["hello"], None, start=43200, dur=380, eot=43580, intent="presence_check")
        t_dup = c.agent("objection", inc["dup"], None, acts=["inform_dues"], entities=[{"type": "amount", "value": dues_value}],
                        responds_to=hello, play_start=44900,
                        stages={"request_ms": 43590, "first_token_ms": 44380, "tts_request_ms": 44390, "first_byte_ms": 44850})
        c.turns.sort(key=lambda x: (x["play_start_ms"] if x["speaker"] == "agent" and x["play_start_ms"] else x.get("vad_start_ms") or 0))
        ren = {}
        for i, t in enumerate(c.turns, 1):
            ren[t["turn_id"]] = i
        for t in c.turns:
            t["turn_id"] = ren[t["turn_id"]]
            if t["speaker"] == "agent" and t["responds_to"]:
                t["responds_to"] = ren[t["responds_to"]]
        c.t = max(t_main["play_end_ms"], t_dup["play_end_ms"])
        c.caller(*W.caller_line(group, "backchannel"), intent="backchannel")
        disclosure_turn(c, group, None, "closing", acts=[])
        c.caller(*W.caller_line(group, "bye"), intent="closing")
        c.agent("closing", *W.agent_line(group, "closing"), acts=["goodbye"], post_tools=[("end_call", {"disposition": "info"})])
        labels = [lab("LAT.TAIL", "3,990 ms tool-turn gap: slow first token, sequential tools, no filler", t_main["turn_id"]),
                  lab("LAT.DUP", "the hello became a new turn; second reply over the first", t_dup["turn_id"], "rv-07")]
        gold["new_rows"] = {"sms_log": [sms_row]}
        gold["call_attempt"] = {"rpc": True, "disposition": "info"}

    elif iid == "T05":
        before = snapshot(c.crm)
        verify_prefix(c, group, dues_opt)
        fill_until(51200)
        c.mark = (c.t, c.n_callers)
        c.extra_gap = 0.0
        part1_text = inc["part1"]
        p1 = c.caller(part1_text, None, start=51200, dur=52950 - 51200, eot=53250, intent="promise_partial")
        p1["pauses"] = [{"start_ms": 52950, "end_ms": 53670, "label": "hold", "content_tag": "date"}]
        a = c.agent("objection", inc["push"], None, acts=["ask_payment"],
                    stages={"request_ms": 53260, "first_token_ms": 53700, "tts_request_ms": 53710, "first_byte_ms": 53850, "playout": 50})
        p2 = c.caller(inc["part2"], None, start=53670, intent="promise",
                      ref_entities=[{"type": "date", "value": "2026-12-05"}])
        c.t = max(a["play_end_ms"], p2["vad_end_ms"])
        dopt = {"value": 0}
        rep_text, rep_gloss = W.caller_line(group, "repeat_date", date=inc["part2"].split(",")[0].split(" ko")[0], date_gloss="fifth")
        c.caller(rep_text, rep_gloss, intent="promise", ref_entities=[{"type": "date", "value": "2026-12-05"}])
        lang = W.agent_lang(group)
        d_words = "December fifth" if lang == "en" and W.global_ed else ("paanch December" if not W.global_ed and lang == "hinglish" else ("fifth December" if not W.global_ed else "el cinco de diciembre"))
        a_amt = amount_words(W, group, dues_opt)
        c.agent("readback", *W.agent_line(group, "readback", amount=a_amt, date=(d_words, "December fifth")), acts=["readback"],
                entities=[{"type": "amount", "value": dues_value}, {"type": "date", "value": "2026-12-05"}])
        c.caller(*W.caller_line(group, "yes"), intent="confirm_yes")
        disclosure_turn(c, group, "ptp_done", "tool", acts=["inform_link"],
                        tools=[("record_promise_to_pay", {amtF: dues_value, "ptp_date": "2026-12-05", "channel": "link", "readback_confirmed": True}),
                               ("send_payment_link", {amtF: dues_value, "channel": "sms"})])
        closing(c, group, "ptp")
        labels = [lab("TURN.CUTOFF", "turn closed at 300 ms of silence in a 720 ms pause before the date", a["turn_id"])]
        gold["new_rows"] = {"ptps": [{amtF: dues_value, "ptp_date": "2026-12-05", "readback_confirmed": True}],
                            "sms_log": [{"template": "payment_link"}, sms_row]}
        gold["call_attempt"] = {"rpc": True, "disposition": "ptp"}

    elif iid == "T06":
        before = snapshot(c.crm)
        verify_prefix(c, group, dues_opt)
        txt, gl = text_of(inc["llm"])
        heard, hgl = text_of(inc["heard"])
        c.caller(*W.caller_line(group, "repeat_ask"), intent="repeat_request")
        c.agent("amount-quote", txt, gl, acts=["inform_dues", "inform_due_date"],
                entities=[{"type": "amount", "value": dues_value}, {"type": "date", "value": inc["stored_date"]}],
                audio_reading=heard + (f" [gloss: {hgl}]" if hgl else ""))
        txt, gl = text_of(inc["ref"])
        ct = c.caller(txt, gl, intent="confirm_yes", ref_entities=[{"type": "date", "value": inc["heard_date"]}])
        disclosure_turn(c, group, "ptp_done", "tool", acts=["inform_link"],
                        tools=[("record_promise_to_pay", {amtF: dues_value, "ptp_date": inc["stored_date"], "channel": "link", "readback_confirmed": True}),
                               ("send_payment_link", {amtF: dues_value, "channel": "sms"})])
        closing(c, group, "ptp")
        labels = [lab("ENT.DATE", "numeric date read in the other field order by the TTS locale", ct["turn_id"] - 1)]
        gold["new_rows"] = {"ptps": [{amtF: dues_value, "ptp_date": inc["stored_date"], "readback_confirmed": True}],
                            "sms_log": [{"template": "payment_link"}, sms_row]}
        gold["call_attempt"] = {"rpc": True, "disposition": "ptp"}
        gold["note"] = "the CRM diff passes; only a spoken-entity round-trip check sees what the borrower heard"

    elif iid == "T07":
        before = snapshot(c.crm)
        c.caller(inc["machine"], None, start=900, dur=6800, source="machine", intent="machine_prompt")
        c.amd = {"label": "human", "confidence": 0.71, "decided_at_ms": 2380, "true_label": inc["amd_true"]}
        t1 = c.agent("greeting", inc["opener"], None, acts=["business_identity", "ai_disclosure", "recording_notice", "identity_question"],
                     tools=[("lookup_account", {"phone_e164": contact["phone_e164"]})], responds_to=None, start_after=2390,
                     stages={"scripted": True, "tool_ms": [110], "ttfb": 50, "playout": 40}, play_start=2600)
        t1["play_end_ms"] = 13600
        c.t = 13600
        c.agent("greeting", inc["repeat"], None, acts=["repeat"], responds_to=None, start_after=13700,
                stages={"scripted": True, "ttfb": 150, "playout": 50}, play_start=13900,
                post_tools=[])
        c.t = 20990
        c.turns[-1]["tool_calls"].append(c.tool("end_call", {"disposition": "no_response"}, 21000, 21020))
        labels = [lab("OUT.AMD", "machine prompt labelled human (0.71); opener played to it; attempt logged as a conversation", 2)]
        gold["call_attempt"] = {"rpc": False, "disposition": "ivr"}

    elif iid == "T08":
        before = snapshot(c.crm)
        verify_prefix(c, group, dues_opt)
        fill_until(70500 - 26000)
        txt, gl = text_of(inc["ref1"])
        c.caller(txt, gl, stt=inc["stt1"], intent="promise", lang_tags=[W.tag_default if W.global_ed else W.tag_other] * len(words(inc["stt1"])),
                 stt_conf=0.51, ref_entities=[{"type": "date", "value": "2026-11-23" if W.global_ed else "2026-12-09"}], stt_entities=[])
        c.agent("objection", inc["ask1"], None, acts=["clarify"])
        txt, gl = text_of(inc["ref2"])
        c.caller(txt, gl, stt=inc["stt2"], intent="promise", stt_conf=0.55,
                 ref_entities=[{"type": "date", "value": "2026-11-23" if W.global_ed else "2026-12-09"}], stt_entities=[])
        ask2 = c.agent("objection", inc["ask2"], None, acts=["clarify"])
        txt, gl = text_of(inc["ref3"])
        c.caller(txt, gl, intent="hangup")
        c.mark = (c.t, c.n_callers)
        c.extra_gap = 0.0
        c.t = max(c.t, 70990)
        hang = c.agent("closing", None, acts=[], responds_to=None, start_after=70990, stages={"scripted": True})
        hang["tool_calls"].append(c.tool("end_call", {"disposition": "caller_hangup"}, 71000, 71010))
        labels = [lab("STT.LID", "STT language identification locked mid-utterance; three clarifications; hang-up at 71 s", 6)]
        gold["new_rows"] = {"ptps": [{amtF: dues_value, "ptp_date": "2026-11-23" if W.global_ed else "2026-12-09", "readback_confirmed": True}],
                            "sms_log": [{"template": "payment_link"}, sms_row]}
        gold["call_attempt"] = {"rpc": True, "disposition": "ptp"}

    elif iid == "T09":
        before = snapshot(c.crm)
        verify_prefix(c, group, dues_opt)
        c.caller(inc["angry"], None, intent="complaint", rate=4.6)
        th = c.agent("objection", inc["threat"], None, acts=["consequence_statement"])
        c.caller(inc["reply"], None, intent="complaint")
        disclosure_turn(c, group, "angry_ok", "objection", acts=["deescalate"])
        c.caller(*W.caller_line(group, "angry_after_ok"), intent="closing")
        c.agent("closing", *W.agent_line(group, "closing"), acts=["goodbye"], post_tools=[("end_call", {"disposition": "complaint"})])
        checks = [{"id": "C07", "result": "fail", "evidence_turns": [th["turn_id"]]}]
        labels = [lab("POL.COERCE", "coercive consequence statement on the angry path", th["turn_id"])]
        gold["new_rows"] = {"sms_log": [sms_row]}
        gold["call_attempt"] = {"rpc": True, "disposition": "complaint"}

    elif iid == "T10":
        before = snapshot(c.crm)
        verify_prefix(c, group, dues_opt)
        txt, gl = text_of(inc["ref"])
        hc = c.caller(txt, gl, intent="hardship", tags=["crying, 4 s"], rate=2.4)
        hc["eot_commit_ms"] = hc["vad_end_ms"] + 150
        small = W.P["small_amounts"][0]
        push = c.agent("objection", inc["push"], None, acts=["ask_payment"], rate=5.9,
                       entities=[{"type": "amount", "value": small["value"]}],
                       stages={"request_ms": hc["vad_end_ms"] - 700, "first_token_ms": hc["vad_end_ms"] - 120,
                               "tts_request_ms": hc["vad_end_ms"] + 60, "first_byte_ms": hc["vad_end_ms"] + 140, "playout": 40})
        c.caller(*W.caller_line(group, "hardship"), intent="hardship", rate=2.6)
        disclosure_turn(c, group, "hardship_ack", "tool", acts=["acknowledge_hardship"], tools=[("flag_hardship", {"reason": "job_loss"})])
        c.caller(*W.caller_line(group, "backchannel"), intent="backchannel")
        c.agent("closing", *W.agent_line(group, "connecting"), acts=["transfer"],
                post_tools=[("transfer_to_human", {"queue": "hardship", "reason": "job loss"})])
        checks = [{"id": "C09", "result": "fail", "evidence_turns": [hc["turn_id"], push["turn_id"]]}]
        judge_scores = [{"judge": "transcript-judge-v2", "dimension": "empathy", "result": "pass", "turn_id": push["turn_id"]},
                        {"judge": "transcript-judge-v2", "dimension": "policy", "result": "pass", "turn_id": push["turn_id"]}]
        labels = [lab("POL.HARDSHIP", "payment requested after hardship; rushed (5.9 syllables/s) and started over the sob", push["turn_id"], "rv-02"),
                  lab("POL.HARDSHIP", "empathy fail; C09 fail", push["turn_id"], "rv-05")]
        gold["new_rows"] = {"hardship": [{"reason": "job_loss"}], "sms_log": [sms_row]}
        gold["account"] = {"hardship_flag": True}
        gold["call_attempt"] = {"rpc": True, "disposition": "transfer_hardship"}

    elif iid == "S1":
        before = snapshot(c.crm)
        c.amd = {"label": "human", "confidence": 0.94, "decided_at_ms": 2380, "true_label": "human"}
        c.agent("greeting", inc["opener"], None, acts=["business_identity", "ai_disclosure", "recording_notice", "identity_question"],
                tools=[("lookup_account", {"phone_e164": contact["phone_e164"]})], responds_to=None, start_after=2380,
                stages={"scripted": True})
        c.caller(inc["reply"], None, intent="identity_confirmed")
        c.agent("verification", inc["ask"], None, acts=["verify_ask"])
        c.caller(inc["zip_words"], None, intent="verify_answer", ref_entities=[{"type": "postal_code", "value": inc["zip"]}])
        c.agent("amount-quote", inc["dues"], None, acts=(["debt_notice"] if W.global_ed else []) + ["inform_dues"],
                tools=[("verify_identity", {"contact_id": "K-20417", "method": F["postal_code"], "value": inc["zip"]}), ("get_dues", {})],
                entities=[{"type": "amount", "value": dues_value}])
        c.caller(*W.caller_line(group, "backchannel"), intent="backchannel")
        disclosure_turn(c, group, None, "closing", acts=[])
        closing(c, group, "guarantor_informed")
        gold["new_rows"] = {"sms_log": [sms_row]}
        gold["call_attempt"] = {"rpc": True, "disposition": "guarantor_informed"}

    elif iid in ("S2a", "S2b"):
        before = snapshot(c.crm)
        c.amd = {"label": "voicemail", "confidence": 0.95, "decided_at_ms": 2400, "true_label": "voicemail"}
        c.caller(W.P["machine"]["voicemail"], None, start=600, dur=8400, source="machine", intent="voicemail_greeting")
        ok = iid == "S2a"
        post = [] if (W.global_ed or not ok) else [(W.sms_tool, {})]
        post += [("mark_contact", {"outcome": "voicemail", "relation": None}), ("end_call", {"disposition": "voicemail"})]
        vt = c.agent("greeting", inc["ok" if ok else "bad"], None,
                     acts=["voicemail_message"] + ([] if ok else ["inform_dues", "debt_detail"]), responds_to=None,
                     start_after=9600, stages={"scripted": True}, post_tools=post,
                     entities=[] if ok else [{"type": "amount", "value": dues_value}])
        if not ok:
            checks = [{"id": "C04", "result": "fail", "evidence_turns": [vt["turn_id"]]}]
            labels = [lab("POL.DISCLOSE", "debt detail in a voicemail", vt["turn_id"])]
        else:
            checks = [{"id": "C04", "result": "pass", "evidence_turns": [vt["turn_id"]]}]
        conn = {"connect_outcome": "voicemail", "counts_toward_cap": True, "conversation": False}
        gold["new_rows"] = {} if W.global_ed else {"sms_log": [sms_row]}
        gold["call_attempt"] = {"rpc": False, "disposition": "voicemail"}

    if not labels:
        labels = [{"labeler": "rv-07", "taxonomy": W.C["taxonomy"]["version"], "code": "NONE", "note": "worked example, no failure", "turn_id": None}]
    carrier = W.C["carriers"][1]
    tzsig = {"area_code": tz, "address": tz}
    if W.global_ed:
        dial = {"attempts_7d_before": 2, **conn}
    else:
        dial = {"connected_calls_today_before": 0, "connected_calls_week_before": 2, "connect_outcome": conn["connect_outcome"]}
    meta = {"persona_or_real": "real", "location_signals": tzsig, "carrier": carrier, "codec_chain": W.C["codec_chains"][carrier],
            "scenario": {"incident": iid, "title": inc["title"], "flow": flow, "persona": pid, "language_group": group}}
    return c.finish(meta, before, gold, checks=checks, judge_scores=judge_scores, labels=labels, dial=dial), c


# ---------------------------------------------------------------------------------------
# entity pairs, pauses, judge labels, production sample
# ---------------------------------------------------------------------------------------
CONDITIONS = ["wideband_16k", "g711_clean", "amr_g711", "amr_g711_loss5", "noise_10db"]
SYS_RATES = {  # (non-entity word error prob, amount confusion prob)
    "sys_a": {"wideband_16k": (0.06, 0.03), "g711_clean": (0.07, 0.04), "amr_g711": (0.08, 0.05), "amr_g711_loss5": (0.10, 0.07), "noise_10db": (0.10, 0.06)},
    "sys_b": {"wideband_16k": (0.02, 0.06), "g711_clean": (0.03, 0.08), "amr_g711": (0.04, 0.10), "amr_g711_loss5": (0.05, 0.12), "noise_10db": (0.05, 0.11)},
    "sys_c": {"wideband_16k": (0.05, 0.01), "g711_clean": (0.07, 0.06), "amr_g711": (0.09, 0.15), "amr_g711_loss5": (0.12, 0.20), "noise_10db": (0.11, 0.17)},
}


def noisy(W: World, rng: random.Random, text: str, protect: set, p: float) -> str:
    subs = W.P["stt_noise"]["subs"]
    out = []
    for w in text.split():
        core = re.sub(r"[^\w'-]", "", w.lower())
        if core in protect or rng.random() >= p:
            out.append(w)
            continue
        r = rng.random()
        if r < 0.6 and core in subs:
            out.append(subs[core])
        elif r < 0.85:
            continue  # deletion
        else:
            out.append(w)
            out.append(rng.choice(W.P["stt_noise"]["fillers"]))
    return " ".join(out)


def generate_entity_pairs(W: World, t01: dict) -> list[dict]:
    rng = random.Random(W.C["seed"] + 11)
    groups = W.C["language_groups"]
    speakers = [(f"spk-{i:03d}", groups[i % 3]) for i in range(1, 91)]
    pairs = []
    inc = W.P["incidents"]["T01"]
    pairs.append({"pair_id": "T01", "speaker_id": "spk-T01", "language_group": W.persona["P01"]["language_group"],
                  "condition": "amr_g711", "call_date": "2026-11-14", "kind": "promise", "reference": inc["ref"],
                  "hyps": {"sys_a": inc["stt"], "sys_b": inc["ref"].replace(",", ""), "sys_c": inc["ref"].replace(",", "")},
                  "ref_entities": [{"type": "amount", "value": inc["said"]}, {"type": "date", "value": inc["date"]}],
                  "hyp_entities": {"sys_a": [{"type": "amount", "value": inc["stored"]}, {"type": "date", "value": inc["date"]}],
                                   "sys_b": [{"type": "amount", "value": inc["said"]}, {"type": "date", "value": inc["date"]}],
                                   "sys_c": [{"type": "amount", "value": inc["said"]}, {"type": "date", "value": inc["date"]}]}})
    for n in range(1, 600):
        spk, group = speakers[rng.randrange(len(speakers))]
        cond = CONDITIONS[n % len(CONDITIONS)]
        kind = "promise" if rng.random() < 0.8 else "confirm"
        if kind == "promise":
            popt = rng.choice(W.P["promise_amounts"])
            dopt = rng.choice(W.P["promise_dates"])
            amt_say, date_say = popt["say"][group], dopt["say"][group]
            ref, _ = W.caller_line(group, "promise", amount=amt_say, date=date_say, amount_gloss="", date_gloss="")
            ref_ent = [{"type": "amount", "value": popt["value"]}, {"type": "date", "value": dopt["iso"]}]
            protect = set(words(amt_say)) | set(words(date_say))
            hyps, hyp_ent = {}, {}
            for sysname, table in SYS_RATES.items():
                pw, pa = table[cond]
                conf = rng.random() < pa
                use = popt["confusable"] if conf else popt
                h_amt = use["say"][group]
                h, _ = W.caller_line(group, "promise", amount=h_amt, date=date_say, amount_gloss="", date_gloss="")
                hyps[sysname] = noisy(W, rng, h.replace(",", ""), set(words(h_amt)) | protect, pw)
                hyp_ent[sysname] = [{"type": "amount", "value": use["value"]}, {"type": "date", "value": dopt["iso"]}]
        else:
            ref, _ = W.caller_line(group, "yes")
            ref_ent = [{"type": "confirmation", "value": "yes"}]
            hyps, hyp_ent = {}, {}
            for sysname, table in SYS_RATES.items():
                pw, pa = table[cond]
                if rng.random() < pa / 2:
                    h, _ = W.caller_line(group, "backchannel")
                    hyp_ent[sysname] = [{"type": "confirmation", "value": "backchannel"}]
                else:
                    h = ref
                    hyp_ent[sysname] = [{"type": "confirmation", "value": "yes"}]
                hyps[sysname] = noisy(W, rng, h.replace(",", ""), set(), pw)
        pairs.append({"pair_id": f"EP{n:03d}", "speaker_id": spk, "language_group": group, "condition": cond,
                      "call_date": "2026-11-18", "kind": kind, "reference": ref, "hyps": hyps,
                      "ref_entities": ref_ent, "hyp_entities": hyp_ent})
    return pairs


def generate_pauses(W: World) -> list[dict]:
    rng = random.Random(W.C["seed"] + 13)
    gf = {W.C["group_roles"]["english"]: 1.0, W.C["group_roles"]["native"]: 1.18, W.C["group_roles"]["mixed"]: 1.08}
    tag_med = {"date": 320, "amount": 300, "dispute": 250, "small_talk": 180, "none": 200}
    camps = list(W.C["campaigns"])
    rows = []
    n = 0
    for group in W.C["language_groups"]:
        for i in range(400):
            n += 1
            camp = camps[i % len(camps)]
            book = W.C["campaigns"][camp]["book"]
            older = book in ("SDL", "MFI")
            state = rng.choice(["default", "default", "amount_asked", "date_asked"])
            label = "hold" if rng.random() < 0.42 else "end"
            if state == "date_asked":
                tag = rng.choice(["date", "date", "date", "none"])
            elif state == "amount_asked":
                tag = rng.choice(["amount", "amount", "amount", "none"])
            else:
                tag = rng.choice(["date", "amount", "dispute", "small_talk", "none", "small_talk"])
            if label == "hold":
                med = tag_med[tag] * gf[group] * (1.15 if older else 1.0)
                pause = lognorm(rng, med, med * 1.9, 60, 2500)
                pa = min(0.98, max(0.02, rng.gauss(0.55 if tag in ("date", "amount") else 0.30, 0.15)))
                pb = min(0.98, max(0.02, rng.gauss(0.45 if tag in ("date", "amount") else 0.25, 0.12)))
            else:
                pause = lognorm(rng, 1700, 3200, 700, 6000)
                pa = min(0.98, max(0.02, rng.gauss(0.22, 0.14)))
                pb = min(0.98, max(0.02, rng.gauss(0.18, 0.10)))
            rows.append({"pause_id": f"PZ{n:05d}", "call_id": f"PC-{rng.randint(100000, 999999)}", "turn_id": rng.randint(2, 14),
                         "language_group": group, "campaign": camp, "call_state": state, "content_tag": tag,
                         "label": label, "pause_ms": pause, "model_a_hold_prob": round(pa, 3), "model_b_hold_prob": round(pb, 3)})
    t05_camp = W.book_campaign[W.persona["P01"]["product"]]
    rows.append({"pause_id": "T05-p1", "call_id": "T05", "turn_id": 0, "language_group": W.persona["P01"]["language_group"],
                 "campaign": t05_camp, "call_state": "date_asked", "content_tag": "date", "label": "hold", "pause_ms": 720,
                 "model_a_hold_prob": 0.41, "model_b_hold_prob": 0.38})
    return rows


def generate_judge_labels(W: World) -> list[dict]:
    rng = random.Random(W.C["seed"] + 17)
    rows = []
    vgroup = W.C["judge_validation_group"]
    native = W.C["group_roles"]["native"]
    for gi, group in enumerate(W.C["language_groups"]):
        for dim in ("C07", "TONE.PACE"):
            if dim == "C07" and group == vgroup:
                cells = [(True, True)] * 15 + [(True, False)] * 3 + [(False, True)] * 6 + [(False, False)] * 96
                rng.shuffle(cells)
            else:
                prev = rng.uniform(0.10, 0.18) if dim == "C07" else rng.uniform(0.15, 0.25)
                cells = []
                for _ in range(120):
                    h = rng.random() < prev
                    rec = rng.uniform(0.80, 0.93) if dim == "C07" else 0.70
                    j = (rng.random() < rec) if h else (rng.random() < 0.06)
                    cells.append((h, j))
            for k, (h, tj) in enumerate(cells, 1):
                if dim == "TONE.PACE":
                    if group == vgroup:
                        bj = (rng.random() < 0.92) if h else (rng.random() < 0.05)
                    elif group == native:
                        bj = (rng.random() < 0.55) if h else (rng.random() < 0.12)
                    else:
                        bj = (rng.random() < 0.80) if h else (rng.random() < 0.07)
                else:
                    bj = (rng.random() < 0.88) if h else (rng.random() < 0.05)
                ra = h if rng.random() < 0.95 else (not h)
                rb = h if rng.random() < 0.95 else (not h)
                rows.append({"call_id": f"JV-{gi}{'C' if dim == 'C07' else 'P'}{k:03d}", "language_group": group, "dimension": dim,
                             "rater_a": ra, "rater_b": rb, "human_label": h, "transcript_judge": tj, "blueprint_judge": bj})
    return rows


def generate_production(W: World) -> list[dict]:
    rng = random.Random(W.C["seed"] + 19)
    C = W.C
    amd = C["amd_classes"]  # human, voicemail, x, y, ivr, silence
    true_mix = [("human", 0.88), (amd[1], 0.07), (amd[2], 0.015), (amd[3], 0.015), (amd[4], 0.012), (amd[5], 0.008)]
    confusion = {"human": [("human", 0.97), (amd[1], 0.02), (amd[5], 0.01)],
                 amd[1]: [(amd[1], 0.90), ("human", 0.08), (amd[5], 0.02)],
                 amd[2]: [(amd[2], 0.60), ("human", 0.25), (amd[1], 0.15)],
                 amd[3]: [(amd[3], 0.70), ("human", 0.20), (amd[1], 0.10)],
                 amd[4]: [(amd[4], 0.85), ("human", 0.10), (amd[1], 0.05)],
                 amd[5]: [(amd[5], 0.80), ("human", 0.15), (amd[1], 0.05)]}
    strata = [("angry", 1 / 600), ("complaint", 0.006), ("dispute", 0.012), ("hardship", 0.008),
              ("stop_request", 0.005), ("window_edge", 0.04 - 1 / 600 - 0.006 - 0.012 - 0.008 - 0.005)]

    def pick(pairs):
        r, acc = rng.random(), 0.0
        for v, p in pairs:
            acc += p
            if r < acc:
                return v
        return pairs[-1][0]
    camps = list(C["campaigns"])
    rows = []
    for i in range(1, 4001):
        camp = camps[min(int(rng.random() ** 1.6 * 5), 4)]
        book = C["campaigns"][camp]["book"]
        langs = C["campaigns"][camp]["languages"]
        group = rng.choice([g for g in langs if g in C["language_groups"]] or C["language_groups"])
        lo, hi = C["calling_window"]["by_product"].get(book, C["calling_window"]["default"])
        lo_m, hi_m = int(lo[:2]) * 60 + int(lo[3:]), int(hi[:2]) * 60 + int(hi[3:])
        minute = rng.randint(lo_m, hi_m - 1)
        u = rng.random()
        if u < 0.52:
            outcome = "answered"
            true = pick(true_mix)
            if true == amd[1]:
                outcome = "voicemail"
        else:
            outcome = pick([("unanswered", 0.80), ("busy", 0.15), ("out_of_service", 0.05)])
            true = None
        pred = pick(confusion[true]) if true else None
        human = true == "human"
        rpc = human and rng.random() < 0.70
        stratum = None
        if human:
            r, acc = rng.random(), 0.0
            for s, p in strata:
                acc += p
                if r < acc:
                    stratum = s
                    break
            stratum = stratum or "other"
        flow = None
        if rpc:
            flow = {"dispute": "F03", "hardship": "F04", "angry": "F10", "complaint": "F10"}.get(stratum) or rng.choice(["F01", "F01", "F01", "F02", "F09"])
        elif human:
            flow = "F05"
        ptp = bool(rpc and flow in ("F01", "F09") and rng.random() < 0.38 / 0.80)
        verified = None
        kept = None
        checks = None
        if human:
            c12 = "pass"
            if ptp and rng.random() < 0.012:
                c12 = "fail"
            c04 = "fail" if rng.random() < 0.0008 else "pass"
            c08 = "fail" if flow in ("F02", "F03") and rng.random() < 0.05 else ("pass" if flow in ("F02", "F03") else "n/a")
            c09 = "fail" if flow == "F04" and rng.random() < 0.06 else ("pass" if flow == "F04" else "n/a")
            checks = {"C04": c04, "C08": c08, "C09": c09, "C12": c12 if ptp else "n/a"}
            verified = (c12 == "pass") if ptp else None
            if ptp:
                kept = rng.random() < (0.62 if c12 == "pass" else 0.15)
        connected = outcome in ("answered", "voicemail")
        secs = 0 if not connected else (lognorm(rng, 135, 260, 20, 600) if human else rng.randint(8, 25))
        judged = bool(human and (stratum != "other" or rng.random() < 0.02))
        violation = None
        if checks:
            for k in ("C04", "C08", "C09", "C12"):
                if checks[k] == "fail":
                    violation = k
                    break
        rows.append({"attempt_id": f"PR-{i:05d}", "call_date": "2026-11-05", "campaign": camp, "product": book,
                     "language_group": group, "local_time": f"{minute // 60:02d}:{minute % 60:02d}",
                     "connect_outcome": outcome, "connected": connected, "amd_true": true, "amd_pred": pred,
                     "human_answer": human, "rpc": rpc, "flow": flow, "stratum": stratum, "ptp": ptp,
                     "ptp_verified": verified, "kept": kept, "call_seconds": secs, "checks": checks,
                     "violation": violation, "judge_sampled": judged, "concurrency": rng.randint(200, 2400)})
    return rows


# ---------------------------------------------------------------------------------------
# write
# ---------------------------------------------------------------------------------------
def dump_json(obj) -> bytes:
    return (json.dumps(obj, indent=2, ensure_ascii=True) + "\n").encode()


def dump_jsonl(rows) -> bytes:
    return "".join(json.dumps(r, ensure_ascii=True, separators=(",", ":")) + "\n" for r in rows).encode()


def build(edition: str) -> dict[str, bytes]:
    W = World(edition)
    files: dict[str, bytes] = {}
    traces = {}
    for k, iid in enumerate(INCIDENT_META, 1):
        tr = incident_call(W, iid, k)
        traces[iid] = tr
        files[f"traces/{iid}.json"] = dump_json(tr)
    files["calls.jsonl"] = dump_jsonl(generate_calls(W))
    files["entity_pairs.jsonl"] = dump_jsonl(generate_entity_pairs(W, traces["T01"]))
    files["pauses.jsonl"] = dump_jsonl(generate_pauses(W))
    files["judge_labels.jsonl"] = dump_jsonl(generate_judge_labels(W))
    files["production_sample.jsonl"] = dump_jsonl(generate_production(W))
    manifest = {"edition": edition, "dataset": W.C["dataset"], "seed": W.C["seed"], "world_version": W.C["world_version"],
                "generator_version": GENERATOR_VERSION, "note": W.C["lender_note"] + " All data is synthetic.",
                "files": {name: {"sha256": sha256(data),
                                 "records": (data.count(b"\n") if name.endswith(".jsonl") else 1)}
                          for name, data in sorted(files.items())}}
    files["manifest.json"] = dump_json(manifest)
    return files


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--edition", choices=["global", "india"], default="global")
    ap.add_argument("--out", help="output folder (default data/<edition>)")
    ap.add_argument("--check", action="store_true", help="compare a fresh build with the files on disk")
    args = ap.parse_args(argv)
    out = Path(args.out) if args.out else HERE / args.edition
    files = build(args.edition)
    if args.check:
        bad = [n for n, d in files.items() if not (out / n).exists() or (out / n).read_bytes() != d]
        extra = sorted(str(p.relative_to(out)) for p in out.rglob("*") if p.is_file()
                       and str(p.relative_to(out)) not in files)
        for n in bad:
            print(f"differs: {n}")
        for n in extra:
            print(f"not generated: {n}")
        print("OK" if not bad and not extra else "MISMATCH")
        return 0 if not bad and not extra else 1
    for name, data in files.items():
        p = out / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    print(f"wrote {len(files)} files to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
