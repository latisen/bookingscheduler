from copy import deepcopy
from typing import Any

from .scheduler import SchedulerEngine


def validate_manual_move(
    schedule_payload: dict[str, Any],
    all_data: dict[str, Any],
    session_id: str,
    target_weekday: int,
    target_hall_id: str,
    target_start: int,
    swap_with_id: str | None = None,
    allow_exception: bool = False,
) -> tuple[bool, str, dict[str, Any]]:
    sessions = deepcopy(schedule_payload.get("sessions", []))
    by_id = {item["id"]: item for item in sessions}

    if session_id not in by_id:
        return False, "Passet finns inte", schedule_payload

    moving = by_id[session_id]
    duration = moving["end"] - moving["start"]

    if swap_with_id:
        if swap_with_id not in by_id:
            return False, "Pass att byta med finns inte", schedule_payload
        other = by_id[swap_with_id]
        other_duration = other["end"] - other["start"]

        other_target = {
            "weekday": moving["weekday"],
            "hall_id": moving["hall_id"],
            "start": moving["start"],
            "end": moving["start"] + other_duration,
        }
        moving_target = {
            "weekday": other["weekday"],
            "hall_id": other["hall_id"],
            "start": other["start"],
            "end": other["start"] + duration,
        }

        moving.update(moving_target)
        other.update(other_target)
    else:
        moving["weekday"] = int(target_weekday)
        moving["hall_id"] = target_hall_id
        moving["start"] = int(target_start)
        moving["end"] = int(target_start) + duration

    engine = SchedulerEngine(all_data)
    hard_errors = engine.validate_hard_constraints(sessions)
    conflicts = engine.evaluate_schedule(sessions)

    if hard_errors and not allow_exception:
        conflict_payload = [
            {"type": "hard_rule", "message": msg}
            for msg in hard_errors
        ]
        return (
            False,
            "Flytten bryter mot regler",
            {**schedule_payload, "sessions": sessions, "conflicts": conflict_payload + conflicts},
        )

    if hard_errors and allow_exception:
        by_id[session_id]["manual_exception"] = True

    return True, "Flytt sparad", {**schedule_payload, "sessions": sessions, "conflicts": conflicts}
