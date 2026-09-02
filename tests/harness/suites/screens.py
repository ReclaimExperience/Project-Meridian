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


def _frame_variance(path: Path) -> float:
    """Standard deviation of pixel values, 0..1. A blank or frozen-black screen
    is near zero; any real desktop is not."""
    import numpy as np
    from PIL import Image

    return float(
        np.asarray(Image.open(path).convert("L"), dtype=np.float64).std() / 255.0
    )


def _settle_screen(vm: VM, tries: int = 20, interval: float = 1.5) -> None:
    """Block until the screen stops changing, and prove it is a real screen.

    Two conditions, and the second is the one that is easy to omit:

      * consecutive frames match — the screen has settled;
      * the frame has real content — it is not blank or frozen black.

    Without the second, a screen showing nothing "settles" on frame two, which
    is the BL-1 failure shape — "saw nothing" read as "nothing is happening" —
    moved from an audit into a wait. It matters most for `just baseline`, which
    shares this path: a baseline captured from a blank frame becomes the
    expectation everything is later compared against.

    An earlier attempt instead required the screen to be OBSERVED CHANGING, and
    failed a perfectly good desktop: by the time this runs, the suite has
    already waited for plasmashell, so a correctly-finished desktop is static
    from the first frame. Static is the goal here, not the symptom.
    """
    import time

    # Below this a frame carries essentially no detail. A real desktop with a
    # wallpaper and a panel is an order of magnitude above it.
    BLANK_STDDEV = 0.02
    SETTLED_RMSE = 0.001

    def rmse(a: Path, b: Path) -> float:
        import numpy as np
        from PIL import Image

        left = np.asarray(Image.open(a).convert("RGB"), dtype=np.float64)
        right = np.asarray(Image.open(b).convert("RGB"), dtype=np.float64)
        if left.shape != right.shape:
            return 1.0
        return float(np.sqrt(((left - right) ** 2).mean()) / 255.0)

    previous: Path | None = None
    for attempt in range(tries):
        current = vm.screenshot(f"_settle-{attempt}")
        if previous is not None and rmse(previous, current) <= SETTLED_RMSE:
            variance = _frame_variance(current)
            previous.unlink(missing_ok=True)
            if variance < BLANK_STDDEV:
                current.unlink(missing_ok=True)
                raise AssertionError(
                    f"the screen settled but is effectively blank "
                    f"(stddev {variance:.4f} < {BLANK_STDDEV}). A frozen or "
                    f"black screen is not a finished one, and capturing it "
                    f"would make 'nothing' the baseline."
                )
            current.unlink(missing_ok=True)
            print(
                f"screens: settled after {attempt + 1} frame(s) (detail {variance:.3f})"
            )
            return
        if previous is not None:
            previous.unlink(missing_ok=True)
        previous = current
        time.sleep(interval)

    if previous is not None:
        previous.unlink(missing_ok=True)
    raise AssertionError(
        f"the screen never settled in {tries} frames ({tries * interval:.0f}s). "
        f"Capturing now would compare a half-drawn desktop against a settled "
        f"baseline."
    )


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
