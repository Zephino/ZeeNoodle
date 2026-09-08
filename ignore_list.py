"""Persist extra ignored channel IDs. The incident channel is always ignored."""

from __future__ import annotations

import json
from pathlib import Path


class IgnoreStore:
    def __init__(self, path: Path, always_ignore: set[int]) -> None:
        self.path = path
        self.always_ignore = set(always_ignore)
        self.ids: set[int] = set()
        self.load()

    def load(self) -> None:
        self.ids = set()
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return
        for item in data.get("channel_ids", []):
            self.ids.add(int(item))

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"channel_ids": sorted(self.ids)}
        self.path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def is_ignored(self, channel_id: int) -> bool:
        return channel_id in self.always_ignore or channel_id in self.ids

    def extra_ids(self) -> list[int]:
        return sorted(self.ids)

    def add(self, channel_id: int) -> str:
        if channel_id in self.always_ignore:
            return "always"
        if channel_id in self.ids:
            return "exists"
        self.ids.add(channel_id)
        self.save()
        return "added"

    def remove(self, channel_id: int) -> str:
        if channel_id in self.always_ignore:
            return "always"
        if channel_id not in self.ids:
            return "missing"
        self.ids.discard(channel_id)
        self.save()
        return "removed"
