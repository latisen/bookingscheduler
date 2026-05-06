const WEEKDAYS = ["Måndag", "Tisdag", "Onsdag", "Torsdag", "Fredag", "Lördag", "Söndag"];
const DAY_START = 360;
const DAY_END = 1380;
const PIXELS_PER_MIN = 0.8;

const state = {
  data: {
    halls: [],
    clubs: [],
    groups: [],
    availability_blocks: [],
    combined_sessions: [],
    resurfacing_rules: [],
  },
  schedule: {
    sessions: [],
    unscheduled: [],
    conflicts: [],
    idle_time: [],
  },
  aiSummary: "",
};

const $ = (id) => document.getElementById(id);

function selectedValues(selectId) {
  const select = $(selectId);
  return [...select.options].filter((o) => o.selected).map((o) => o.value);
}

function minutesToTime(minutes) {
  const h = String(Math.floor(minutes / 60)).padStart(2, "0");
  const m = String(minutes % 60).padStart(2, "0");
  return `${h}:${m}`;
}

function timeToMinutes(value) {
  const [h, m] = value.split(":").map(Number);
  return h * 60 + m;
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.error || payload.message || "API-fel");
  }
  const ct = response.headers.get("content-type") || "";
  if (ct.includes("application/json")) {
    return response.json();
  }
  return response;
}

function optionHTML(items, emptyLabel = "Välj") {
  let html = emptyLabel ? `<option value="">${emptyLabel}</option>` : "";
  for (const item of items) {
    html += `<option value="${item.id}">${item.name}</option>`;
  }
  return html;
}

function weekdayOptions() {
  return WEEKDAYS.map((name, index) => `<option value="${index}">${name}</option>`).join("");
}

function setStatus(text, isError = false) {
  const box = $("statusBox");
  box.textContent = text;
  box.classList.toggle("error", isError);
}

function bindList(listId, items, labelFn, onEdit, onDelete) {
  const list = $(listId);
  list.innerHTML = "";
  for (const item of items) {
    const li = document.createElement("li");
    const left = document.createElement("span");
    left.textContent = labelFn(item);
    const actions = document.createElement("div");
    const editBtn = document.createElement("button");
    editBtn.type = "button";
    editBtn.textContent = "Redigera";
    editBtn.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      onEdit(item);
    });
    const delBtn = document.createElement("button");
    delBtn.type = "button";
    delBtn.textContent = "Ta bort";
    delBtn.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      onDelete(item.id);
    });
    actions.appendChild(editBtn);
    actions.appendChild(delBtn);
    li.appendChild(left);
    li.appendChild(actions);
    list.appendChild(li);
  }
}

function fillSelects() {
  const clubs = state.data.clubs;
  const halls = state.data.halls;
  const groups = state.data.groups;

  $("blockClub").innerHTML = optionHTML(clubs, "Välj förening");
  $("blockHall").innerHTML = optionHTML(halls, "Välj hall");
  $("blockWeekday").innerHTML = weekdayOptions();

  $("groupClub").innerHTML = optionHTML(clubs, "Välj förening");
  $("groupAllowedHalls").innerHTML = optionHTML(halls, "");
  $("groupForbiddenHalls").innerHTML = optionHTML(halls, "");
  $("groupStrictHall").innerHTML = `<option value="">Ingen</option>${optionHTML(halls, "")}`;
  $("groupPreferredDays").innerHTML = weekdayOptions();

  $("combinedGroups").innerHTML = optionHTML(groups, "");

  $("ruleHall").innerHTML = `<option value="">Alla</option>${optionHTML(halls, "")}`;
  $("ruleClub").innerHTML = `<option value="">Alla</option>${optionHTML(clubs, "")}`;
  $("ruleBlockedDays").innerHTML = weekdayOptions();
}

function resetForms() {
  ["hallForm", "clubForm", "blockForm", "groupForm", "combinedForm", "ruleForm"].forEach((id) => $(id).reset());
  ["hallId", "clubId", "blockId", "groupId", "combinedId", "ruleId"].forEach((id) => ($(id).value = ""));
}

