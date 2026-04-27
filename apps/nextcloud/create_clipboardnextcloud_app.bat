@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
for %%I in ("%SCRIPT_DIR%\..\..") do set "REPO_ROOT=%%~fI"
set "TARGET_SCRIPT=%SCRIPT_DIR%\clipboardnextcloud.py"
set "DEFAULT_VENV_PYTHON=C:\Users\tinyos\devel_opment\venv\Scripts\python.exe"
set "PYTHON_BIN=%PYTHON_BIN%"
set "OUTPUT_PATH="

if not defined PYTHON_BIN (
  if exist "%DEFAULT_VENV_PYTHON%" (
    set "PYTHON_BIN=%DEFAULT_VENV_PYTHON%"
  ) else (
    set "PYTHON_BIN=python"
  )
)

:parse_args
if "%~1"=="" goto args_done
if /I "%~1"=="--python" (
  if "%~2"=="" goto usage_error
  set "PYTHON_BIN=%~2"
  shift
  shift
  goto parse_args
)
if /I "%~1"=="-h" goto show_usage
if /I "%~1"=="--help" goto show_usage
if defined OUTPUT_PATH goto usage_error
set "OUTPUT_PATH=%~1"
shift
goto parse_args

:args_done
if not defined OUTPUT_PATH set "OUTPUT_PATH=%SCRIPT_DIR%\ClipboardNextcloud"
if not exist "%OUTPUT_PATH%" mkdir "%OUTPUT_PATH%"
if errorlevel 1 (
  echo Failed to create output directory: %OUTPUT_PATH%
  exit /b 1
)

call :to_ps_literal "%PYTHON_BIN%" PYTHON_PS
call :to_ps_literal "%TARGET_SCRIPT%" TARGET_PS
call :to_ps_literal "%OUTPUT_PATH%" OUTPUT_PS
set "PS1_PATH=%OUTPUT_PATH%\ClipboardNextcloud.ps1"
set "LAUNCHER_BAT=%OUTPUT_PATH%\ClipboardNextcloud.bat"
set "SHORTCUT_PATH=%OUTPUT_PATH%\ClipboardNextcloud.lnk"

call :write_ps1
if errorlevel 1 exit /b 1

call :write_launcher_bat
if errorlevel 1 exit /b 1

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$shell = New-Object -ComObject WScript.Shell; " ^
  "$shortcut = $shell.CreateShortcut('%SHORTCUT_PATH%'); " ^
  "$shortcut.TargetPath = '%LAUNCHER_BAT%'; " ^
  "$shortcut.WorkingDirectory = '%OUTPUT_PATH%'; " ^
  "$shortcut.Description = 'Launch ClipboardNextcloud'; " ^
  "$shortcut.Save()" >nul 2>&1
if errorlevel 1 (
  echo Warning: Windows shortcut creation failed, launcher files were still generated.
)

echo Created Windows launcher directory: %OUTPUT_PATH%
echo Run this file on Windows: %LAUNCHER_BAT%
if exist "%SHORTCUT_PATH%" echo Created Windows shortcut: %SHORTCUT_PATH%
echo Target script: %TARGET_SCRIPT%
echo Python executable: %PYTHON_BIN%
echo Repository root: %REPO_ROOT%
exit /b 0

