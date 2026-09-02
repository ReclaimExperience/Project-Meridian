"""Screens suite: compare live screens against committed baselines (PRD 7.4).

The suite WP-05 will lean on: it drives the image to each named screen, captures
it, and compares against `tests/baselines/<screen>/<arch>.png`.

Adding a screen here is how a work package gets visual regression coverage. Each
screen names the state it wants and how to reach it; getting there is scripted,
never assumed, because a screenshot of the wrong screen compares cleanly against
nothing and fails in a way that looks like a rendering bug.
"""

from __future__ import annotations

from pathlib import Path

from harness import screendiff
from harness.vm import ROOT, VM

BASELINES = ROOT / "tests" / "baselines"


def capture_screens(vm: VM, credentials: dict) -> dict[str, Path]:
    """Drive the image to each named screen and capture it.

    Returns {screen_name: png_path}. Shared by the comparison run and by
    `just baseline`, so a baseline is always produced the same way the
    comparison will reproduce it.
    """
    console = vm.console
    user, password = credentials["user"], credentials["password"]
    captured: dict[str, Path] = {}

    console.login(user, password, timeout=600)
    console.wait_until(
        "systemctl is-active display-manager",
        # NOT endswith("active"): "inactive" ends with "active".
        lambda out: out.strip().splitlines()[-1].strip() == "active",
        timeout=300,
        description="display-manager to be active",
    )

    # --- the login greeter ---------------------------------------------------
    vm.qmp.wake_display()
    captured["sddm-login"] = vm.screenshot("screen-sddm-login")

    # --- the desktop, after a real login -------------------------------------
    vm.qmp.type_text(password)
    vm.qmp.key("ret")
    console.wait_until(
        "pgrep -a plasmashell || true",
        lambda out: "plasmashell" in out,
        timeout=420,
        description="plasmashell to start after the GUI login",
    )
    # Let the shell finish painting before capturing. An earlier version polled
    # `qdbus6 ... || echo settled`, whose `|| echo` guaranteed non-empty output —
    # so the predicate was true on the first poll and the wait never waited.
    # Wait on something that can actually be false: the panel process.
    console.wait_until(
        "pgrep -c plasmashell || true",
        lambda out: (
            out.strip().splitlines()[-1].strip().isdigit()
            and int(out.strip().splitlines()[-1].strip()) >= 1
        ),
        timeout=120,
        description="the panel to be up",
    )
    captured["desktop"] = vm.screenshot("screen-desktop")

    return captured


def run(vm: VM, credentials: dict) -> None:
    captured = capture_screens(vm, credentials)

    results = []
    for screen, actual in captured.items():
        directory = BASELINES / screen
        config = screendiff.ScreenConfig.load(directory / "config.json")
        baseline = directory / f"{vm.arch}.png"
        results.append(
            screendiff.compare(screen, actual, baseline, config, vm.evidence)
        )

    for result in results:
        if result.passed:
            # Masked fraction is printed on PASSES too: a mask is a quieter way
            # of doing what raising the threshold does, so it should be visible
            # in normal output rather than only in a config file.
            print(
                f"  ok    {result.screen}: RMSE {result.rmse:.4f} "
                f"<= {result.threshold:.4f}  "
                f"(masked {result.masked_fraction:.1%})"
            )
        else:
            print(f"  FAIL  {result.message}")

    failures = [r for r in results if not r.passed]
    assert not failures, (
        f"{len(failures)} screen(s) differ from their baseline. "
        f"Diff sheets (baseline | actual | amplified difference) are in {vm.evidence}."
    )
    print(f"screens: {len(results)} screen(s) match their baselines")
