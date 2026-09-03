# ADR-022 — Image signing is keyless (GitHub OIDC / Sigstore), implementing ADR-014

**Status:** Accepted — **primary design blocked by VERIFY; pre-authorized fallback in force**
**Implements:** ADR-014
**Source:** owner decision, 2026-09-03

---

**Decision:** sign OS images in CI via cosign **keyless** — a Fulcio short-lived
certificate bound to the GitHub Actions OIDC identity, logged to Rekor. No
long-lived private key exists to custody, rotate, or leak; the signer **is** the
release workflow. The client `/etc/containers/policy.json` pins our identity
(`certificate-identity` = the release workflow ref, `oidc-issuer` = GitHub's).

**Why:** matches ADR-014 (public from day 1, zero-infrastructure distribution);
deletes the "where does the key live" problem rather than managing it; standard
practice for public GHCR.

**VERIFY** (blocks the negative test, **not** the drill): confirm that bootc +
containers-policy can enforce a keyless sigstore identity match and honour it on
`bootc upgrade`.

**Fallback** (pre-authorized, no escalation): if bootc cannot do keyless, a cosign
key pair — public key baked into the image policy, private key in a GitHub
Environment secret with required-reviewer protection and documented rotation. The
negative test is identical either way.

**Consequence:** the permissive default policy is a **`:testing`-only development
state**. "Negative test green" is a **hard gate on the first `:stable` image**
(promote gate 7.5).

---

## VERIFY result (2026-09-03): the client half cannot express it

`ci/verify-signing-policy.sh` is the check, committed so the answer is
reproducible rather than remembered. Run against **containers-common 0.67.0 /
skopeo 1.22.2 (Fedora 44 — the version the image ships)**:

```
positive control: a reject-all policy does reject
fulcio identity fields supported here:
  subjectEmail                 yes
  subjectHostname              no
  subjectURI                   no
  certificateIdentity          no
  certificateIdentityRegexp    no
  identityRegexp               no
  subject                      no
```

`fulcio` accepts exactly `oidcIssuer`, `subjectEmail`, `caPath`, `caData`. There
is **no field for a certificate identity or URI SAN**. GitHub Actions OIDC
certificates carry the workflow identity as a URI SAN —
`https://github.com/OWNER/REPO/.github/workflows/…@refs/…` — and have **no email
SAN**, so neither supported field can express "signed by our release workflow".

The decision's own words — *"client policy.json pins our identity
(certificate-identity = the release workflow ref)"* — are therefore not
implementable on the shipping stack. **The fallback is in force.**

Two honest limits on that finding:

1. It establishes what the **policy language** can express. Whether `bootc
   upgrade` honours `policy.json` **at all** is the other half of the VERIFY and
   still needs a booted VM. That half applies equally to the key-pair fallback and
   still gates the negative test.
2. It is a statement about one version. Re-run the script after a
   containers-image update; if an identity field appears, keyless becomes
   implementable and **the key pair should be retired**, since the reason for
   preferring keyless — no key to custody — has not gone away.

### A note on how nearly this went wrong

The first version of the verification script reported that **all seven** identity
fields were supported — the opposite conclusion, and the dangerous direction: it
would have had us ship a policy that looks like it pins an identity and enforces
nothing. The cause was `skopeo … | grep -q 'Unknown key'` under `set -o pipefail`:
`grep -q` exits the moment it matches, `skopeo` dies of SIGPIPE, and `pipefail`
makes the pipeline non-zero — so the `if` read false exactly when the match
succeeded. It was caught only because it disagreed with a manual result taken
minutes earlier.

An earlier version was worse and quieter: it used `skopeo inspect`, which does not
enforce policy at all, so three different policy shapes all "passed" without ever
being evaluated. Hence the positive control that now runs first: if a
reject-everything policy does not reject, nothing below it means anything.

**Consequences of the fallback being in force:**

- A private key now exists, which is precisely the problem this ADR wanted to
  delete. It lives in a GitHub Environment secret with required reviewers, and
  rotation is documented in `docs/updates.md` — a procedure that exists is the
  minimum price of holding a key at all.
- The first `:stable` image is still gated on the negative test. Until an
  unsigned or wrong-key image is demonstrably **refused**, signing is unproven
  whatever the files say, and the permissive default stays honest about that.
