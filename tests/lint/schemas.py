#!/usr/bin/env python3
"""JSON Schema validation for the repo's data contracts (PRD 6.3).

Each (instance, schema) pair below is a cross-WP contract: branding.json is the
rename invariant (6.5), tokens.json is the design contract (Appendix A), and
catalog/compat are WP-15's editorial data consumed by WP-13/20.

Pairs are registered here as their WPs land; a missing instance whose WP has not
run yet is skipped with a note, never silently ignored.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]

# (instance, schema, owning WP)
PAIRS = [
    (
        "os/rootfs/usr/share/meridian/branding.json",
        "catalog/schemas/branding.schema.json",
        "WP-00",
    ),
    ("docs/design/tokens.json", "docs/design/schemas/tokens.schema.json", "WP-00"),
    ("catalog/catalog.json", "catalog/schemas/catalog.schema.json", "WP-15"),
    ("catalog/compat.json", "catalog/schemas/compat.schema.json", "WP-15"),
    ("os/packages.yml", "catalog/schemas/packages.schema.json", "WP-01"),
]


def main() -> int:
    failed = skipped = passed = 0

    for inst_rel, schema_rel, wp in PAIRS:
        inst, schema = ROOT / inst_rel, ROOT / schema_rel
        if not inst.exists() and not schema.exists():
            print(f"  skip  {inst_rel}  (not yet delivered — {wp})")
            skipped += 1
            continue
        if not schema.exists():
            print(
                f"  FAIL  {inst_rel}  — instance exists but schema {schema_rel} is missing"
            )
            failed += 1
            continue
        if not inst.exists():
            print(f"  skip  {inst_rel}  (schema ready, instance lands in {wp})")
            skipped += 1
            continue

        try:
            if inst.suffix in (".yml", ".yaml"):
                import yaml  # only needed once a YAML instance exists

                data = yaml.safe_load(inst.read_text())
            else:
                data = json.loads(inst.read_text())
            validator = Draft202012Validator(json.loads(schema.read_text()))
        except Exception as exc:  # noqa: BLE001 — report any load error the same way
            print(f"  FAIL  {inst_rel}  — could not load: {exc}")
            failed += 1
            continue

        errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
        if errors:
            print(f"  FAIL  {inst_rel}  ({len(errors)} error(s), schema: {schema_rel})")
            for err in errors:
                loc = "/".join(str(p) for p in err.path) or "<root>"
                print(f"          at {loc}: {err.message}")
            failed += 1
        else:
            print(f"  ok    {inst_rel}")
            passed += 1

    print(
        f"\nschema-lint: {passed} passed, {failed} failed, {skipped} pending future WPs"
    )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
