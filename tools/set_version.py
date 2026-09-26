"""
Stamp a version into version_info.txt (the PyInstaller version resource).

Used by the release workflow so the executable's file/product version always
matches the git tag, instead of drifting like it did between 1.3.0 and 1.7.x.

Usage:
    python tools/set_version.py 1.7.1
    python tools/set_version.py 1.7.1 --check   # verify only, no write
"""

import argparse
import re
import sys
from pathlib import Path

VERSION_FILE = Path(__file__).resolve().parent.parent / "version_info.txt"

# 1.7.1 or 1.7.1.0 ; an optional leading 'v' is tolerated for tag input.
_SEMVER = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:\.(\d+))?$")


def parse_version(raw: str):
    """'v1.7.1' -> (1, 7, 1, 0). Raises SystemExit on malformed input."""
    m = _SEMVER.match((raw or "").strip())
    if not m:
        sys.exit(
            f"error: '{raw}' is not a valid version. "
            "Expected MAJOR.MINOR.PATCH (e.g. 1.7.1), optionally v-prefixed."
        )
    major, minor, patch, build = m.groups()
    return int(major), int(minor), int(patch), int(build or 0)


def render(text: str, parts) -> str:
    """Rewrite every version field in the version resource."""
    major, minor, patch, build = parts
    dotted = f"{major}.{minor}.{patch}"

    text = re.sub(
        r"filevers=\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*,\s*\d+\s*\)",
        f"filevers=({major}, {minor}, {patch}, {build})",
        text,
    )
    text = re.sub(
        r"prodvers=\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*,\s*\d+\s*\)",
        f"prodvers=({major}, {minor}, {patch}, {build})",
        text,
    )
    text = re.sub(
        r"(StringStruct\('FileVersion',\s*')[^']*(')",
        rf"\g<1>{dotted}\g<2>",
        text,
    )
    text = re.sub(
        r"(StringStruct\('ProductVersion',\s*')[^']*(')",
        rf"\g<1>{dotted}\g<2>",
        text,
    )
    return text


def current_version(text: str):
    m = re.search(r"StringStruct\('ProductVersion',\s*'([^']*)'", text)
    return m.group(1) if m else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("version", help="e.g. 1.7.1 or v1.7.1")
    ap.add_argument("--check", action="store_true",
                    help="verify the file already matches; do not write")
    args = ap.parse_args()

    parts = parse_version(args.version)
    dotted = ".".join(str(p) for p in parts[:3])

    if not VERSION_FILE.exists():
        sys.exit(f"error: {VERSION_FILE} not found")

    text = VERSION_FILE.read_text(encoding="utf-8")
    updated = render(text, parts)

    if args.check:
        found = current_version(text)
        if found != dotted:
            sys.exit(f"error: version_info.txt says {found}, expected {dotted}")
        print(f"version_info.txt matches {dotted}")
        return

    if updated == text:
        print(f"version_info.txt already at {dotted}; nothing to do")
        return

    VERSION_FILE.write_text(updated, encoding="utf-8")
    print(f"version_info.txt stamped {current_version(text)} -> {dotted}")


if __name__ == "__main__":
    main()
