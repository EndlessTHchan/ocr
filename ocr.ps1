param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Args
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Py = Join-Path $Root ".venv\Scripts\python.exe"

if (-not (Test-Path $Py)) {
    Write-Error "Missing venv python at $Py. Create it with one of:"
    Write-Error "  py -3.10 -m venv .venv"
    Write-Error "  python -m venv .venv"
    exit 1
}

Set-Location -Path $Root
& $Py -m ocr_tool.cli @Args
exit $LASTEXITCODE
