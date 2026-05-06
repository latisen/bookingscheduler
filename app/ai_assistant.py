from typing import Any


class AIScheduleAssistant:
    """Plats for framtida OpenAI-stod. Harda regler valideras alltid i backend."""

    def explain_schedule(self, schedule_payload: dict[str, Any], context: dict[str, Any]) -> str:
        sessions = schedule_payload.get("sessions", [])
        unscheduled = schedule_payload.get("unscheduled", [])
        conflicts = schedule_payload.get("conflicts", [])

        return (
            f"Schema innehaller {len(sessions)} pass, "
            f"{len(unscheduled)} ej placerade och {len(conflicts)} konflikter. "
            "AI-forklaringar kan senare byggas ut med OpenAI API men valideras alltid mot harda regler."
        )

    def propose_improvements(self, schedule_payload: dict[str, Any], context: dict[str, Any]) -> list[dict[str, Any]]:
        # Returnerar inga forslag i MVP men metoden finns for fortsatt utveckling.
        return []
