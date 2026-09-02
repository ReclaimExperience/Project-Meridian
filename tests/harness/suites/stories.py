"""Runs the Zero-Terminal stories (PRD 10.1) — the INV-0 enforcement checklist.

Discovers every `tests/stories/zt_*.py`, runs each in turn against one booted
image, and reports coverage against the 22 stories the PRD defines.

Coverage short of 22 is expected for most of the project and is NOT a failure:
each story lands with the work package that ships its flow. What IS a failure is
a story that exists and does not pass.
"""

from __future__ import annotations

import importlib.util
import traceback
from pathlib import Path

from harness.vm import ROOT, VM

STORIES = ROOT / "tests" / "stories"
TOTAL_STORIES = 22  # PRD 10.1


def discover() -> list[Path]:
    return sorted(p for p in STORIES.glob("zt_*.py") if p.stem != "zt_template")


def load(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(vm: VM, credentials: dict) -> None:
    paths = discover()
    print(f"stories: {len(paths)} of {TOTAL_STORIES} Zero-Terminal stories implemented")
    if not paths:
        print(
            "stories: none yet — each lands with the WP that ships its flow (PRD 10.1)"
        )
        return

    failures = []
    for path in paths:
        # Import inside the try: a story with a bad import previously aborted
        # every story after it, which is the opposite of what the comment below
        # promises.
        try:
            module = load(path)
        except BaseException as exc:  # noqa: BLE001
            print(f"stories:   FAIL  {path.stem}: could not be imported: {exc}")
            failures.append(f"{path.stem}: import failed: {exc}")
            continue
        title = getattr(module, "STORY", path.stem)
        owner = getattr(module, "OWNER_WP", "unknown WP")
        print(f"\nstories: {title}   [{owner}]")
        try:
            module.run(vm, credentials)
            print(f"stories:   PASS  {path.stem}")
        except BaseException as exc:  # noqa: BLE001 — one story must not stop the rest
            print(f"stories:   FAIL  {path.stem}: {exc}")
            traceback.print_exc()
            failures.append(f"{title} [{owner}]: {exc}")

    assert not failures, (
        f"{len(failures)} Zero-Terminal story/stories failed — each one is a task a "
        f"user cannot complete:\n  " + "\n  ".join(failures)
    )
    print(f"\nstories: all {len(paths)} implemented stories pass")
