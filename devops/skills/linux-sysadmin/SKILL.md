---
name: linux-sysadmin
description: This skill should be used when the user asks to "configure cron", "set up systemd service", "create systemd timer", "use .d directories", "set up sudoers", "configure sysctl", "manage system configs", "set up logging with journald", "create drop-in configs", "use systemd overrides", or works with Debian/Ubuntu system administration tasks involving cron.d, systemd units, sudoers.d, apt sources, and other modular configuration directories following modern Linux best practices.
user-invocable: false
allowed-tools: Bash
---

# Linux Sysadmin Best Practices (Debian/Ubuntu)

Follow modern, modular approaches for system configuration. Prioritize portability, maintainability, and easy backup/migration.

## 1. Use .d Directories Instead of Monolithic Configs

**Always prefer drop-in directories** — they are easier to manage, backup, and transfer between servers.

| Instead of editing... | Use directory... |
|----------------------|------------------|
| `crontab -e` | `/etc/cron.d/` |
| `/etc/sudoers` | `/etc/sudoers.d/` |
| `/etc/apt/sources.list` | `/etc/apt/sources.list.d/` |
| `/etc/sysctl.conf` | `/etc/sysctl.d/` |
| `/etc/fstab` (for transient mounts) | `/etc/systemd/system/*.mount` |
| `/etc/modules` | `/etc/modules-load.d/` |
| `/etc/modprobe.conf` | `/etc/modprobe.d/` |
| `/etc/security/limits.conf` | `/etc/security/limits.d/` |
| `/etc/profile` | `/etc/profile.d/` |
| `/etc/environment` | `/etc/environment.d/` |
| `/etc/ssh/sshd_config` | `/etc/ssh/sshd_config.d/` (OpenSSH 8.2+) |
| `/etc/ld.so.conf` | `/etc/ld.so.conf.d/` |
| `/etc/logrotate.conf` | `/etc/logrotate.d/` |
| `/etc/rsyslog.conf` | `/etc/rsyslog.d/` |
| `/etc/nginx/nginx.conf` | `/etc/nginx/conf.d/`, `/etc/nginx/sites-enabled/` |

### How to Check .d Support
Look for `Include` directive in the main config file:
```bash
grep -i include /etc/ssh/sshd_config
# Include /etc/ssh/sshd_config.d/*.conf
```

### File Naming Convention
- Use descriptive names: `10-docker-dns-watchdog` not `myjob`
- Prefix with numbers for ordering: `10-`, `20-`, `50-`, `99-`
- Files are read **alphabetically** — later files override earlier ones
- Lower numbers load first, use `99-` for final overrides
- **No dots** in cron.d filenames (they will be ignored!)
- Use `.conf` extension for most .d directories

### Examples

**Cron job** (`/etc/cron.d/docker-dns-watchdog`):
```
*/5 * * * * root /usr/local/bin/docker-dns-watchdog.sh
```

**Sudoers** (`/etc/sudoers.d/developers`):
```
%developers ALL=(ALL) NOPASSWD: /usr/bin/docker, /usr/bin/systemctl restart myapp
```

**Sysctl** (`/etc/sysctl.d/99-custom.conf`):
```
net.core.somaxconn = 65535
vm.swappiness = 10
```

## 2. Systemd Over Legacy Init

**Prefer systemd** for services and timers:

| Legacy | Modern |
|--------|--------|
| `/etc/init.d/` scripts | `/etc/systemd/system/*.service` |
| `cron` for complex schedules | systemd timers (`.timer` + `.service`) |
| `screen`/`nohup` for daemons | systemd user services |
| `/etc/rc.local` | systemd oneshot service |

### Systemd Timer Example (instead of cron)
For complex scheduling with dependencies, logging, and better control:

`/etc/systemd/system/docker-dns-watchdog.timer`:
```ini
[Unit]
Description=Docker DNS Watchdog Timer

[Timer]
OnBootSec=1min
OnUnitActiveSec=5min

[Install]
WantedBy=timers.target
```

`/etc/systemd/system/docker-dns-watchdog.service`:
```ini
[Unit]
Description=Docker DNS Watchdog

[Service]
Type=oneshot
ExecStart=/usr/local/bin/docker-dns-watchdog.sh
```

Enable: `systemctl enable --now docker-dns-watchdog.timer`

### Systemd Unit Overrides (drop-in)
**Never edit package-provided unit files** — they will be overwritten on upgrade.

Use drop-in overrides instead:
```bash
# Create override directory
sudo systemctl edit docker.service
# Creates: /etc/systemd/system/docker.service.d/override.conf
```

Or manually:
```bash
sudo mkdir -p /etc/systemd/system/docker.service.d/
sudo nano /etc/systemd/system/docker.service.d/10-custom.conf
```

Override file example:
```ini
[Service]
# Empty ExecStart= clears the previous value (required before redefining)
ExecStart=
ExecStart=/usr/bin/dockerd --storage-driver=overlay2
Environment="HTTP_PROXY=http://proxy:8080"
```

**Important**: `After=` only affects ordering, not dependency. Use `Requires=` or `Wants=` for dependencies.

After editing: `systemctl daemon-reload && systemctl restart <unit>`

## 3. File Locations

| Purpose | Location |
|---------|----------|
| Custom scripts | `/usr/local/bin/` |
| Custom libraries | `/usr/local/lib/` |
| Application configs | `/etc/` or `/etc/<appname>/` |
| Variable data | `/var/lib/<appname>/` |
| Logs | `/var/log/<appname>/` or journald |
| Temporary files | `/tmp/` or `mktemp` |
| Runtime files (PID, sockets) | `/run/` |

## 4. Logging

- **Prefer journald** for systemd services — logs are structured and queryable
- Use `logger` command for script logging to syslog
- If file logging needed, use `/var/log/` with logrotate config

```bash
# Log to syslog/journald
logger --tag 'docker-dns-watchdog' "DNS broken, restarting project"

# Query logs
journalctl --unit docker-dns-watchdog --since '1 hour ago'
```

## 5. Permissions & Security

- Scripts in `/usr/local/bin/`: owned by root, mode `0755`
- Configs in `/etc/cron.d/`, `/etc/sudoers.d/`: owned by root, mode `0644` (cron) or `0440` (sudoers)
- Use `visudo -c -f /etc/sudoers.d/myfile` to validate sudoers syntax
- Secrets: use `0600` permissions, consider `/etc/<app>/secrets/` or systemd credentials

## 6. Package Management

- Pin versions for production: `apt-mark hold <package>`
- Custom repos in `/etc/apt/sources.list.d/`
- GPG keys in `/etc/apt/keyrings/` (modern) or `/usr/share/keyrings/`
- Preferences in `/etc/apt/preferences.d/`

## 7. Backup-Friendly Practices

Keep custom configs in predictable locations for easy backup:
```bash
# What to backup for full config recovery:
/etc/cron.d/
/etc/sudoers.d/
/etc/sysctl.d/
/etc/systemd/system/
/etc/apt/sources.list.d/
/usr/local/bin/
/usr/local/lib/
```

Avoid editing package-managed files — they may be overwritten on upgrade.

## References
- [Drop-In (.d) Directories Explained - OSTechNix](https://ostechnix.com/drop-in-d-directories-linux-configuration-explained/)
- [Debian Wiki - systemd](https://wiki.debian.org/systemd)
- [Debian pkg-systemd Packaging](https://wiki.debian.org/Teams/pkg-systemd/Packaging)
