$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

if (-not $env:PROJECT_AGENT_PORT) {
    $env:PROJECT_AGENT_PORT = "18765"
}

py -3 app.py
