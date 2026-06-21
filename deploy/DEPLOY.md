# Deploying the Component Tracker to Proxmox

This guide stands the app up in a fresh, unprivileged **LXC container** on your
Proxmox server and exposes it privately over **Tailscale**. Nothing is published
to the public internet. You already run nightly Proxmox backups, so the only
extra piece here is a consistent SQLite snapshot taken just before that window.

Two machines are involved:

- **Proxmox host** — the physical server. You run `pct` / edit container config here.
- **The container** — the small Linux box the app runs inside. You `git`, `pip`,
  and `systemctl` here.

Throughout, the container ID is **`110`** — change it to a free ID on your node.

---

## 1. Create the LXC container (on the Proxmox host)

From the host shell (or the web UI — these are the equivalent CLI steps):

```bash
# Pick the latest Debian template (download it if you don't have it yet)
pveam update
pveam available | grep debian-12
pveam download local debian-12-standard_12.7-1_amd64.tar.zst

# Create an unprivileged container: 1 vCPU, 1 GB RAM, 6 GB disk.
pct create 110 local:vztmpl/debian-12-standard_12.7-1_amd64.tar.zst \
  --hostname component-tracker \
  --cores 1 --memory 1024 --swap 512 \
  --rootfs local-lvm:6 \
  --net0 name=eth0,bridge=vmbr0,ip=dhcp \
  --unprivileged 1 \
  --features nesting=1 \
  --onboot 1
```

`nesting=1` lets Tailscale's userspace bits run cleanly inside an unprivileged
container. Adjust `--rootfs` storage (`local-lvm`) and `--net0` bridge
(`vmbr0`) to match your node.

## 2. Allow Tailscale's TUN device (on the Proxmox host)

An unprivileged container can't open `/dev/net/tun` unless you grant it. Edit the
container config on the host:

```bash
nano /etc/pve/lxc/110.conf
```

Add these two lines:

```
lxc.cgroup2.devices.allow: c 10:200 rwm
lxc.mount.entry: /dev/net/tun dev/net/tun none bind,create=file
```

Then start it:

```bash
pct start 110
pct enter 110      # drops you into a root shell inside the container
```

Everything from here on runs **inside the container**.

## 3. Install base packages (inside the container)

```bash
apt update && apt upgrade -y
apt install -y python3 python3-venv python3-pip git sqlite3 curl
```

`sqlite3` is needed by the backup script; `curl` by the Tailscale installer.

## 4. Get the code and run the installer (inside the container)

Clone your repository into `/opt/component-tracker`:

```bash
git clone <YOUR_REPO_URL> /opt/component-tracker
cd /opt/component-tracker
./deploy/install.sh
```

`install.sh` creates a dedicated `tracker` user, builds the virtualenv, installs
dependencies, initialises the database, and installs + starts two systemd units:
the app and the nightly backup timer. It's safe to re-run after any `git pull`.

## 5. Set a real secret key (inside the container)

The session secret ships as a placeholder. Generate a real one and drop it in:

```bash
openssl rand -hex 32          # copy the output
nano /etc/systemd/system/component-tracker.service
#   -> replace the TRACKER_SECRET=... line with your value
systemctl daemon-reload
systemctl restart component-tracker
```

## 6. Confirm it's running (inside the container)

```bash
systemctl status component-tracker --no-pager
curl -s localhost:8000 | head -n 5      # should print HTML
```

If the app misbehaves, `journalctl -u component-tracker -f` shows live logs.

## 7. Join your tailnet (inside the container)

```bash
curl -fsSL https://tailscale.com/install.sh | sh
tailscale up
```

Follow the printed link to authorise the node in your Tailscale admin. Once it's
up:

```bash
tailscale ip -4        # the container's tailnet IP, e.g. 100.x.y.z
```

Now reach the tracker from any device on your tailnet at:

```
http://<tailscale-ip>:8000
```

or, with MagicDNS enabled, `http://component-tracker:8000`. Because it's bound to
the tailnet only, nothing outside your private network can see it.

---

## Updating the app later

```bash
cd /opt/component-tracker
git pull
./deploy/install.sh          # re-installs deps, runs migrations, restarts service
```

The database lives in `data/components.db` (gitignored), so `git pull` never
touches your inventory. `init-db` only adds missing tables/columns — it never
drops data.

## Backups and restore

The nightly timer writes a consistent, gzipped snapshot to
`data/backups/components-YYYYMMDD-HHMMSS.db.gz` and keeps the latest 14. Check it:

```bash
systemctl list-timers component-tracker-backup --no-pager
systemctl start component-tracker-backup        # run one now to test
ls -lh /opt/component-tracker/data/backups
```

To **restore** a snapshot:

```bash
systemctl stop component-tracker
gunzip -c data/backups/components-20260620-023000.db.gz > data/components.db
chown tracker:tracker data/components.db
systemctl start component-tracker
```

Set the timer a few minutes before your Proxmox vzdump window so each container
backup also captures the fresh snapshot. (If your vzdump uses snapshot mode on
ZFS/LVM-thin, the live `.db` is already captured atomically — this snapshot just
adds a clean, per-file copy you can restore without unpacking the whole CT.)

## Troubleshooting

- **Service won't start** — `journalctl -u component-tracker -e`. Usually a bad
  `TRACKER_SECRET` line or a venv that didn't build (re-run `install.sh`).
- **`tailscale up` fails with a TUN error** — the two lines in step 2 are missing
  or the container wasn't restarted after adding them.
- **Port 8000 in use** — change `bind` in `deploy/gunicorn.conf.py`, then
  `systemctl restart component-tracker`.
- **"database is locked"** — rare; the app already waits up to 5s on a lock. If
  it persists you have a stuck process: `systemctl restart component-tracker`.
