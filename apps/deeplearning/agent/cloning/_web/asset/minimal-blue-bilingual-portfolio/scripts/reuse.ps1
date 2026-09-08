param(
    [Parameter(Mandatory = $true)]
    [string]$Destination
)
$ErrorActionPreference = 'Stop'
$source = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../assets/site'))
$target = [IO.Path]::GetFullPath($Destination)
if (Test-Path -LiteralPath $target) {
    throw "Destination already exists; choose a new directory: $target"
}
if (-not (Test-Path -LiteralPath (Join-Path $source 'index.html'))) {
    throw "Site template is missing: $source"
}
Copy-Item -LiteralPath $source -Destination $target -Recurse
Write-Output "Created: $target"
Write-Output "Open: $(Join-Path $target 'index.html')"
