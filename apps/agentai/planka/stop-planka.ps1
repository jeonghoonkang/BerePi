param(
    [switch] $RemoveVolumes
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$EnvFile = Join-Path $ScriptDir ".env"
$ComposeFile = Join-Path $ScriptDir "docker-compose.yml"

$args = @("compose", "-f", $ComposeFile)
if (Test-Path -LiteralPath $EnvFile) {
    $args += @("--env-file", $EnvFile)
}
$args += "down"
if ($RemoveVolumes) {
    $args += "-v"
}

docker @args
