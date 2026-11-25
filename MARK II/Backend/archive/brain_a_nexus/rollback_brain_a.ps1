#Requires -Version 5.1
<#
.SYNOPSIS
    Brain A (NEXUS) Rollback Script — Vennela AI 2.0 (MARK-II)

.DESCRIPTION
    Restores Brain A source files from the archive back to Backend/agents/.

    DEFAULT MODE: DRY-RUN (safe, no changes made).
    EXECUTE MODE: Requires -Execute flag for actual restoration.

    The rollback script:
      - Verifies archive integrity before any file operation (SHA256 comparison).
      - Restores Brain A files to Backend/agents/ and Backend/agents/web_hunt/.
      - Does NOT modify app.py or re-activate Brain A automatically.
      - After restore, manually update Backend/app.py to re-enable Brain A.

.PARAMETER Execute
    Switch. When present, files are actually restored. Without this, only a
    dry-run simulation is performed (no files are changed).

.EXAMPLE
    # Dry-run (default, safe):
    .\rollback_brain_a.ps1

    # Actual restore:
    .\rollback_brain_a.ps1 -Execute

.NOTES
    NEVER expose secrets. This script does not read or print .env files.
    STAGE 3 AUTHORIZATION: NOT GRANTED — Do not deploy to production.
#>

