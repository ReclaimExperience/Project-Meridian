#!/usr/bin/env bash
# Answer "is the probe still running?" without guessing.
#
# Deliberately does NOT pattern-match process command lines: that is what made
# a finished probe look alive for two hours and a dead one look alive for six.
set -euo pipefail

STATE="${MERIDIAN_PROBE_STATE:-$HOME/.meridian-probe}"
PIDFILE="$STATE.pid"
LOG="$STATE.log"
LINES="${1:-12}"

if [[ ! -f "$LOG" ]]; then
  echo "probe: no log at $LOG — nothing has run"
  exit 0
fi

now=$(date -u '+%s')
mtime=$(stat -c %Y "$LOG" 2>/dev/null || echo "$now")
idle=$((now - mtime))

if [[ -f "$PIDFILE" ]] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  pid=$(cat "$PIDFILE")
  echo "probe: RUNNING pid $pid, last wrote ${idle}s ago"
  # A live process that has not written in a long time is the shape of a hang,
  # and saying so is the whole point of this script.
  if (( idle > 300 )); then
    echo "probe: WARNING silent for ${idle}s — treat as hung, not as working"
  fi
elif grep -q '^=== PROBE EXIT ' "$LOG"; then
  echo "probe: FINISHED — $(grep '^=== PROBE EXIT ' "$LOG" | tail -1)"
else
  echo "probe: DEAD — no exit sentinel and no live pid; it was killed"
fi

echo "--- last ${LINES} line(s) ---"
sed 's/\x1b\[[0-9;?]*[A-Za-z]//g; s/\r//g' "$LOG" | grep -v '^\s*$' | tail -"$LINES"
