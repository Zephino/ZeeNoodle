"""Match lacewin-style scam images and narrow text markers."""

from __future__ import annotations

import datetime
import io
import re
from dataclasses import dataclass
from pathlib import Path

import imagehash
from PIL import Image

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}

_LACEWIN_RE = re.compile(r"lacewin\.com|\blacewin\b", re.IGNORECASE)
_EPIC_RE = re.compile(r"\bepic\b", re.IGNORECASE)
_CASINO_PHRASES = (
    "cryptocurrency casino",
    "crypto casino",
)
_WITHDRAW_PHRASES = (
    "withdraw the bonus immediately",
    "withdraw the bonus",
)


@dataclass(frozen=True)
class ImageHit:
    reference: str
    distance: int


@dataclass(frozen=True)
class Match:
    image_hits: tuple[ImageHit, ...] = ()
    text_reasons: tuple[str, ...] = ()

    @property
    def matched(self) -> bool:
        return bool(self.image_hits or self.text_reasons)

    def summary(self) -> str:
        parts: list[str] = []
        for hit in self.image_hits:
            parts.append(f"image {hit.reference} (distance {hit.distance})")
        parts.extend(self.text_reasons)
        return "; ".join(parts) if parts else "no match"


_UNSAFE_NAME = re.compile(r"[^\w.\-]+")


def safe_image_name(name: str) -> str:
    base = Path(name).name
    if not base or base in {".", ".."}:
        base = "reference.png"
    suffix = Path(base).suffix.lower()
    if suffix not in IMAGE_SUFFIXES:
        base = f"{base}.png"
    cleaned = _UNSAFE_NAME.sub("_", base)
    return cleaned or "reference.png"


class Detector:
    def __init__(self, references_dir: Path, max_distance: int = 10) -> None:
        self.references_dir = references_dir
        self.max_distance = max_distance
        self.references: list[tuple[str, imagehash.ImageHash]] = []
        self.reload()

    def reload(self) -> None:
        self.references = []
        self._load(self.references_dir)

    def names(self) -> list[str]:
        return [name for name, _ in self.references]

    def _load(self, folder: Path) -> None:
        if not folder.is_dir():
            return
        for path in sorted(folder.iterdir()):
            if path.suffix.lower() not in IMAGE_SUFFIXES:
                continue
            with Image.open(path) as img:
                self.references.append((path.name, imagehash.phash(img.convert("RGB"))))

    def add_image(self, data: bytes) -> str:
        """Save *data* as a new reference image with an auto-generated name.

        Returns the filename that was saved.  Raises ``ValueError`` if *data*
        is not a readable image.
        """
        self.references_dir.mkdir(parents=True, exist_ok=True)
        try:
            with Image.open(io.BytesIO(data)) as img:
                fmt = (img.format or "PNG").lower()
        except OSError:
            raise ValueError("That file is not a readable image.")
        if fmt == "jpeg":
            fmt = "jpg"
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"ref_{stamp}.{fmt}"
        dest = self.references_dir / filename
        index = 2
        while dest.exists():
            filename = f"ref_{stamp}_{index}.{fmt}"
            dest = self.references_dir / filename
            index += 1
        dest.write_bytes(data)
        self.reload()
        return filename

    def remove_image(self, name: str) -> bool:
        filename = Path(name).name
        dest = self.references_dir / filename
        if not dest.is_file():
            return False
        dest.unlink()
        self.reload()
        return True

    def hash_bytes(self, data: bytes) -> imagehash.ImageHash | None:
        try:
            with Image.open(io.BytesIO(data)) as img:
                return imagehash.phash(img.convert("RGB"))
        except OSError:
            return None

    def match_image(self, data: bytes) -> tuple[ImageHit, ...]:
        hashed = self.hash_bytes(data)
        if hashed is None:
            return ()
        hits = []
        for name, ref in self.references:
            distance = hashed - ref
            if distance <= self.max_distance:
                hits.append(ImageHit(name, int(distance)))
        return tuple(hits)

    def match_text(self, text: str) -> tuple[str, ...]:
        if not text.strip():
            return ()
        lowered = text.lower()
        reasons: list[str] = []
        if _LACEWIN_RE.search(text):
            reasons.append("lacewin URL or mention")
        if any(phrase in lowered for phrase in _CASINO_PHRASES):
            reasons.append("crypto-casino wording")
        if any(phrase in lowered for phrase in _WITHDRAW_PHRASES) and "casino" in lowered:
            reasons.append("withdraw-bonus wording")
        casino_context = (
            "lacewin" in lowered
            or "casino" in lowered
            and ("bonus" in lowered or "promo" in lowered)
        )
        if _EPIC_RE.search(text) and casino_context:
            reasons.append("EPIC promo with casino context")
        return tuple(reasons)
