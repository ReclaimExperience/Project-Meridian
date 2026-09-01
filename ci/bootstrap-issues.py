#!/usr/bin/env python3
"""Open one tracking issue per work package (WP-00 deliverable).

Each issue is seeded from the PRD itself — objective, acceptance list, forbidden
actions and escalation triggers copied verbatim — so an agent starting a WP can
work from the issue without re-reading section 8 in full.

Requires an authenticated `gh` with issue-write access. Idempotent: a WP that
already has an open tracking issue is skipped, so this is safe to re-run.

    python3 ci/bootstrap-issues.py --dry-run    # print what would be created
    python3 ci/bootstrap-issues.py              # create them
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRD = ROOT / "docs" / "PRD.md"


def parse_work_packages() -> list[dict]:
    section = (
        PRD.read_text().split("## 8. Work packages")[1].split("### 8.7 Sequencing")[0]
    )
    packages = []
    for match in re.finditer(
        r"^#### (WP-\d\d) — (.+?)\n(.*?)(?=\n####|\Z)",
        section,
        re.MULTILINE | re.DOTALL,
    ):
        wp, title, body = match.group(1), match.group(2).strip(), match.group(3).strip()
        packages.append({"wp": wp, "title": title, "body": body})
    return packages


def issue_body(pkg: dict) -> str:
    body = pkg["body"]

    def field(label: str) -> str:
        m = re.search(rf"\*\*{label}:?\*\*(.+?)(?=\n\*\*|\Z)", body, re.DOTALL)
        return m.group(1).strip() if m else "_See the PRD._"

    meta = body.split("\n")[0]
    return (
        f"{meta}\n\n"
        f"**PRD:** `docs/PRD.md` section 8, {pkg['wp']} — read it in full before starting, "
        f"including Forbidden and Escalate if.\n\n"
        f"## Objective\n\n{field('Objective')}\n\n"
        f"## Acceptance\n\n> This is the definition of done. Copy it into your PR "
        f"description as a checklist (PRD 14.2 item 2) and do not edit it.\n\n"
        f"{field('Acceptance')}\n\n"
        f"## Forbidden\n\n{field('Forbidden')}\n\n"
        f"## Escalate if\n\n{field('Escalate if')}\n\n"
        f"## Sessions\n\n"
        f"| # | Date | Slice delivered | PR | Verified |\n|---|---|---|---|---|\n"
    )


def existing_issues() -> set[str]:
    out = subprocess.run(
        ["gh", "issue", "list", "--limit", "200", "--state", "all", "--json", "title"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if out.returncode != 0:
        print(f"error: `gh issue list` failed: {out.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
    titles = [i["title"] for i in json.loads(out.stdout or "[]")]
    return {m.group(1) for t in titles if (m := re.match(r"(WP-\d\d)", t))}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    packages = parse_work_packages()
    print(f"parsed {len(packages)} work packages from the PRD")

    have: set[str] = set()
    if not args.dry_run:
        have = existing_issues()

    created = skipped = 0
    for pkg in packages:
        # WP-00 is this bootstrap; it has no tracking issue to open for itself.
        if pkg["wp"] == "WP-00":
            continue
        title = f"{pkg['wp']} — {pkg['title']}"
        if pkg["wp"] in have:
            print(f"  skip   {title} (already exists)")
            skipped += 1
            continue
        if args.dry_run:
            print(f"  would create  {title}")
            created += 1
            continue
        result = subprocess.run(
            [
                "gh",
                "issue",
                "create",
                "--title",
                title,
                "--body",
                issue_body(pkg),
                "--label",
                "work-package",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            print(f"  FAIL   {title}: {result.stderr.strip()}", file=sys.stderr)
            return 1
        print(f"  created {title}  {result.stdout.strip()}")
        created += 1

    verb = "would create" if args.dry_run else "created"
    print(f"\n{verb} {created}, skipped {skipped}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
