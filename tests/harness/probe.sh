#!/usr/bin/env bash
# Run a one-off VM probe with a status you can trust.
#
# Three failures this replaces, all of which cost hours rather than minutes:
#
#   * `pgrep -f probe.py` matches the SSH command line that contains that
#     string, so a finished probe reports as running — and `pkill -f` with the
#     same pattern kills the querying shell. Liveness is a PID file plus
#     `kill -0` here, which cannot match itself.
#   * Python buffers stdout when it is redirected, so a log stays empty until
#     the process exits: "no output yet" and "hung for six hours" look
#     identical. `-u` makes progress visible as it happens.
#   * A crashed probe leaves a log that simply stops. There is no way to tell
#     that from one still working. Every run now ends with a sentinel line,
#     so "did this finish" is a grep, not an inference.
set -euo pipefail

SCRIPT="${1:?usage: probe.sh <script.py> [timeout_seconds]}"
TIMEOUT="${2:-1200}"
STATE="${MERIDIAN_PROBE_STATE:-$HOME/.meridian-probe}"
PIDFILE="$STATE.pid"
LOG="$STATE.log"

if [[ -f "$PIDFILE" ]] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  echo "probe: already running (pid $(cat "$PIDFILE")); refusing to start a second"
  echo "probe: two probes fight over the disk lock and both fail confusingly"
  exit 1
fi

: >"$LOG"
{
  echo "=== PROBE START $(date -u '+%Y-%m-%dT%H:%M:%SZ') $SCRIPT (timeout ${TIMEOUT}s) ==="
} >>"$LOG"

# Unbuffered, so the log is a progress indicator rather than a post-mortem.
#
# The sentinel is written by the SAME shell that runs the probe. An earlier
# version put it in a separate background subshell calling `wait $PID`, which
# silently does nothing: `wait` only works on children of the calling shell, so
# it returned immediately and stamped "EXIT 0" while the probe was still
# booting the VM. A status tool that lies is worse than no status tool, so this
# one is tested below rather than assumed.
export MERIDIAN_RUN_SCRIPT="$SCRIPT" MERIDIAN_RUN_LOG="$LOG"
export MERIDIAN_RUN_PIDFILE="$PIDFILE" MERIDIAN_RUN_TIMEOUT="$TIMEOUT"
# shellcheck disable=SC2016  # deliberate: the inner shell expands these, not us.
setsid bash -c '
  timeout -k 10 "$MERIDIAN_RUN_TIMEOUT" python3 -u "$MERIDIAN_RUN_SCRIPT" \
      >>"$MERIDIAN_RUN_LOG" 2>&1
  code=$?
  echo "=== PROBE EXIT ${code} $(date -u "+%Y-%m-%dT%H:%M:%SZ") ===" \
      >>"$MERIDIAN_RUN_LOG"
  rm -f "$MERIDIAN_RUN_PIDFILE"
' >/dev/null 2>&1 &
PID=$!
echo "$PID" >"$PIDFILE"

echo "probe: started pid $PID, log $LOG"
