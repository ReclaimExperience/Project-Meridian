#!/usr/bin/env bash
# greenboot health check: did this boot produce a usable desktop? (ADR-008)
#
# A failing required check makes greenboot roll the machine back to the previous
# deployment automatically. That is the whole self-healing promise, and it means
# this file decides whether an update is kept — so it checks the things whose
# absence a person would actually notice, and nothing else. A check that is
# merely interesting does not belong here: every false positive costs someone
# their update, silently.
#
# PRD WP-04 words the second check as "sddm active". Fedora 44 / Plasma 6.7 does
# not ship SDDM — plasmalogin replaced it, and `systemctl is-active sddm` on this
# image answers "inactive" on a perfectly healthy boot. Asking systemd about
# display-manager.service instead is the same question in a form that survives
# the greeter being swapped again, which it already has been once.
set -euo pipefail

fail() { echo "greenboot: FAIL — $*" >&2; exit 1; }

# 1. The graphical stage was reached, within the time PRD WP-04 allows.
deadline=90
elapsed=0
until systemctl is-active --quiet graphical.target; do
    if [[ "$elapsed" -ge "$deadline" ]]; then
        fail "graphical.target not reached after ${deadline}s. A boot that never
      gets to a desktop is the case rollback exists for."
    fi
    sleep 2
    elapsed=$((elapsed + 2))
done
echo "greenboot: graphical.target reached in under ${deadline}s"

# 2. There is a way to log in.
systemctl is-active --quiet display-manager.service \
    || fail "display-manager.service is not active — no login screen, and on a
      machine with no terminal by design (INV-0) that is unrecoverable."
echo "greenboot: display-manager is active"

# 3. Networking can start. NOT "is connected": a desktop with no cable plugged
#    in and no saved Wi-Fi is healthy, and rolling that machine back would
#    punish someone for being offline.
systemctl is-enabled --quiet NetworkManager.service \
    || fail "NetworkManager is not enabled — the machine cannot get online at
      all, which is not a state any update should be allowed to leave behind."
systemctl is-failed --quiet NetworkManager.service \
    && fail "NetworkManager entered a failed state during boot."
echo "greenboot: NetworkManager is enabled and not failed"

echo "greenboot: desktop health checks passed"
