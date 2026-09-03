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

**ADR-022 chose keyless signing** (GitHub OIDC / Sigstore) so that no long-lived
private key would exist. Its VERIFY found the client cannot express it:
containers-common 0.67.0's `fulcio` stanza supports only `oidcIssuer`,
`subjectEmail`, `caPath` and `caData`, while GitHub Actions OIDC certificates
carry the workflow identity in a URI SAN and have no email SAN. So the
pre-authorized fallback is in force — a cosign key pair.

`ci/verify-signing-policy.sh` runs on every build and re-asks that question. **If
it ever reports that identity pinning is available, retire the key**: the reason
to prefer keyless — no key to custody, rotate, or leak — has not gone away.

### Where the key lives

- **Public half:** `os/rootfs/etc/pki/containers/meridian.pub`, shipped in the
  image. ECDSA P-256, SHA-256 fingerprint `920fc4c6…53a5896e`.
- **Private half:** the `COSIGN_PRIVATE_KEY` secret on the **`release` GitHub
  Environment**, behind **required reviewers**. That protection is not
  decoration: it means a human approves every signature, so a compromised
  workflow cannot sign on its own. It is the only thing that makes holding a key
  tolerable after keyless was ruled out.
- Pull requests never reach the `sign` job, so a fork PR cannot touch the key.

Signing is **by digest, never by tag**. A tag is a moving pointer; signing
`:testing` would attest "whatever that name points at right now", which is
precisely what an attacker moves.

### Rotating the key

1. `cosign generate-key-pair` on a trusted machine, outside the repository.
2. Replace `COSIGN_PRIVATE_KEY` and `COSIGN_PASSWORD` on the `release`
   environment.
3. Commit the new `cosign.pub` to `os/rootfs/etc/pki/containers/meridian.pub`.
4. **Re-sign the current `:stable` digest with the new key before shipping the
   new public key**, or installed machines will reject the image they are already
   running from. The public key reaches them in an update; the signature it must
   verify was made before that update existed.
5. Run the negative test.

### Two keys, because one key is a single point of no return (ADR-023)

`policy.json` trusts a **set**: the **primary** (CI, human-gated) and a
**recovery** key whose private half lives **offline, in cold storage, never in CI
or any secret store**.

The reason is narrow and worth stating plainly: a fleet that enforces exactly one
key **cannot be rescued if that key is lost or leaked**, because the image that
would introduce a replacement key must itself be signed by a key the fleet already
trusts. A backup does not help with compromise — a leaked key stays leaked. Only a
distinct, trusted-but-unused key does.

**A bad update rolls back and you ship a fix. A lost key means you cannot ship the
fix.**

> **Currently outstanding.** The recovery key does not exist yet, so the fleet
> trusts one key and is **not recoverable**. Generating it and adding its public
> half **gates the first `:stable` image**. It cannot be done by CI or by an
> agent: a key reachable by either is not a recovery key, it is a second primary.

#### Introducing or rotating a trusted key — the order matters

1. Add the new **public** key to `policy.json`.
2. Build and sign that image **with an already-trusted key**.
3. **Wait for the fleet to adopt it.** Only now do machines trust the new key.
4. Only then may the new key sign anything.

Doing 4 before 3 publishes an image that no machine trusts — and the fix for that
would itself need to be signed by the key they do not have. `sign-image.sh`
verifies its own signature against the shipped public key, which catches a
mismatched pair; it cannot catch this ordering mistake, which is why the protocol
is written down rather than left to care.

#### Do not write two requirements instead of one

Use `keyPaths` with several keys in **one** `sigstoreSigned` requirement. Multiple
requirements in a scope are **ANDed** — verified empirically — so two side by side
demand **both** signatures and break every rotation instead of smoothing it.

### The negative test is the gate

`ci/negative-test-signing.sh` asserts three things, in order: that the policy
rejects *something* (a positive control — otherwise the rest is noise), that the
signed image is **accepted**, and that an unsigned image **in our namespace** is
**refused**. It finds its own unsigned reference: PRs push `pr-*` tags and never
reach the signing job.

Skipping the third assertion **fails** the script. Runs 1 and 2 show the policy
accepts what it should, not that it refuses what it must, and a gate satisfied by
its positive cases alone is not a gate.

**"Negative test green" is a hard gate on the first `:stable` image** (ADR-022,
promote gate 7.5). Until then the permissive default in `policy.json` is an
honest description of a development state, not a lapse.

**Still unverified, and all three gate the first `:stable`:**

1. Whether `bootc upgrade` honours `policy.json` at all. Needs a booted machine.
2. Whether `keyPaths` accepts an image signed by **any one** listed key, or
   requires **all** of them. If it means all, ADR-023's rotation overlap does not
   exist and the protocol above needs redesigning.
3. **A cosign/containers-image version mismatch.** cosign v3.1.3 wrote its
   signature to a tag named `sha256-<hex>`; containers-image looks for
   `sha256-<hex>.sig`. If that reproduces in CI, images we sign **will not verify
   on the machines that receive them**, and it would present as "signing is
   broken everywhere" rather than as a version problem. Pin a cosign version whose
   output containers-image reads, and assert it.

`registries.d/meridian.yaml` is the other half of the client side. Without it the
policy rejects every image, because containers-image never fetches the signature
to check — found the hard way while verifying ADR-023.

## Channels and promotion (PRD §7.5, §7.6)

`:testing` is built from `main`. `:stable` is promoted by **retag of a `:testing`
digest** — never a rebuild, so the bits users get are the bits that were tested.

Promotion requires the gates in §7.5. Nothing here promotes automatically: every
push to `stable` reaches users on their next boot, which is why release
discipline lives in CI gates rather than in anyone's judgement at the time.
