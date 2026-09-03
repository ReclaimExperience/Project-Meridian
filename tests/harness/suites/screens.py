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
from harness.screen import wait_for_screen
from harness.vm import ROOT, VM

BASELINES = ROOT / "tests" / "baselines"


def _settle_screen(vm: VM, tries: int = 20, interval: float = 1.5) -> None:
    """Block until the screen stops changing, and prove it is a real screen.

    Both conditions live in harness.screen now, shared with the suites that run
    on every PR. They were written here, for this suite — and this suite runs in
    no automated context, so the guard sat where it could never fire while
    `smoke` typed a password at a black screen on the PR gate. A check is only
    as useful as the paths that call it.
    """
    wait_for_screen(vm, "the screen", tries=tries, interval=interval)


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
        # Any line, not the last: a kernel printk can land after the output
        # on this console. Not endswith: "inactive" ends with "active".
        # Empty output must not raise IndexError.
        lambda out: any(ln.strip() == "active" for ln in out.splitlines()),
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
    # Wait for the desktop to STOP CHANGING before capturing.
    #
    # Two previous attempts did not wait at all. `qdbus6 ... || echo settled`
    # guaranteed non-empty output, so its predicate was true immediately; then
    # `pgrep -c plasmashell >= 1` was true in exactly the states the wait above
    # already required, so it also returned on the first poll. Both looked like
    # waits and neither was.
    #
    # This waits on something neither of those guarantees and that genuinely
    # starts false: consecutive screenshots being identical. A panel that is
    # still painting differs frame to frame.
    _settle_screen(vm)
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
