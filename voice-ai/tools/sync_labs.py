"""Keep the 12 lab folders identical to the recipe scripts the site publishes.

The site repo holds each recipe as scripts/voice-recipes/<slug>.py with its expected
output in <slug>.out.txt (global edition) and <slug>.india.out.txt (India edition).
Each lab folder here holds the same three files as <slug>.py, expected_output.txt
and expected_output.india.txt.

    python3.11 tools/sync_labs.py --site /path/to/site --check   # report drift, exit 1 if any
    python3.11 tools/sync_labs.py --site /path/to/site           # copy the site files over the labs

Run the check before every release of this folder, and after any change to a recipe
on the site. Standard library only.
"""
from __future__ import annotations

import argparse
import difflib
import shutil
import sys
from pathlib import Path

VA = Path(__file__).resolve().parent.parent  # voice-ai/
FILES = (("{slug}.py", "{slug}.py"),
         ("{slug}.out.txt", "expected_output.txt"),
         ("{slug}.india.out.txt", "expected_output.india.txt"))


def pairs(site: Path) -> list[tuple[Path, Path]]:
    recipes = site / "scripts" / "voice-recipes"
    if not recipes.is_dir():
        raise SystemExit(f"no scripts/voice-recipes folder under {site}")
    labs = sorted(p.name for p in (VA / "labs").iterdir() if p.is_dir())
    site_slugs = sorted(p.stem for p in recipes.glob("*.py"))
    if labs != site_slugs:
        raise SystemExit(f"lab folders and site recipes differ: only here {sorted(set(labs) - set(site_slugs))}, "
                         f"only on the site {sorted(set(site_slugs) - set(labs))}")
    return [(recipes / src.format(slug=s), VA / "labs" / s / dst.format(slug=s)) for s in labs for src, dst in FILES]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--site", required=True, type=Path, help="root of the site repo")
    ap.add_argument("--check", action="store_true", help="compare only; exit 1 on any difference")
    args = ap.parse_args(argv)
    drift = 0
    ps = pairs(args.site.resolve())
    for src, dst in ps:
        if not src.is_file():
            print(f"missing on the site: {src}")
            drift += 1
            continue
        if dst.is_file() and dst.read_bytes() == src.read_bytes():
            continue
        drift += 1
        rel = dst.relative_to(VA)
        if args.check:
            old = dst.read_text().splitlines(keepends=True) if dst.is_file() else []
            sys.stdout.writelines(difflib.unified_diff(old, src.read_text().splitlines(keepends=True), str(rel), str(src)))
        else:
            shutil.copyfile(src, dst)
            print(f"updated {rel}")
    print(f"{drift} of {len(ps)} lab files differ from the site" if args.check else f"{drift} lab files updated")
    return 1 if args.check and drift else 0


if __name__ == "__main__":
    raise SystemExit(main())
