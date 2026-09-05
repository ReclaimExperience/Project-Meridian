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

# 3. The graphical stack actually came up.
#
#    This is the ORIGINAL check, restored, and the story is worth keeping
#    because two corrections in a row aimed at the wrong half of it.
#
#    The original waited for graphical.target to go active on a 90s deadline.
#    The target clears at ~80s here, so it was a coin toss, and every lost toss
#    spent a boot attempt until a machine had none left. Correct diagnosis:
#    THE DEADLINE was too tight. My first fix instead deleted the target check
#    and asserted only the greeter — which the rollback drill's sabotage does
#    not disturb, so a sabotaged boot passed and greenboot kept a broken
#    update. My second fix asked `is-failed graphical.target`, which is FALSE
#    for a target that never activated at all: unreached is `inactive`, not
#    `failed`. The sabotage prevents activation; it produces no failure state
#    to find. That passed too.
#
#    So: wait for it, generously. Waiting is correct; the old deadline was not.
#    NetworkManager-wait-online is masked (see the note beside that mask), which
#    is what makes the target arrive promptly instead of at the ~80s mark.
elapsed=0
until systemctl is-active --quiet graphical.target; do
    if [[ "$elapsed" -ge "$DEADLINE" ]]; then
        fail "graphical.target did not come up within ${DEADLINE}s. Something
      the desktop is built on did not start, and this update should not be
      kept. (If a healthy machine ever trips this, the deadline is wrong —
      raise it from PRD 10.2's measured column. Do NOT delete the check: that
      was tried, and it let a sabotaged boot pass.)"
    fi
    sleep 2
    elapsed=$((elapsed + 2))
done
echo "greenboot: graphical.target active after ${elapsed}s"

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
