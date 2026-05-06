import uuid
from copy import deepcopy
from typing import Any


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def normalize_hall(payload: dict[str, Any]) -> dict[str, Any]:
    data = deepcopy(payload)
    data.setdefault("id", new_id("hall"))
    data["name"] = data.get("name", "").strip()
    return data


def normalize_club(payload: dict[str, Any]) -> dict[str, Any]:
    data = deepcopy(payload)
    data.setdefault("id", new_id("club"))
    data["name"] = data.get("name", "").strip()
    data["color"] = data.get("color", "#b4a7d6")
    return data


def normalize_group(payload: dict[str, Any]) -> dict[str, Any]:
    data = deepcopy(payload)
    data.setdefault("id", new_id("group"))
    data["name"] = data.get("name", "").strip()
    data["club_id"] = data.get("club_id", "")
    data["sessions_per_week"] = int(data.get("sessions_per_week", 1))
    data["session_length"] = int(data.get("session_length", 60))
    data["allowed_halls"] = data.get("allowed_halls", [])
    data["forbidden_halls"] = data.get("forbidden_halls", [])
    data["strict_hall_id"] = data.get("strict_hall_id")
    data["preferred_days"] = data.get("preferred_days", [])
    data["preferred_time_range"] = data.get("preferred_time_range")
    data["time_preference_priority"] = int(data.get("time_preference_priority", 1))
    data["no_two_same_day"] = bool(data.get("no_two_same_day", False))
    data["avoid_consecutive_days"] = bool(data.get("avoid_consecutive_days", False))
    data["max_sessions_per_week"] = int(data.get("max_sessions_per_week", data["sessions_per_week"]))
    data["min_rest_hours"] = int(data.get("min_rest_hours", 0))
    data["discipline"] = data.get("discipline", "hockey")
    data["age_level"] = data.get("age_level", "youth")
    return data


def normalize_block(payload: dict[str, Any]) -> dict[str, Any]:
    data = deepcopy(payload)
    data.setdefault("id", new_id("block"))
    data["club_id"] = data.get("club_id", "")
    data["hall_id"] = data.get("hall_id", "")
    data["weekday"] = int(data.get("weekday", 0))
    data["start"] = data.get("start", "17:00")
    data["end"] = data.get("end", "18:00")
    return data


def normalize_combined(payload: dict[str, Any]) -> dict[str, Any]:
    data = deepcopy(payload)
    data.setdefault("id", new_id("combined"))
    data["name"] = data.get("name", "Kombinerat pass")
    data["group_ids"] = data.get("group_ids", [])
    data["sessions_per_week"] = int(data.get("sessions_per_week", 1))
    data["session_length"] = int(data.get("session_length", 60))
    return data


def normalize_resurfacing_rule(payload: dict[str, Any]) -> dict[str, Any]:
    data = deepcopy(payload)
    data.setdefault("id", new_id("rule"))
    data["name"] = data.get("name", "Spolningsregel")
    data["scope"] = data.get("scope", "hall")
    data["hall_id"] = data.get("hall_id")
    data["club_id"] = data.get("club_id")
    data["rule_type"] = data.get("rule_type", "between_all_sessions")
    data["buffer_minutes"] = int(data.get("buffer_minutes", 10))
    data["max_in_row"] = int(data.get("max_in_row", 2))
    data["discipline"] = data.get("discipline", "figure")
    data["blocked_weekdays"] = data.get("blocked_weekdays", [])
    return data
