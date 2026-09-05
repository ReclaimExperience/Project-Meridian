#!/usr/bin/env bash
# greenboot health check: did this boot produce a usable desktop? (ADR-008)
#
# A failing required check makes greenboot roll the machine back to the previous
# deployment. That is the self-healing promise — and it is also a loaded gun, so
# this file checks the things whose absence a person would actually notice, and
# nothing else. Every false positive costs someone their update, silently.
#
# It has already fired for the wrong reason twice, and both times the cause was
# the same: the check asserted something ADJACENT to a usable desktop rather
# than the desktop itself.
#
#   1. `systemctl is-active sddm` — Fedora 44 replaced SDDM with plasmalogin, so
#      this answered "inactive" on a perfectly healthy boot.
#   2. `graphical.target` with a 90s deadline — the target goes active at ~80s
#      on our own test hardware while `plasmalogin.service` has been up and
#      serving a greeter the whole time. A ten-second margin is a coin toss, and
#      every lost toss decremented `boot_counter` until the machine had no
#      bootable deployment left. A machine was found in exactly that state.
#
# So: assert the EFFECT — the greeter a person logs in through — not the
# systemd abstraction that trails it. Rule R-I.
#
# NOTHING here may depend on the network. A desktop for a switcher has to reach
# a usable state fast with no network at all, so a network-dependent health
# check rolls back exactly the machine that is working correctly: the laptop on
# a train. greenboot's own 01_repository_dns_check.sh is disabled on this image
# for the same reason.
set -euo pipefail

fail() { echo "greenboot: FAIL — $*" >&2; exit 1; }

# Provisional, and deliberately generous. PRD 10.2's hardware matrix has no
# boot timings in it yet, so this is not yet "derived from the slowest matrix
# machine plus margin" — it is a ceiling chosen to be far outside any plausible
# healthy boot, because the failure mode of too-tight is a bricked machine and
# the failure mode of too-loose is a slow rollback. Re-derive when the matrix
# reports real numbers.
DEADLINE="${MERIDIAN_HEALTH_DEADLINE:-300}"

# 1. There is a way in: the greeter is running.
#
#    display-manager.service is an alias, so ask about it rather than about any
#    one implementation's name — that is what survived the SDDM -> plasmalogin
#    swap, and will survive the next one.
elapsed=0
until systemctl is-active --quiet display-manager.service; do
    if [[ "$elapsed" -ge "$DEADLINE" ]]; then
        fail "no display manager after ${DEADLINE}s. A boot that never reaches a
      greeter is the case rollback exists for, and on a machine with no terminal
      by design (INV-0) it is unrecoverable without it."
    fi
    sleep 2
    elapsed=$((elapsed + 2))
done
echo "greenboot: greeter up after ${elapsed}s"

# 2. It did not immediately die.
if systemctl is-failed --quiet display-manager.service; then
    fail "the display manager entered a failed state."
fi

# 3. Nothing in the graphical stack FAILED.
#
#    Read this next to check 1, because the pair is the whole lesson. The
#    original check WAITED for graphical.target to go active, on a deadline
#    tighter than the target's own worst case — that is what bricked machines.
#    The first fix removed the target from the check altogether, and that
#    removed the only thing the rollback drill's sabotage trips: the sabotage
#    fails a unit RequiredBy=graphical.target while plasmalogin keeps serving a
#    greeter perfectly well. greenboot passed the boot and marked it good.
#
#    Waiting for a target to ACTIVATE and asking whether it FAILED are
#    different questions. The first is a race against slow hardware. The second
#    is a fact, available immediately, and it is the one that matters.
if systemctl is-failed --quiet graphical.target; then
    fail "graphical.target is in a failed state. Something the desktop is
      built on did not come up, and this update should not be kept."
fi
echo "greenboot: graphical.target has not failed"

# 4. Networking CAN start. NOT "is connected", and not "can resolve": a desktop
#    with no cable and no saved Wi-Fi is healthy, and rolling that machine back
#    punishes someone for being offline.
if ! systemctl is-enabled --quiet NetworkManager.service; then
    fail "NetworkManager is not enabled — the machine cannot get online at all,
      which is not a state any update should be allowed to leave behind."
fi
if systemctl is-failed --quiet NetworkManager.service; then
    fail "NetworkManager entered a failed state during boot."
fi
echo "greenboot: NetworkManager enabled and not failed"

echo "greenboot: desktop health checks passed"
