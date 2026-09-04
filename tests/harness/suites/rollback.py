"""Rollback drill (WP-04): a bad update must undo itself.

ADR-008 promises a boot that fails its health checks "automatically reboots into
the previous deployment and flags the failure to Settings". This is the test of
that promise, and PRD WP-04 calls it the flagship.

It breaks the machine the way a bad update breaks it — a unit that makes
graphical.target fail — and then asserts the machine returns to the previous
deployment ON ITS OWN. WP-04 forbids shortening the drill by faking the failure
detection, so nothing here plants the rollback marker, disables a health check,
or tells greenboot what to conclude.

Two assertions, and the second is the one a user would notice:

  1. the booted deployment is the ORIGINAL image again;
  2. /var/lib/meridian/rollback-happened exists, so Settings can say what
     happened rather than leaving someone with a machine that quietly behaves
     differently (contract 8.0).

If this fails, the interesting question is always "did the health check even
run?", so the failure path collects greenboot's own state rather than reporting
a timeout. PRD WP-04 flags greenboot+bootc integration as [VERIFY], with our own
boot-counter as the pre-authorized fallback — and telling those two outcomes
apart needs evidence, not a stopwatch.
"""

from __future__ import annotations

import time

from harness.vm import VM

# Each failed boot costs the health check's own timeout plus a boot, and
# greenboot retries GREENBOOT_MAX_BOOT_ATTEMPTS (3) times before rolling back.
ROLLBACK_DEADLINE = 900


def _booted_image(console) -> tuple[str, str]:
    """The image digest this machine is running, and the raw status behind it.

    Returns the raw output too, because "unknown" is the answer that stops the
    drill and the next question is always "what did bootc actually say?". The
    first run of this drill returned unknown and the transcript held nothing to
    explain it — the diagnostic cost more than the fix.

    Uses `sudo -n`, never bare `sudo`. The harness account can sudo but the disk
    image must grant it without a password: a prompt on a serial console does not
    fail, it HANGS until the step times out, and the drill lost a cycle to a
    120-second wait that read like bootc being broken. `-n` turns that into an
    instant, legible error.
    """
    _status, raw = console.run(
        "sudo -n bootc status --json 2>&1 | head -c 4000", timeout=120
    )
    _status, parsed = console.run(
        "sudo -n bootc status --json 2>/dev/null | "
        'python3 -c "import json,sys\n'
        "try:\n"
        "    d=json.load(sys.stdin)\n"
        "except Exception as e:\n"
        "    print('PARSE-ERROR:'+str(e)[:80]); raise SystemExit(0)\n"
        "b=((d.get('status') or {}).get('booted') or {})\n"
        "i=(b.get('image') or {})\n"
        "print(i.get('imageDigest') or ((i.get('image') or {}).get('image')) or 'unknown')\" "
        "|| echo unknown",
        timeout=120,
    )
    for line in parsed.splitlines():
        line = line.strip()
        if line.startswith(("sha256:", "ghcr.io", "PARSE-ERROR:")) or line == "unknown":
            return line, raw.strip()
    return "unknown", raw.strip()


def _greenboot_evidence(console) -> str:
    """What greenboot actually did. Collected only when the drill fails."""
    parts = []
    for label, command in (
        ("healthcheck unit", "systemctl is-enabled greenboot-healthcheck.service 2>&1"),
        (
            "healthcheck result",
            "systemctl is-active greenboot-healthcheck.service 2>&1",
        ),
        (
            "boot counter",
            "sudo -n grub2-editenv list 2>/dev/null | grep -i boot || echo none",
        ),
        (
            "greenboot journal",
            "journalctl -u greenboot-healthcheck --no-pager -n 8 2>&1 | tail -8",
        ),
        (
            "our check ran",
            "journalctl --no-pager -n 20 2>&1 | grep -c greenboot || true",
        ),
    ):
        _s, out = console.run(command, timeout=90)
        parts.append(f"  {label}: {out.strip()[:300]}")
    return "\n".join(parts)


