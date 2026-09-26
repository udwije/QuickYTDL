# MSI installer

Wraps the PyInstaller output (`dist\QuickYTDL.exe`) in a Windows Installer
package using [WiX](https://wixtoolset.org/).

These files are what `.github/workflows/release.yml` looks for. If
`installer/QuickYTDL.wxs` and `installer/License.rtf` are missing, the release
workflow logs a notice and ships the `.exe` only.

## Build locally

From the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File .\Build-Installer.ps1
```

That builds the exe and then the MSI in one pass. Output:

```
dist\QuickYTDL.exe
dist\QuickYTDL-1.7.1-x64.msi
```

To package an exe you already built:

```powershell
.\Build-Installer.ps1 -SkipExe
```

To override the version:

```powershell
.\Build-Installer.ps1 -Version 1.7.2
```

## Prerequisites

| Tool | Install |
|---|---|
| PyInstaller | `pip install pyinstaller` |
| .NET SDK 6+ | <https://dotnet.microsoft.com/download> |
| WiX .NET tool | `dotnet tool install --global wix` |
| WiX UI extension | `wix extension add --global WixToolset.UI.wixext` |

`Build-Installer.ps1` checks each of these and installs the WiX pieces
automatically if they're missing. If `wix` still isn't resolved right after
the tool install, re-open the shell so the updated PATH is picked up.

## What the MSI does

- Installs `QuickYTDL.exe` to `C:\Program Files\QuickYTDL\` (per-machine,
  so it prompts for elevation).
- Creates Start Menu and Desktop shortcuts, both removed on uninstall.
- Registers in Apps & Features with the app icon and a link to the repo.
- Handles upgrades: installing a newer version removes the old one instead
  of leaving duplicate entries.

## Silent install

```powershell
msiexec /i "QuickYTDL-1.7.1-x64.msi" /qn                  # install
msiexec /x "QuickYTDL-1.7.1-x64.msi" /qn                  # uninstall
msiexec /i "QuickYTDL-1.7.1-x64.msi" /l*v install.log     # verbose log
msiexec /i "QuickYTDL-1.7.1-x64.msi" INSTALLFOLDER="D:\Apps\QuickYTDL" /qn
```

## Maintaining it

The `UpgradeCode` GUID in `QuickYTDL.wxs` identifies the product across all
releases - **never change it**, or future versions will install alongside the
old ones rather than upgrading them.

Version numbers come from `version_info.txt`, which the release workflow
stamps from the git tag via `tools/set_version.py`, so the MSI version and the
exe's file version stay in sync automatically.
