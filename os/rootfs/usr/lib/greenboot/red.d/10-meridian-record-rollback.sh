#!/usr/bin/env bash
# greenboot ran out of retries and the machine is going back. Leave a marker so
# Settings can tell the truth about it (contract 8.0, WP-12's Updates page).
#
# Without this the rollback is invisible: the machine quietly returns to the
# previous version and the person is left with a computer that behaves
# differently for no reason they were given. ADR-008 promises the failure is
# "flagged to Settings → Updates", and this is that flag.
set -euo pipefail
MARKER=/var/lib/meridian/rollback-happened
mkdir -p "$(dirname "$MARKER")"
date -Is > "$MARKER"
echo "meridian: recorded automatic rollback at $(cat "$MARKER")"
