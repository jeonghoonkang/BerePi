param(
    [string]$BackupRoot = "",
    [int]$KeepLast = 10,
    [switch]$SkipData
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PlankaDir = Split-Path -Parent $ScriptDir

if ([string]::IsNullOrWhiteSpace($BackupRoot)) {
    $BackupRoot = Join-Path $ScriptDir "backups"
}

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

Write-Host "Backup complete: $BackupDir"

