# `tests/stories/`

**Owned by WP-03 (framework); each story is owned by the work package that ships
its flow.** The 22 Zero-Terminal stories from `docs/PRD.md` section 10.1 — the
enforcement checklist for INV-0.

Copy `zt_template.py` to `zt_NN_short_name.py`. The template carries the rules;
read it before writing one.

A story asserts that a **person** can finish a task. If passing it needs a
terminal, a config file, or a command, that is a product bug, not a test
problem — PRD 0.3 says so in as many words: *"If you find yourself writing
documentation that says 'open a terminal', you have found a product bug."*

The harness console is for **observing** the system. Performing the user's step
in a shell and then asserting it worked proves only that the shell works.

## Coverage

`just vm-test stories` runs every `zt_*.py` here and prints how many of the 22
exist. It is expected to be far short of 22 for most of the project; the number
is a progress signal, not a failure, until the M5 gate.
