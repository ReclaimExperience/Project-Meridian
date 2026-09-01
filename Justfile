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
lint: lint-toolchain lint-shell lint-justfile lint-python lint-schemas lint-branding lint-strings lint-codeowners lint-markdown
    @echo
    @echo "lint: all checks passed"

# Fail when the local linters differ from ci/tool-versions.env. A green run on a
# different shellcheck says nothing about CI — that exact drift made `just lint`
# green locally and red in CI on the same commit. Set MERIDIAN_ALLOW_TOOL_DRIFT=1
# to proceed anyway, knowing the result is not comparable to CI's.
lint-toolchain:
    #!/usr/bin/env bash
    set -euo pipefail
    # Resolved at runtime relative to the repo root; shellcheck cannot follow it.
    # shellcheck source=/dev/null
    source ci/tool-versions.env
    drift=0
    check() {
        if [ "$2" != "$3" ]; then
            echo "  $1: have $3, pinned $2"
            drift=1
        fi
    }
    check shellcheck   "$SHELLCHECK_VERSION"   "$(shellcheck --version | awk '/^version:/{print $2}')"
    check ruff         "$RUFF_VERSION"         "$(ruff --version | awk '{print $2}')"
    check markdownlint "$MARKDOWNLINT_VERSION" "$(markdownlint --version 2>/dev/null || echo absent)"
    if [ "$drift" -ne 0 ]; then
        if [ "${MERIDIAN_ALLOW_TOOL_DRIFT:-0}" = "1" ]; then
            echo "  lint-toolchain: drift allowed by MERIDIAN_ALLOW_TOOL_DRIFT=1 — results are NOT comparable to CI"
            exit 0
        fi
        echo "  lint-toolchain: FAILED — pinned versions live in ci/tool-versions.env."
        echo "                  Install the pinned versions, or set"
        echo "                  MERIDIAN_ALLOW_TOOL_DRIFT=1 to accept a result CI will not reproduce."
        exit 1
    fi
    echo "  lint-toolchain: matches ci/tool-versions.env"

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

# shellcheck the bash embedded in Justfile recipes — the largest unlinted
# shell surface in the repo, and where every shell defect so far has lived.
lint-justfile:
    @python3 tests/lint/justfile_shell.py

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

# every CODEOWNERS rule must be able to match something (rule R-H)
lint-codeowners:
    @./tests/lint/codeowners.sh

lint-markdown:
    #!/usr/bin/env bash
    set -euo pipefail
    if ! command -v markdownlint >/dev/null 2>&1; then
        echo "  lint-markdown: FAIL — markdownlint-cli is not installed."
        echo "                 Install it (npm i -g markdownlint-cli); a skipped"
        echo "                 check that reports success is how false greens start."
        exit 1
    fi
    files=()
    while IFS= read -r f; do files+=("$f"); done < <(git ls-files '*.md')
    markdownlint --config .markdownlint.json --ignore-path .markdownlintignore "${files[@]}"
    echo "  lint-markdown: clean"

# prove the lints and parsers actually do what they claim to
test-lint:
    @./tests/lint/test_branding_lint.sh
    @echo
    @./tests/lint/test_strings_lint.sh
    @echo
    @python3 tests/lint/test_packages_parser.py

# ------------------------------------------------------------------ build ---

# Where the ADR-002 decision is recorded. `just verify-base` regenerates it;
# `just build` consumes it. This is verify-then-use (PRD 0.2) with an auditable
# committed record, instead of a network round trip on every single build.
base_env := "os/base-images.env"

