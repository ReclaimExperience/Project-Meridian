#!/usr/bin/env python3
"""User-visible string lint — PRD 4.5 (voice) and INV-0 (zero-terminal).

Extracts strings that a user can actually read, then fails on:

  * jargon from PRD 4.5's forbidden list
  * any phrase that sends the user to a terminal (INV-0)

Seeded at WP-00 so it exists before the first UI string does. Extraction gets
richer as real surfaces land; the forbidden lists come straight from the PRD
and only the owner may shorten them.

Justified exceptions live in tests/lint/strings-allow.txt, one
"<path>::<substring>::<reason>" per line. Every exception is auditable in review.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# PRD 4.5: "Never: mount, partition, repository, flatpak, daemon, prefix, rebase"
JARGON = ["mount", "partition", "repository", "flatpak", "daemon", "prefix", "rebase"]

# INV-0: no user-visible text may route the user to a terminal.
TERMINAL_PHRASES = [
    r"open (?:a|the|your) terminal",
    r"run (?:the|this|these|following) command",
    r"in (?:a|the) terminal",
    r"command[- ]line",
    r"\bsudo\b",
    r"type the following",
]

JARGON_RE = re.compile(r"\b(" + "|".join(JARGON) + r")(?:s|ed|ing)?\b", re.IGNORECASE)
TERMINAL_RE = re.compile("|".join(TERMINAL_PHRASES), re.IGNORECASE)

# Where user-visible strings live, and how to pull them out.
QML_PROPS = (
    "text",
    "title",
    "subtitle",
    "placeholderText",
    "description",
    "toolTip",
    "tooltip",
    "label",
    "header",
    "message",
)
QML_PROP_RE = re.compile(r"\b(?:" + "|".join(QML_PROPS) + r")\s*:\s*[\"'](.+?)[\"']")
I18N_RE = re.compile(r"\bi18n(?:c|p|d)?\s*\(\s*(?:\"[^\"]*\"\s*,\s*)?\"([^\"]+)\"")
TR_RE = re.compile(r"\btr\s*\(\s*\"([^\"]+)\"")
DESKTOP_RE = re.compile(
    r"^(?:Name|GenericName|Comment|Keywords)(?:\[[^\]]+\])?\s*=\s*(.+)$", re.MULTILINE
)
JSON_STR_RE = re.compile(
    r'"(?:name|blurb|note|replaces|description|title|message)"\s*:\s*"([^"]+)"'
)


def tracked_files() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.split("\n")
    return [ROOT / f for f in out if f]


def extract(path: Path) -> list[tuple[int, str]]:
    """Return (line_no, user_visible_string) pairs for one file."""
    rel = path.relative_to(ROOT).as_posix()
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, FileNotFoundError):
        return []

    def with_lines(pattern: re.Pattern) -> list[tuple[int, str]]:
        return [
            (text[: m.start()].count("\n") + 1, m.group(1))
            for m in pattern.finditer(text)
        ]

    if path.suffix == ".qml":
        return with_lines(QML_PROP_RE) + with_lines(I18N_RE)
    if path.suffix in (".cpp", ".cxx", ".h", ".hpp"):
        return with_lines(I18N_RE) + with_lines(TR_RE)
    if path.suffix in (".desktop", ".directory", ".notifyrc"):
        return with_lines(DESKTOP_RE)
    # catalog/*.json is user-visible editorial copy; catalog/schemas/*.json is
    # developer-facing metadata and must not be linted as UI text.
    if (
        rel.startswith("catalog/")
        and not rel.startswith("catalog/schemas/")
        and path.suffix == ".json"
    ):
        return with_lines(JSON_STR_RE)
    # Help articles are user-visible prose in full (INV-0 applies to docs too).
    if rel.startswith("docs/help/") and path.suffix == ".md":
        return [(i, ln) for i, ln in enumerate(text.split("\n"), 1) if ln.strip()]
    return []


def load_allowlist() -> list[tuple[str, str, str]]:
    f = ROOT / "tests/lint/strings-allow.txt"
    if not f.exists():
        return []
    entries = []
    for raw in f.read_text().split("\n"):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("::", 2)
        if len(parts) != 3:
            print(f"strings-lint: malformed allowlist line: {raw}", file=sys.stderr)
            sys.exit(2)
        entries.append((parts[0].strip(), parts[1].strip(), parts[2].strip()))
    return entries


def main() -> int:
    allow = load_allowlist()
    failures: list[str] = []
    checked = 0

    for path in tracked_files():
        rel = path.relative_to(ROOT).as_posix()
        for lineno, s in extract(path):
            checked += 1
            if any(a_path == rel and a_sub in s for a_path, a_sub, _ in allow):
                continue
            if m := TERMINAL_RE.search(s):
                failures.append(
                    f"{rel}:{lineno}: INV-0 violation — sends the user to a terminal\n"
                    f"    {s.strip()!r}\n"
                    f"    matched: {m.group(0)!r}\n"
                    f"    -> This is a product bug. Fix the product, not the wording (PRD 0.3)."
                )
            if m := JARGON_RE.search(s):
                failures.append(
                    f"{rel}:{lineno}: jargon '{m.group(0)}' in a user-visible string (PRD 4.5)\n"
                    f"    {s.strip()!r}\n"
                    f"    -> Say it the way Pat would: 'disk' not 'partition', "
                    f"'app' not 'flatpak', 'connect' not 'mount'."
                )

    if failures:
        print(
            f"strings-lint: {len(failures)} problem(s) in {checked} user-visible string(s)\n"
        )
        for f in failures:
            print(f + "\n")
        return 1

    print(
        f"strings-lint: clean ({checked} user-visible string(s) checked, "
        f"{len(allow)} allowlisted)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
