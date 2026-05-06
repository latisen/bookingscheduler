from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any, Callable

from flask import Blueprint, Response, jsonify, render_template, request, send_file
from PIL import Image, ImageDraw
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from .ai_assistant import AIScheduleAssistant
from .models import (
    normalize_block,
    normalize_club,
    normalize_combined,
    normalize_group,
    normalize_hall,
    normalize_resurfacing_rule,
)
from .scheduler import SchedulerEngine, compute_idle_time_per_hall_day
from .storage import BASE_DIR, ensure_data_files, read_json, write_json
from .utils import minutes_to_time, now_iso
from .validators import validate_manual_move

web = Blueprint("web", __name__)

RESOURCE_FILES = {
    "halls": "halls.json",
    "clubs": "clubs.json",
    "groups": "groups.json",
    "availability_blocks": "availability_blocks.json",
    "combined_sessions": "combined_sessions.json",
    "resurfacing_rules": "resurfacing_rules.json",
}

NORMALIZERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "halls": normalize_hall,
    "clubs": normalize_club,
    "groups": normalize_group,
    "availability_blocks": normalize_block,
    "combined_sessions": normalize_combined,
    "resurfacing_rules": normalize_resurfacing_rule,
}


def load_all_data() -> dict[str, Any]:
    ensure_data_files()
    return {
        "halls": _load_resource_entries("halls"),
        "clubs": _load_resource_entries("clubs"),
        "groups": _load_resource_entries("groups"),
        "availability_blocks": _load_resource_entries("availability_blocks"),
        "combined_sessions": _load_resource_entries("combined_sessions"),
        "resurfacing_rules": _load_resource_entries("resurfacing_rules"),
    }


def _load_resource_entries(resource: str) -> list[dict[str, Any]]:
    file_name = RESOURCE_FILES[resource]
    entries = read_json(file_name, [])
    normalizer = NORMALIZERS[resource]
    changed = False
    normalized_entries: list[dict[str, Any]] = []

    for entry in entries:
        normalized = normalizer(entry)
        normalized_entries.append(normalized)
        if normalized != entry:
            changed = True

    if changed:
        write_json(file_name, normalized_entries)

    return normalized_entries


@web.route("/")
def index() -> str:
    ensure_data_files()
    return render_template("index.html")


@web.route("/api/bootstrap", methods=["GET"])
def bootstrap() -> Response:
    data = load_all_data()
    schedule_payload = read_json("schedule.json", {})
    idle = compute_idle_time_per_hall_day(schedule_payload.get("sessions", []), data["halls"])
    ai = AIScheduleAssistant()
    explanation = ai.explain_schedule(schedule_payload, data)
    return jsonify({"data": data, "schedule": schedule_payload, "idle_time": idle, "ai_summary": explanation})


@web.route("/api/<resource>", methods=["POST"])
def create_resource(resource: str) -> Response:
    if resource not in RESOURCE_FILES:
        return jsonify({"error": "Okand resurs"}), 404
    payload = request.get_json(silent=True) or {}
    normalizer = NORMALIZERS[resource]
    item = normalizer(payload)
    entries = _load_resource_entries(resource)
    entries.append(item)
    write_json(RESOURCE_FILES[resource], entries)
    return jsonify(item), 201


@web.route("/api/<resource>/<item_id>", methods=["PUT"])
def update_resource(resource: str, item_id: str) -> Response:
    if resource not in RESOURCE_FILES:
        return jsonify({"error": "Okand resurs"}), 404
    payload = request.get_json(silent=True) or {}
    payload["id"] = item_id
    normalizer = NORMALIZERS[resource]
    updated = normalizer(payload)

    entries = _load_resource_entries(resource)
    found = False
    for idx, entry in enumerate(entries):
        if entry.get("id") == item_id:
            entries[idx] = updated
            found = True
            break

    if not found:
        return jsonify({"error": "Objektet hittades inte"}), 404

    write_json(RESOURCE_FILES[resource], entries)
    return jsonify(updated)


@web.route("/api/<resource>/<item_id>", methods=["DELETE"])
def delete_resource(resource: str, item_id: str) -> Response:
    if resource not in RESOURCE_FILES:
        return jsonify({"error": "Okand resurs"}), 404

    entries = _load_resource_entries(resource)
    next_entries = [entry for entry in entries if entry.get("id") != item_id]
    if len(next_entries) == len(entries):
        return jsonify({"error": "Objektet hittades inte"}), 404

    write_json(RESOURCE_FILES[resource], next_entries)
    return jsonify({"ok": True})


@web.route("/api/schedule", methods=["GET"])
def get_schedule() -> Response:
    ensure_data_files()
    payload = read_json("schedule.json", {})
    return jsonify(payload)


@web.route("/api/schedule/save", methods=["POST"])
def save_schedule() -> Response:
    payload = request.get_json(silent=True) or {}
    payload["generated_at"] = now_iso()
    write_json("schedule.json", payload)
    return jsonify({"ok": True})


@web.route("/api/schedule/load", methods=["POST"])
def load_schedule() -> Response:
    payload = read_json("schedule.json", {})
    return jsonify(payload)


@web.route("/api/schedule/generate", methods=["POST"])
def generate_schedule() -> Response:
    data = load_all_data()
    engine = SchedulerEngine(data)
    payload = engine.generate()
    payload["generated_at"] = now_iso()
    payload["idle_time"] = compute_idle_time_per_hall_day(payload.get("sessions", []), data["halls"])
    write_json("schedule.json", payload)
    return jsonify(payload)