# Build the OS image. arch: x86_64 (default) | aarch64
build arch="x86_64":
    #!/usr/bin/env bash
    set -euo pipefail
    if [ ! -f "{{ base_env }}" ]; then
        echo "just build: {{ base_env }} is missing — run 'just verify-base' first (ADR-002)."
        exit 1
    fi
    # shellcheck source=/dev/null
    source "{{ base_env }}"

    case "{{ arch }}" in
        x86_64)  platform=linux/amd64; base="$BASE_X86_64" ;;
        aarch64) platform=linux/arm64; base="$BASE_AARCH64" ;;
        *) echo "just build: unknown arch '{{ arch }}' (want x86_64 or aarch64)"; exit 1 ;;
    esac

    read_brand() { python3 -c "import json,sys;d=json.load(open('os/rootfs/usr/share/meridian/branding.json'));print(eval(sys.argv[1],{'d':d}))" "$1"; }
    name="$(read_brand "d['name']")"
    tagline="$(read_brand "d['tagline']")"
    source_url="$(read_brand "d['urls']['source']")"
    version="$(read_brand "d['version']")"
    image="$(read_brand "d['registry']['namespace'] + '/' + d['registry']['image']")"

    tag="${image}:testing-{{ arch }}"
    echo "building ${tag}"
    echo "  base:     ${base}"
    echo "  platform: ${platform}"

    # Pull the base separately, with retries. `podman build` does its own pull
    # with none, and a single CDN hiccup from the registry then fails the whole
    # job — which happened: "unable to copy from source ...fedora-kinoite:44:
    # unexpected EOF (while reconnecting)". Rule R-A treats flaky as broken, so
    # the transient case gets handled rather than re-run.
    podman pull --retry 3 --retry-delay 5s --platform "${platform}" "${base}"

    podman build \
        --platform "${platform}" \
        --build-arg "BASE_IMAGE=${base}" \
        --build-arg "MERIDIAN_VERSION=${version}" \
        --build-arg "MERIDIAN_CHANNEL=testing" \
        --build-arg "BRAND_NAME=${name}" \
        --build-arg "BRAND_TAGLINE=${tagline}" \
        --build-arg "BRAND_SOURCE_URL=${source_url}" \
        --build-arg "BUILD_DATE=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
        --build-arg "GIT_SHA=$(git rev-parse --short HEAD)" \
        --tag "${tag}" \
        --file os/Containerfile \
        os/

    echo
    echo "built ${tag}"
    podman image inspect "${tag}" --format '  size: {{{{ .Size }} bytes'

# bootc-image-builder: image -> bootable qcow2
vm-image arch="x86_64":
    #!/usr/bin/env bash
    set -euo pipefail
    image="$(python3 -c "import json;d=json.load(open('os/rootfs/usr/share/meridian/branding.json'));print(d['registry']['namespace']+'/'+d['registry']['image'])")"
    tag="${image}:testing-{{ arch }}"

    if ! podman image exists "${tag}"; then
        echo "just vm-image: ${tag} not found — run 'just build {{ arch }}' first."
        exit 1
    fi

    case "{{ arch }}" in
        x86_64)  platform=linux/amd64; want=x86_64 ;;
        aarch64) platform=linux/arm64; want=aarch64 ;;
        *) echo "just vm-image: unknown arch '{{ arch }}'"; exit 1 ;;
    esac

    # bootc-image-builder runs podman inside itself. Under qemu emulation that
    # nested podman cannot allocate its locks:
    #
    #   failed to open 2048 locks in /libpod_lock: numerical result out of range
    #
    # Confirmed on an Apple Silicon host building x86_64, with and without
    # --ipc=host. `just build {{ arch }}` cross-builds fine — it is only the
    # DISK image step that cannot cross-build. PRD 7.2 already makes CI the
    # authoritative x86_64 loop; this is the concrete reason.
    host="$(uname -m)"
    [ "$host" = "arm64" ] && host=aarch64
    if [ "$want" != "$host" ] && [ "${MERIDIAN_FORCE_CROSS_VM_IMAGE:-0}" != "1" ]; then
        echo "just vm-image: cannot build a ${want} disk image on a ${host} host."
        echo
        echo "  bootc-image-builder runs podman inside itself, and the nested"
        echo "  podman fails under emulation with:"
        echo "    failed to open 2048 locks in /libpod_lock: numerical result out of range"
        echo
        echo "  'just build {{ arch }}' does work — only this disk-image step cannot"
        echo "  cross-build. Use CI for ${want} disk images (PRD 7.2), or set"
        echo "  MERIDIAN_FORCE_CROSS_VM_IMAGE=1 to try anyway."
        exit 1
    fi

    # bootc-image-builder refuses to run rootless. On the Mac dev loop that means
    # the podman machine has to be rootful; its message alone does not say how.
    if [ "$(podman info --format '{{{{ .Host.Security.Rootless }}')" = "true" ]; then
        echo "just vm-image: bootc-image-builder requires rootful podman."
        echo
        echo "  On macOS (PRD 7.2):"
        echo "    podman machine stop && podman machine set --rootful && podman machine start"
        echo "    just build {{ arch }}      # rootful storage is separate; rebuild into it"
        echo
        echo "  On Linux: run this target as root, or use a rootful podman socket."
        exit 1
    fi

    mkdir -p build
    # bootc-image-builder reads the source image straight out of the local
    # container store, so the store has to be visible inside it. Ask podman
    # where the store actually is rather than assuming the rootful path —
    # the Mac dev loop (PRD 7.2) runs a rootless podman machine.
    graphroot="$(podman info --format '{{{{ .Store.GraphRoot }}')"

    echo "building qcow2 from ${tag}"
    podman run --rm --privileged \
        --platform "${platform}" \
        --security-opt label=type:unconfined_t \
        -v "$(pwd)/build:/output" \
        -v "${graphroot}:/var/lib/containers/storage" \
        quay.io/centos-bootc/bootc-image-builder:latest \
        --type qcow2 \
        --local "${tag}"

    find build -name '*.qcow2' -exec ls -lh {} \;

