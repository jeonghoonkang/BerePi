param(
    [switch] $Pull,
    [switch] $Foreground
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$EnvFile = Join-Path $ScriptDir ".env"
$SampleFile = Join-Path $ScriptDir ".env.sample"
$ComposeFile = Join-Path $ScriptDir "docker-compose.yml"

function New-SecretKey {
    $bytes = New-Object byte[] 64
    [System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
    return ($bytes | ForEach-Object { $_.ToString("x2") }) -join ""
}

if (-not (Test-Path -LiteralPath $EnvFile)) {
    Copy-Item -LiteralPath $SampleFile -Destination $EnvFile
    $secret = New-SecretKey
    $content = Get-Content -LiteralPath $EnvFile -Raw
    $content = $content -replace "SECRET_KEY=replace_with_64_byte_hex_secret", "SECRET_KEY=$secret"
    Set-Content -LiteralPath $EnvFile -Value $content -Encoding UTF8
    Write-Host "Created .env with a generated SECRET_KEY."
    Write-Host "Edit .env if you want a different port, base URL, or admin account."
}

if ($Pull) {
    docker compose -f $ComposeFile --env-file $EnvFile pull
}

$args = @("compose", "-f", $ComposeFile, "--env-file", $EnvFile, "up")
if (-not $Foreground) {
    $args += "-d"
}

Write-Host "Starting PLANKA..."
docker @args

Write-Host ""
Write-Host "PLANKA URL:"
$envMap = @{}
Get-Content -LiteralPath $EnvFile | ForEach-Object {
    if ($_ -match "^\s*([^#=]+)=(.*)$") {
        $envMap[$matches[1].Trim()] = $matches[2].Trim()
    }
}
$baseUrl = $envMap["BASE_URL"]
if (-not $baseUrl) {
    $baseUrl = "http://localhost:3000"
}
Write-Host $baseUrl
Write-Host ""
docker compose -f $ComposeFile --env-file $EnvFile ps
