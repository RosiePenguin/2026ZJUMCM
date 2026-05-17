$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$outDir = Join-Path $root "out"

if (-not (Test-Path -LiteralPath $outDir)) {
    New-Item -ItemType Directory -Path $outDir | Out-Null
}

Set-Location $root
xelatex -interaction=nonstopmode -halt-on-error -output-directory=out main.tex
xelatex -interaction=nonstopmode -halt-on-error -output-directory=out main.tex
