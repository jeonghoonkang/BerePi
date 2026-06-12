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

If Docker only works with `sudo`, the scripts will automatically try
`sudo docker compose`. Check Compose first:

```bash
sudo docker compose version || docker-compose version
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
