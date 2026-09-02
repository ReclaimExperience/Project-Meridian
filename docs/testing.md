# Testing

How to run the harness, how to write a story, and how to re-baseline a screen.

The harness exists so an agent can verify its own work (PRD 7.4). If you are
about to claim something works, this is how you find out.

## Running a suite

```bash
just build aarch64        # the OS image
just vm-image aarch64     # a bootable disk from it
just vm-test smoke        # boot it and check
```

`just vm-image` also writes `build/dev-credentials.json`, which the harness needs
to log in. Rebuild the disk image if that file is missing.

| Suite | Asserts | Runs where |
|---|---|---|
| `smoke` | boots to SDDM, GUI login works, plasmashell alive, no failed units | PR gate + local |
| `screens` | screens match `tests/baselines/` within RMSE tolerance | local (needs baselines for the arch) |
| `security` | ADR-015: no unlisted non-loopback listener, no SSH daemon | nightly |
| `privacy` | ADR-011: an idle system contacts nothing unlisted | nightly |
| `stories` | the Zero-Terminal stories in `tests/stories/` | PR gate once stories exist |

Useful flags:

```bash
just vm-test smoke aarch64          # pick the architecture
MERIDIAN_IDLE_SECONDS=120 just vm-test privacy   # shorten the idle window while iterating
python3 tests/harness/run.py smoke --keep        # leave the VM running to poke at it
```

The `privacy` idle window defaults to the full 10 minutes ADR-011 implies.
Shorten it while iterating, never in the gate: a daily check-in is invisible to a
two-minute sample, and a daily check-in is what the audit exists to catch.

## Evidence

Every run writes to `build/evidence/`, on success as well as failure — a suite
whose artifacts appear only when it fails gives you nothing to compare a
regression against.

| File | What it is |
|---|---|
| `<suite>-final-<arch>.png` | last screen before teardown |
| `<suite>-<arch>.json` | pass/fail, duration, unit counts |
| `serial-<arch>.log` | the whole console transcript |
| `capture-<arch>.pcap` | every packet (privacy suite) |
| `diff-<screen>.png` | baseline \| actual \| amplified difference |

CI uploads these as artifacts on every run of the build workflow.

## Writing a Zero-Terminal story

Copy `tests/stories/zt_template.py` to `tests/stories/zt_NN_short_name.py`. The
template carries the rules; the important one:

> The harness console **observes** the system. It never performs the user's
> step. Doing the task in a shell and then asserting it worked proves that the
> shell works, while INV-0 is a claim about what a person can do.

Drive the UI with `vm.qmp` (keys, pointer) the way a person would, then observe
the result with `console`. Wait for conditions with `console.wait_until(...)` —
never `sleep`. PRD WP-03 forbids wall-clock waits, and R-A treats flaky as
broken.

Write the assertion message for whoever reads it at 2am. `"Typing 'fire' in
Start and pressing Enter did not open the web browser"` is a bug report;
`"assert rc == 0"` is a puzzle.

If passing your story would need a terminal, a config file, or a command, stop:
you have found a product bug, not a test problem (PRD 0.3).

## Re-baselining a screen

```bash
just baseline sddm-login     # one screen
just baseline all            # every screen the suite captures
```

Baselines are **never** written by a test run — only by this command (rule R-F).
A suite that can rewrite its own expectation turns a regression into the new
normal.

Then:

1. Look at the images. `git diff` shows you that bytes changed, not what.
2. Commit them **on their own**, with a STATUS.md note saying what changed and
   why.
3. Never raise a threshold to make a screen pass (PRD 7.4). A threshold that
   drifts upward one commit at a time ends up asserting nothing. If a screen is
   legitimately noisier, add a **mask** with a written reason in
   `tests/baselines/<screen>/config.json`, so a reviewer sees what is excluded.

Masks are rectangles `[x, y, width, height]`. The greeter's clock is masked; its
password field is not. That boundary is the point.

## Adding a screen

Add it to `capture_screens()` in `tests/harness/suites/screens.py`: drive the
image to the state you want, capture, return it under a name. Then
`just baseline <name>`.

Script the way there; never assume it. A screenshot of the wrong screen compares
cleanly against nothing and fails looking like a rendering bug.

## When something fails

1. Read `build/evidence/serial-<arch>.log` first. Most failures are visible in
   the boot log.
2. Look at the screenshots. `smoke-greeter.png` and `smoke-desktop.png` show
   what the harness saw.
3. Re-run with `--keep` and connect to the VM's console socket to poke at it.

Two failure modes worth knowing, because both have already cost time:

- **systemd does not narrate the display manager to serial.** Waiting for it in
  the boot log waits forever. Ask systemd directly.
- **A console login is not a desktop login.** `plasmashell` starts only when a
  session begins through SDDM.
