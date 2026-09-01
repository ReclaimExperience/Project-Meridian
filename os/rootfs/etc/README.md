# `os/rootfs/etc/`

**Owned by WP-07.** Image defaults for `/etc`: xdg config, KIOSK locks, polkit rules.

> **Path note (WP-01).** The PRD's section 6.1 tree shows this directory as
> `os/rootfs/usr/etc/`. That does not build: current `bootc container lint`
> rejects `/usr/etc` in a container image —
> *"this is a bootc implementation detail and not supported to use in containers"* —
> and fails the build. Files placed in `/etc` at build time are turned into the
> default `/etc` (i.e. `/usr/etc`) by `ostree container commit`, so ADR-001's
> actual requirement — configuration baked as image defaults rather than applied
> by post-install scripts — is fully met. Only the source path changes.
>
> Write your image defaults here, not under `rootfs/usr/etc/`.

See `docs/PRD.md` section 8, WP-07, for the deliverables that land here.
