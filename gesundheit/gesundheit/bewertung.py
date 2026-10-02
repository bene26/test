"""Orientation values. No diagnosis: the pages always say so next to them."""

# ESH 2023, office blood pressure. The higher of the two categories counts.
BP_LEVELS = [
    # key, label, systolic from, diastolic from
    ("optimal", "Optimal", 0, 0),
    ("normal", "Normal", 120, 80),
    ("hochnormal", "Hoch normal", 130, 85),
    ("grad1", "Hypertonie Grad 1", 140, 90),
    ("grad2", "Hypertonie Grad 2", 160, 100),
    ("grad3", "Hypertonie Grad 3", 180, 110),
]
BP_NOTE = ("Einteilung nach der Europäischen Gesellschaft für Hypertonie (ESH 2023) für "
           "Praxismessungen. Für Messungen zu Hause gilt ein Mittelwert ab 135/85 mmHg als "
           "erhöht. Das ist keine Diagnose; bitte Werte mit der Ärztin oder dem Arzt besprechen.")


def bp_category(systolic: float, diastolic: float) -> tuple[str, str]:
    level = 0
    for index, (_key, _label, sys_from, dia_from) in enumerate(BP_LEVELS):
        if systolic >= sys_from or diastolic >= dia_from:
            level = index
    return BP_LEVELS[level][0], BP_LEVELS[level][1]


def home_bp_raised(systolic: float, diastolic: float) -> bool:
    return systolic >= 135 or diastolic >= 85


BMI_LEVELS = [(0, "untergewicht", "Untergewicht"), (18.5, "normal", "Normalgewicht"),
              (25, "uebergewicht", "Übergewicht"), (30, "adipositas", "Adipositas")]


def bmi(weight_kg: float | None, height_cm: float | None) -> float | None:
    if not weight_kg or not height_cm:
        return None
    meters = height_cm / 100
    return weight_kg / (meters * meters)


def bmi_category(value: float) -> tuple[str, str]:
    result = BMI_LEVELS[0]
    for level in BMI_LEVELS:
        if value >= level[0]:
            result = level
    return result[1], result[2]


def trend_class(change: float | None, good: str) -> str:
    """CSS class for a change: 'gut', 'schlecht' or 'neutral'."""
    if change is None or abs(change) < 1e-9 or not good:
        return "neutral"
    better = change > 0 if good == "up" else change < 0
    return "gut" if better else "schlecht"