@web.route("/api/schedule/move", methods=["POST"])
def move_session() -> Response:
    payload = request.get_json(silent=True) or {}
    session_id = payload.get("session_id")
    if not session_id:
        return jsonify({"ok": False, "message": "session_id saknas"}), 400

    schedule_payload = read_json("schedule.json", {})
    all_data = load_all_data()
    ok, message, updated_schedule = validate_manual_move(
        schedule_payload=schedule_payload,
        all_data=all_data,
        session_id=session_id,
        target_weekday=int(payload.get("weekday", 0)),
        target_hall_id=payload.get("hall_id", ""),
        target_start=int(payload.get("start", 0)),
        swap_with_id=payload.get("swap_with_id"),
        allow_exception=bool(payload.get("allow_exception", False)),
    )

    if ok:
        updated_schedule["generated_at"] = now_iso()
        write_json("schedule.json", updated_schedule)
        if payload.get("allow_exception"):
            exceptions = read_json("manual_exceptions.json", [])
            exceptions.append(
                {
                    "session_id": session_id,
                    "timestamp": now_iso(),
                    "reason": payload.get("reason", "Manuellt undantag"),
                }
            )
            write_json("manual_exceptions.json", exceptions)

    return jsonify({"ok": ok, "message": message, "schedule": updated_schedule})


@web.route("/api/export/<fmt>", methods=["GET"])
def export_schedule(fmt: str) -> Response:
    schedule_payload = read_json("schedule.json", {})
    sessions = schedule_payload.get("sessions", [])
    data = load_all_data()

    hall_map = {h["id"]: h["name"] for h in data["halls"]}
    club_map = {c["id"]: c["name"] for c in data["clubs"]}
    group_map = {g["id"]: g["name"] for g in data["groups"]}

    if fmt == "json":
        return Response(
            json.dumps(schedule_payload, ensure_ascii=False, indent=2),
            mimetype="application/json",
            headers={"Content-Disposition": "attachment; filename=schema.json"},
        )

    if fmt == "csv":
        stream = io.StringIO()
        writer = csv.writer(stream)
        writer.writerow(["id", "weekday", "hall", "start", "end", "club", "groups", "name"])
        for item in sessions:
            groups = ", ".join(group_map.get(gid, gid) for gid in item.get("group_ids", []))
            writer.writerow(
                [
                    item.get("id"),
                    item.get("weekday"),
                    hall_map.get(item.get("hall_id"), item.get("hall_id")),
                    minutes_to_time(item.get("start", 0)),
                    minutes_to_time(item.get("end", 0)),
                    club_map.get(item.get("club_id"), item.get("club_id")),
                    groups,
                    item.get("name", ""),
                ]
            )
        output = io.BytesIO(stream.getvalue().encode("utf-8"))
        return send_file(output, mimetype="text/csv", as_attachment=True, download_name="schema.csv")

    if fmt == "pdf":
        output = io.BytesIO()
        pdf = canvas.Canvas(output, pagesize=A4)
        width, height = A4
        y = height - 40
        pdf.setFont("Helvetica-Bold", 14)
        pdf.drawString(40, y, "Schemaexport")
        y -= 24
        pdf.setFont("Helvetica", 10)
        for item in sessions:
            groups = ", ".join(group_map.get(gid, gid) for gid in item.get("group_ids", []))
            row = (
                f"Dag {item.get('weekday')} | {minutes_to_time(item.get('start', 0))}-{minutes_to_time(item.get('end', 0))} | "
                f"{hall_map.get(item.get('hall_id'), item.get('hall_id'))} | {item.get('name')} | {groups}"
            )
            pdf.drawString(40, y, row[:120])
            y -= 14
            if y < 40:
                pdf.showPage()
                y = height - 40
                pdf.setFont("Helvetica", 10)
        pdf.save()
        output.seek(0)
        return send_file(output, mimetype="application/pdf", as_attachment=True, download_name="schema.pdf")

    if fmt == "png":
        image = Image.new("RGB", (1400, 900), "white")
        draw = ImageDraw.Draw(image)
        draw.text((20, 20), "Schemaexport", fill="black")

        y = 60
        for item in sessions:
            groups = ", ".join(group_map.get(gid, gid) for gid in item.get("group_ids", []))
            line = (
                f"Dag {item.get('weekday')} {minutes_to_time(item.get('start', 0))}-{minutes_to_time(item.get('end', 0))} "
                f"{hall_map.get(item.get('hall_id'), item.get('hall_id'))} {item.get('name')} ({groups})"
            )
            draw.text((20, y), line[:140], fill="black")
            y += 18
            if y > 860:
                break

        output = io.BytesIO()
        image.save(output, format="PNG")
        output.seek(0)
        return send_file(output, mimetype="image/png", as_attachment=True, download_name="schema.png")

    return jsonify({"error": "Okant exportformat"}), 400


@web.route("/api/meta/reset", methods=["POST"])
def reset_seed() -> Response:
    data_path = Path(BASE_DIR) / "data"
    seed_path = Path(BASE_DIR) / "data" / "seed"
    if not seed_path.exists():
        return jsonify({"error": "Seed-data saknas"}), 404

    for file in seed_path.glob("*.json"):
        target = data_path / file.name.replace("seed_", "")
        with file.open("r", encoding="utf-8") as src:
            payload = json.load(src)
        write_json(target.name, payload)

    return jsonify({"ok": True})
