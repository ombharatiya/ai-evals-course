"""The datasets regenerate byte for byte and validate against the schemas."""
from __future__ import annotations

import copy
import importlib.util
import json
import unittest

from tests._util import EDITIONS, VA
from tools.jsonschema_lite import validate
from tools.mini_yaml import load as load_yaml

spec = importlib.util.spec_from_file_location("generate", VA / "data" / "generate.py")
generate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generate)

SCHEMAS = {n: json.loads((VA / "data" / "schemas" / f"{n}.schema.json").read_text())
           for n in ("trace", "entity_pair", "pause", "judge_label", "production_row")}
FILES = {"entity_pair": "entity_pairs", "pause": "pauses", "judge_label": "judge_labels",
         "production_row": "production_sample"}


def records(edition: str) -> list[dict]:
    d = VA / "data" / edition
    out = [json.loads(p.read_text()) for p in sorted((d / "traces").glob("*.json"))]
    out += [json.loads(line) for line in (d / "calls.jsonl").read_text().splitlines()]
    return out


def jsonl(edition: str, name: str) -> list[dict]:
    return [json.loads(line) for line in (VA / "data" / edition / f"{name}.jsonl").read_text().splitlines()]


class TestGenerate(unittest.TestCase):
    def test_regenerates_byte_for_byte(self):
        for edition in EDITIONS:
            with self.subTest(edition=edition):
                files = generate.build(edition)
                on_disk = {str(p.relative_to(VA / "data" / edition)) for p in (VA / "data" / edition).rglob("*") if p.is_file()}
                self.assertEqual(set(files), on_disk)
                for name, data in files.items():
                    self.assertEqual((VA / "data" / edition / name).read_bytes(), data, name)

    def test_counts(self):
        for edition in EDITIONS:
            with self.subTest(edition=edition):
                m = json.loads((VA / "data" / edition / "manifest.json").read_text())
                self.assertEqual(m["files"]["calls.jsonl"]["records"], 200)
                self.assertEqual(m["files"]["entity_pairs.jsonl"]["records"], 600)
                self.assertEqual(m["files"]["judge_labels.jsonl"]["records"], 720)
                self.assertEqual(m["files"]["production_sample.jsonl"]["records"], 4000)
                for t in [f"T{i:02d}" for i in range(1, 11)] + ["S1", "S2a", "S2b"]:
                    self.assertIn(f"traces/{t}.json", m["files"])
                C = json.loads((VA / "world" / edition / "constants.json").read_text())
                self.assertEqual(m["seed"], C["seed"])


class TestSchemas(unittest.TestCase):
    def test_validator_catches_errors(self):
        rec = records("global")[0]
        bad = copy.deepcopy(rec)
        bad["turns"][0]["speaker"] = "robot"
        del bad["amd"]
        self.assertFalse(validate(rec, SCHEMAS["trace"]))
        self.assertTrue(validate(bad, SCHEMAS["trace"]))

    def test_calls_and_traces(self):
        for edition in EDITIONS:
            tools = json.loads((VA / "world" / edition / "tools.schema.json").read_text())
            crm = json.loads((VA / "world" / edition / "crm.schema.json").read_text())
            for rec in records(edition):
                with self.subTest(edition=edition, call=rec["call_id"]):
                    self.assertEqual(validate(rec, SCHEMAS["trace"]), [])
                    self.assertEqual(rec["edition"], edition)
                    errs = []
                    for turn in rec["turns"]:
                        for tc in turn.get("tool_calls", []):
                            ts = tools["tools"][tc["name"]]
                            args = dict(ts["args"])
                            args["required"] = [k for k in args["required"] if k not in tools["x-redacted"]]
                            errs += validate(tc["args_redacted"], args, tools, f"{tc['name']}.args")
                            errs += validate(tc["result"], ts["result"], tools, f"{tc['name']}.result")
                    for snap in ("crm_before", "crm_after"):
                        self.assertEqual(set(rec[snap]), set(crm["tables"]))
                        for table, rows in rec[snap].items():
                            for row in rows:
                                errs += validate(row, crm["tables"][table], crm, f"{snap}.{table}")
                    self.assertEqual(errs, [])

    def test_other_datasets(self):
        for edition in EDITIONS:
            for schema, name in FILES.items():
                with self.subTest(edition=edition, file=name):
                    errs = []
                    for row in jsonl(edition, name):
                        errs += validate(row, SCHEMAS[schema])
                    self.assertEqual(errs, [])

    def test_policies_yaml(self):
        for edition in EDITIONS:
            pol = load_yaml((VA / "world" / edition / "policies.yaml").read_text())
            self.assertEqual(pol["edition"], edition)
            self.assertEqual([p["id"] for p in pol["policies"]], [f"C{i:02d}" for i in range(1, 17)])
            for p in pol["policies"]:
                self.assertTrue(set(p) >= {"id", "title", "rule", "source", "check_type", "inputs", "parameters"})


