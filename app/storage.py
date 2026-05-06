import json
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"


def ensure_data_files() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    defaults = {
        "halls.json": [],
        "clubs.json": [],
        "groups.json": [],
        "availability_blocks.json": [],
        "combined_sessions.json": [],
        "resurfacing_rules.json": [],
        "schedule.json": {
            "sessions": [],
            "unscheduled": [],
            "conflicts": [],
            "generated_at": None,
        },
        "manual_exceptions.json": [],
    }
    for filename, default in defaults.items():
        target = DATA_DIR / filename
        if not target.exists():
            write_json(filename, default)


def _path(name: str) -> Path:
    return DATA_DIR / name


def read_json(name: str, fallback: Any = None) -> Any:
    file_path = _path(name)
    if not file_path.exists():
        return fallback
    with file_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(name: str, payload: Any) -> None:
    file_path = _path(name)
    temp_path = file_path.with_suffix(file_path.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    temp_path.replace(file_path)
