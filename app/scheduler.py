from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from .utils import overlap, time_to_minutes

TIME_STEP = 10


@dataclass
class Demand:
    demand_id: str
    name: str
    group_ids: list[str]
    club_ids: list[str]
    min_length: int
    max_length: int
    preferred_length: int
    source: str


class SchedulerEngine:
    """Deterministisk schemalaggare som alltid prioriterar harda regler."""

    def __init__(self, data: dict[str, Any]):
        self.data = data
        self.halls = data.get("halls", [])
        self.clubs = data.get("clubs", [])
        self.groups = data.get("groups", [])
        self.blocks = data.get("availability_blocks", [])
        self.combined = data.get("combined_sessions", [])
        self.rules = data.get("resurfacing_rules", [])

        self.group_by_id = {g["id"]: g for g in self.groups}
        self.club_by_id = {c["id"]: c for c in self.clubs}
        self.hall_by_id = {h["id"]: h for h in self.halls}

        self.sessions_per_group: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.reasons_per_demand: dict[str, list[str]] = defaultdict(list)

    def generate(self) -> dict[str, Any]:
        demands = self._build_demands()
        demands = sorted(demands, key=self._demand_sort_key)

        placed: list[dict[str, Any]] = []
        unscheduled: list[dict[str, Any]] = []

        for demand in demands:
            candidates = self._candidate_slots(demand, placed)
            if not candidates:
                reasons = self.reasons_per_demand.get(demand.demand_id, ["Ingen giltig lucka hittades"])
                unscheduled.append(
                    {
                        "demand_id": demand.demand_id,
                        "name": demand.name,
                        "group_ids": demand.group_ids,
                        "reasons": sorted(set(reasons)),
                    }
                )
                continue

            candidates.sort(key=lambda c: (c["score"], c["hall_id"], c["weekday"], c["start"]))
            chosen = candidates[0]
            session = {
                "id": f"sess_{demand.demand_id}_{len(placed)+1}",
                "name": demand.name,
                "source": demand.source,
                "group_ids": demand.group_ids,
                "club_id": chosen["club_id"],
                "hall_id": chosen["hall_id"],
                "weekday": chosen["weekday"],
                "start": chosen["start"],
                "end": chosen["end"],
                "manual_exception": False,
            }
            placed.append(session)
            for group_id in demand.group_ids:
                self.sessions_per_group[group_id].append(session)

        conflicts = self.evaluate_schedule(placed)
        return {
            "sessions": sorted(placed, key=lambda s: (s["weekday"], s["hall_id"], s["start"])),
            "unscheduled": unscheduled,
            "conflicts": conflicts,
        }

    def _build_demands(self) -> list[Demand]:
        demands: list[Demand] = []
        combined_demands: list[Demand] = []

        # Räkna hur många combined-pass varje grupp täcks av,
        # så att vi vet hur många individuella demands som återstår.
        combined_count_per_group: dict[str, int] = defaultdict(int)

        for combined in self.combined:
            group_ids = [gid for gid in combined.get("group_ids", []) if gid in self.group_by_id]
            if not group_ids:
                continue

            # Grupper från olika klubbar kan aldrig ha gemensamma pass.
            club_ids = {self.group_by_id[gid]["club_id"] for gid in group_ids}
            if len(club_ids) > 1:
                # Hoppa över och rapportera som ej placerat vid generering
                self.reasons_per_demand[combined["id"]] = [
                    "Kombinerade pass kan bara skapas inom samma förening"
                ]
                continue

            club_id = next(iter(club_ids))
            n = int(combined.get("sessions_per_week", 1))
            for gid in group_ids:
                combined_count_per_group[gid] += n

            for index in range(n):
                combined_demands.append(
                    Demand(
                        demand_id=f"{combined['id']}_{index+1}",
                        name=combined.get("name", "Kombinerat pass"),
                        group_ids=group_ids,
                        club_ids=[club_id],
                        min_length=int(combined.get("min_session_length", combined.get("session_length", 60))),
                        max_length=int(combined.get("max_session_length", combined.get("session_length", 60))),
                        preferred_length=int(combined.get("max_session_length", combined.get("session_length", 60))),
                        source="combined",
                    )
                )

        # Individuella demands: sessions_per_week är totalmålet inklusive combined-pass.
        # Skapa bara det antal individuella som återstår efter combined.
        for group in self.groups:
            total_target = int(group.get("sessions_per_week", 0))
            already_covered = combined_count_per_group.get(group["id"], 0)
            individual_target = max(0, total_target - already_covered)
            for index in range(individual_target):
                demands.append(
                    Demand(
                        demand_id=f"{group['id']}_{index+1}",
                        name=group["name"],
                        group_ids=[group["id"]],
                        club_ids=[group["club_id"]],
                        min_length=int(group.get("min_session_length", group.get("session_length", 60))),
                        max_length=int(group.get("max_session_length", group.get("session_length", 60))),
                        preferred_length=int(group.get("max_session_length", group.get("session_length", 60))),
                        source="group",
                    )
                )

        # Combined placeras först — de har fler hallrestriktioner och måste säkras före
        # de individuella passen delas ut.
        return combined_demands + demands

    def _demand_sort_key(self, demand: Demand) -> tuple:
        strictness = 0
        hall_options = 99
        for group_id in demand.group_ids:
            group = self.group_by_id[group_id]
            if group.get("strict_hall_id"):
                strictness += 1
            hall_options = min(hall_options, self._count_hall_options(group))
        return (-strictness, hall_options, -demand.max_length, demand.name, demand.demand_id)

    def _count_hall_options(self, group: dict[str, Any]) -> int:
        halls = [h["id"] for h in self.halls]
        return len([hid for hid in halls if self._hall_allowed(group, hid)])

    def _candidate_slots(self, demand: Demand, placed: list[dict[str, Any]]) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []

        # Alla combined-pass är alltid inom en och samma förening, så club_ids har exakt ett element.
        club_id = demand.club_ids[0]

        candidate_blocks = [
            block
            for block in self.blocks
            if block.get("club_id") == club_id
            and self._demand_fits_hall(block.get("hall_id"), demand)
        ]

        for block in sorted(candidate_blocks, key=lambda b: (b["weekday"], b["hall_id"], b["start"])):
            hall_id = block["hall_id"]
            weekday = int(block["weekday"])
            start_min = time_to_minutes(block["start"])
            end_min = time_to_minutes(block["end"])
            min_len = max(TIME_STEP, int(demand.min_length))
            max_len = int(demand.max_length)
            if min_len > max_len:
                min_len, max_len = max_len, min_len
            if end_min - start_min < min_len:
                continue
            for slot_start in range(start_min, end_min - min_len + 1, TIME_STEP):
                max_possible = min(max_len, end_min - slot_start)
                if max_possible < min_len:
                    continue

                # Langre pass provas forst i samma slot. Soft score avgor slutvalet.
                length_options = range(max_possible, min_len - 1, -TIME_STEP)
                for session_length in length_options:
                    session = {
                        "id": "candidate",
                        "name": demand.name,
                        "source": demand.source,
                        "group_ids": demand.group_ids,
                        "club_id": club_id,
                        "hall_id": hall_id,
                        "weekday": weekday,
                        "start": slot_start,
                        "end": slot_start + session_length,
                        "manual_exception": False,
                    }
                    ok, reasons = self._passes_hard_rules(session, placed)
                    if not ok:
                        self.reasons_per_demand[demand.demand_id].extend(reasons)
                        continue
                    score = self._soft_score(session, demand, start_min, end_min)
                    candidates.append({**session, "score": score})

        return candidates

    def _demand_fits_hall(self, hall_id: str, demand: Demand) -> bool:
        for group_id in demand.group_ids:
            if not self._hall_allowed(self.group_by_id[group_id], hall_id):
                return False
        return True

    def _hall_allowed(self, group: dict[str, Any], hall_id: str) -> bool:
        strict_hall = group.get("strict_hall_id")
        if strict_hall and strict_hall != hall_id:
            return False
        allowed = group.get("allowed_halls", [])
        if allowed and hall_id not in allowed:
            return False
        forbidden = group.get("forbidden_halls", [])
        if hall_id in forbidden:
            return False
        return True

    def _passes_hard_rules(self, session: dict[str, Any], placed: list[dict[str, Any]]) -> tuple[bool, list[str]]:
        reasons: list[str] = []

        if not self._session_within_blocks(session):
            reasons.append("Passet ligger utanfor tillgangliga tidsblock")
            return False, reasons

        for existing in placed:
            if existing["hall_id"] == session["hall_id"] and existing["weekday"] == session["weekday"]:
                if overlap(existing["start"], existing["end"], session["start"], session["end"]):
                    reasons.append("Hallen ar upptagen i tidsintervallet")
                    return False, reasons

        for group_id in session["group_ids"]:
            group = self.group_by_id[group_id]
            group_sessions = self.sessions_per_group[group_id]
            total_target = int(group.get("sessions_per_week", 0))
            # max_sessions_per_week är ett absolut tak men får aldrig vara lägre än målet
            # (skyddar mot att gammal sparad data blockerar när sessions_per_week höjs)
            hard_max = max(total_target, int(group.get("max_sessions_per_week", total_target)))
            if len(group_sessions) >= hard_max:
                reasons.append(f"Gruppen {group['name']} har redan max antal pass ({hard_max})")
                return False, reasons
            if len(group_sessions) >= total_target:
                reasons.append(f"Gruppen {group['name']} har natt malantalpass per vecka ({total_target})")
                return False, reasons

            if group.get("no_two_same_day"):
                if any(s["weekday"] == session["weekday"] for s in group_sessions):
                    reasons.append(f"Gruppen {group['name']} far inte ha tva pass samma dag")
                    return False, reasons

            rest_minutes = int(group.get("min_rest_hours", 0)) * 60
            for existing in group_sessions:
                if existing["weekday"] != session["weekday"]:
                    continue
                if overlap(existing["start"], existing["end"], session["start"], session["end"]):
                    reasons.append(f"Gruppen {group['name']} overlappar ett annat pass")
                    return False, reasons
                if rest_minutes > 0:
                    gap = min(abs(session["start"] - existing["end"]), abs(existing["start"] - session["end"]))
                    if gap < rest_minutes:
                        reasons.append(f"Gruppen {group['name']} bryter minsta vila")
                        return False, reasons

        resurfacing_ok, resurfacing_reasons = self._passes_resurfacing_rules(session, placed)
        if not resurfacing_ok:
            reasons.extend(resurfacing_reasons)
            return False, reasons

        return True, reasons

    def _session_within_blocks(self, session: dict[str, Any]) -> bool:
        for group_id in session.get("group_ids", []):
            group = self.group_by_id.get(group_id)
            if not group:
                return False
            club_id = group.get("club_id")
            match = False
            for block in self.blocks:
                if block.get("club_id") != club_id:
                    continue
                if block.get("hall_id") != session.get("hall_id"):
                    continue
                if int(block.get("weekday", -1)) != int(session.get("weekday", -2)):
                    continue
                if time_to_minutes(block["start"]) <= session.get("start", 0) and time_to_minutes(block["end"]) >= session.get("end", 0):
                    match = True
                    break
            if not match:
                return False
        return True

    def _passes_resurfacing_rules(self, session: dict[str, Any], placed: list[dict[str, Any]]) -> tuple[bool, list[str]]:
        reasons: list[str] = []
        weekday = int(session["weekday"])

        related = [
            s
            for s in placed
            if s["hall_id"] == session["hall_id"] and s["weekday"] == weekday
        ] + [session]
        related = sorted(related, key=lambda s: s["start"])

        for rule in self.rules:
            if not self._rule_matches_scope(rule, session):
                continue
            blocked_days = set(rule.get("blocked_weekdays", []))
            if weekday in blocked_days and rule.get("rule_type") in {"between_all_sessions", "max_in_row"}:
                reasons.append("Spolningsregel blockerar denna veckodag")
                return False, reasons

            if rule.get("rule_type") == "between_all_sessions":
                buffer_minutes = int(rule.get("buffer_minutes", 10))
                for idx in range(len(related) - 1):
                    a = related[idx]
                    b = related[idx + 1]
                    if self._rule_targets_session(rule, a) and self._rule_targets_session(rule, b):
                        gap = b["start"] - a["end"]
                        if gap < buffer_minutes:
                            reasons.append("Spolningstid mellan pass uppfylls inte")
                            return False, reasons

            if rule.get("rule_type") == "max_in_row":
                max_in_row = int(rule.get("max_in_row", 2))
                buffer_minutes = int(rule.get("buffer_minutes", 10))
                run = 0
                last_target_end = None
                for item in related:
                    if not self._rule_targets_session(rule, item):
                        run = 0
                        last_target_end = None
                        continue
                    if last_target_end is None:
                        run = 1
                        last_target_end = item["end"]
                        continue
                    gap = item["start"] - last_target_end
                    if gap >= buffer_minutes:
                        run = 1
                    else:
                        run += 1
                    last_target_end = item["end"]
                    if run > max_in_row:
                        reasons.append("For manga pass i rad utan spolning")
                        return False, reasons

        return True, reasons

    def _rule_matches_scope(self, rule: dict[str, Any], session: dict[str, Any]) -> bool:
        scope = rule.get("scope", "hall")
        hall_id = rule.get("hall_id")
        club_id = rule.get("club_id")
        if scope == "hall":
            return (not hall_id) or hall_id == session["hall_id"]
        if scope == "club":
            return (not club_id) or club_id == session["club_id"]
        return True

    def _rule_targets_session(self, rule: dict[str, Any], session: dict[str, Any]) -> bool:
        discipline = rule.get("discipline")
        if not discipline:
            return True
        for group_id in session.get("group_ids", []):
            group = self.group_by_id.get(group_id)
            if group and group.get("discipline") == discipline:
                return True
        return False

    def _soft_score(self, session: dict[str, Any], demand: Demand | None = None, block_start: int | None = None, block_end: int | None = None) -> int:
        score = 0
        start = session["start"]
        weekday = session["weekday"]
        length = session["end"] - session["start"]

        # Globalt mal: fa plats med sa manga pass som mojligt.
        # Kortare pass far en liten bonus inom tillatet intervall.
        score += length // 10

        # Samtidigt vill vi utnyttja blocken effektivt.
        if block_start is not None and block_end is not None:
            left_gap = max(0, start - block_start)
            right_gap = max(0, block_end - session["end"])
            smallest_gap = min(left_gap, right_gap)
            score += smallest_gap // 10

        if demand is not None:
            preferred_length = int(demand.preferred_length)
            score += abs(preferred_length - length) // 10

        for group_id in session["group_ids"]:
            group = self.group_by_id[group_id]
            prior_sessions = self.sessions_per_group[group_id]
            prior_days = [s["weekday"] for s in prior_sessions]

            # Starkt straff om gruppen redan har pass denna dag
            if weekday in prior_days:
                score += 30

            # Premiär dagar med minst befintliga pass i hallen (sprid ut)
            hall_day_count = sum(
                1 for s in prior_sessions if s["weekday"] == weekday and s["hall_id"] == session["hall_id"]
            )
            score += hall_day_count * 10

            # Önskade dagar
            preferred_days = group.get("preferred_days", [])
            if preferred_days and weekday not in preferred_days:
                score += 8

            # Önskad tidspann
            pref_range = group.get("preferred_time_range")
            priority = max(1, int(group.get("time_preference_priority", 1)))
            if pref_range and len(pref_range) == 2:
                pref_start = time_to_minutes(pref_range[0])
                pref_end = time_to_minutes(pref_range[1])
                if start < pref_start:
                    score += ((pref_start - start) // 10) * priority
                elif start > pref_end:
                    score += ((start - pref_end) // 10) * priority

            # Undvik dagar i rad
            if group.get("avoid_consecutive_days") and any(abs(weekday - d) == 1 for d in prior_days):
                score += 12

            # Åldersanpassning
            if group.get("age_level") == "youth" and start >= 20 * 60:
                score += 8
            if group.get("age_level") in {"senior", "adult"} and start < 17 * 60:
                score += 4

            # Hallspridning: undvik för hög koncentration i en hall
            hall_usage = sum(1 for s in prior_sessions if s["hall_id"] == session["hall_id"])
            score += hall_usage * 3

        return score

    def evaluate_schedule(self, sessions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        conflicts: list[dict[str, Any]] = []

        by_hall_day: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
        by_group: dict[str, list[dict[str, Any]]] = defaultdict(list)

        for session in sessions:
            by_hall_day[(session["hall_id"], session["weekday"])].append(session)
            for gid in session["group_ids"]:
                by_group[gid].append(session)

        for (hall_id, weekday), items in by_hall_day.items():
            ordered = sorted(items, key=lambda s: s["start"])
            for i in range(len(ordered) - 1):
                if ordered[i]["end"] > ordered[i + 1]["start"]:
                    conflicts.append(
                        {
                            "type": "hall_overlap",
                            "hall_id": hall_id,
                            "weekday": weekday,
                            "sessions": [ordered[i]["id"], ordered[i + 1]["id"]],
                            "message": "Overlapp i samma hall",
                        }
                    )

        for group_id, items in by_group.items():
            ordered = sorted(items, key=lambda s: (s["weekday"], s["start"]))
            group = self.group_by_id.get(group_id, {})
            if group.get("no_two_same_day"):
                days: dict[int, int] = defaultdict(int)
                for item in ordered:
                    days[item["weekday"]] += 1
                for day, count in days.items():
                    if count > 1:
                        conflicts.append(
                            {
                                "type": "same_day",
                                "group_id": group_id,
                                "weekday": day,
                                "message": "Gruppen har flera pass samma dag",
                            }
                        )
            for i in range(len(ordered) - 1):
                a = ordered[i]
                b = ordered[i + 1]
                if a["weekday"] == b["weekday"] and overlap(a["start"], a["end"], b["start"], b["end"]):
                    conflicts.append(
                        {
                            "type": "group_overlap",
                            "group_id": group_id,
                            "sessions": [a["id"], b["id"]],
                            "message": "Gruppen overlappar sig sjalv",
                        }
                    )

        return conflicts

    def validate_hard_constraints(self, sessions: list[dict[str, Any]]) -> list[str]:
        errors: list[str] = []
        ordered = sorted(sessions, key=lambda s: (s["weekday"], s["hall_id"], s["start"]))
        placed: list[dict[str, Any]] = []
        self.sessions_per_group = defaultdict(list)

        for session in ordered:
            for group_id in session.get("group_ids", []):
                if group_id not in self.group_by_id:
                    errors.append(f"Okand grupp i pass {session.get('id')}")
            ok, reasons = self._passes_hard_rules(session, placed)
            if not ok:
                label = session.get("name") or session.get("id")
                for reason in reasons:
                    errors.append(f"{label}: {reason}")
            placed.append(session)
            for group_id in session.get("group_ids", []):
                self.sessions_per_group[group_id].append(session)

        return sorted(set(errors))


def compute_idle_time_per_hall_day(sessions: list[dict[str, Any]], halls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for hall in halls:
        for weekday in range(7):
            items = [
                session
                for session in sessions
                if session["hall_id"] == hall["id"] and int(session["weekday"]) == weekday
            ]
            if not items:
                continue
            ordered = sorted(items, key=lambda s: s["start"])
            idle = 0
            for i in range(len(ordered) - 1):
                gap = ordered[i + 1]["start"] - ordered[i]["end"]
                if gap > 0:
                    idle += gap
            result.append(
                {
                    "hall_id": hall["id"],
                    "weekday": weekday,
                    "idle_minutes": idle,
                }
            )
    return result
