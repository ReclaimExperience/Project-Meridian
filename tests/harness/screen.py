"""Is anything actually on the screen?

This exists because of a nightly run in which every captured frame was pure
black — stddev 0.00000, maximum pixel value 0 — and the harness said:

    smoke: greeter screenshot smoke-greeter.png
    smoke: logging in through SDDM as mtest
    ConsoleError: timed out after 420s waiting for 'plasmashell to start'

Three things went wrong there, and only the last one was reported.

  1. The greeter screenshot photographed nothing, and printing its filename
     read as evidence that a greeter had been seen.
  2. The password was typed into a black screen.
  3. The failure blamed `plasmashell`, which was blameless. Someone would have
     spent the morning on the wrong process.

`screens.py` already had a blank-frame guard, written after review round 3 for
exactly this shape ("saw nothing" read as "nothing is happening"). But it lived
inside the one suite that runs in no automated context, while `smoke` — which
gates every pull request — had no such check at all. The guard was in the room
that never gets used. So it lives here now, and the suites that actually run
call it.

Requires pillow and numpy, like the rest of the screen apparatus.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from harness.vm import VM

# Below this a frame carries essentially no detail. Calibrated on real captures:
# a Plasma desktop with wallpaper and panel measures ~0.125, a greeter with a
# form and a wallpaper is comfortably above it, and a black frame is 0.000.
BLANK_STDDEV = 0.02

# Two frames closer than this are the same picture. Not zero: virtio cursor
# blink and a clock's seconds move a handful of pixels without meaning the
# screen is still arriving.
SETTLED_RMSE = 0.001


def frame_detail(path: Path) -> float:
    """Standard deviation of pixel values, 0..1. Black or frozen is ~0."""
    import numpy as np
    from PIL import Image

    return float(
        np.asarray(Image.open(path).convert("L"), dtype=np.float64).std() / 255.0
    )


def frame_rmse(a: Path, b: Path) -> float:
    """Root-mean-square difference between two frames, 0..1."""
    import numpy as np
    from PIL import Image

    left = np.asarray(Image.open(a).convert("RGB"), dtype=np.float64)
    right = np.asarray(Image.open(b).convert("RGB"), dtype=np.float64)
    if left.shape != right.shape:
        return 1.0
    return float(np.sqrt(((left - right) ** 2).mean()) / 255.0)


def wait_for_screen(
    vm: VM,
    what: str,
    keep_as: str | None = None,
    tries: int = 20,
    interval: float = 1.5,
) -> Path:
    """Wait until the screen has settled AND is showing something. Return it.

    `what` names what the caller is waiting for ("the greeter"), so a failure
    says which screen never arrived rather than "the screen differs".

    Both conditions are required and the second is the one that gets omitted:
    a black screen "settles" on frame two. An earlier version of this logic in
    screens.py instead demanded that the screen be observed CHANGING, and failed
    a perfectly good desktop — static is the goal here, not the symptom.

    Raises AssertionError rather than returning a flag: a caller that forgets to
    check a return value gets the old behaviour back, silently.
    """
    import time

    previous: Path | None = None
    settled: Path | None = None
    for attempt in range(tries):
        current = vm.screenshot(keep_as or f"_wait-{what.replace(' ', '-')}-{attempt}")
        if previous is not None and frame_rmse(previous, current) <= SETTLED_RMSE:
            settled = current
            if keep_as is None:
                previous.unlink(missing_ok=True)
            break
        if previous is not None and keep_as is None:
            previous.unlink(missing_ok=True)
        previous = current
        time.sleep(interval)

    if settled is None:
        # Never stopped changing. Report the detail of the last frame anyway:
        # "still animating" and "flickering black" are different problems.
        detail = frame_detail(previous) if previous else 0.0
        raise AssertionError(
            f"{what} never stopped changing after {tries} frames "
            f"({tries * interval:.0f}s). Last frame detail {detail:.4f}."
        )

    detail = frame_detail(settled)
    if detail < BLANK_STDDEV:
        raise AssertionError(
            f"{what} is BLANK: the screen settled with no content at all "
            f"(detail {detail:.5f} < {BLANK_STDDEV}).\n"
            f"  Frame kept at {settled}.\n"
            "  The display produced nothing — so anything typed after this goes\n"
            "  nowhere, and a later timeout would name the wrong culprit. This is\n"
            "  the display or the greeter, not whatever was waited on next."
        )
    print(f"screen: {what} is up and settled (detail {detail:.3f})")
    return settled
