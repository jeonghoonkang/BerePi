# PLANKA Runner

This folder runs PLANKA with Docker Compose.

Source project:

- https://github.com/plankanban/planka

## Start

```powershell
cd E:\devel\BerePi\apps\agentai\planka
.\start-planka.ps1 -Pull
```

Open:

```text
http://localhost:3000
```

Default admin account from `.env`:

```text
username: admin
email: admin@example.local
password: admin1234
```

Edit `.env` before first startup if you want another account, port, or base URL.

## Commands

```powershell
.\start-planka.ps1
.\status-planka.ps1
.\logs-planka.ps1
.\stop-planka.ps1
```

Ubuntu:

```bash
cd /path/to/BerePi/apps/agentai/planka
chmod +x *.sh
./start-planka.sh --pull
./status-planka.sh
./logs-planka.sh
./stop-planka.sh
```

The scripts prefer `docker compose`, then legacy `docker-compose`, and only
then try sudo variants. Check Compose first:

```bash
sudo docker compose version || docker-compose version
```

The included `docker-compose.yml` uses Compose file version `2.3` on purpose,
so old Ubuntu 18.04 environments such as `docker-compose version 1.17.1` can
parse it.

If you see `Couldn't connect to Docker daemon`, Docker is either not running or
your current user cannot access `/var/run/docker.sock`. The scripts now test
daemon access and will use `sudo docker-compose` automatically when sudo can
reach Docker.

If PLANKA logs show `ECONNREFUSED ...:5432`, PostgreSQL was not ready when
PLANKA tried to connect. `start-planka.sh` starts PostgreSQL first and waits
for its healthcheck before starting PLANKA. Check database logs with:

```bash
sudo docker logs planka_postgres_1
```

On Ubuntu 18.04, install Compose if the command is missing:

```bash
sudo apt update
sudo apt install docker-compose-plugin
```

If the plugin package is unavailable on that machine:

```bash
sudo apt install docker-compose
```

Remove database and uploaded data:

```powershell
.\stop-planka.ps1 -RemoveVolumes
```

Ubuntu:

```bash
./stop-planka.sh --remove-volumes
```

## Backup

Backup scripts are in `backup_proc/`:

```bash
cd backup_proc
./backup-planka.sh
```

By default, the backup is also copied to:

```text
user@10.0.0.53:backup/planka/<local-machine-name>/
```

Use `--skip-remote-copy` when you only want the local backup. Use
`--remote-root USER@HOST:PATH` to override the remote root path.

Each backup directory includes the PostgreSQL dump, PLANKA data archive,
compose/env files, `manifest.sha256`, and `stack-info.txt`. The stack info file
records the PostgreSQL server version, pg_dump/pg_restore versions, Docker and
Compose versions, and the running PLANKA/PostgreSQL container image details and
labels.

## Files

- `docker-compose.yml`: PLANKA and PostgreSQL services
- `.env.sample`: environment template
- `.env`: generated on first start, not committed by default
- `start-planka.ps1`: create `.env`, pull optionally, and start
- `stop-planka.ps1`: stop containers
- `status-planka.ps1`: show containers
- `logs-planka.ps1`: follow logs
- `start-planka.sh`: Ubuntu/Linux start script
- `stop-planka.sh`: Ubuntu/Linux stop script
- `status-planka.sh`: Ubuntu/Linux status script
- `logs-planka.sh`: Ubuntu/Linux log script
- `backup_proc/backup-planka.sh`: Linux backup script
- `backup_proc/backup-planka.ps1`: Windows backup script
- `backup_proc/restore-planka.sh`: Linux restore script
- /var/lib/docker/volumes/planka_planka-data/_data/private/attachments/1796848490710565956