function renderEntities() {
  bindList(
    "hallList",
    state.data.halls,
    (h) => h.name,
    (h) => {
      $("hallId").value = h.id;
      $("hallName").value = h.name;
    },
    (id) => removeResource("halls", id)
  );

  bindList(
    "clubList",
    state.data.clubs,
    (c) => c.name,
    (c) => {
      $("clubId").value = c.id;
      $("clubName").value = c.name;
      $("clubColor").value = c.color || "#bda8d8";
    },
    (id) => removeResource("clubs", id)
  );

  bindList(
    "blockList",
    state.data.availability_blocks,
    (b) => {
      const club = state.data.clubs.find((c) => c.id === b.club_id)?.name || b.club_id;
      const hall = state.data.halls.find((h) => h.id === b.hall_id)?.name || b.hall_id;
      return `${WEEKDAYS[b.weekday]} ${b.start}-${b.end} | ${hall} | ${club}`;
    },
    (b) => {
      $("blockId").value = b.id;
      $("blockClub").value = b.club_id;
      $("blockHall").value = b.hall_id;
      $("blockWeekday").value = b.weekday;
      $("blockStart").value = b.start;
      $("blockEnd").value = b.end;
    },
    (id) => removeResource("availability_blocks", id)
  );

  bindList(
    "groupList",
    state.data.groups,
    (g) => {
      const minLen = g.min_session_length ?? g.session_length ?? 60;
      const maxLen = g.max_session_length ?? g.session_length ?? 60;
      return `${g.name} (${g.sessions_per_week} pass/vecka, ${minLen}-${maxLen} min)`;
    },
    (g) => {
      $("groupId").value = g.id;
      $("groupName").value = g.name;
      $("groupClub").value = g.club_id;
      $("groupSessionsPerWeek").value = g.sessions_per_week;
      $("groupMinSessionLength").value = g.min_session_length ?? g.session_length ?? 60;
      $("groupMaxSessionLength").value = g.max_session_length ?? g.session_length ?? 60;
      $("groupTimePriority").value = g.time_preference_priority;
      $("groupMaxPerWeek").value = g.max_sessions_per_week;
      $("groupMinRest").value = g.min_rest_hours;
      $("groupDiscipline").value = g.discipline;
      $("groupAgeLevel").value = g.age_level;
      $("groupNoTwoSameDay").checked = !!g.no_two_same_day;
      $("groupAvoidConsecutive").checked = !!g.avoid_consecutive_days;
      $("groupPrefStart").value = g.preferred_time_range?.[0] || "";
      $("groupPrefEnd").value = g.preferred_time_range?.[1] || "";

      [...$("groupAllowedHalls").options].forEach((opt) => {
        opt.selected = (g.allowed_halls || []).includes(opt.value);
      });
      [...$("groupForbiddenHalls").options].forEach((opt) => {
        opt.selected = (g.forbidden_halls || []).includes(opt.value);
      });
      [...$("groupPreferredDays").options].forEach((opt) => {
        opt.selected = (g.preferred_days || []).includes(Number(opt.value));
      });
      $("groupStrictHall").value = g.strict_hall_id || "";
    },
    (id) => removeResource("groups", id)
  );

  bindList(
    "combinedList",
    state.data.combined_sessions,
    (c) => {
      const minLen = c.min_session_length ?? c.session_length ?? 60;
      const maxLen = c.max_session_length ?? c.session_length ?? 60;
      return `${c.name} (${c.sessions_per_week} pass, ${minLen}-${maxLen} min)`;
    },
    (c) => {
      $("combinedId").value = c.id;
      $("combinedName").value = c.name;
      $("combinedSessionsPerWeek").value = c.sessions_per_week;
      $("combinedMinSessionLength").value = c.min_session_length ?? c.session_length ?? 60;
      $("combinedMaxSessionLength").value = c.max_session_length ?? c.session_length ?? 60;
      [...$("combinedGroups").options].forEach((opt) => {
        opt.selected = (c.group_ids || []).includes(opt.value);
      });
    },
    (id) => removeResource("combined_sessions", id)
  );

  bindList(
    "ruleList",
    state.data.resurfacing_rules,
    (r) => `${r.name} (${r.rule_type})`,
    (r) => {
      $("ruleId").value = r.id;
      $("ruleName").value = r.name;
      $("ruleScope").value = r.scope;
      $("ruleHall").value = r.hall_id || "";
      $("ruleClub").value = r.club_id || "";
      $("ruleType").value = r.rule_type;
      $("ruleBuffer").value = r.buffer_minutes;
      $("ruleMaxInRow").value = r.max_in_row;
      $("ruleDiscipline").value = r.discipline;
      [...$("ruleBlockedDays").options].forEach((opt) => {
        opt.selected = (r.blocked_weekdays || []).includes(Number(opt.value));
      });
    },
    (id) => removeResource("resurfacing_rules", id)
  );
}

