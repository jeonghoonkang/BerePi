param(
    [string]$BackupRoot = "",
    [int]$KeepLast = 10,
    [switch]$SkipData,
    [string]$RemoteRoot = "user@10.0.0.53:backup/planka",
    [switch]$SkipRemoteCopy
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PlankaDir = Split-Path -Parent $ScriptDir

if ([string]::IsNullOrWhiteSpace($BackupRoot)) {
    $BackupRoot = Join-Path $ScriptDir "backups"
}

$LocalMachineName = [System.Net.Dns]::GetHostName()
if ([string]::IsNullOrWhiteSpace($LocalMachineName)) {
    $LocalMachineName = $env:COMPUTERNAME
}
if ([string]::IsNullOrWhiteSpace($LocalMachineName)) {
    $LocalMachineName = "unknown"
}
$LocalMachineName = [regex]::Replace($LocalMachineName, "[^A-Za-z0-9._-]", "_")

function Test-Command {
    param([string]$Name)
    $null -ne (Get-Command $Name -ErrorAction SilentlyContinue)
}

if (-not (Test-Command "docker")) {
    throw "Docker was not found in PATH."
}

$script:ComposeMode = $null
& docker compose version *> $null
if ($LASTEXITCODE -eq 0) {
    $script:ComposeMode = "plugin"
}
elseif (Test-Command "docker-compose") {
    & docker-compose version *> $null
    if ($LASTEXITCODE -eq 0) {
        $script:ComposeMode = "legacy"
    }
}

if ($null -eq $script:ComposeMode) {
    throw "Neither 'docker compose' nor 'docker-compose' is available."
}

function Invoke-PlankaCompose {
    param([string[]]$ComposeArgs)

    if ($script:ComposeMode -eq "plugin") {
        & docker compose --project-directory $PlankaDir @ComposeArgs
    }
    else {
        & docker-compose --project-directory $PlankaDir @ComposeArgs
    }

    if ($LASTEXITCODE -ne 0) {
        throw "Compose command failed: $($ComposeArgs -join ' ')"
    }
}

function Get-ComposeValue {
    param([string[]]$ComposeArgs)

    if ($script:ComposeMode -eq "plugin") {
        $value = & docker compose --project-directory $PlankaDir @ComposeArgs
    }
    else {
        $value = & docker-compose --project-directory $PlankaDir @ComposeArgs
    }

    if ($LASTEXITCODE -ne 0) {
        throw "Compose command failed: $($ComposeArgs -join ' ')"
    }

    return ($value | Select-Object -First 1).Trim()
}

function Copy-BackupToRemote {
    param(
        [string]$SourceBackupDir,
        [string]$DestinationRoot,
        [string]$MachineName
    )

    $separatorIndex = $DestinationRoot.IndexOf(":")
    if ($separatorIndex -lt 1) {
        throw "Remote root must use USER@HOST:PATH format: $DestinationRoot"
    }

    $RemoteHost = $DestinationRoot.Substring(0, $separatorIndex)
    $RemotePath = $DestinationRoot.Substring($separatorIndex + 1)
    $RemoteMachinePath = "$RemotePath/$MachineName"

    if (-not (Test-Command "ssh")) {
        throw "ssh was not found in PATH. Install OpenSSH or run with -SkipRemoteCopy."
    }
    if (-not (Test-Command "scp")) {
        throw "scp was not found in PATH. Install OpenSSH or run with -SkipRemoteCopy."
    }

    Write-Host "Copying backup to ${RemoteHost}:${RemoteMachinePath}/"
    & ssh $RemoteHost "mkdir -p '$RemoteMachinePath'"
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create remote backup directory: ${RemoteHost}:${RemoteMachinePath}"
    }

    & scp -r $SourceBackupDir "${RemoteHost}:${RemoteMachinePath}/"
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to copy backup to remote host: ${RemoteHost}:${RemoteMachinePath}/"
    }
}