# Boot the qcow2 under qemu (HVF on Apple Silicon, KVM on Linux, else TCG). mode: gui | headless
vm-run arch="x86_64" mode="gui":
    #!/usr/bin/env bash
    set -euo pipefail
    # `find build` exits non-zero when build/ does not exist, and under
    # `set -euo pipefail` that killed the recipe before reaching the helpful
    # message below — so the error branch was unreachable in exactly the case
    # it was written for.
    disk=""
    if [ -d build ]; then
        disk="$(find build -name '*.qcow2' 2>/dev/null | head -1 || true)"
    fi
    if [ -z "$disk" ]; then
        echo "just vm-run: no qcow2 in build/ — run 'just vm-image {{ arch }}' first."
        exit 1
    fi

    # Locate UEFI firmware across distros. The previous version used
    # `brew --prefix qemu 2>/dev/null`, whose failure under `set -e` aborted the
    # recipe with NO output at all on any machine without Homebrew — and its
    # fallback path was Debian-only. That made the dev loop depend on one
    # machine's setup rather than on repo files.
    find_firmware() {
        local name dir
        local dirs=(/usr/share/qemu /usr/share/edk2/aarch64 /usr/share/edk2/x64
                    /usr/share/edk2/ovmf /usr/share/OVMF /usr/share/AAVMF
                    /usr/share/qemu-efi-aarch64)
        if command -v brew >/dev/null 2>&1; then
            local prefix
            prefix="$(brew --prefix qemu 2>/dev/null || true)"
            [ -n "$prefix" ] && dirs=("${prefix}/share/qemu" "${dirs[@]}")
        fi
        for name in "$@"; do
            for dir in "${dirs[@]}"; do
                [ -f "${dir}/${name}" ] && { echo "${dir}/${name}"; return 0; }
            done
        done
        echo "just vm-run: no UEFI firmware found. Looked for [$*] in:" >&2
        printf '  %s\n' "${dirs[@]}" >&2
        echo "Install one: macOS 'brew install qemu'; Fedora 'edk2-ovmf'/'edk2-aarch64';" >&2
        echo "Debian/Ubuntu 'ovmf'/'qemu-efi-aarch64'." >&2
        return 1
    }

    host_arch="$(uname -m)"
    accel=tcg
    case "$(uname -s)" in
        Darwin) [ "{{ arch }}" = "aarch64" ] && [ "$host_arch" = "arm64" ] && accel=hvf ;;
        Linux)  [ -w /dev/kvm ] && [ "{{ arch }}" = "$host_arch" ] && accel=kvm ;;
    esac

    # shellcheck disable=SC2054  # the commas are inside quoted qemu arguments
    common=(-m 4096 -smp 4 -drive "file=${disk},if=virtio,format=qcow2"
            -device virtio-net-pci,netdev=n0 -netdev user,id=n0
            -device virtio-rng-pci)

    case "{{ arch }}" in
        aarch64)
            fw="$(find_firmware edk2-aarch64-code.fd QEMU_EFI.fd AAVMF_CODE.fd)"
            bin=qemu-system-aarch64
            args=(-M virt -cpu host -bios "$fw" -device virtio-gpu-pci
                  -device qemu-xhci -device usb-kbd -device usb-tablet)
            [ "$accel" = "tcg" ] && args=("${args[@]/-cpu host/-cpu cortex-a72}")
            ;;
        x86_64)
            # ADR-013 makes UEFI the first-class boot path, and bootc-image-builder
            # emits a UEFI-oriented qcow2. Booting SeaBIOS here would not work.
            fw="$(find_firmware edk2-x86_64-code.fd OVMF_CODE.fd OVMF.fd)"
            bin=qemu-system-x86_64
            args=(-M q35 -bios "$fw" -device virtio-vga
                  -device qemu-xhci -device usb-kbd -device usb-tablet)
            ;;
        *) echo "just vm-run: unknown arch '{{ arch }}'"; exit 1 ;;
    esac

    display=(-display cocoa)
    [ "$(uname -s)" = "Linux" ] && display=(-display gtk)
    # headless: no window, plus the three things needed to inspect a boot from a
    # script — a serial log, a VNC surface, and a QMP socket. WP-03's harness
    # drives exactly these; this target is what it will build on.
    if [ "{{ mode }}" = "headless" ]; then
        rm -f build/qmp-{{ arch }}.sock
        display=(-display none -vnc :0
                 -serial "file:build/serial-{{ arch }}.log"
                 -qmp "unix:build/qmp-{{ arch }}.sock,server,nowait")
    fi

    echo "booting ${disk}  arch={{ arch }}  accel=${accel}  mode={{ mode }}"
    exec "$bin" -accel "$accel" "${common[@]}" "${args[@]}" "${display[@]}"

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