function renderMetaPanels() {
  const unscheduledList = $("unscheduledList");
  unscheduledList.innerHTML = "";
  for (const item of state.schedule.unscheduled || []) {
    const li = document.createElement("li");
    li.textContent = `${item.name}: ${(item.reasons || []).join("; ")}`;
    unscheduledList.appendChild(li);
  }

  const conflictList = $("conflictList");
  conflictList.innerHTML = "";
  for (const c of state.schedule.conflicts || []) {
    const li = document.createElement("li");
    li.textContent = c.message || c.type;
    conflictList.appendChild(li);
  }

  const idleList = $("idleList");
  idleList.innerHTML = "";
  for (const row of state.schedule.idle_time || []) {
    const hall = state.data.halls.find((h) => h.id === row.hall_id)?.name || row.hall_id;
    const li = document.createElement("li");
    li.textContent = `${WEEKDAYS[row.weekday]} | ${hall}: ${row.idle_minutes}`;
    idleList.appendChild(li);
  }
}

function findClubColor(clubId) {
  return state.data.clubs.find((c) => c.id === clubId)?.color || "#bdbdbd";
}

function renderBoard() {
  const board = $("weeklyBoard");
  board.innerHTML = "";

  const row = document.createElement("div");
  row.className = "day-row";

  for (let day = 0; day < 7; day++) {
    const col = document.createElement("div");
    col.className = "day-col";

    const head = document.createElement("div");
    head.className = "day-header";
    head.textContent = WEEKDAYS[day];
    col.appendChild(head);

    for (const hall of state.data.halls) {
      const hallWrap = document.createElement("div");
      hallWrap.className = "hall-lane";

      const hallHead = document.createElement("div");
      hallHead.className = "hall-header";
      hallHead.textContent = hall.name;
      hallWrap.appendChild(hallHead);

      const timeline = document.createElement("div");
      timeline.className = "timeline";
      timeline.dataset.day = String(day);
      timeline.dataset.hall = hall.id;

      timeline.addEventListener("dragover", (ev) => {
        ev.preventDefault();
        timeline.classList.add("drop-target");
      });
      timeline.addEventListener("dragleave", () => timeline.classList.remove("drop-target"));
      timeline.addEventListener("drop", async (ev) => {
        ev.preventDefault();
        timeline.classList.remove("drop-target");
        const draggedId = ev.dataTransfer.getData("text/session-id");
        const swapId = ev.dataTransfer.getData("text/swap-id") || null;
        if (!draggedId) return;

        const rect = timeline.getBoundingClientRect();
        const y = ev.clientY - rect.top;
        const absoluteMin = Math.round(y / PIXELS_PER_MIN) + DAY_START;
        const snapped = Math.max(DAY_START, Math.min(DAY_END, Math.round(absoluteMin / 10) * 10));

        try {
          let payload = {
            session_id: draggedId,
            weekday: day,
            hall_id: hall.id,
            start: snapped,
          };
          if (swapId && swapId !== draggedId) {
            payload.swap_with_id = swapId;
          }
          let result = await api("/api/schedule/move", {
            method: "POST",
            body: JSON.stringify(payload),
          });

          if (!result.ok) {
            const allow = confirm(`${result.message}. Vill du markera som manuellt undantag?`);
            if (allow) {
              payload.allow_exception = true;
              payload.reason = "Drag-and-drop manuellt undantag";
              result = await api("/api/schedule/move", {
                method: "POST",
                body: JSON.stringify(payload),
              });
            } else {
              setStatus(result.message, true);
              return;
            }
          }

          state.schedule = result.schedule;
          renderBoard();
          renderMetaPanels();
          setStatus(result.message || "Flyttad");
        } catch (err) {
          setStatus(err.message, true);
        }
      });

      const availabilityBlocks = (state.data.availability_blocks || []).filter(
        (b) => Number(b.weekday) === day && b.hall_id === hall.id
      );
      for (const block of availabilityBlocks) {
        const blockStart = timeToMinutes(block.start);
        const blockEnd = timeToMinutes(block.end);
        const top = (blockStart - DAY_START) * PIXELS_PER_MIN;
        const height = Math.max(10, (blockEnd - blockStart) * PIXELS_PER_MIN);
        if (height <= 0) continue;

        const club = state.data.clubs.find((c) => c.id === block.club_id);
        const outline = document.createElement("div");
        outline.className = "availability-outline";
        outline.style.top = `${top}px`;
        outline.style.height = `${height}px`;
        outline.style.color = club?.color || "#7a7a7a";
        outline.style.background = club?.color || "#d0d0d0";

        const label = document.createElement("span");
        label.className = "availability-label";
        label.textContent = `${club?.name || block.club_id} ${block.start}-${block.end}`;
        outline.appendChild(label);

        timeline.appendChild(outline);
      }

      const sessions = (state.schedule.sessions || []).filter(
        (s) => Number(s.weekday) === day && s.hall_id === hall.id
      );
      for (const session of sessions) {
        const card = document.createElement("div");
        card.className = "session-card";
        if (session.manual_exception) card.classList.add("manual");
        card.draggable = true;
        card.dataset.sessionId = session.id;

        const top = (session.start - DAY_START) * PIXELS_PER_MIN;
        const height = Math.max(28, (session.end - session.start) * PIXELS_PER_MIN);
        card.style.top = `${top}px`;
        card.style.height = `${height}px`;
        card.style.background = findClubColor(session.club_id);

        const groupNames = (session.group_ids || [])
          .map((gid) => state.data.groups.find((g) => g.id === gid)?.name || gid)
          .join("/");
        const clubName = state.data.clubs.find((c) => c.id === session.club_id)?.name || session.club_id;
        card.innerHTML = `
          <strong>${session.name}</strong><br />
          ${minutesToTime(session.start)}-${minutesToTime(session.end)}<br />
          ${clubName}<br />
          ${groupNames}
        `;

        card.addEventListener("dragstart", (ev) => {
          ev.dataTransfer.setData("text/session-id", session.id);
          ev.dataTransfer.setData("text/swap-id", session.id);
        });

        card.addEventListener("dragover", (ev) => {
          ev.preventDefault();
          card.classList.add("drop-target");
        });

        card.addEventListener("dragleave", () => {
          card.classList.remove("drop-target");
        });

        card.addEventListener("drop", async (ev) => {
          ev.preventDefault();
          ev.stopPropagation();
          card.classList.remove("drop-target");
          const draggedId = ev.dataTransfer.getData("text/session-id");
          if (!draggedId || draggedId === session.id) return;
          try {
            let result = await api("/api/schedule/move", {
              method: "POST",
              body: JSON.stringify({
                session_id: draggedId,
                swap_with_id: session.id,
              }),
            });

            if (!result.ok) {
              const allow = confirm(`${result.message}. Vill du markera som manuellt undantag?`);
              if (!allow) {
                setStatus(result.message, true);
                return;
              }
              result = await api("/api/schedule/move", {
                method: "POST",
                body: JSON.stringify({
                  session_id: draggedId,
                  swap_with_id: session.id,
                  allow_exception: true,
                  reason: "Manuell platsbyte via drag-and-drop",
                }),
              });
            }

            state.schedule = result.schedule;
            renderBoard();
            renderMetaPanels();
            setStatus(result.message || "Pass bytta");
          } catch (err) {
            setStatus(err.message, true);
          }
        });

        timeline.appendChild(card);
      }

      hallWrap.appendChild(timeline);
      col.appendChild(hallWrap);
    }

    row.appendChild(col);
  }

  board.appendChild(row);
}

