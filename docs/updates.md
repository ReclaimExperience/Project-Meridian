# Updates, channels, and rollback

How a change reaches a machine, and how a machine protects itself when that
change is bad. Implements ADR-008 and ADR-014; the promote gate is PRD §7.5.

## What a user experiences

Nothing. That is the feature.

A timer checks daily, downloads and **stages** an update in the background, and
the new version takes effect the next time the machine is restarted for any
reason. There is no prompt, no progress bar holding the machine hostage, and no
forced restart — ever. ADR-008 exists because that behaviour is the single
most-hated thing about the system these users are leaving.

If a staged update turns out to break the boot, the machine returns to the
previous version by itself and Settings → Updates says so afterwards.

## The pieces

| Unit | What it does |
|---|---|
| `meridian-os-update.timer` | Daily, randomised over 3 h, `Persistent=true` |
| `meridian-os-update.service` | `bootc upgrade` — **stages only**, never reboots |
| `meridian-flatpak-update.timer` | Twice daily, apps only |
| `meridian-update-status.service` | Publishes the status file on every boot |
| `meridian-maintenance.target` | Wants the timers — one place to see it all |

`systemctl list-dependencies meridian-maintenance.target` answers "what does this
machine do when nobody is looking". ADR-011 says a user is entitled to a straight
answer to that, so it is one command rather than an archaeology exercise.

### Why there is no `--apply` anywhere

`bootc upgrade --apply` reboots. Its absence in `os-update` is deliberate, not an
oversight, and WP-04's Forbidden list names auto-reboot logic explicitly. If you
are reading this because you want an update to take effect now: restart the
machine.

### Metered connections

Skipped, via NetworkManager's metered flag. Someone tethered to a phone should
not discover a multi-gigabyte OS image on their bill because a timer fired.

## Health checks and rollback

greenboot runs `/usr/lib/greenboot/check/required.d/` on each boot. Ours checks:

1. `graphical.target` reached within 90 s;
2. `display-manager.service` active — **not** `sddm`. Fedora 44 ships plasmalogin
   and `is-active sddm` answers "inactive" on a perfectly healthy boot, which
   would roll back every good update forever;
3. NetworkManager is enabled and not failed — **not** "is connected". A desktop
   with no cable and no saved Wi-Fi is healthy, and rolling that machine back
   would punish someone for being offline.

A failed required check spends greenboot's retries and then boots the previous
deployment. `red.d/` writes `/var/lib/meridian/rollback-happened`, which is what
lets Settings say what happened instead of leaving the user with a machine that
quietly behaves differently.

**Adding a check is a serious act.** Every false positive costs somebody their
update, silently, and they will never know why. Check things whose absence a
person would actually notice; nothing that is merely interesting.

## The status file (contract 8.0)

`bootc` is daemonless and has no D-Bus API, so `/run/meridian/update-status.json`
is the interface to Settings, not a convenience. Shape:
`catalog/schemas/update-status.schema.json`, contract-tested in
`tests/lint/test_update_status.py`.

Written atomically. `/run` is a tmpfs, so it is republished on every boot — which
is exactly when it matters, because the boot after a rollback is when Settings
most needs something true to show.

`state` is one of `up-to-date`, `staged`, `rolled-back`, `error`. **`rolled-back`
outranks `staged`**: a machine that healed itself must say so even when an update
is also waiting, because that is the one state the user is owed an explanation
for and good news must not bury it.

## Signing

Images are cosign-signed in CI (ADR-014). `os/rootfs/etc/containers/policy.json`
is the client half — without it the signing is theatre, since nothing checks it.

The scoped rule requires a signature for our repository. The **default is
permissive on purpose**: this ships before the key exists, and a policy that
rejects everything produces an unbootable machine rather than a secure one. It
tightens when signing is live and the negative test passes — an unsigned or
wrong-key image must be **refused**, and until that test exists the enforcement
is unproven whatever the file says.

PRD WP-04 specifies `usr/etc/containers/policy.json`. That path cannot be built:
`bootc container lint` rejects `/usr/etc`, as WP-01 already found and recorded.

## Channels and promotion (PRD §7.5, §7.6)

`:testing` is built from `main`. `:stable` is promoted by **retag of a `:testing`
digest** — never a rebuild, so the bits users get are the bits that were tested.

Promotion requires the gates in §7.5. Nothing here promotes automatically: every
push to `stable` reaches users on their next boot, which is why release
discipline lives in CI gates rather than in anyone's judgement at the time.
