# =========================
# app/models.py
# =========================

from dataclasses import dataclass, field

@dataclass
class PlaylistItem:
    index: int
    video_id: str
    title: str
    url: str
    duration: int
    status: str = field(default="⏸️")  # Default: paused/pending
    selected: bool = field(default=True)

    def update_status(self, new_status: str):
        """Update the download status emoji."""
        self.status = new_status
