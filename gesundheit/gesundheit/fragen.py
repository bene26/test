"""Ask the cockpit: a handful of prepared questions, answered from the person's own values.

No language model and no network: every answer is a fixed sentence pattern filled with numbers
computed here, so it works offline and every number can be checked on the pages. A question
only appears when there is enough data to answer it honestly.
"""

import logging
import statistics
from datetime import timedelta

from . import ausblick, auswertung, bewertung, store, util

log = logging.getLogger(__name__)
WHO_WEEKLY_MIN = 150


def _n(value, decimals=0):
    return util.fmt_num(value, decimals).replace("-", "−")


def sleep_enough(db, pid, person, today, ctx):
    nights = [n for n in store.sleep_series(db, pid, today - timedelta(days=13), today) if n["asleep_min"]]
    if len(nights) < 7:
        return None
    goal = person.get("goal_sleep_min") or 450
    values = [n["asleep_min"] for n in nights]
    avg = statistics.mean(values)
    reached = sum(1 for v in values if v >= goal)
    best = max(nights, key=lambda n: n["asleep_min"])
    if avg >= goal:
        head = "Ja, im Schnitt schon."
    elif avg >= goal - 30:
        head = "Knapp nicht."
    else:
        head = f"Nein, dir fehlen im Schnitt {util.fmt_minutes(goal - avg)} pro Nacht."
    return head, (f"In den letzten {len(nights)} Nächten hast du im Schnitt {util.fmt_minutes(avg)} "
                  f"geschlafen, dein Ziel sind {util.fmt_minutes(goal)}. Erreicht hast du es in "
                  f"{reached} Nächten. Am längsten war die Nacht auf {util.fmt_date(best['night'], weekday=True)} "
                  f"mit {util.fmt_minutes(best['asleep_min'])}.")


def recovered(db, pid, person, today, ctx):
    form = ctx.get("form")
    rest = auswertung.series(db, pid, "resting_hr", today - timedelta(days=34), today)
    if not form and len(rest) < 14:
        return None
    bits = []
    score = 0
    if form:
        bits.append(f"deine Form steht bei {util.fmt_signed(form['form'], 0)} ({form['label']})")
        score += -1 if form["form"] < -10 else (1 if form["form"] > 5 else 0)
    if len(rest) >= 14:
        recent = [p["value"] for p in rest if p["day"] > (today - timedelta(days=3)).isoformat()]
        base = [p["value"] for p in rest if p["day"] <= (today - timedelta(days=7)).isoformat()]
        if recent and len(base) >= 7:
            diff = statistics.mean(recent) - statistics.mean(base)
            if round(diff) == 0:
                bits.append("dein Ruhepuls liegt genau auf deinem Mittel der Wochen davor")
            else:
                bits.append(f"dein Ruhepuls liegt {_n(abs(diff))} Schläge {'über' if diff > 0 else 'unter'} "
                            f"deinem Mittel der Wochen davor")
            score += -1 if diff >= 3 else (1 if diff <= -2 else 0)
    night = store.sleep_series(db, pid, today - timedelta(days=1), today)
    if night and night[-1]["asleep_min"]:
        bits.append(f"letzte Nacht waren es {util.fmt_minutes(night[-1]['asleep_min'])} Schlaf")
        goal = person.get("goal_sleep_min") or 450
        score += -1 if night[-1]["asleep_min"] < goal - 60 else 0
    head = ("Eher nicht, heute lieber locker." if score <= -2 else
            "Halbwegs, nichts Hartes übertreiben." if score < 0 else
            "Ja, du wirkst erholt.")
    return head, "Kurz zusammengefasst: " + "; ".join(bits) + "."


def weight_course(db, pid, person, today, ctx):
    points = auswertung.series(db, pid, "weight", today - timedelta(days=89), today)
    if len(points) < 8:
        return None
    first, last = points[0], points[-1]
    change = last["value"] - first["value"]
    month = [p for p in points if p["day"] >= (today - timedelta(days=29)).isoformat()]
    month_change = month[-1]["value"] - month[0]["value"] if len(month) >= 2 else None
    head = ("Es geht nach unten." if change <= -0.5 else
            "Es geht nach oben." if change >= 0.5 else "Ziemlich stabil.")
    text = (f"Seit {util.fmt_date(first['day'])} von {_n(first['value'], 1)} auf {_n(last['value'], 1)} kg, "
            f"also {util.fmt_signed(change, 1)} kg")
    if month_change is not None:
        text += f", davon {util.fmt_signed(month_change, 1)} kg in den letzten 30 Tagen"
    text += "."
    forecast = next((f for f in ctx.get("forecasts", []) if f["kind"] == "gewicht"), None)
    if forecast:
        text += (f" Für {forecast['question'][:-1]} rechnet das Cockpit mit "
                 f"{forecast['probability']} % Chance.")
    return head, text


def move_enough(db, pid, person, today, ctx):
    week = store.daily_series(db, pid, "active_min", today - timedelta(days=6), today)
    steps = store.daily_series(db, pid, "steps", today - timedelta(days=13), today)
    if len(week) < 5 and len(steps) < 7:
        return None
    parts = []
    head = "Ja."
    if len(week) >= 5:
        total = sum(p["value"] for p in week)
        parts.append(f"In den letzten 7 Tagen hattest du {_n(total)} aktive Minuten; die WHO empfiehlt "
                     f"Erwachsenen {WHO_WEEKLY_MIN} bis 300 pro Woche")
        if total < WHO_WEEKLY_MIN:
            head = "Noch nicht ganz."
    if len(steps) >= 7 and person.get("goal_steps"):
        avg = statistics.mean(p["value"] for p in steps)
        reached = sum(1 for p in steps if p["value"] >= person["goal_steps"])
        parts.append(f"Schritte im Schnitt {_n(avg)} bei einem Ziel von {_n(person['goal_steps'])}, "
                     f"geschafft an {reached} von {len(steps)} Tagen")
        if avg < person["goal_steps"] * 0.8:
            head = "Noch nicht ganz."
    return head, ". ".join(parts) + "."


