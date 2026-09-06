#!/usr/bin/env python3
"""The health check's three states, measured before the check is trusted.

This predicate decides whether a user keeps an update. It has been wrong three
times, each time in a way that reasoning endorsed:

  1. waited for graphical.target on a 90s deadline — a race against ~80s, and
     every lost race spent a boot attempt until a machine would not boot;
  2. asserted only the greeter — which the rollback drill's sabotage does not
     disturb, so a sabotaged boot PASSED and greenboot kept a broken update;
  3. asked `is-failed graphical.target` — false for a target that never
     activated, because unreached is `inactive`, not `failed`.

The root cause of (1) turned out to be a deadlock, not a deadline: the check
runs inside a unit that multi-user.target waits for, and graphical.target
requires multi-user.target. It can never observe that target activate.

So the states are exercised against a stubbed systemctl, with the two that
carry the risk first-class: the sabotage MUST fail fast, and a transiently
failing unit that systemd is still restarting MUST NOT.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECK = ROOT / "os/rootfs/usr/lib/greenboot/check/required.d/10-meridian-desktop.sh"

STUB = r"""#!/usr/bin/env bash
# A stub systemctl driven by files, so each state is constructed exactly.
case "$*" in
  *"show -p Wants -p Requires -p ConsistsOf --value graphical.target"*)
      cat "$STATE/graphical_deps" 2>/dev/null; exit 0 ;;
  *"list-units --state=failed"*)
      cat "$STATE/failed" 2>/dev/null; exit 0 ;;
  *"is-active --quiet display-manager.service"*)
      [ -f "$STATE/greeter_up" ]; exit $? ;;
  *"is-enabled --quiet NetworkManager.service"*)
      [ ! -f "$STATE/nm_disabled" ]; exit $? ;;
  *"is-failed --quiet NetworkManager.service"*)
      [ -f "$STATE/nm_failed" ]; exit $? ;;
esac
exit 0
"""

# (name, files to create, expect_pass, must_mention)
CASES = [
    (
        "greeter serving, nothing failed",
        {
            "greeter_up": "",
            "graphical_deps": "display-manager.service\nudisks2.service\n",
            "failed": "",
        },
        True,
        "greeter serving",
    ),
    (
        "SABOTAGE: a graphical dep has failed",
        {
            "greeter_up": "",
            "graphical_deps": "meridian-drill-sabotage.service\ndisplay-manager.service\n",
            "failed": "meridian-drill-sabotage.service loaded failed failed Sabotage\n",
        },
        False,
        "depends on failed unit",
    ),
    (
        "unrelated unit failed — must NOT roll back",
        {
            "greeter_up": "",
            "graphical_deps": "display-manager.service\n",
            "failed": "some-unrelated.service loaded failed failed Thing\n",
        },
        True,
        "greeter serving",
    ),
    (
        "restarting unit is not 'failed' — must NOT roll back",
        {
            "greeter_up": "",
            "graphical_deps": "flaky.service\ndisplay-manager.service\n",
            "failed": "",
        },
        True,
        "greeter serving",
    ),
    (
        "nothing up, nothing failed — ambiguous, times out",
        {"graphical_deps": "display-manager.service\n", "failed": ""},
        False,
        "ambiguous case",
    ),
    (
        "greeter up but NetworkManager disabled",
        {
            "greeter_up": "",
            "graphical_deps": "display-manager.service\n",
            "failed": "",
            "nm_disabled": "",
        },
        False,
        "cannot get online",
    ),
]


def main() -> int:
    failures = 0
    for name, files, expect_pass, mention in CASES:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            state, bindir = tmp / "state", tmp / "bin"
            state.mkdir()
            bindir.mkdir()
            for fname, content in files.items():
                (state / fname).write_text(content)
            stub = bindir / "systemctl"
            stub.write_text(STUB)
            stub.chmod(0o755)

            env = dict(os.environ)
            env["STATE"] = str(state)
            env["MERIDIAN_SYSTEMCTL"] = str(stub)
            env["MERIDIAN_HEALTH_DEADLINE"] = "4"  # keep the ambiguous case quick
            proc = subprocess.run(
                ["bash", str(CHECK)],
                env=env,
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
            passed = proc.returncode == 0
            output = proc.stdout + proc.stderr
            if passed != expect_pass:
                verb = "passed" if passed else "failed"
                print(
                    f"FAIL [{name}]: check {verb}, expected the opposite\n  {output.strip()[:300]}"
                )
                failures += 1
            elif mention not in output:
                print(
                    f"FAIL [{name}]: expected {mention!r} in output:\n  {output.strip()[:300]}"
                )
                failures += 1

    if failures:
        print(f"health-check: {failures} failure(s)")
        return 1
    print(
        f"health-check: {len(CASES)} states — sabotage fails fast, transients and unrelated failures do not"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
