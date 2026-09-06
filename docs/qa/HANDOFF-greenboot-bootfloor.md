# Handoff: greenboot health check, boot floor, and the CI image pipeline

Written 2026-09-06. Branch `wp/05-theme-core`, 50 commits ahead of `main`,
not merged. Everything below is reproducible from that branch.

## 1. What this was trying to do

A test machine was found **dead at the bootloader**. Its GRUB environment:

```text
boot_counter=-1   boot_success=0   saved_entry=1
```

...against `/boot/loader/entries/` containing exactly one entry, `ostree-1.conf`.
Fedora's ostree `grub.cfg` contains:

```text
if [ -n "${boot_counter}" -a "${boot_success}" = "0" ]; then
  if [ "${boot_counter}" = "0" -o "${boot_counter}" = "-1" ]; then
    set default=1        # unconditional — never checks entry 1 exists
```

`default=1` is the rollback deployment. On a single-deployment machine — every
fresh install — it points at nothing, GRUB boots nothing, and control returns to
the firmware. `/boot` is read-only from userspace, so `grub2-editenv` fails from
inside the OS, and INV-0 means there is no terminal to run it from anyway.
**A machine in this state cannot be recovered without external media.**

The work: stop the machine reaching that state, and give the bootloader a floor.

## 2. Confirmed findings (evidence attached)

### 2.1 The health check's deadline was a race — CONFIRMED, FIXED

`10-meridian-desktop.sh` waited for `graphical.target` with a **90s** deadline.
Measured inside the VM with `bash -x`, the target cleared at **~80s**:

```text
+ elapsed=78 ; systemctl is-active --quiet graphical.target ; [[ 78 -ge 90 ]]
+ elapsed=80 ; systemctl is-active --quiet graphical.target
+ echo 'greenboot: graphical.target reached in under 90s'
```

A ten-second margin. Every lost race rebooted the machine and spent a boot
attempt. Deadline now 300s, explicitly provisional (see 4.1).

### 2.2 Boot counters accrete — CONFIRMED

Armed `boot_counter=3`, booted healthy, observed `boot_counter=2` with
`boot_success=0`. Every boot spends an attempt; nothing returns one. That is how
the wild machine reached `-1`.
Caveat: measured on a disk whose greenboot had been masked by earlier harness
work (see 3.2). Re-measure on a clean image.

### 2.3 Deleting the target check breaks rollback — CONFIRMED, FIXED

An attempted fix asserted only the greeter, not `graphical.target`. The rollback
drill's sabotage fails a unit `RequiredBy=graphical.target` while `plasmalogin`
keeps serving a greeter, so a **sabotaged boot passed** and greenboot marked it
good:

```text
healthcheck unit:   enabled
healthcheck result: active
greenboot journal:  Set grubenv: boot_success...
```

For two commits this branch shipped a check that would keep a broken update on a
user's machine. `is-failed graphical.target` was then tried and is also wrong: an
unreached target is `inactive`, not `failed`. Current code waits for the target
with a generous deadline. **Waiting was never the mistake; racing was.**

### 2.4 The CI image pipeline had never produced an artifact — FIXED

Three separate causes, in order of discovery: missing Python deps in the
`rollback-drill` job; the container store's recorded path not matching where the
builder mounted it; and root's podman resolving to the *rootless* graphroot with
no root-readable config saying so. Fixed by naming the store explicitly via
`CONTAINERS_STORAGE_CONF`. First successful artifact: run `33947223804`.

**The disk build is still intermittent.** Same configuration has produced 3
successes and 3 failures with two different error messages. Unexplained.

### 2.5 The CI-built image reaches a working desktop — CONFIRMED

`build/evidence/ci-boot-{60,120,180,300,420}s.png`: the plasmalogin greeter, with
the `mtest` user and a password field, present and stable at every sample across
seven minutes. No reboot, no splash, clock advancing normally.

**This contradicts the CI `boottime` measurement**, which reported
`graphical.target` never active across 420s. The image is fine; the measurement
is wrong. See 4.2 — this is the most important open item.

## 3. Harness defects found (all fixed unless noted)

These matter because **six "product defects" investigated during this work were
all harness artifacts**, none real:

| Symptom | Actual cause |
|---|---|
| Dolphin white under a dark scheme | app launched with 4 env vars, no `XDG_CURRENT_DESKTOP` |
| Wallpaper ΔRGB 83 vs mockup | compared against a JPEG of a *newer* mockup than the tokens |
| Icon theme killed every Breeze icon | `index.theme` landed 0 bytes via hand-install |
| greenboot never confirmed a boot | a mask applied by earlier harness work, persistently |
| Health check "enabled but not running" | the same mask had removed its `WantedBy` symlink |
| Counter 3→2, `boot_success=0` | grubenv read before greenboot finished |