class TestClock(unittest.TestCase):
    def test_turn_gaps_add_up(self):
        for edition in EDITIONS:
            for rec in records(edition):
                byid = {t["turn_id"]: t for t in rec["turns"]}
                ts = rec["timings_summary"]
                for i, tid in enumerate(ts["agent_turn_ids"]):
                    a = byid[tid]
                    c = byid[a["responds_to"]]
                    self.assertEqual(ts["turn_gap_ms"][i], a["play_start_ms"] - c["vad_end_ms"])
                    self.assertGreaterEqual(a["play_start_ms"], c["eot_commit_ms"])
                    if rec["persona_or_real"] == "sim" and a["llm"] and not a["llm"].get("speculative"):
                        n_tools = sum(1 for x in a["tool_calls"] if x["start_ms"] < a["tts"]["request_ms"])
                        st = ts["stage_ms"]
                        total = st["eot_delay"][i] + st["llm_ttft"][i] + st["tool"][i] + st["tts_ttfb"][i] + st["playout"][i]
                        self.assertEqual(ts["turn_gap_ms"][i], total + 10 * (2 + n_tools), rec["call_id"])

    def test_incident_numbers(self):
        for edition in EDITIONS:
            d = VA / "data" / edition / "traces"
            t01 = json.loads((d / "T01.json").read_text())
            caller = next(t for t in t01["turns"] if t["speaker"] == "caller" and t["vad_start_ms"] == 18220)
            self.assertEqual((caller["vad_end_ms"], caller["eot_commit_ms"]), (21940, 22310))
            self.assertEqual(len(caller["reference_text"].replace(",", "").split()), 12)
            agent = next(t for t in t01["turns"] if t["speaker"] == "agent" and t.get("play_start_ms") == 23740)
            self.assertEqual(agent["tool_calls"][0]["name"], "record_promise_to_pay")
            self.assertFalse(agent["tool_calls"][0]["args_redacted"]["readback_confirmed"])
            t04 = json.loads((d / "T04.json").read_text())
            self.assertEqual(max(t04["timings_summary"]["turn_gap_ms"]), 3990)
            t02 = json.loads((d / "T02.json").read_text())
            dues = next(t for t in t02["turns"] if t["speaker"] == "agent" and t.get("play_start_ms") == 30500)
            self.assertEqual(dues["barge_in"], {"t_ms": 33000, "tts_stop_ms": 33060, "stop_latency_ms": 900})
            t05 = json.loads((d / "T05.json").read_text())
            p1 = next(t for t in t05["turns"] if t["speaker"] == "caller" and t["vad_start_ms"] == 51200)
            self.assertEqual(p1["pauses"][0]["end_ms"] - p1["pauses"][0]["start_ms"], 720)
            self.assertEqual(p1["eot_commit_ms"], 53250)
            t08 = json.loads((d / "T08.json").read_text())
            end = [tc for t in t08["turns"] for tc in t.get("tool_calls", []) if tc["name"] == "end_call"][0]
            self.assertEqual(end["start_ms"], 71000)

    def test_judge_validation_cell(self):
        for edition in EDITIONS:
            C = json.loads((VA / "world" / edition / "constants.json").read_text())
            rows = [r for r in jsonl(edition, "judge_labels")
                    if r["dimension"] == "C07" and r["language_group"] == C["judge_validation_group"]]
            tp = sum(r["human_label"] and r["transcript_judge"] for r in rows)
            fn = sum(r["human_label"] and not r["transcript_judge"] for r in rows)
            fp = sum(not r["human_label"] and r["transcript_judge"] for r in rows)
            self.assertEqual((len(rows), tp, fn, fp), (120, 15, 3, 6))


if __name__ == "__main__":
    unittest.main()
