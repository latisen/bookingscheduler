from datetime import datetime
from typing import Iterable

WEEKDAY_NAMES = [
    "Måndag",
    "Tisdag",
    "Onsdag",
    "Torsdag",
    "Fredag",
    "Lördag",
    "Söndag",
]


def time_to_minutes(value: str) -> int:
    hours, minutes = value.split(":")
    return int(hours) * 60 + int(minutes)


def minutes_to_time(value: int) -> str:
    hours = value // 60
    minutes = value % 60
    return f"{hours:02d}:{minutes:02d}"


def overlap(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    return a_start < b_end and b_start < a_end


def now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def pairwise(iterable: Iterable):
    items = list(iterable)
    for index in range(len(items) - 1):
        yield items[index], items[index + 1]
