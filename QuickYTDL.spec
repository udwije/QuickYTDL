# QuickYTDL.spec
#
# Build with:
#   pyinstaller QuickYTDL.spec
#
# Output: dist/QuickYTDL.exe (single file, no console window)

from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

# Bundle our own resources folder (icon/logo used at runtime for the
# window/taskbar icon), plus the actual ffmpeg binary that imageio-ffmpeg
# ships inside its own package directory (imageio_ffmpeg/binaries/...).
# Without this second one, get_ffmpeg_exe() has nothing to find at runtime
# on a machine that doesn't already have it cached.
datas = [
    ('resources', 'resources'),
]
datas += collect_data_files('imageio_ffmpeg')

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    # yt-dlp resolves its ~1800 site extractors dynamically, so static
    # analysis misses them and the frozen exe fails with "Unsupported URL".
    # Pulling in the extractor package keeps YouTube (and everything else)
    # working in the bundle.
    hiddenimports=['yt_dlp.extractor'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='QuickYTDL',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # UPX and the ffmpeg binary don't mix well; compressing it has been a
    # recurring source of "ffmpeg exited with code -1073741819" on Windows.
    upx=True,
    upx_exclude=['ffmpeg*.exe', 'ffmpeg*'],
    runtime_tmpdir=None,
    console=False,          # windowed app, no console popup
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='resources/QuickYTDL.ico',
    version='version_info.txt',
)
