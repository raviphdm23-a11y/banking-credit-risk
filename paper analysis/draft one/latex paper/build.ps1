# build.ps1 - compile the IEEE TAI paper and (re)open it for review.
# Workflow: if the target PDF is locked (open in Acrobat), close Acrobat first,
# then compile (latexmk: pdflatex + bibtex passes), then reopen the PDF.
# Usage:  powershell -ExecutionPolicy Bypass -File build.ps1 [-Tex main]
param([string]$Tex = "main")
$ErrorActionPreference = "Stop"
$dir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $dir
$pdf = Join-Path $dir "$Tex.pdf"

function Test-Locked($path) {
  if (-not (Test-Path $path)) { return $false }
  try { $fs = [System.IO.File]::Open($path, 'Open', 'ReadWrite', 'None'); $fs.Close(); return $false }
  catch { return $true }
}

if (Test-Locked $pdf) {
  Write-Host "[build] $Tex.pdf is open/locked -> closing Acrobat..."
  Get-Process Acrobat, AcroRd32 -ErrorAction SilentlyContinue | Stop-Process -Force
  Start-Sleep -Milliseconds 800
}

Write-Host "[build] compiling $Tex.tex (pdflatex + bibtex passes; no Perl needed) ..."
$pl = "-interaction=nonstopmode", "-halt-on-error", "$Tex"
& pdflatex @pl | Out-Null
& bibtex $Tex | Out-Null
& pdflatex @pl | Out-Null
& pdflatex @pl | Out-Host
$built = ($LASTEXITCODE -eq 0) -and (Test-Path $pdf)
if (-not $built) {
  Write-Host "[build] BUILD FAILED - see $Tex.log (showing last errors):"
  if (Test-Path "$Tex.log") { Select-String -Path "$Tex.log" -Pattern '^!|Undefined|Error' | Select-Object -Last 15 | ForEach-Object { $_.Line } }
  exit 1
}

Write-Host "[build] opening $pdf"
Start-Process $pdf
Write-Host "[build] done."