New-Item -ItemType Directory -Force -Path $BackupRoot | Out-Null

$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$BackupDir = Join-Path $BackupRoot "planka-$Timestamp"
New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null

Write-Host "Creating PLANKA backup: $BackupDir"

$PostgresContainer = Get-ComposeValue @("ps", "-q", "postgres")
if ([string]::IsNullOrWhiteSpace($PostgresContainer)) {
    throw "PostgreSQL container was not found. Start PLANKA before running backup."
}

$PlankaContainer = Get-ComposeValue @("ps", "-q", "planka")
if ([string]::IsNullOrWhiteSpace($PlankaContainer) -and -not $SkipData) {
    throw "PLANKA container was not found. Start PLANKA or use -SkipData."
}

function Get-DockerValue {
    param([string[]]$DockerArgs)

    $value = & docker @DockerArgs 2>$null
    if ($LASTEXITCODE -ne 0) {
        return "unavailable"
    }

    $first = ($value | Select-Object -First 1) -as [string]
    if ([string]::IsNullOrWhiteSpace($first)) {
        return "unavailable"
    }

    return $first.Trim()
}

function Get-ComposeOptionalValue {
    param([string[]]$ComposeArgs)

    if ($script:ComposeMode -eq "plugin") {
        $value = & docker compose --project-directory $PlankaDir @ComposeArgs 2>$null
    }
    else {
        $value = & docker-compose --project-directory $PlankaDir @ComposeArgs 2>$null
    }

    if ($LASTEXITCODE -ne 0) {
        return "unavailable"
    }

    $first = ($value | Select-Object -First 1) -as [string]
    if ([string]::IsNullOrWhiteSpace($first)) {
        return "unavailable"
    }

    return $first.Trim()
}

function Add-ContainerStackInfo {
    param(
        [System.Collections.Generic.List[string]]$Lines,
        [string]$ServiceName,
        [string]$ContainerId
    )

    $Lines.Add("## $ServiceName")
    if ([string]::IsNullOrWhiteSpace($ContainerId)) {
        $Lines.Add("container: not running")
        $Lines.Add("")
        return
    }

    $Lines.Add("container_id: $(Get-DockerValue @('inspect', '--format', '{{.Id}}', $ContainerId))")
    $Lines.Add("configured_image: $(Get-DockerValue @('inspect', '--format', '{{.Config.Image}}', $ContainerId))")
    $Lines.Add("image_id: $(Get-DockerValue @('inspect', '--format', '{{.Image}}', $ContainerId))")
    $Lines.Add("image_labels: $(Get-DockerValue @('inspect', '--format', '{{json .Config.Labels}}', $ContainerId))")
    $Lines.Add("created: $(Get-DockerValue @('inspect', '--format', '{{.Created}}', $ContainerId))")
    $Lines.Add("")
}

Write-Host "Writing stack version info..."
$StackInfo = [System.Collections.Generic.List[string]]::new()
$StackInfo.Add("# PLANKA stack info")
$StackInfo.Add("backup_timestamp: $Timestamp")
$StackInfo.Add("backup_host: $LocalMachineName")
$StackInfo.Add("planka_dir: $PlankaDir")
$StackInfo.Add("")
$StackInfo.Add("## Docker")
$StackInfo.Add("docker_client: $(Get-DockerValue @('version', '--format', '{{.Client.Version}}'))")
$StackInfo.Add("docker_server: $(Get-DockerValue @('version', '--format', '{{.Server.Version}}'))")
$StackInfo.Add("compose: $(Get-ComposeOptionalValue @('version'))")
$StackInfo.Add("")
$StackInfo.Add("## PostgreSQL database")
$StackInfo.Add("server_version: $(Get-ComposeOptionalValue @('exec', '-T', 'postgres', 'psql', '-U', 'postgres', '-d', 'postgres', '-Atc', 'SHOW server_version;'))")
$StackInfo.Add("server_version_num: $(Get-ComposeOptionalValue @('exec', '-T', 'postgres', 'psql', '-U', 'postgres', '-d', 'postgres', '-Atc', 'SHOW server_version_num;'))")
$StackInfo.Add("pg_dump: $(Get-ComposeOptionalValue @('exec', '-T', 'postgres', 'pg_dump', '--version'))")
$StackInfo.Add("pg_restore: $(Get-ComposeOptionalValue @('exec', '-T', 'postgres', 'pg_restore', '--version'))")
$StackInfo.Add("")
Add-ContainerStackInfo -Lines $StackInfo -ServiceName "planka container" -ContainerId $PlankaContainer
Add-ContainerStackInfo -Lines $StackInfo -ServiceName "postgres container" -ContainerId $PostgresContainer
$StackInfo | Set-Content -LiteralPath (Join-Path $BackupDir "stack-info.txt") -Encoding ascii

