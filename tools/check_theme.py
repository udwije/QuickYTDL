"""
Static checks on the theme so a styling mistake fails CI rather than
shipping as an unstyled or half-styled window.

Verifies:
  * both themes render with no unresolved {placeholder}
  * the light and dark palettes define exactly the same keys
  * every status the downloader emits has a colour in both themes
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from quickytdl.ui import theme  # noqa: E402

# Statuses produced by DownloadWorker / the models.
REQUIRED_STATUSES = ("Queued", "Downloading", "Merging",
                     "Completed", "Failed", "Canceled")

failed = False


def fail(msg):
    global failed
    failed = True
    print(f"  FAIL {msg}")


for dark in (False, True):
    label = "dark" if dark else "light"
    try:
        css = theme.stylesheet(dark)
    except KeyError as exc:
        # A palette missing a key the template uses - report it plainly
        # instead of dumping a traceback in the CI log.
        fail(f"{label}: palette is missing key {exc}")
        continue
    leftover = re.findall(r"\{(\w+)\}", css)
    if leftover:
        fail(f"{label}: unresolved placeholders {sorted(set(leftover))}")
    elif not css.strip():
        fail(f"{label}: stylesheet is empty")
    else:
        print(f"  OK   {label}: {len(css)} chars, no unresolved placeholders")

missing_dark = set(theme.LIGHT) - set(theme.DARK)
missing_light = set(theme.DARK) - set(theme.LIGHT)
if missing_dark or missing_light:
    fail(f"palette key mismatch: missing in DARK={sorted(missing_dark)}, "
         f"missing in LIGHT={sorted(missing_light)}")
else:
    print(f"  OK   palettes share all {len(theme.LIGHT)} keys")

for dark in (False, True):
    label = "dark" if dark else "light"
    bad = [s for s in REQUIRED_STATUSES
           if not re.fullmatch(r"#[0-9a-fA-F]{6}", theme.status_color(s, dark) or "")]
    if bad:
        fail(f"{label}: statuses with invalid colours: {bad}")
    else:
        print(f"  OK   {label}: all {len(REQUIRED_STATUSES)} statuses have colours")

print("\nRESULT:", "FAILED" if failed else "PASSED")
sys.exit(1 if failed else 0)
