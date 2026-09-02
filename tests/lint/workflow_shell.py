#!/usr/bin/env python3
"""shellcheck the inline `run:` blocks in GitHub workflows (PRD 6.3).

`lint-shell` sweeps tracked *.sh; `lint-justfile` extracts and shellchecks the
Justfile recipes on the grounds that they were "the largest unlinted shell
surface in the repo, and where every shell defect so far has lived". The same
argument now applies to the workflows: the residue after extracting logic into
ci/*.sh is still the whole nightly gating body and the tag computation.

The tell that this was needed: a live `# shellcheck disable=SC2086` sat in
nightly.yml, written by an author who believed the file was linted.

`${{ }}` expressions are replaced with a shell variable reference before
linting — shellcheck cannot know their values, and substituting a literal makes
every `case "${{ ... }}" in` look like a constant.
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"
EXPR = re.compile(r"\$\{\{[^}]*\}\}")


def blocks() -> list[tuple[str, str, str]]:
    """(workflow, step name, script) for every inline run: block."""
    found = []
    for path in sorted(WORKFLOWS.glob("*.yml")):
        document = yaml.safe_load(path.read_text())
        for job_name, job in (document.get("jobs") or {}).items():
            for index, step in enumerate(job.get("steps") or []):
                script = step.get("run")
                if not script or not script.strip():
                    continue
                label = step.get("name") or f"step {index}"
                found.append((path.name, f"{job_name} / {label}", script))
    return found


def main() -> int:
    found = blocks()
    if not found:
        print("workflow-shell: no inline run: blocks found — did the format change?")
        return 1

    failures = 0
    with tempfile.TemporaryDirectory() as tmp:
        for number, (workflow, label, script) in enumerate(found):
            path = Path(tmp) / f"b{number}.sh"
            # Only declare the placeholder when the block actually uses one,
            # or shellcheck reports it unused in every expression-free block.
            stub = "export WFEXPR=x\n" if EXPR.search(script) else ""
            path.write_text(
                "#!/usr/bin/env bash\n" + stub + EXPR.sub("${WFEXPR}", script)
            )
            result = subprocess.run(
                ["shellcheck", "--shell=bash", "--severity=warning", str(path)],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                print(f"  FAIL  {workflow}: {label}")
                for line in result.stdout.split("\n"):
                    if line.strip():
                        print(f"      {line}")
                failures += 1

    if failures:
        print(f"\nworkflow-shell: {failures} block(s) with findings")
        return 1
    print(f"workflow-shell: {len(found)} inline run: block(s) clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
