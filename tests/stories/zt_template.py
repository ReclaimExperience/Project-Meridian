"""ZT-NN — <the user outcome, in the words of PRD 10.1>.

COPY THIS FILE to `tests/stories/zt_NN_short_name.py` when your work package
ships a user-visible flow. PRD 0.3 makes the 22 Zero-Terminal stories the
enforcement checklist for INV-0, and every release gate runs them.

A story is not a unit test. It asserts that a PERSON can complete a task, so it
should read like the thing Pat was trying to do:

    fails well:  "the Start menu never opened after pressing Meta"
    fails badly: "assert plasmashell_dbus_call_3 == 0"

Three rules, all from the PRD:

  * **INV-0 above all.** If passing this story requires a terminal, a config
    file, or a command, the product is wrong — not the story. File the product
    bug (PRD 0.3). The harness console exists to OBSERVE the system, never to
    perform the user's task on their behalf: doing the step in a shell and then
    asserting it worked proves the shell works.
  * **Wait for conditions, not clocks** (WP-03 Forbidden). Use
    `console.wait_until(...)` or `console.wait_for(...)`. A `sleep` that passes
    on this machine is a flake on a slower one, and R-A treats flaky as broken.
  * **No network assertions in smoke-adjacent paths.** A registry hiccup must
    never read as a broken product.

Run them all:       just vm-test stories
Debug a run:        python3 tests/harness/run.py stories --keep  (leaves the VM up)
"""

from __future__ import annotations

from harness.vm import VM

# One line, quoted from PRD 10.1. Printed in the run output and in failures, so
# a red CI job names the user outcome that broke rather than a file name.
STORY = "ZT-NN — <outcome from PRD 10.1>"

# The work package that owns this story, from the "WP" column of PRD 10.1.
OWNER_WP = "WP-NN"


def run(vm: VM, credentials: dict) -> None:
    console = vm.console
    user, password = credentials["user"], credentials["password"]

    # Reach the state the user starts from. Most stories begin at a logged-in
    # desktop; get there the way a person does, through the greeter.
    console.login(user, password, timeout=600)
    console.wait_until(
        "systemctl is-active display-manager",
        # Any line, not the last: a kernel printk can land after the output
        # on this console. Not endswith: "inactive" ends with "active".
        # Empty output must not raise IndexError.
        lambda out: any(ln.strip() == "active" for ln in out.splitlines()),
        timeout=300,
        description="display-manager to be active",
    )
    vm.qmp.wake_display()
    vm.qmp.type_text(password)
    vm.qmp.key("ret")
    console.wait_until(
        "pgrep -a plasmashell || true",
        lambda out: "plasmashell" in out,
        timeout=420,
        description="the desktop to be ready",
    )

    # --- the user's actions --------------------------------------------------
    #
    # Drive the UI the way a person would: keys and pointer via vm.qmp, never a
    # shell command that performs the task itself.
    #
    #     vm.qmp.key("meta")                  # press the Windows key
    #     vm.qmp.type_text("fire")            # type into whatever has focus
    #     vm.qmp.key("ret")
    #
    # Capture a screenshot at each step a human would recognise. On failure
    # these are the artifacts someone reads first.
    #
    #     vm.screenshot("zt_NN-start-menu-open")

    # --- what must be true afterwards ----------------------------------------
    #
    # Observe with the console; do not act with it.
    #
    #     console.wait_until(
    #         "pgrep -a firefox || true",
    #         lambda out: "firefox" in out,
    #         timeout=120,
    #         description="Firefox to open after choosing it in Start",
    #     )
    #
    # Write the assertion message for whoever sees it fail at 2am:
    #
    #     assert found, (
    #         "Typing 'fire' in Start and pressing Enter did not open the web "
    #         "browser. This is ZT-01; a switcher who cannot launch an app by "
    #         "typing its name has no way in."
    #     )

    raise NotImplementedError(
        "zt_template is a template, not a story. Copy it to "
        "tests/stories/zt_NN_short_name.py and implement the flow."
    )
