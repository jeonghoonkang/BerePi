# PLANKA Backup

This folder contains backup scripts for the PLANKA Docker Compose app in the
parent directory.

Each backup creates:

- `postgres.dump`: PostgreSQL custom-format dump from the `postgres` service
- `planka-data.tar.gz`: uploaded files and PLANKA data from `/app/data`
- `docker-compose.yml`, `.env`, `.env.sample`: restore metadata
- `manifest.sha256`: checksums for the backup files

## Windows

```powershell
cd E:\devel\BerePi\apps\agentai\planka\backup_proc
.\backup-planka.ps1
```

Optional:

```powershell
.\backup-planka.ps1 -BackupRoot D:\backups\planka -KeepLast 14
.\backup-planka.ps1 -SkipData
```

## Ubuntu/Linux

```bash
cd /path/to/BerePi/apps/agentai/planka/backup_proc
chmod +x backup-planka.sh restore-planka.sh
./backup-planka.sh
```

Optional:

```bash
./backup-planka.sh --backup-root /mnt/backups/planka --keep-last 14
./backup-planka.sh --skip-data
```

The scripts expect the PLANKA stack to be running because they call
`docker compose exec` to create a PostgreSQL dump.

## Ubuntu/Linux Restore

Restore from a backup directory:

```bash
cd /path/to/BerePi/apps/agentai/planka/backup_proc
./restore-planka.sh ./backups/planka-20260616-120000
```

Automated restore without confirmation:

```bash
./restore-planka.sh /mnt/backups/planka/planka-20260616-120000 --yes
```

Optional:

```bash
./restore-planka.sh ./backups/planka-20260616-120000 --skip-data
./restore-planka.sh ./backups/planka-20260616-120000 --skip-db
./restore-planka.sh ./backups/planka-20260616-120000 --restore-env
```

Restore stops the `planka` container, replaces the selected PostgreSQL database
and/or `/app/data` volume contents, then starts the stack again. Use
`--restore-env` only when you also want to replace the current `.env` with the
backup copy.
