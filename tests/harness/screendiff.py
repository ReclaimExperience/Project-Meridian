"""Screenshot comparison with masks (PRD 7.4).

Compares a captured screen against a committed baseline by RMSE, ignoring
regions that legitimately change between runs — the clock, the battery readout,
anything else a per-screen config names.

Two rules from the PRD shape this file:

  * **R-F: baselines change deliberately.** Re-baselining is its own commit with
    a STATUS.md note, never something a suite does for itself. Nothing here
    writes a baseline; only `just baseline <screen>` does.
  * **Never raise a threshold to make a test pass** (PRD 7.4). A threshold that
    drifts upward one commit at a time ends up asserting nothing, so the
    per-screen value lives in a committed config file where a change to it shows
    up in review as a change to it.

A failure writes three artifacts side by side — baseline, actual, and an
amplified difference map — because "RMSE 0.081 exceeds 0.030" tells you a screen
changed but not what changed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_THRESHOLD = 0.03

# Beyond this, a comparison is asserting about too little of the screen to
# mean anything. Chosen to leave room for a clock and a battery readout.
MAX_MASKED_FRACTION = 0.25

# And a ceiling on the threshold itself. Capping masks while leaving the
# threshold unbounded just moves the bypass: `{"threshold": 1.0}` passes every
# comparison. Anything above this is not a tolerance, it is a disabled check.
MAX_THRESHOLD = 0.15


@dataclass
class ScreenConfig:
    """Per-screen comparison settings, committed beside the baseline."""

    threshold: float = DEFAULT_THRESHOLD
    # Rectangles to ignore, as [x, y, width, height] in pixels.
    masks: list[list[int]] = field(default_factory=list)
    note: str = ""

    @classmethod
    def load(cls, path: Path) -> ScreenConfig:
        if not path.is_file():
            return cls()
        data = json.loads(path.read_text())
        return cls(
            threshold=float(data.get("threshold", DEFAULT_THRESHOLD)),
            masks=[list(map(int, m)) for m in data.get("masks", [])],
            note=data.get("note", ""),
        )


@dataclass
class Comparison:
    screen: str
    rmse: float
    threshold: float
    passed: bool
    baseline: Path | None
    actual: Path
    diff: Path | None = None
    message: str = ""
    masked_fraction: float = 0.0


def _load_rgb(path: Path):
    from PIL import Image

    return Image.open(path).convert("RGB")


def _apply_masks(image, masks: list[list[int]]):
    """Paint masked regions a flat colour in BOTH images.

    Masking rather than cropping keeps the geometry identical, so a mask can
    never shift the rest of the comparison.
    """
    if not masks:
        return image
    from PIL import ImageDraw

    copy = image.copy()
    draw = ImageDraw.Draw(copy)
    for x, y, width, height in masks:
        draw.rectangle([x, y, x + width, y + height], fill=(0, 0, 0))
    return copy


def compare(
    screen: str,
    actual_path: Path,
    baseline_path: Path,
    config: ScreenConfig,
    evidence: Path,
) -> Comparison:
    """Compare one screenshot against its baseline."""
    import numpy as np

    actual = _load_rgb(actual_path)

    if not baseline_path.is_file():
        return Comparison(
            screen=screen,
            rmse=float("nan"),
            threshold=config.threshold,
            passed=False,
            baseline=None,
            actual=actual_path,
            message=(
                f"no baseline for {screen!r} at {baseline_path}.\n"
                f"  If this screen is new, create it deliberately:  just baseline {screen}\n"
                f"  Baselines are never written by a test run (rule R-F)."
            ),
        )

    baseline = _load_rgb(baseline_path)
    if baseline.size != actual.size:
        return Comparison(
            screen=screen,
            rmse=float("nan"),
            threshold=config.threshold,
            passed=False,
            baseline=baseline_path,
            actual=actual_path,
            message=(
                f"{screen}: size changed, {baseline.size} -> {actual.size}. "
                f"A resolution change is a real difference, not a rendering one."
            ),
        )

    # A mask does the same job as a raised threshold, more quietly: mask the
    # whole image and any two screens compare identical. Cap it, and report the
    # masked fraction on EVERY comparison so it is visible in passing output
    # rather than only discoverable by reading a config file.
    width, height = baseline.size
    masked_area = sum(w * h for _x, _y, w, h in config.masks)
    masked_fraction = masked_area / float(width * height)
    if config.threshold > MAX_THRESHOLD:
        return Comparison(
            screen=screen,
            rmse=float("nan"),
            threshold=config.threshold,
            passed=False,
            baseline=baseline_path,
            actual=actual_path,
            message=(
                f"{screen}: threshold {config.threshold} exceeds the "
                f"{MAX_THRESHOLD} ceiling.\n"
                f"  Above this a comparison is not tolerant, it is switched off."
            ),
        )

    if masked_fraction > MAX_MASKED_FRACTION:
        return Comparison(
            screen=screen,
            rmse=float("nan"),
            threshold=config.threshold,
            passed=False,
            baseline=baseline_path,
            actual=actual_path,
            message=(
                f"{screen}: masks cover {masked_fraction:.0%} of the screen, over "
                f"the {MAX_MASKED_FRACTION:.0%} limit.\n"
                f"  A mask is a quieter way of doing what raising the threshold "
                f"does. If this much of the screen is unstable, the screen is the\n"
                f"  wrong thing to be comparing."
            ),
        )

    masked_baseline = np.asarray(_apply_masks(baseline, config.masks), dtype=np.float64)
    masked_actual = np.asarray(_apply_masks(actual, config.masks), dtype=np.float64)

    # RMSE normalised to 0..1 so the threshold means the same thing whatever the
    # bit depth, matching the 0.03 figure in PRD 7.4.
    rmse = float(np.sqrt(((masked_baseline - masked_actual) ** 2).mean()) / 255.0)
    passed = rmse <= config.threshold

    diff_path = None
    if not passed:
        diff_path = _write_diff(screen, baseline, actual, config, evidence)

    return Comparison(
        screen=screen,
        rmse=rmse,
        threshold=config.threshold,
        passed=passed,
        masked_fraction=masked_fraction,
        baseline=baseline_path,
        actual=actual_path,
        diff=diff_path,
        message=""
        if passed
        else (
            f"{screen}: RMSE {rmse:.4f} exceeds {config.threshold:.4f}\n"
            f"  baseline: {baseline_path}\n"
            f"  actual:   {actual_path}\n"
            f"  diff:     {diff_path}\n"
            f"  If the change is intended, re-baseline deliberately in its own\n"
            f"  commit with a STATUS.md note (rule R-F). Do NOT raise the\n"
            f"  threshold to make this pass (PRD 7.4)."
        ),
    )


def _write_diff(
    screen: str, baseline, actual, config: ScreenConfig, evidence: Path
) -> Path:
    """Baseline | actual | amplified difference, in one image."""
    import numpy as np
    from PIL import Image

    difference = np.abs(
        np.asarray(_apply_masks(baseline, config.masks), dtype=np.int16)
        - np.asarray(_apply_masks(actual, config.masks), dtype=np.int16)
    )
    # Amplify: a real regression is often a few subtle pixels, and an unscaled
    # difference map of a subtle change looks like a black rectangle.
    amplified = np.clip(difference * 8, 0, 255).astype(np.uint8)

    width, height = baseline.size
    sheet = Image.new("RGB", (width * 3, height), (0, 0, 0))
    sheet.paste(baseline, (0, 0))
    sheet.paste(actual, (width, 0))
    sheet.paste(Image.fromarray(amplified), (width * 2, 0))

    evidence.mkdir(parents=True, exist_ok=True)
    path = evidence / f"diff-{screen}.png"
    sheet.save(path)
    return path