# ADR-002 base-image verification (the [VERIFY] gate on the whole stack).
# Refreshes both the human-readable evidence and the machine-readable decision.
verify-base:
    #!/usr/bin/env bash
    set -euo pipefail
    out="os/scripts/build/verify-base.latest.txt"
    tmp="$(mktemp)"
    trap 'rm -f "$tmp"' EXIT
    {
        echo "# Generated by os/scripts/build/verify-base.sh — ADR-002 evidence."
        echo "# Regenerate with: just verify-base"
        echo "# Run on: $(date -u +%Y-%m-%d) (host: $(uname -s | tr '[:upper:]' '[:lower:]')/$(uname -m))"
        echo
        ./os/scripts/build/verify-base.sh
    } > "$tmp"
    # Only replace the committed evidence once the run actually succeeded.
    # mktemp creates 0600; this file is committed and read by humans.
    mv "$tmp" "$out"
    chmod 644 "$out"
    cat "$out"
    {
        echo "# Generated by 'just verify-base'. Do not edit — it records the ADR-002"
        echo "# decision that os/Containerfile is built against."
        grep -E '^(DECISION|BASE_[A-Z0-9_]+)=' "$out"
    } > "{{ base_env }}"
    echo
    echo "wrote {{ base_env }}:"
    sed 's/^/    /' "{{ base_env }}"