:write_ps1
(
  echo $ErrorActionPreference = "Stop"
  echo.
  echo $configuredPythonBin = '%PYTHON_PS%'
  echo $targetScript = '%TARGET_PS%'
  echo $port = 8517
  echo $url = "http://localhost:$port"
  echo $logDir = Join-Path $env:LOCALAPPDATA "ClipboardNextcloud\Logs"
  echo $pidFile = Join-Path $logDir "streamlit.pid"
  echo $logFile = Join-Path $logDir "streamlit.log"
  echo $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
  echo $targetScriptFull = [System.IO.Path]::GetFullPath((Join-Path $scriptDir $targetScript^))
  echo $pythonCandidates = @(^)
  echo.
  echo if ($configuredPythonBin^) {
  echo ^  $pythonCandidates += $configuredPythonBin
  echo }
  echo $pythonCandidates += @("python", "py"^)
  echo.
  echo function Resolve-PythonPath {
  echo ^  param([string[]]$Candidates^)
  echo.
  echo ^  foreach ($candidate in $Candidates^) {
  echo ^    if (-not $candidate^) {
  echo ^      continue
  echo ^    }
  echo.
  echo ^    if (Test-Path -LiteralPath $candidate^) {
  echo ^      return (Resolve-Path -LiteralPath $candidate^).Path
  echo ^    }
  echo.
  echo ^    try {
  echo ^      $resolved = Get-Command $candidate -ErrorAction Stop
  echo ^      if ($resolved -and $resolved.Source^) {
  echo ^        return $resolved.Source
  echo ^      }
  echo ^    } catch {
  echo ^    }
  echo ^  }
  echo.
  echo ^  return $null
  echo }
  echo.
  echo New-Item -ItemType Directory -Force -Path $logDir ^| Out-Null
  echo.
  echo if (-not (Test-Path -LiteralPath $targetScriptFull^)^) {
  echo ^  Write-Host "Target script not found: $targetScriptFull"
  echo ^  Write-Host "Please regenerate launcher with the correct script path."
  echo ^  exit 1
  echo }
  echo.
  echo $pythonBin = Resolve-PythonPath -Candidates $pythonCandidates
  echo if (-not $pythonBin^) {
  echo ^  Write-Host "Python executable not found."
  echo ^  Write-Host "Checked configured path: $configuredPythonBin"
  echo ^  Write-Host "Also tried command names: python, py"
  echo ^  exit 1
  echo }
  echo.
  echo if (Test-Path $pidFile^) {
  echo ^  $existingPid = (Get-Content $pidFile -ErrorAction SilentlyContinue ^| Select-Object -First 1^).Trim(^)
  echo ^  if ($existingPid^) {
  echo ^    $existingProcess = Get-Process -Id $existingPid -ErrorAction SilentlyContinue
  echo ^    if ($existingProcess^) {
  echo ^      Start-Process $url
  echo ^      exit 0
  echo ^    }
  echo ^  }
  echo ^  Remove-Item $pidFile -ErrorAction SilentlyContinue
  echo }
  echo.
  echo $streamlitProcess = Start-Process -FilePath $pythonBin `
  echo ^  -ArgumentList "-m", "streamlit", "run", $targetScriptFull, "--server.port", "$port", "--server.address", "localhost", "--server.headless", "true", "--browser.gatherUsageStats", "false" `
  echo ^  -RedirectStandardOutput $logFile -RedirectStandardError $logFile -PassThru
  echo.
  echo $streamlitProcess.Id ^| Set-Content -Path $pidFile
  echo.
  echo for ($i = 0; $i -lt 30; $i++^) {
  echo ^  try {
  echo ^    Invoke-WebRequest -UseBasicParsing -Uri $url -TimeoutSec 1 ^| Out-Null
  echo ^    Start-Process $url
  echo ^    exit 0
  echo ^  } catch {
  echo ^    Start-Sleep -Seconds 1
  echo ^  }
  echo }
  echo.
  echo Start-Process $url
  echo exit 0
) > "%PS1_PATH%"
exit /b 0

:write_launcher_bat
(
  echo @echo off
  echo setlocal
  echo set "SCRIPT_DIR=%%~dp0"
  echo powershell -NoProfile -ExecutionPolicy Bypass -File "%%SCRIPT_DIR%%ClipboardNextcloud.ps1"
) > "%LAUNCHER_BAT%"
exit /b 0

:to_ps_literal
set "%~2=%~1"
set "%~2=!%~2:'=''!"
exit /b 0

:show_usage
echo Usage: %~nx0 [--python PATH] [output_path]
echo   Default output: .\ClipboardNextcloud
exit /b 0

:usage_error
call :show_usage
exit /b 1
