#!/usr/bin/env bash
# greenboot health check: did this boot produce a usable desktop? (ADR-008)
#
# A failing required check rolls the machine back. That is the self-healing
# promise and also a loaded gun, so this file checks what a person would
# actually notice and nothing else — every false positive costs someone their
# update, silently.
#
# ---------------------------------------------------------------------------
# THE CONSTRAINT THAT SHAPES ALL OF THIS
#
# This script runs inside greenboot-healthcheck.service, which is
# WantedBy=multi-user.target. systemd will not complete multi-user.target's job
# while this service is running, and graphical.target Requires=multi-user.target.
#
# So this script MUST NOT WAIT FOR graphical.target. It cannot activate until
# this script exits. Observed directly in systemd's job list:
#
#   378 greenboot-healthcheck.service start running
#   158 multi-user.target             start waiting
#   157 graphical.target              start waiting
#   display-manager.service:          active
#
# Earlier versions waited for that target on a 90s and then a 300s deadline.
# Both always ran to the deadline, because the thing being waited for was
# structurally prevented from happening. The check then failed, greenboot
# rebooted, a boot attempt was spent, and enough of those left a machine
# unbootable. The deadline was never the bug; the dependency cycle was.
#
# Asking `is-failed graphical.target` does not work either: a target that is
# WAITING is not a target that has FAILED.
#
# ---------------------------------------------------------------------------
# THREE STATES, not one deadline
#
#   fast PASS  — the greeter is serving. display-manager.service is outside the
#                dependency cycle and comes up in seconds.
#   fast FAIL  — something graphical.target depends on has genuinely failed.
#                A failed dependency means the desktop is never arriving, so
#                waiting the full deadline only delays a rollback that is
#                already certain.
#   TIMEOUT    — the ambiguous case only: nothing has failed, nothing is up
#                yet. This is the sole case that needs a generous ceiling, and
#                the only one a tight deadline could wrongly brick.
set -euo pipefail

fail() { echo "greenboot: FAIL — $*" >&2; exit 1; }

DEADLINE="${MERIDIAN_HEALTH_DEADLINE:-300}"
SYSTEMCTL="${MERIDIAN_SYSTEMCTL:-systemctl}"
POLL=2

# Units graphical.target pulls in. The drill's sabotage installs itself as
# RequiredBy=graphical.target, so it appears here.
graphical_deps() {
    "$SYSTEMCTL" show -p Wants -p Requires -p ConsistsOf --value graphical.target \
        2>/dev/null | tr ' ' '\n' | sed '/^$/d' | sort -u
}

# Only units systemd has GIVEN UP on. A unit restarting shows as activating
# (auto-restart), not failed, so a transient failure that recovers does not
# trip this — which is the difference between fast-fail and trigger-happy.
failed_units() {
    "$SYSTEMCTL" list-units --state=failed --no-legend --plain --all 2>/dev/null \
        | awk '{print $1}' | sed '/^$/d' | sort -u
}

broken_dependency() {
    local common
    common="$(comm -12 <(graphical_deps) <(failed_units) | head -3 | tr '\n' ' ')"
    [[ -n "${common// /}" ]] && { echo "$common"; return 0; }
    return 1
}

elapsed=0
confirmations=0
while :; do
    # FAIL is checked first, and deliberately so: the sabotage fails early and
    # the greeter still comes up, so a greeter-first order would pass a boot
    # whose graphical stack is already broken. That exact ordering mistake
    # shipped once and let a sabotaged boot through.
    if broken="$(broken_dependency)"; then
        fail "graphical.target depends on failed unit(s): ${broken}
      systemd has given up on them, so the desktop is not coming. Rolling back
      now rather than waiting out the ${DEADLINE}s ceiling."
    fi

    if "$SYSTEMCTL" is-active --quiet display-manager.service; then
        # Confirm twice before passing. The failure check above races the
        # sabotage on the first poll; a second look a poll later closes it.
        confirmations=$((confirmations + 1))
        if [[ "$confirmations" -ge 2 ]]; then
            echo "greenboot: greeter serving after ${elapsed}s, no failed graphical units"
            break
        fi
    else
        confirmations=0
    fi

    if [[ "$elapsed" -ge "$DEADLINE" ]]; then
        fail "no greeter after ${DEADLINE}s, and nothing has failed outright.
      This is the ambiguous case: the machine may simply be slower than the
      ceiling allows. If a HEALTHY machine trips this, the ceiling is wrong —
      raise it from PRD 10.2's measured Boot->greeter column. Do NOT make this
      wait for graphical.target: it cannot activate while this check runs."
    fi
    sleep "$POLL"
    elapsed=$((elapsed + POLL))
done

# Networking CAN start. NOT "is connected", and not "can resolve": a desktop
# with no cable and no saved Wi-Fi is healthy, and rolling that machine back
# punishes someone for being offline. greenboot's own DNS check is disabled on
# this image for the same reason.
if ! "$SYSTEMCTL" is-enabled --quiet NetworkManager.service; then
    fail "NetworkManager is not enabled — the machine cannot get online at all."
fi
if "$SYSTEMCTL" is-failed --quiet NetworkManager.service; then
    fail "NetworkManager entered a failed state during boot."
fi

echo "greenboot: desktop health checks passed"
