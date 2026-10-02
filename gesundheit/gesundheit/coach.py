"""Week coach: this week's plan from the person's own habits, adjusted when recovery is poor.

The plan is not invented: a weekday gets a session when the person trained on that weekday in
at least half of the last eight weeks (most common kind, usual duration). Done sessions are
ticked off. When the findings or the form say "too much" (load jump, raised resting pulse, low
HRV, sleep debt, strained form), the next planned hard session becomes an easy one below the
zone 2 limit; a strongly strained person also gets a rest day. Like a coach, not a doctor.
"""

import statistics
from collections import Counter
from datetime import timedelta

from . import belastung, store, util
from .katalog import WORKOUT_KINDS

HABIT_WEEKS = 8
REASON_LABELS = {"sprung": "Belastung diese Woche", "ruhepuls": "Ruhepuls",
                 "hrv": "Herzfrequenzvariabilität", "schlaf": "Schlaf fehlt"}


def _label(kind: str) -> str:
    return WORKOUT_KINDS.get(kind, "Training")


def _round5(minutes: float) -> int:
    return max(5, int(round(minutes / 5) * 5))


def habits(db, pid: int, monday) -> dict[int, dict]:
    """{weekday: {kind, minutes, hr, weeks}} from the eight full weeks before `monday`."""
    start = monday - timedelta(weeks=HABIT_WEEKS)
    by_slot: dict[tuple, dict] = {}
    for w in store.workouts(db, pid, start, monday - timedelta(days=1)):
        day = util.to_date(w["day"])
        slot = ((day - start).days // 7, day.weekday())
        if slot not in by_slot or (w["duration_min"] or 0) > (by_slot[slot]["duration_min"] or 0):
            by_slot[slot] = w
    result = {}
    for weekday in range(7):
        sessions = [w for (week, wd), w in by_slot.items() if wd == weekday]
        if len(sessions) < HABIT_WEEKS / 2:
            continue
        kind = Counter(w["kind"] for w in sessions).most_common(1)[0][0]
        same = [w for w in sessions if w["kind"] == kind]
        hrs = [w["hr_avg"] for w in same if w["hr_avg"]]
        result[weekday] = {
            "kind": kind,
            "minutes": _round5(statistics.median(w["duration_min"] or 0 for w in same)),
            "km": statistics.median(w["distance_km"] for w in same if w["distance_km"])
            if any(w["distance_km"] for w in same) else None,
            "hr": statistics.median(hrs) if hrs else None,
            "weeks": len(sessions),
        }
    return result


def week(db, pid: int, person: dict, today, findings=(), form=None) -> dict:
    today = util.to_date(today)
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    plan = habits(db, pid, monday)
    rest, maximum = belastung.heart_limits(db, pid, person, today)
    limit = round(rest + 0.7 * (maximum - rest))
    done: dict[str, list] = {}
    for w in store.workouts(db, pid, monday, sunday):
        done.setdefault(w["day"], []).append(w)

    rows = []
    for i in range(7):
        day = monday + timedelta(days=i)
        habit = plan.get(i)
        row = {"day": day, "weekday": util.WEEKDAYS[i], "date": f"{day.day}.{day.month}.",
               "today": day == today, "repaired": False, "original": "", "value": ""}
        sessions = sorted(done.get(day.isoformat(), []), key=lambda w: w["started_at"])
        if sessions:
            main = max(sessions, key=lambda w: w["duration_min"] or 0)
            parts = []
            if main["distance_km"]:
                parts.append(f"{util.fmt_num(main['distance_km'], 1)} km")
            if main["hr_avg"]:
                parts.append(f"Ø {util.fmt_num(main['hr_avg'])} Puls")
            row.update(status="erledigt", title=f"{_label(main['kind'])} {util.fmt_num(main['duration_min'] or 0)} min",
                       sub=" · ".join(parts + ([f"+{len(sessions) - 1} weitere"] if len(sessions) > 1 else []))
                       or "erledigt",
                       value=f"{util.fmt_num(main['distance_km'], 1)} km" if main["distance_km"] else "")
        elif habit:
            title = f"{_label(habit['kind'])} {habit['minutes']} min"
            row.update(status="verpasst" if day < today else "offen", title=title,
                       sub=f"wie an {habit['weeks']} der letzten {HABIT_WEEKS} {util.WEEKDAYS[i]}-Tage",
                       value=f"{util.fmt_num(habit['km'], 0)} km" if habit["km"] else "",
                       habit=habit)
        else:
            goal = person.get("goal_steps")
            row.update(status="ruhe", title="Ruhetag",
                       sub=f"Schrittziel {util.fmt_num(goal)}" if goal else "Bewegung im Alltag")
        rows.append(row)

    reasons = []
    if form and form["form"] < -10:
        reasons.append((util.fmt_signed(form["form"], 0), f"Form heute ({form['label']})"))
    for f in findings:
        if f.tone == "warn" and f.rule in REASON_LABELS:
            reasons.append((f.big, REASON_LABELS[f.rule]))
    reasons = reasons[:3]
    strained = bool(form and form["form"] < -30) or len(reasons) >= 3

    repaired = 0
    if reasons and (len(reasons) >= 2 or strained):
        open_rows = [r for r in rows if r["status"] == "offen"]
        # the next hard one first: above the zone 2 limit or long
        hard = [r for r in open_rows if (r["habit"]["hr"] or 0) >= limit or r["habit"]["minutes"] >= 60]
        targets = (hard or open_rows)[:2 if strained else 1]
        for n, row in enumerate(targets):
            habit = row["habit"]
            row["original"] = row["title"]
            row["repaired"] = True
            if n == 1:
                row.update(title="Ruhetag", sub="statt der zweiten Einheit: Spaziergang, Dehnen, früh schlafen",
                           value="")
            else:
                minutes = _round5(habit["minutes"] * 0.6)
                row.update(title=f"{_label(habit['kind'])} {minutes} min locker, unter {limit} Puls",
                           sub="kürzer und ruhig, damit die Erholung aufholen kann",
                           value=f"{util.fmt_num(habit['km'] * 0.6, 0)} km" if habit["km"] else "")
            repaired += 1

    planned = sum(1 for r in rows if r["status"] in ("offen", "verpasst", "erledigt"))
    return {
        "rows": rows, "week": monday.isocalendar()[1],
        "range": f"{monday.day}. {util.MONTHS[monday.month - 1]} bis {sunday.day}. {util.MONTHS[sunday.month - 1]}",
        "repaired": repaired, "reasons": reasons, "limit": limit,
        "done": sum(1 for r in rows if r["status"] == "erledigt"), "planned": planned,
        "has_habits": bool(plan),
    }