### 3.1 `wait_until` aborted on a slow poll — FIXED

Each poll ran with `timeout=min(60, timeout)` and let `ConsoleError` propagate
out of the wait. One slow reply killed a 420s wait at 60s with "command timed
out", which reads as the machine having rebooted. It was load. This is the
primitive every suite waits on.

### 3.2 Persistent masks contaminated the golden disk — FIXED

The theme suite masks greenboot with `--runtime`; a manual repair did it
*without*, so the mask persisted in `/etc` and survived every later run,
silencing the mechanism `bootfloor` measures. `bootfloor` now refuses to run on a
disk whose greenboot is masked.

### 3.3 Destructive suites shared one mutable disk — FIXED

`bootfloor` and `rollback` now run on a copy-on-write overlay.

### 3.4 Console commands typed into a login prompt — NOT FIXED

After a reboot mid-suite the shell session is gone, and `console.run` types into
`fedora login:`. The serial log shows commands sitting there verbatim, never
executed, while the harness waits for a sentinel that cannot come. **Every such
"timeout" is a command that never ran, and they have been misread as product
findings more than once.** The harness needs to detect a reboot and re-login.

### 3.5 Serial output stops at `plymouth-quit`

Console mirroring ends there, so `Reached target Graphical Interface` never
appears in ANY serial log regardless of whether it happened. Absence of a marker
in the serial log is not evidence of absence. This produced at least two false
conclusions.

## 4. Open, with the exact next step

### 4.1 The deadline is still a guess

300s is provisional. PRD 10.2 now has a `Boot→greeter (measured)` column with no
numbers in it. Set the deadline at **slowest observed × 2** on the low-end row
(4 GB Celeron/eMMC). Do not tighten by guessing — 90s was guessed and it bricked
a machine. Note the trade-off is real in both directions: at 300s the rollback
drill overruns its own 900s patience because greenboot needs ~3 attempts.

### 4.2 Why does CI's `boottime` disagree with the screenshots? ← START HERE

Local boot of the CI image shows a greeter at 60s. CI's `boottime` says
`graphical.target` never activates in 420s, with only 2 unanswered polls out of
~140. One of these is wrong. Candidates: CI's VM differs (KVM availability,
timing), or the polls were not executing and the "2 unanswered" count is
misleading (see 3.4). **Resolve this before touching the health check again** —
every conclusion about the check depends on it.

### 4.3 The rollback drill has never passed on this branch

Latest attempt: the check correctly refuses the sabotaged boot (`result:
activating`, `failed units=4`) but takes the full 300s, so rollback needs ~20
minutes and exceeds the drill's 900s window. Either shorten the deadline (4.1) or
raise the drill's patience to exceed `max_attempts × (boot + deadline)`.

### 4.4 `bootfloor` has never reached its cure phase

The prevention phase (counter must reset) fails first. The cure phase — corrupt
grubenv, assert the machine still boots — has not run once, so
`meridian-boot-floor` is **untested on a machine**. It has unit tests
(`tests/lint/test_boot_floor.py`, 4 states, mutation-verified) and nothing more.

### 4.5 The intermittent disk build (2.4)

### 4.6 `nightly-x86_64` fails at `Build image`

Its sibling job builds the same image from the same script successfully. One
known cause was fixed (a diagnostic step running root podman against the
rootless store, leaving root-owned files). Unverified since.

## 5. Where things are

- Branch `wp/05-theme-core`, 50 commits, unmerged.
- CI artifacts: `meridian-qcow2-x86_64` (~4.9 GB, 5-day retention),
  `rollback-drill-evidence` (serial logs + JSON reports).
- Local evidence: `build/evidence/` — `ci-boot-*.png`, serial logs, reports.
- Probe tooling: `tests/harness/probe.sh` / `probe-status.sh` (PID file, exit
  sentinel, unbuffered output, warns when a live process goes silent).
- The health check: `os/rootfs/usr/lib/greenboot/check/required.d/10-meridian-desktop.sh`
- The boot floor: `os/rootfs/usr/libexec/meridian-boot-floor` + its unit.

## 6. Honest assessment of how this went

Roughly 15 CI runs were consumed. **Three produced findings; the rest were
self-inflicted** — wrong fixes to the container store made on single red runs,
one commit that changed two variables so its result was unattributable, a
diagnostic step that corrupted the store it was measuring, and a config with two
green runs behind it removed on the strength of one red one.

The recurring failure is not any single bug. It is **promoting a plausible
mechanism to a conclusion without measuring it**, then acting on it. The
instrumentation that eventually worked — printing the store's actual state,
photographing the booting VM — each answered in one run what reasoning had failed
to answer in four.

Anyone picking this up: distrust every "X never happens" in the history above
unless it cites a command that demonstrably executed. Several did not.