def blood_pressure(db, pid, person, today, ctx):
    readings = [r for r in store.readings(db, pid, ("bp_sys", "bp_dia"), today - timedelta(days=29), today)
                if "bp_sys" in r["values"] and "bp_dia" in r["values"]]
    if len(readings) < 3:
        return None
    sys_avg = statistics.mean(r["values"]["bp_sys"] for r in readings)
    dia_avg = statistics.mean(r["values"]["bp_dia"] for r in readings)
    raised = sum(1 for r in readings if bewertung.home_bp_raised(r["values"]["bp_sys"], r["values"]["bp_dia"]))
    label = bewertung.bp_category(sys_avg, dia_avg)[1]
    head = f"Im Schnitt {_n(sys_avg)}/{_n(dia_avg)}: {label}."
    return head, (f"{len(readings)} Messungen in den letzten 30 Tagen, {raised} davon ab 135/85 (Grenze "
                  f"für Messungen zu Hause). Einstufung nach ESH 2023 als Orientierung, keine Diagnose.")


def improved(db, pid, person, today, ctx):
    better, worse = [], []
    for key in ("steps", "active_min", "schlaf_dauer", "resting_hr", "hrv_rmssd", "weight"):
        result = auswertung.compare_periods(db, pid, key, 30, today)
        if result["current"]["count"] < 10 or result["previous"]["count"] < 10 or result["change_prev"] is None:
            continue
        meta = result["meta"]
        if abs(result["change_prev"]) < 3 or not meta.good:
            continue
        good = (result["change_prev"] > 0) == (meta.good == "up")
        (better if good else worse).append(f"{meta.label} {util.fmt_signed(result['change_prev'], 0)} %")
    if not better and not worse:
        return None
    def count(n, word):
        return f"{'Eine Sache' if n == 1 else f'{n} Dinge' if n else 'Nichts'} {word}"
    second = count(len(worse), "schlechter")
    head = f"{count(len(better), 'besser')}, {second[0].lower()}{second[1:]}."
    text = "Letzte 30 Tage gegen die 30 davor. "
    if better:
        text += "Besser: " + ", ".join(better) + ". "
    if worse:
        text += "Schlechter: " + ", ".join(worse) + "."
    return head, text.strip()


def too_hard(db, pid, person, today, ctx):
    finding = next((f for f in ctx.get("findings", []) if f.rule in ("locker", "sprung")), None)
    sessions = [w for w in store.workouts(db, pid, today - timedelta(days=83), today) if w["hr_avg"]]
    if not finding and len(sessions) < 6:
        return None
    if finding:
        return f"Ja, {finding.title_a[0].lower()}{finding.title_a[1:]} {finding.title_b}", finding.text
    return "Nein, das sieht ausgewogen aus.", (
        f"Von {len(sessions)} Trainings der letzten zwölf Wochen lagen genug locker unter deiner Grenze "
        "von Zone 2, und die Belastung dieser Woche passt zu den Wochen davor.")


def outlook(db, pid, person, today, ctx):
    found = {o.key: o for o in ausblick.all_outlooks(db, pid, person, today, 12)}
    order = ["weight", "resting_hr", "fitness", "steps", "schlaf_dauer", "hrv_rmssd", "hrv_sdnn"]
    chosen = [found[k] for k in order if k in found][:3]
    if not chosen:
        return None
    better = worse = 0
    for o in chosen:
        end = o.paths["erwartet"].end
        if not o.direction or abs(end - o.current) < max(abs(o.current) * 0.01, 10 ** -o.decimals):
            continue
        if (end < o.current) == (o.direction == "down"):
            better += 1
        else:
            worse += 1
    head = ("Wenn alles bleibt wie bisher, eher aufwärts." if better > worse else
            "Wenn alles bleibt wie bisher, eher abwärts." if worse > better else
            "Wenn alles bleibt wie bisher, gemischt: manches besser, manches schlechter."
            if better else "Wenn alles bleibt wie bisher, ziemlich stabil.")

    def line(key):
        return ", ".join(f"{o.label} {o.fmt(o.paths[key].end)}" for o in chosen)
    return head, (f"In drei Monaten wie bisher: {line('erwartet')}. Positiv, wie in deinen besten "
                  f"Wochen: {line('gut')}. Negativ, wie in deinen schwächsten: {line('schlecht')}. "
                  "Alle Werte mit Verlauf stehen unter Ausblick.")


QUESTIONS = [
    ("erholt", "Bin ich heute erholt?", recovered),
    ("schlaf", "Schlafe ich genug?", sleep_enough),
    ("hart", "Trainiere ich zu hart?", too_hard),
    ("bewegung", "Bewege ich mich genug?", move_enough),
    ("gewicht", "Wie entwickelt sich mein Gewicht?", weight_course),
    ("blutdruck", "Wie ist mein Blutdruck?", blood_pressure),
    ("besser", "Was hat sich diesen Monat verändert?", improved),
    ("weiter", "Wie könnte es weitergehen?", outlook),
]


def answers(db, pid: int, person: dict, today, **ctx) -> list[dict]:
    today = util.to_date(today)
    out = []
    for key, question, func in QUESTIONS:
        try:
            result = func(db, pid, person, today, ctx)
        except Exception:  # one broken answer must not take the overview down
            log.exception("Frage %s fehlgeschlagen", key)
            continue
        if result:
            out.append({"key": key, "q": question, "head": result[0], "text": result[1]})
    return out