[CmdletBinding()]
param(
    [switch]$Execute
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# =========================================================
# CONFIGURATION
# =========================================================
$ScriptDir      = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendRoot    = Split-Path -Parent (Split-Path -Parent $ScriptDir)
$ArchiveDir     = $ScriptDir
$TargetAgents   = Join-Path $BackendRoot "agents"
$TargetWebHunt  = Join-Path $TargetAgents "web_hunt"
$ManifestPath   = Join-Path $ArchiveDir "brain_a_manifest.json"

$Mode = if ($Execute) { "EXECUTE" } else { "DRY-RUN" }

Write-Host ""
Write-Host "============================================================"
Write-Host " BRAIN A (NEXUS) ROLLBACK SCRIPT"
Write-Host " Mode      : $Mode"
Write-Host " Backend   : $BackendRoot"
Write-Host " Archive   : $ArchiveDir"
Write-Host " Target    : $TargetAgents"
Write-Host "============================================================"
Write-Host ""

if (-not $Execute) {
    Write-Host "[DRY-RUN] No files will be changed. Use -Execute to restore." -ForegroundColor Yellow
    Write-Host ""
}

# =========================================================
# STEP 1: VERIFY ARCHIVE INTEGRITY
# =========================================================
Write-Host "[STEP 1] Verifying archive integrity..."

if (-not (Test-Path $ManifestPath)) {
    Write-Error "ABORT: Manifest not found at: $ManifestPath"
    exit 1
}

$manifest = Get-Content $ManifestPath -Raw | ConvertFrom-Json
$manifestFiles = $manifest.files.PSObject.Properties

$allOk = $true
foreach ($entry in $manifestFiles) {
    $relPath   = $entry.Name
    $expected  = $entry.Value.sha256
    $fullPath  = Join-Path $ArchiveDir ($relPath -replace "/", "\")

    if (-not (Test-Path $fullPath)) {
        Write-Host "  MISSING: $relPath" -ForegroundColor Red
        $allOk = $false
        continue
    }

    $actual = (Get-FileHash $fullPath -Algorithm SHA256).Hash.ToLower()
    $content = [System.IO.File]::ReadAllText($fullPath).Replace("`r`n", "`n")
    $hasher = [System.Security.Cryptography.SHA256]::Create()
    $normalizedBytes = [System.Text.Encoding]::UTF8.GetBytes($content)
    $normalizedHash = [System.BitConverter]::ToString($hasher.ComputeHash($normalizedBytes)).Replace("-", "").ToLower()

    if ($actual -eq $expected -or $normalizedHash -eq $expected) {
        Write-Host "  OK: $relPath" -ForegroundColor Green
    } else {
        Write-Host "  HASH MISMATCH: $relPath" -ForegroundColor Red
        Write-Host "    Expected : $expected"
        Write-Host "    Actual   : $actual"
        $allOk = $false
    }
}

if (-not $allOk) {
    Write-Host ""
    Write-Error "ABORT: Archive integrity check FAILED. Do not proceed."
    exit 2
}

Write-Host ""
Write-Host "[STEP 1] Archive integrity: VERIFIED" -ForegroundColor Green
Write-Host ""

# =========================================================
# STEP 2: CONFLICT DETECTION
# =========================================================
Write-Host "[STEP 2] Checking for conflicts in target directory..."

$FileMap = @{
    "brain.py"              = $TargetAgents
    "models.py"             = $TargetAgents
    "orchestrator.py"       = $TargetAgents
    "planner.py"            = $TargetAgents
    "reasoning.py"          = $TargetAgents
    "registry.py"           = $TargetAgents
    "__init__.py"           = $TargetAgents
}
$WebHuntFileMap = @{
    "agent.py"              = $TargetWebHunt
    "config.py"             = $TargetWebHunt
    "errors.py"             = $TargetWebHunt
    "models.py"             = $TargetWebHunt
    "__init__.py"           = $TargetWebHunt
}

$conflicts = @()
foreach ($fname in $FileMap.Keys) {
    $dest = Join-Path $FileMap[$fname] $fname
    if (Test-Path $dest) { $conflicts += $dest }
}
foreach ($fname in $WebHuntFileMap.Keys) {
    $dest = Join-Path $WebHuntFileMap[$fname] $fname
    if (Test-Path $dest) { $conflicts += $dest }
}

if ($conflicts.Count -gt 0) {
    Write-Host "  CONFLICTS DETECTED — files already exist at target:" -ForegroundColor Yellow
    foreach ($c in $conflicts) { Write-Host "    $c" -ForegroundColor Yellow }
    Write-Host ""
    if ($Execute) {
        Write-Host "  [EXECUTE] Conflicts will be OVERWRITTEN during restore." -ForegroundColor Yellow
    } else {
        Write-Host "  [DRY-RUN] Would overwrite these files." -ForegroundColor Yellow
    }
} else {
    Write-Host "  No conflicts — target paths are clear." -ForegroundColor Green
}
Write-Host ""

# =========================================================
# STEP 3: RESTORE FILES
# =========================================================
Write-Host "[STEP 3] Restoring Brain A files..."

function Restore-File {
    param([string]$SrcName, [string]$SrcSubdir, [string]$DestDir)
    $src  = Join-Path $ArchiveDir "$SrcSubdir\$SrcName"
    $dest = Join-Path $DestDir $SrcName
    if ($Execute) {
        if (-not (Test-Path $DestDir)) { New-Item -ItemType Directory -Path $DestDir -Force | Out-Null }
        Copy-Item $src $dest -Force
        Write-Host "  RESTORED: $dest" -ForegroundColor Green
    } else {
        Write-Host "  [DRY-Run] Would restore: $src -> $dest" -ForegroundColor Cyan
    }
}

foreach ($fname in $FileMap.Keys) {
    Restore-File -SrcName $fname -SrcSubdir "" -DestDir $TargetAgents
}
foreach ($fname in $WebHuntFileMap.Keys) {
    Restore-File -SrcName $fname -SrcSubdir "web_hunt_original" -DestDir $TargetWebHunt
}

Write-Host ""

# =========================================================
# STEP 4: POST-RESTORE VERIFICATION (Execute mode only)
# =========================================================
if ($Execute) {
    Write-Host "[STEP 4] Post-restore hash verification..."
    $postOk = $true
    foreach ($fname in $FileMap.Keys) {
        $src    = Join-Path $ArchiveDir $fname
        $dest   = Join-Path $TargetAgents $fname
        $srcH   = (Get-FileHash $src  -Algorithm SHA256).Hash.ToLower()
        $destH  = (Get-FileHash $dest -Algorithm SHA256).Hash.ToLower()
        if ($srcH -eq $destH) {
            Write-Host "  VERIFIED: agents/$fname" -ForegroundColor Green
        } else {
            Write-Host "  HASH FAIL: agents/$fname" -ForegroundColor Red
            $postOk = $false
        }
    }
    foreach ($fname in $WebHuntFileMap.Keys) {
        $src    = Join-Path $ArchiveDir "web_hunt_original\$fname"
        $dest   = Join-Path $TargetWebHunt $fname
        $srcH   = (Get-FileHash $src  -Algorithm SHA256).Hash.ToLower()
        $destH  = (Get-FileHash $dest -Algorithm SHA256).Hash.ToLower()
        if ($srcH -eq $destH) {
            Write-Host "  VERIFIED: agents/web_hunt/$fname" -ForegroundColor Green
        } else {
            Write-Host "  HASH FAIL: agents/web_hunt/$fname" -ForegroundColor Red
            $postOk = $false
        }
    }

    Write-Host ""
    if ($postOk) {
        Write-Host "[STEP 4] Post-restore verification: PASSED" -ForegroundColor Green
    } else {
        Write-Error "[STEP 4] Post-restore verification: FAILED — check archive integrity"
        exit 3
    }
}

# =========================================================
# SUMMARY
# =========================================================
Write-Host ""
Write-Host "============================================================"
if ($Execute) {
    Write-Host " ROLLBACK COMPLETE — Brain A files restored to agents/" -ForegroundColor Green
    Write-Host ""
    Write-Host " NEXT STEPS (manual — not done by this script):"
    Write-Host "   1. Update Backend/app.py to re-enable Brain A."
    Write-Host "      Restore _build_legacy_brain() and the VENNELA_LANGGRAPH_ENABLED"
    Write-Host "      conditional in get_brain() from the git history:"
    Write-Host "        git show HEAD~1:MARK II/Backend/app.py > app_brain_a.py"
    Write-Host "   2. Restart the application."
    Write-Host "   3. Run pytest Backend/tests/ to verify Brain A functionality."
    Write-Host ""
    Write-Host " STAGE 3 AUTHORIZATION: NOT GRANTED"
} else {
    Write-Host " DRY-RUN COMPLETE — no files changed." -ForegroundColor Yellow
    Write-Host " Run with -Execute to perform actual restore."
    Write-Host ""
    Write-Host " STAGE 3 AUTHORIZATION: NOT GRANTED"
}
Write-Host "============================================================"
Write-Host ""
