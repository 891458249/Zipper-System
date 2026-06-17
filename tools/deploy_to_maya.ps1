<#
.SYNOPSIS
    Pull the latest Zipper System source and deploy it into the installed Maya
    module, purging stale Python bytecode so the new code actually loads.

.DESCRIPTION
    Maya runs the INSTALLED copy under  <Documents>\maya\modules\ZipperSystem\
    scripts\zipper_system , not the git repo. And Python does NOT hot-reload:
    a running Maya keeps the old modules cached. So "fix in repo" alone never
    takes effect on the artist machine. This script closes that gap:
      1. git pull (fast-forward) in the repo
      2. copy repo  zipper_system\  ->  installed  scripts\zipper_system\
      3. delete every *.pyc / *.pyo / __pycache__ in BOTH trees (Py2 drops .pyc
         next to the source; Py3 uses __pycache__ -- either can shadow the fix)
      4. tell you to restart Maya (or do it for you with -RestartMaya)

    Safe by default: additive copy (does not mirror-delete), and it will not
    kill Maya unless you pass -RestartMaya.

.PARAMETER Repo
    Repo root. Defaults to the parent folder of this script (tools\..).

.PARAMETER ModuleRoot
    Installed module root. Defaults to <MyDocuments>\maya\modules\ZipperSystem.
    Pass this if the target artist uses a different Documents location.

.PARAMETER NoPull        Skip 'git pull' (deploy the working tree as-is).
.PARAMETER RestartMaya   Close any running Maya and relaunch it afterwards.
.PARAMETER MayaExe       maya.exe to relaunch; auto-detected if omitted.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File tools\deploy_to_maya.ps1
.EXAMPLE
    # full auto: pull, deploy, bounce Maya
    powershell -ExecutionPolicy Bypass -File tools\deploy_to_maya.ps1 -RestartMaya
#>
param(
    [string]$Repo = (Split-Path -Parent $PSScriptRoot),
    [string]$ModuleRoot,
    [switch]$NoPull,
    [switch]$RestartMaya,
    [string]$MayaExe
)
$ErrorActionPreference = "Stop"

# --- resolve paths -------------------------------------------------------- #
if (-not $ModuleRoot) {
    $docs = [Environment]::GetFolderPath('MyDocuments')
    $ModuleRoot = Join-Path $docs 'maya\modules\ZipperSystem'
}
$src  = Join-Path $Repo 'zipper_system'
$dest = Join-Path $ModuleRoot 'scripts\zipper_system'

if (-not (Test-Path $src)) { throw "source package not found: $src" }
if (-not (Test-Path $dest)) {
    throw "installed module not found: $dest`n  Run the installer once first (installer\ZipperSystemInstaller.exe)."
}
Write-Host "Repo   : $Repo"
Write-Host "Source : $src"
Write-Host "Target : $dest"

# --- 1. pull -------------------------------------------------------------- #
if (-not $NoPull) {
    Push-Location $Repo
    try {
        Write-Host "`n[1/4] git pull --ff-only ..."
        git pull --ff-only
        if ($LASTEXITCODE -ne 0) {
            throw "git pull failed (exit $LASTEXITCODE). Resolve manually, or re-run with -NoPull."
        }
    } finally { Pop-Location }
} else {
    Write-Host "`n[1/4] skip pull (-NoPull)"
}

# --- 2. copy source -> installed (additive overwrite, not a mirror) ------- #
Write-Host "[2/4] copy source into installed module ..."
# /E copy subdirs incl. empty; /XD/XF skip caches; /NJH /NJS /NP quiet-ish.
robocopy $src $dest /E /XD __pycache__ /XF *.pyc *.pyo /NJH /NJS /NP /NDL | Out-Null
# robocopy exit codes 0-7 are success (8+ = real error)
if ($LASTEXITCODE -ge 8) { throw "robocopy failed (exit $LASTEXITCODE)" }

# --- 3. purge stale bytecode in BOTH trees -------------------------------- #
Write-Host "[3/4] purge stale .pyc / __pycache__ ..."
foreach ($root in @($src, $dest)) {
    Get-ChildItem $root -Recurse -File -Include *.pyc, *.pyo -ErrorAction SilentlyContinue |
        Remove-Item -Force -ErrorAction SilentlyContinue
    Get-ChildItem $root -Recurse -Directory -Filter __pycache__ -ErrorAction SilentlyContinue |
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
}

# --- 4. restart Maya (or warn) -------------------------------------------- #
Write-Host "[4/4] checking Maya ..."
$maya = Get-Process maya -ErrorAction SilentlyContinue
if ($maya) {
    if ($RestartMaya) {
        if (-not $MayaExe) {
            $MayaExe = $maya | Select-Object -First 1 -ExpandProperty Path
        }
        Write-Warning "Closing Maya (SAVE YOUR SCENE if needed -- this force-closes it)."
        $maya | Stop-Process -Force
        Start-Sleep -Seconds 3
        if ($MayaExe -and (Test-Path $MayaExe)) {
            Start-Process $MayaExe
            Write-Host "Relaunched: $MayaExe"
        } else {
            Write-Warning "Could not resolve maya.exe path; start Maya manually."
        }
    } else {
        Write-Warning "Maya is RUNNING with the old modules cached. Restart Maya for the fix to load (or re-run with -RestartMaya)."
    }
} else {
    Write-Host "Maya not running -- next launch will pick up the new code."
}

Write-Host "`nDeploy complete." -ForegroundColor Green
Write-Host "After Maya restarts: open the UI -> Manage tab should open without error."
