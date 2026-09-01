# The complete dev vocabulary (PRD 7.1).
#
# THE GOLDEN RULE: if it isn't reproduced by `just <target>` from a clean
# checkout, it doesn't exist. Nothing here may depend on a hand-configured VM.
#
# Targets not yet implemented fail loudly, naming the work package that owns
# them. That is deliberate: a silent no-op would let an agent believe it built
# something.

set shell := ["bash", "-euo", "pipefail", "-c"]

_default:
    @just --list --unsorted

# ---------------------------------------------------------------- helpers ---

_todo wp target:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "just {{ target }}: not implemented yet — owned by {{ wp }}."
    echo "See docs/PRD.md section 8, {{ wp }}, for its deliverables and acceptance list."
    exit 1

# ------------------------------------------------------------------- lint ---

# Full lint suite (PRD 6.3). Green from day one — this is WP-00's acceptance.
lint: lint-shell lint-python lint-schemas lint-branding lint-strings lint-markdown
    @echo
    @echo "lint: all checks passed"

# shellcheck every tracked shell script
lint-shell:
    #!/usr/bin/env bash
    set -euo pipefail
    # NOTE: macOS ships bash 3.2, which has no `mapfile`. Build the array the
    # portable way so this recipe behaves identically on the Mac dev loop and on
    # CI's bash 5 (PRD 7.2: nothing may require macOS specifics, and nothing may
    # silently pass because a builtin was missing).
    files=()
    while IFS= read -r f; do files+=("$f"); done < <(git ls-files '*.sh')
    if [ ${#files[@]} -eq 0 ]; then echo "  lint-shell: no shell scripts tracked yet"; exit 0; fi
    shellcheck "${files[@]}"
    echo "  lint-shell: ${#files[@]} script(s) clean"

# ruff over every tracked Python file
lint-python:
    #!/usr/bin/env bash
    set -euo pipefail
    files=()
    while IFS= read -r f; do files+=("$f"); done < <(git ls-files '*.py')
    if [ ${#files[@]} -eq 0 ]; then echo "  lint-python: no Python tracked yet"; exit 0; fi
    ruff check "${files[@]}"
    ruff format --check "${files[@]}"
    echo "  lint-python: ${#files[@]} file(s) clean"

# validate every JSON data contract against its schema
lint-schemas:
    @python3 tests/lint/schemas.py

# the rename invariant (PRD 6.5) — product name lives in branding.json only
lint-branding:
    @./tests/lint/branding.sh

# INV-0 + voice rules over user-visible strings (PRD 0.3, 4.5)
lint-strings:
    @./tests/lint/strings.sh

lint-markdown:
    #!/usr/bin/env bash
    set -euo pipefail
    if ! command -v markdownlint >/dev/null 2>&1; then
        echo "  lint-markdown: markdownlint not installed — skipped (CI installs it)"; exit 0
    fi
    files=()
    while IFS= read -r f; do files+=("$f"); done < <(git ls-files '*.md')
    markdownlint --config .markdownlint.json "${files[@]}"
    echo "  lint-markdown: clean"

# prove the lints actually catch what they claim to (WP-00 acceptance)
test-lint:
    @./tests/lint/test_branding_lint.sh
    @echo
    @./tests/lint/test_strings_lint.sh

# ------------------------------------------------------------------ build ---

# Build the OS image. arch: x86_64 (default) | aarch64
build arch="x86_64":
    @just _todo WP-01 "build {{ arch }}"

# bootc-image-builder: image -> bootable qcow2
vm-image arch="x86_64":
    @just _todo WP-01 "vm-image {{ arch }}"

# Boot the qcow2 under qemu (KVM/HVF/TCG autodetect)
vm-run arch="x86_64":
    @just _todo WP-01 "vm-run {{ arch }}"

# Boot the installer ISO under qemu
vm-run-iso:
    @just _todo WP-16 "vm-run-iso"

# ------------------------------------------------------------------- test ---

# Run a harness suite: smoke | stories | screens | perf | security | privacy
vm-test suite="smoke":
    @just _todo WP-03 "vm-test {{ suite }}"

# Re-baseline one screenshot, deliberately (PRD 7.4, rule R-F)
baseline screen:
    @just _todo WP-03 "baseline {{ screen }}"

# Perf gates: idle RAM and boot time (PRD 1.5)
perf:
    @just _todo WP-02 "perf"

# ----------------------------------------------------------------- assets ---

# Regenerate rasters/wallpapers from SVG sources and template branding strings
assets:
    @just _todo WP-05 "assets"

# -------------------------------------------------------------------- iso ---

# Build the installable live ISO
iso:
    @just _todo WP-16 "iso"

# ------------------------------------------------------------------ verify ---

# ADR-002 base-image verification (the [VERIFY] gate on the whole stack)
verify-base:
    @just _todo WP-01 "verify-base"