Copy-Item -LiteralPath (Join-Path $PlankaDir "docker-compose.yml") -Destination $BackupDir -Force
Copy-Item -LiteralPath (Join-Path $PlankaDir ".env.sample") -Destination $BackupDir -Force
if (Test-Path -LiteralPath (Join-Path $PlankaDir ".env")) {
    Copy-Item -LiteralPath (Join-Path $PlankaDir ".env") -Destination $BackupDir -Force
}

$DumpName = "planka-$Timestamp.dump"
$DumpInContainer = "/tmp/$DumpName"
$DumpOut = Join-Path $BackupDir "postgres.dump"

Write-Host "Dumping PostgreSQL database..."
Invoke-PlankaCompose @("exec", "-T", "postgres", "pg_dump", "-U", "postgres", "-d", "planka", "-Fc", "-f", $DumpInContainer)
& docker cp "${PostgresContainer}:${DumpInContainer}" $DumpOut
if ($LASTEXITCODE -ne 0) {
    throw "Failed to copy database dump from container."
}
Invoke-PlankaCompose @("exec", "-T", "postgres", "rm", "-f", $DumpInContainer)

if (-not $SkipData) {
    Write-Host "Archiving PLANKA data volume..."
    $Inspect = (& docker inspect $PlankaContainer | ConvertFrom-Json)
    $DataMount = $Inspect[0].Mounts | Where-Object { $_.Destination -eq "/app/data" } | Select-Object -First 1
    if ($null -eq $DataMount -or [string]::IsNullOrWhiteSpace($DataMount.Name)) {
        throw "Could not find the Docker volume mounted at /app/data."
    }

    $VolumeMountArg = "$($DataMount.Name):/data:ro"
    $BackupMountArg = "$($BackupDir):/backup"
    & docker run --rm -v $VolumeMountArg -v $BackupMountArg alpine:3.20 sh -c "cd /data && tar -czf /backup/planka-data.tar.gz ."
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to archive PLANKA data volume."
    }
}

Write-Host "Writing checksum manifest..."
$ManifestPath = Join-Path $BackupDir "manifest.sha256"
Get-ChildItem -LiteralPath $BackupDir -File |
    Where-Object { $_.Name -ne "manifest.sha256" } |
    Sort-Object Name |
    ForEach-Object {
        $Hash = Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName
        "$($Hash.Hash.ToLowerInvariant())  $($_.Name)"
    } | Set-Content -LiteralPath $ManifestPath -Encoding ascii

if ($KeepLast -gt 0) {
    Get-ChildItem -LiteralPath $BackupRoot -Directory -Filter "planka-*" |
        Sort-Object Name -Descending |
        Select-Object -Skip $KeepLast |
        Remove-Item -Recurse -Force
}

if (-not $SkipRemoteCopy) {
    Copy-BackupToRemote -SourceBackupDir $BackupDir -DestinationRoot $RemoteRoot -MachineName $LocalMachineName
}

Write-Host "Backup complete: $BackupDir"