async function removeResource(resource, id) {
  if (!confirm("Ta bort posten?")) return;
  if (!id) {
    setStatus("Objektet saknar id och kan inte tas bort", true);
    return;
  }
  try {
    await api(`/api/${resource}/${encodeURIComponent(id)}`, { method: "DELETE" });
    await reload();
    setStatus("Post borttagen");
  } catch (err) {
    setStatus(`Kunde inte ta bort posten: ${err.message}`, true);
  }
}

async function saveResource(resource, id, payload) {
  if (id) {
    await api(`/api/${resource}/${id}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    });
  } else {
    await api(`/api/${resource}`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }
  await reload();
}

function bindForms() {
  $("hallForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    await saveResource("halls", $("hallId").value, {
      name: $("hallName").value,
    });
  });

  $("clubForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    await saveResource("clubs", $("clubId").value, {
      name: $("clubName").value,
      color: $("clubColor").value,
    });
  });

  $("blockForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    await saveResource("availability_blocks", $("blockId").value, {
      club_id: $("blockClub").value,
      hall_id: $("blockHall").value,
      weekday: Number($("blockWeekday").value),
      start: $("blockStart").value,
      end: $("blockEnd").value,
    });
  });

  $("groupForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const prefStart = $("groupPrefStart").value;
    const prefEnd = $("groupPrefEnd").value;
    const minLength = Number($("groupMinSessionLength").value);
    const maxLength = Number($("groupMaxSessionLength").value);
    const finalMin = Math.min(minLength, maxLength);
    const finalMax = Math.max(minLength, maxLength);
    await saveResource("groups", $("groupId").value, {
      name: $("groupName").value,
      club_id: $("groupClub").value,
      sessions_per_week: Number($("groupSessionsPerWeek").value),
      min_session_length: finalMin,
      max_session_length: finalMax,
      session_length: finalMax,
      allowed_halls: selectedValues("groupAllowedHalls"),
      forbidden_halls: selectedValues("groupForbiddenHalls"),
      strict_hall_id: $("groupStrictHall").value || null,
      preferred_days: selectedValues("groupPreferredDays").map((v) => Number(v)),
      preferred_time_range: prefStart && prefEnd ? [prefStart, prefEnd] : null,
      time_preference_priority: Number($("groupTimePriority").value),
      no_two_same_day: $("groupNoTwoSameDay").checked,
      avoid_consecutive_days: $("groupAvoidConsecutive").checked,
      max_sessions_per_week: Number($("groupMaxPerWeek").value),
      min_rest_hours: Number($("groupMinRest").value),
      discipline: $("groupDiscipline").value,
      age_level: $("groupAgeLevel").value,
    });
  });

  $("combinedForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const minLength = Number($("combinedMinSessionLength").value);
    const maxLength = Number($("combinedMaxSessionLength").value);
    const finalMin = Math.min(minLength, maxLength);
    const finalMax = Math.max(minLength, maxLength);
    await saveResource("combined_sessions", $("combinedId").value, {
      name: $("combinedName").value,
      group_ids: selectedValues("combinedGroups"),
      sessions_per_week: Number($("combinedSessionsPerWeek").value),
      min_session_length: finalMin,
      max_session_length: finalMax,
      session_length: finalMax,
    });
  });

  $("ruleForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    await saveResource("resurfacing_rules", $("ruleId").value, {
      name: $("ruleName").value,
      scope: $("ruleScope").value,
      hall_id: $("ruleHall").value || null,
      club_id: $("ruleClub").value || null,
      rule_type: $("ruleType").value,
      buffer_minutes: Number($("ruleBuffer").value),
      max_in_row: Number($("ruleMaxInRow").value),
      discipline: $("ruleDiscipline").value,
      blocked_weekdays: selectedValues("ruleBlockedDays").map((v) => Number(v)),
    });
  });

  $("hallReset").addEventListener("click", resetForms);
  $("clubReset").addEventListener("click", resetForms);
  $("blockReset").addEventListener("click", resetForms);
  $("groupReset").addEventListener("click", resetForms);
  $("combinedReset").addEventListener("click", resetForms);
  $("ruleReset").addEventListener("click", resetForms);

  $("generateScheduleBtn").addEventListener("click", async () => {
    const result = await api("/api/schedule/generate", { method: "POST" });
    state.schedule = result;
    renderBoard();
    renderMetaPanels();
    setStatus("Schema genererat");
  });

  $("saveScheduleBtn").addEventListener("click", async () => {
    await api("/api/schedule/save", {
      method: "POST",
      body: JSON.stringify(state.schedule),
    });
    setStatus("Schema sparat lokalt");
  });

  $("loadScheduleBtn").addEventListener("click", async () => {
    state.schedule = await api("/api/schedule/load", { method: "POST" });
    renderBoard();
    renderMetaPanels();
    setStatus("Schema laddat");
  });

  $("resetSeedBtn").addEventListener("click", async () => {
    await api("/api/meta/reset", { method: "POST" });
    await reload();
    setStatus("Seed-data återställd");
  });

  $("exportBtn").addEventListener("click", async () => {
    const fmt = $("exportFormat").value;
    window.location.href = `/api/export/${fmt}`;
  });
}

async function reload() {
  try {
    const boot = await api("/api/bootstrap");
    state.data = boot.data;
    state.schedule = {
      sessions: boot.schedule.sessions || [],
      unscheduled: boot.schedule.unscheduled || [],
      conflicts: boot.schedule.conflicts || [],
      idle_time: boot.schedule.idle_time || boot.idle_time || [],
    };
    state.aiSummary = boot.ai_summary || "";

    fillSelects();
    renderEntities();
    renderBoard();
    renderMetaPanels();
    setStatus(state.aiSummary || "Redo");
  } catch (err) {
    setStatus(err.message, true);
  }
}

bindForms();
reload();
