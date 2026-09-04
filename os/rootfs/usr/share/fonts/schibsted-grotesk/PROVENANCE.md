# Schibsted Grotesk — bundled font provenance

PRD §4.1 names Schibsted Grotesk as the UI family and says "OFL; bundle in
image". It is not packaged in Fedora, so the files here are vendored.

| | |
|---|---|
| Source | `https://github.com/schibsted/schibsted-grotesk` |
| Version | **1.100** (GitHub release, published 2023-03-08) |
| Commit | `d485f61f105e1b3935f4d21dfb4d371359798603` |
| Fetched | 2026-09-04 |
| Licence | SIL Open Font License 1.1 — `OFL.txt`, committed alongside |

## Files

| File | SHA-256 |
|---|---|
| `SchibstedGrotesk[wght].ttf` | `6ceeadf6be8e1fd7687011c7fa38ed0edd1abe967a0b73d97caec183552e823d` |
| `OFL.txt` | `3b4f3063b6ac7c1e403e2c4a5e8ef3a58190ff83ed7b15af66511858699139ce` |

`tests/lint/font_provenance.py` asserts these checksums on every run. A silent
font swap is then caught the same way `theme_generated.py` catches colour drift —
by comparing against a recorded value rather than trusting that the file in the
tree is the file someone reviewed.

## Why this cut, and why unmodified

The mockup's own `<head>` loads `Schibsted+Grotesk:wght@400;500;600;700` from
Google Fonts, and upstream's 1.100 notes describe it as adapted to Google Fonts
specifications. So the public OFL release **is** the cut the design was authored
against — bundling it matches the brand face exactly rather than approximating it.

**Variable, roman only.** One file carries the wght axis across 400–700, which is
every weight `tokens.font.weight` uses. The family also ships italics; the chrome
does not need them, and shipping faces nothing renders is the kind of weight
pillar 4 exists to refuse. Add italics when a surface actually calls for one.

**Unmodified.** OFL's Reserved Font Name clause restricts *modified* fonts from
reusing the name; we ship the upstream binary byte-for-byte, so the RFN is not
engaged. If anyone ever subsets or patches these files, the name must change and
this note stops being true.
