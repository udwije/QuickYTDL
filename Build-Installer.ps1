<#
.SYNOPSIS
    Builds QuickYTDL.exe with PyInstaller, then wraps it in an MSI with WiX.

.DESCRIPTION
    Run from the repository root:

        powershell -ExecutionPolicy Bypass -File .\Build-Installer.ps1

    Produces:
        dist\QuickYTDL.exe                  (PyInstaller, single file)
        dist\QuickYTDL-<version>-x64.msi    (WiX)

    This is the local equivalent of what .github/workflows/release.yml does
    on a Windows runner, so you can test an installer without tagging.

    Prerequisites (checked below, with install hints if missing):
        - Python with the project's requirements installed
        - pyinstaller           pip install pyinstaller
        - .NET SDK 6 or later   https://dotnet.microsoft.com/download
        - WiX .NET tool         dotnet tool install --global wix

.PARAMETER Version
    Product version for the MSI. Defaults to the ProductVersion found in
    version_info.txt, falling back to 1.0.0.

.PARAMETER SkipExe
    Skip the PyInstaller step and package an already-built dist\QuickYTDL.exe.
#>

[CmdletBinding()]
param(
    [string] $Version,
    [switch] $SkipExe
)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
Set-Location $root

function Write-Step($n, $text) { Write-Host "`n[$n] $text" -ForegroundColor Cyan }
function Fail($text, $hint) {
    Write-Host "  ERROR: $text" -ForegroundColor Red
    if ($hint) { Write-Host "  -> $hint" -ForegroundColor Yellow }
    exit 1
}

# ---------------------------------------------------------------- version
Write-Step 1 'Resolving version'

if (-not $Version) {
    $vi = Join-Path $root 'version_info.txt'
    if (Test-Path $vi) {
        # PyInstaller version resource: StringStruct('ProductVersion', '1.7.1')
        $m = Select-String -Path $vi -Pattern "ProductVersion'\s*,\s*'([0-9]+(\.[0-9]+){1,3})" |
             Select-Object -First 1
        if ($m) { $Version = $m.Matches[0].Groups[1].Value }
    }
}
if (-not $Version) { $Version = '1.0.0' }

# MSI versions must be a.b.c(.d) with each field numeric; trim any extra parts.
$parts = $Version.Split('.') | Select-Object -First 3
while ($parts.Count -lt 3) { $parts += '0' }
$Version = $parts -join '.'
Write-Host "  Version: $Version"

# ---------------------------------------------------------- prerequisites
Write-Step 2 'Checking prerequisites'

if (-not $SkipExe) {
    if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
        Fail 'python not found on PATH.' 'Install Python and re-open the shell.'
    }
    python -c "import PyInstaller" 2>$null
    if ($LASTEXITCODE -ne 0) { Fail 'PyInstaller not installed.' 'pip install pyinstaller' }
    Write-Host '  PyInstaller: OK'
}

if (-not (Get-Command dotnet -ErrorAction SilentlyContinue)) {
    Fail '.NET SDK not found on PATH.' 'Install .NET SDK 6+ from https://dotnet.microsoft.com/download'
}
Write-Host '  .NET SDK: OK'

if (-not (Get-Command wix -ErrorAction SilentlyContinue)) {
    Write-Host '  WiX not found - installing as a global .NET tool...' -ForegroundColor Yellow
    dotnet tool install --global wix
    if ($LASTEXITCODE -ne 0) { Fail 'Could not install the WiX .NET tool.' 'dotnet tool install --global wix' }
    Write-Host '  Re-open the shell if "wix" is still not resolved, then re-run.' -ForegroundColor Yellow
}
$wixVersion = (wix --version) 2>$null
Write-Host "  WiX: $wixVersion"

# The WixUI_InstallDir dialog set lives in the UI extension; it has to be
# registered against the global tool before `wix build -ext` can use it.
$extList = (wix extension list --global) 2>$null
if ($extList -notmatch 'WixToolset\.UI\.wixext') {
    Write-Host '  Adding WixToolset.UI.wixext...' -ForegroundColor Yellow
    wix extension add --global WixToolset.UI.wixext
    if ($LASTEXITCODE -ne 0) { Fail 'Could not add WixToolset.UI.wixext.' 'wix extension add --global WixToolset.UI.wixext' }
}
Write-Host '  WixToolset.UI.wixext: OK'

# ------------------------------------------------------------- build exe
if (-not $SkipExe) {
    Write-Step 3 'Building QuickYTDL.exe (PyInstaller)'
    # Stale caches are the usual cause of "why is my old code still in there".
    if (Test-Path build) { Remove-Item build -Recurse -Force }
    if (Test-Path dist)  { Remove-Item dist  -Recurse -Force }

    pyinstaller QuickYTDL.spec
    if ($LASTEXITCODE -ne 0) { Fail 'PyInstaller failed.' 'Check the output above.' }
} else {
    Write-Step 3 'Skipping PyInstaller (-SkipExe)'
}

$exe = Join-Path $root 'dist\QuickYTDL.exe'
if (-not (Test-Path $exe)) {
    Fail "dist\QuickYTDL.exe not found." 'Run without -SkipExe, or build it first.'
}
$exeSize = [math]::Round((Get-Item $exe).Length / 1MB, 1)
Write-Host "  dist\QuickYTDL.exe  ($exeSize MB)"

# ------------------------------------------------------------- build msi
Write-Step 4 'Building the MSI (WiX)'

$icon    = Join-Path $root 'resources\QuickYTDL.ico'
$license = Join-Path $root 'installer\License.rtf'
$wxs     = Join-Path $root 'installer\QuickYTDL.wxs'
$msi     = Join-Path $root "dist\QuickYTDL-$Version-x64.msi"

foreach ($p in @($icon, $license, $wxs)) {
    if (-not (Test-Path $p)) { Fail "Missing required file: $p" }
}

wix build $wxs `
    -arch x64 `
    -ext WixToolset.UI.wixext `
    -d ExeSource="$exe" `
    -d IconSource="$icon" `
    -d LicenseSource="$license" `
    -d ProductVersion="$Version" `
    -o $msi

if ($LASTEXITCODE -ne 0) { Fail 'WiX build failed.' 'Check the output above.' }

$msiSize = [math]::Round((Get-Item $msi).Length / 1MB, 1)

Write-Host "`nDone." -ForegroundColor Green
Write-Host "  $msi  ($msiSize MB)"
Write-Host @"

Install silently:    msiexec /i "$msi" /qn
Uninstall silently:  msiexec /x "$msi" /qn
Install with a log:  msiexec /i "$msi" /l*v install.log
"@
