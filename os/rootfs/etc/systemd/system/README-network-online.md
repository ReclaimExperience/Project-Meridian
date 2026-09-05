# Why `NetworkManager-wait-online.service` is masked

It sits in the boot critical path and holds `graphical.target` nominally
inactive for up to its 90-second timeout while the greeter is already up and
serving. That produced two separate defects:

1. **A machine that bricked itself.** The greenboot check polled
   `graphical.target` on a 90-second deadline; the target cleared at ~80s. Every
   lost coin-toss rebooted the machine and decremented `boot_counter` until no
   bootable deployment remained. One was found in that state.
2. **Offline laptops rolled back.** greenboot's stock
   `01_repository_dns_check.sh` fails without a network.

Both are the same defect wearing different clothes: **something
network-dependent in the boot or boot-health path**. A desktop for a switcher
has to reach a usable state fast with no network at all — the laptop on a train
is a correctly working machine, and neither the boot nor the health check may
punish it.

**Side effect, stated:** with this masked, `network-online.target` is reached
without waiting for a connection. Units that order themselves `After=` it start
sooner; any unit that genuinely needs connectivity must wait for it itself,
which is the correct design for a desktop and the wrong one only for a server.