def run(vm: VM, credentials: dict) -> None:
    console = vm.console
    user, password = credentials["user"], credentials["password"]
    sabotage = credentials.get("sabotage_ref")
    if not sabotage:
        raise AssertionError(
            "no sabotage_ref supplied. The drill needs a deliberately broken image "
            "to stage; running it without one would assert nothing and pass."
        )

    console.login(user, password, timeout=600)
    original, raw = _booted_image(console)
    print(f"rollback: booted deployment before the drill: {original}")
    if original == "unknown" or original.startswith("PARSE-ERROR:"):
        raise AssertionError(
            "could not read the booted image from `bootc status`. The drill "
            "compares before and after, so an unknown 'before' would let any "
            "'after' look like a successful rollback.\n"
            f"  parser said: {original}\n"
            f"  bootc status --json said:\n    {raw[:1200]}"
        )

    # Test scaffolding, not a product change: the drill serves the sabotage image
    # from a plain-HTTP registry on the host (10.0.2.2 under QEMU user
    # networking). This teaches the guest to fetch from it. It affects how the
    # image is OBTAINED, never how the failure is detected or how rollback is
    # decided, which are what the drill asserts.
    console.run(
        "sudo -n mkdir -p /etc/containers/registries.conf.d && "
        "printf '[[registry]]\\nlocation = \"10.0.2.2:5000\"\\ninsecure = true\\n' | "
        "sudo -n tee /etc/containers/registries.conf.d/99-drill.conf >/dev/null",
        timeout=120,
    )

    print(f"rollback: staging the sabotage image {sabotage}")
    _st, out = console.run(f"sudo -n bootc switch --retain {sabotage}", timeout=900)
    _s, staged = console.run("sudo -n bootc status 2>&1 | head -30", timeout=120)
    if "sabotage" not in staged and "10.0.2.2" not in staged:
        raise AssertionError(
            "the sabotage image does not appear staged, so a reboot would prove "
            "nothing.\n"
            f"  bootc switch said: {out.strip()[:400]}\n"
            f"  bootc status says: {staged.strip()[:400]}"
        )
    print("rollback: sabotage staged; rebooting into it")

    console.send_line("sudo -n systemctl reboot")

    # The machine now boots the sabotage, fails its health check, and greenboot
    # retries. Poll rather than sleep: each failed boot still reaches multi-user
    # and offers a login prompt, so "there is a login prompt" does NOT mean the
    # drill is over. Only the booted digest does.
    deadline = time.time() + ROLLBACK_DEADLINE
    attempts = 0
    while time.time() < deadline:
        time.sleep(30)
        attempts += 1
        try:
            console.login(user, password, timeout=180)
            current, _raw = _booted_image(console)
        except Exception as exc:  # noqa: BLE001 — mid-reboot, try again
            print(
                f"rollback: poll {attempts}: console not ready ({type(exc).__name__})"
            )
            continue
        print(f"rollback: poll {attempts}: booted {current}")
        if current == original:
            break
    else:
        evidence = _greenboot_evidence(console)
        raise AssertionError(
            f"the machine did not return to {original} within "
            f"{ROLLBACK_DEADLINE}s.\n"
            "  Either the health check never ran, or it ran and nothing acted on\n"
            "  the result. PRD WP-04 flags greenboot+bootc integration as\n"
            "  [VERIFY]; if the checks ran and no rollback followed, the\n"
            "  pre-authorized fallback applies — our own boot-counter unit\n"
            "  replicating greenboot semantics on top of `bootc rollback`.\n"
            f"{evidence}"
        )

    print(f"rollback: back on the original deployment {original}")

    _status, marker = console.run(
        "cat /var/lib/meridian/rollback-happened 2>/dev/null || echo ABSENT", timeout=90
    )
    if "ABSENT" in marker:
        raise AssertionError(
            "the machine rolled back, but /var/lib/meridian/rollback-happened was "
            "not written.\n"
            "  Settings reads that marker to tell the user their update was undone\n"
            "  (contract 8.0). Without it the machine silently behaves differently\n"
            "  than it did an hour ago and nobody is told why — which is the half\n"
            "  of ADR-008's promise that faces the person using it."
        )
    print(f"rollback: marker present ({marker.strip()[:60]})")

    _status, sabotage_marker = console.run(
        "test -f /usr/share/meridian/drill-sabotage-marker && echo STILL-SABOTAGED || echo clean",
        timeout=90,
    )
    if "STILL-SABOTAGED" in sabotage_marker:
        raise AssertionError(
            "the booted deployment still contains the sabotage marker, so the "
            "digest comparison matched something it should not have."
        )
    print("rollback: the sabotage image is no longer the booted deployment")
    vm.write_report(
        f"rollback-{vm.arch}",
        {"original": original, "sabotage": sabotage, "polls": attempts},
    )
