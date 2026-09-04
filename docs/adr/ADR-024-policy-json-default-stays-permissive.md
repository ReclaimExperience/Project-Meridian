# ADR-024 — policy.json default stays permissive; integrity rides on explicit scopes

**Status:** Accepted — closes ADR-022's open item
**Relates to:** ADR-022, ADR-023, ADR-004 (Advanced tooling)
**Source:** owner decision, 2026-09-04

---

**Decision:** keep `default: insecureAcceptAnything`. Do **not** set
`default: reject`.

Update integrity is enforced by the explicit `sigstoreSigned` rule scoped to our
registry. The only routine image consumer is **bootc pulling our updates**, and
that scope covers it.

`default: reject` breaks `toolbox`/`distrobox` — Advanced tools that legitimately
pull arbitrary images from Fedora, docker.io and quay.io (ADR-004, PRD §3.2). An
allowlist broad enough to keep distrobox working is permissive in practice. So
reject buys **approximately nothing** against the real threat — an attacker who
already has code execution sufficient to run a pull — while breaking real
function.

**Standing guard:** every integrity-critical scope **MUST** be explicitly ruled,
never left to the default. The WP-04 negative test — an unsigned image in our
namespace is refused — is the CI assertion that keeps that scope present and
enforcing. **The permissive default is safe only while that test stays green.**

---

## Why this is a decision and not a shortcut

ADR-022 wrote the permissive default down as a "`:testing`-only development
state" to be tightened once the negative test passed. It has passed. Tightening
it anyway would have been mechanical compliance with a sentence rather than with
its purpose, and it would have cost a shipped feature.

The reasoning that changed it is that `default: reject` protects against the wrong
thing. The threat is a tampered or substituted **update image**, and that arrives
through one path — `bootc` pulling our registry — which the scoped rule already
covers and the negative test already proves. Everything the default would newly
reject is a user deliberately pulling a container in a terminal they had to enable
in Advanced mode.

## What makes it safe, mechanically

Two checks, both of which must keep passing:

1. **`tests/lint/policy_json.py`** asserts our registry scope exists and carries a
   signature requirement. This is the standing guard made mechanical: a permissive
   default is only tolerable while the scope that does the real work is present,
   and "someone deleted the scope" would otherwise be invisible — the file stays
   valid JSON and every image starts being accepted.
2. **The WP-04 negative test** proves that rule is *enforcing*, not merely
   present. A rule that parses but does not refuse anything is the failure this
   ADR's safety argument rests on not happening.

The first runs on every PR; the second on every push to `main` after signing.

**Consequences:**

- If the scoped rule is ever removed, the machine silently accepts **any** image
  from our registry. That is why its presence is asserted rather than trusted.
- `toolbox`/`distrobox` keep working, which is what ADR-004 promised Advanced
  users.
- This does not weaken ADR-022 or ADR-023. Signing, the negative test, and the
  recovery-key requirement are all unchanged; only the default's disposition is
  settled.
