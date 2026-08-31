"""Application-owned synthetic Commstar workflow policy.

This is not a reconstruction of a historical Commstar server.  It supplies a
stable adapter contract around the ROM-confirmed Load/Run payload path.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .program import validate


@dataclass(frozen=True)
class SyntheticWorkflow:
    source: str
    scan_records: tuple[dict[str, Any], ...]
    image: str | None
    run_after_load: bool
    feedback: str
    safe_to_remove: bool

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "SyntheticWorkflow":
        source = value.get("source", "plinth")
        if source not in ("plinth", "v24"):
            raise ValueError("source must be 'plinth' or 'v24'")
        records = value.get("scan_records", [])
        if not isinstance(records, list) or not all(isinstance(item, dict) for item in records):
            raise ValueError("scan_records must be a list of objects")
        image = value.get("image")
        if image is not None and not isinstance(image, str):
            raise ValueError("image must be a path string")
        feedback = value.get("feedback", "safe_to_remove")
        if not isinstance(feedback, str) or not feedback:
            raise ValueError("feedback must be a non-empty string")
        return cls(
            source=source,
            scan_records=tuple(records),
            image=image,
            run_after_load=bool(value.get("run_after_load", False)),
            feedback=feedback,
            safe_to_remove=bool(value.get("safe_to_remove", True)),
        )

    @classmethod
    def from_file(cls, path: str | Path) -> "SyntheticWorkflow":
        with Path(path).open("r", encoding="utf-8") as stream:
            value = json.load(stream)
        if not isinstance(value, dict):
            raise ValueError("workflow JSON must be an object")
        return cls.from_dict(value)

    def events(self) -> tuple[tuple[str, Any], ...]:
        events: list[tuple[str, Any]] = [("session", self.source)]
        events.extend(("upload_scan", record) for record in self.scan_records)
        if self.image is not None:
            events.append(("download_image", self.image))
            if self.run_after_load:
                events.append(("run_image", self.image))
        events.append(("feedback", self.feedback))
        if self.safe_to_remove:
            events.append(("safe_to_remove", None))
        return tuple(events)

    def read_image(self, base: str | Path = ".") -> bytes:
        if self.image is None:
            raise ValueError("workflow has no image")
        data = (Path(base) / self.image).read_bytes()
        result = validate(data)
        if not result.valid:
            raise ValueError("workflow image is not accepted by the ROM loader")
        return data
