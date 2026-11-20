"""Every lab reproduces both expected outputs byte for byte."""
from __future__ import annotations

import subprocess
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor

from tests._util import LABS, PY, VA


def run_lab(slug: str, edition: str) -> tuple[int, bytes, bytes]:
    script = VA / "labs" / slug / f"{slug}.py"
    args = [PY, str(script)] + (["--edition", edition] if edition == "india" else [])
    with tempfile.TemporaryDirectory() as tmp:
        p = subprocess.run(args, cwd=tmp, capture_output=True, timeout=900)
    return p.returncode, p.stdout, p.stderr


class TestLabs(unittest.TestCase):
    results: dict = {}

    @classmethod
    def setUpClass(cls):
        jobs = [(s, e) for s in LABS for e in ("global", "india")]
        with ThreadPoolExecutor(max_workers=8) as ex:
            for key, res in zip(jobs, ex.map(lambda j: run_lab(*j), jobs)):
                cls.results[key] = res

    def test_twelve_labs(self):
        self.assertEqual(len(LABS), 12)
        for slug in LABS:
            d = VA / "labs" / slug
            for name in (f"{slug}.py", "expected_output.txt", "expected_output.india.txt", "README.md"):
                self.assertTrue((d / name).is_file(), f"{slug}/{name}")

    def test_outputs_match(self):
        for slug in LABS:
            for edition, name in (("global", "expected_output.txt"), ("india", "expected_output.india.txt")):
                with self.subTest(lab=slug, edition=edition):
                    code, out, err = self.results[(slug, edition)]
                    self.assertEqual(code, 0, err.decode(errors="replace")[-2000:])
                    expected = (VA / "labs" / slug / name).read_bytes()
                    self.assertEqual(out, expected, f"{slug} --edition {edition} differs from {name}")

    def test_unknown_edition_exits_2(self):
        slug = "rare-violation-sampling"
        p = subprocess.run([PY, str(VA / "labs" / slug / f"{slug}.py"), "--edition", "mars"], capture_output=True)
        self.assertEqual(p.returncode, 2)


if __name__ == "__main__":
    unittest.main()
