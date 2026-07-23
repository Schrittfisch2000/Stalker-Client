from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

MAIN_DIRECTORY = Path(os.getenv("MAIN_DIRECTORY", "/konfiguration"))


def data_file(name: str) -> Path:
    return MAIN_DIRECTORY / name


def ensure_json_file(name: str, default: Any) -> Path:
    path = data_file(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(json.dumps(default, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    return path


def ensure_standard_files() -> None:
    ensure_json_file("portal-einstellungen.json", {})
    ensure_json_file("portal-zuweisungen.json", {})
    ensure_json_file("benutzer.json", [])
    ensure_json_file("benutzer-freigaben.json", {})
    ensure_json_file("wiedergabeverlauf.json", {})
    ensure_json_file("favoriten.json", {})
    ensure_json_file("fortschritt.json", {})
