param(
    [string[]]$ArgsFromCaller
)
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir
Set-Location $projectRoot
python -m src.mrta_rect_coverage.main @ArgsFromCaller
