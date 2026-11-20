"""Every exercise solution runs in both editions and prints its expected output."""
from __future__ import annotations

import subprocess
import unittest
from concurrent.futures import ThreadPoolExecutor

from tests._util import PY, SOLUTIONS, VA


def run(name: str, edition: str):
    p = subprocess.run([PY, str(VA / "solutions" / f"{name}.py"), "--edition", edition],
                       cwd=VA, capture_output=True, timeout=600)
    return p.returncode, p.stdout, p.stderr


class TestSolutions(unittest.TestCase):
    results: dict = {}

    @classmethod
    def setUpClass(cls):
        jobs = [(n, e) for n in SOLUTIONS for e in ("global", "india")]
        with ThreadPoolExecutor(max_workers=8) as ex:
            for key, res in zip(jobs, ex.map(lambda j: run(*j), jobs)):
                cls.results[key] = res

    def test_one_solution_and_exercise_per_module(self):
        self.assertEqual(len(SOLUTIONS), 15)
        for n in range(1, 16):
            self.assertEqual(len([s for s in SOLUTIONS if s.startswith(f"m{n:02d}_")]), 1)
            self.assertEqual(len(list((VA / "exercises").glob(f"m{n:02d}-*.md"))), 1)

    def test_solutions_run_and_match(self):
        for name in SOLUTIONS:
            for edition, suffix in (("global", ".txt"), ("india", ".india.txt")):
                with self.subTest(solution=name, edition=edition):
                    code, out, err = self.results[(name, edition)]
                    self.assertEqual(code, 0, err.decode(errors="replace")[-2000:])
                    self.assertTrue(out.strip())
                    expected = (VA / "solutions" / "expected" / f"{name}{suffix}").read_bytes()
                    self.assertEqual(out, expected, f"{name} --edition {edition}")

    def test_key_numbers(self):
        for edition in ("global", "india"):
            out = self.results[("m05_voice_latency_slos", edition)][1].decode()
            self.assertIn("= turn gap 3990 ms (recorded 3990 ms)", out)
            out = self.results[("m03_stt_entities", edition)][1].decode()
            self.assertIn("WER 1/12 = 0.083", out)
            out = self.results[("m11_voice_reliability", edition)][1].decode()
            self.assertIn("0.2143 unbiased and 0.3164 plug-in", out)
            out = self.results[("m13_voice_monitoring", edition)][1].decode()
            self.assertIn("95% probability: 2995", out)
            self.assertIn("P(at least one) = 0.394", out)
            out = self.results[("m07_speech_output_tts", edition)][1].decode()
            self.assertIn("0 of 400: 0.0075", out)


if __name__ == "__main__":
    unittest.main()
