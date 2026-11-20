"""House rules for the text in this folder: plain ASCII, STT not ASR, no Hindi or Hinglish
outside India-edition files. The lab scripts and their expected outputs are byte-identical
copies of the site's recipes, so they are checked by test_labs.py instead."""
from __future__ import annotations

import re
import unittest

from tests._util import VA

TEXT = {".md", ".py", ".json", ".jsonl", ".yaml", ".yml", ".txt"}
HINDI = re.compile(r"\b(hazaar|lakh|crore|rupaye|tarikh|haan|nahi|theek|kripya|aapka|aapke|aapko|namaste|dhanyavaad|"
                   r"shikayat|dhai|dedh|paune|saade|bol rahi|kar diya|bharne|samajh)\b", re.I)
DEVANAGARI = re.compile("[" + chr(0x0900) + "-" + chr(0x097F) + "]")


def text_files():
    for p in sorted(VA.rglob("*")):
        if not p.is_file() or p.suffix not in TEXT or "__pycache__" in p.parts or ".venv" in p.parts:
            continue
        rel = p.relative_to(VA)
        if rel.parts[0] == "labs" and p.name != "README.md":
            continue
        yield p, rel


def india_file(rel) -> bool:
    return "india" in rel.parts or ".india." in rel.name


class TestTextRules(unittest.TestCase):
    def test_plain_ascii(self):
        for p, rel in text_files():
            with self.subTest(file=str(rel)):
                bad = sorted({c for c in p.read_text(encoding="utf-8") if ord(c) > 127})
                self.assertEqual(bad, [], f"non-ASCII characters in {rel}")

    def test_stt_not_asr(self):
        for p, rel in text_files():
            if rel.name.startswith("test_"):
                continue
            with self.subTest(file=str(rel)):
                self.assertIsNone(re.search(r"\bASR\b", p.read_text()), rel)

    def test_no_hindi_outside_india_files(self):
        for p, rel in text_files():
            if india_file(rel) or rel.name.startswith("test_"):
                continue
            with self.subTest(file=str(rel)):
                text = p.read_text()
                m = HINDI.search(text) or DEVANAGARI.search(text)
                self.assertIsNone(m, f"{rel}: {m.group(0) if m else ''}")

    def test_labs_default_to_global(self):
        # Every lab keeps the India constants between its markers or in its India function, and
        # defaults to the global edition.
        for d in sorted((VA / "labs").iterdir()):
            src = (d / f"{d.name}.py").read_text(encoding="utf-8")
            with self.subTest(lab=d.name):
                self.assertIn("--edition", src)
                self.assertIn('default="global"', src)


if __name__ == "__main__":
    unittest.main()
