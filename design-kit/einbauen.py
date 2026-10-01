"""Baut das Cockpit-Design in bestehende HTML-Seiten ein.

Aufruf (Python 3.9 oder neuer, keine Zusatzpakete):

    python3 einbauen.py ORDNER                         nur anzeigen, was passieren würde
    python3 einbauen.py ORDNER --anwenden              einbauen
    python3 einbauen.py ORDNER --design hell --grundstil --umschalter --anwenden
    python3 einbauen.py ORDNER --design bronze --akzent gelb --menue neon --grundstil --anwenden
    python3 einbauen.py ORDNER --zuruecksetzen --anwenden
    python3 einbauen.py ORDNER --sicherungen-loeschen --anwenden

Was passiert:
  * Die Design-Dateien werden nach ORDNER/design/ kopiert.
  * In jede .html/.htm-Datei unter ORDNER kommen vor </head> die Verweise auf
    die CSS-Datei (zwischen zwei Kommentaren, damit ein zweiter Lauf sie ersetzt),
    und <html> bekommt data-theme="…".
  * --grundstil: zusätzlich cockpit-basis.css und <body class="cockpit-auto">, damit
    Seiten ohne Cockpit-Klassen (header, nav, main, section, button …) passend aussehen.
  * --umschalter: bindet theme-umschalter.js ein (Design im Browser umschaltbar).
  * --modus, --akzent, --schrift, --ecken, --menue: weitere Einstellungen des Designs,
    wie unter Einstellungen → Darstellung im Projekt-Cockpit.
  * Von jeder geänderten Datei bleibt eine Kopie DATEI.vor-cockpit.bak.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
from pathlib import Path

THEMES = ("violett", "glas", "bronze", "hell", "schlicht")
TONES = {"violett": "dunkel", "glas": "dunkel", "bronze": "dunkel", "hell": "hell", "schlicht": ""}
LOOK = {  # option: (attribute on <html>, allowed values)
    "modus": ("data-mode", ("hell", "dunkel")),
    "akzent": ("data-accent", ("violett", "blau", "pink", "gruen", "orange", "gelb", "rot")),
    "schrift": ("data-size", ("klein", "gross")),
    "ecken": ("data-shape", ("rund", "weich", "kantig")),
    "menue": ("data-menu", ("fluessig", "magnet", "kapsel", "segment", "orbit", "welle", "neon",
                            "blob", "karten", "luxus")),
}
MANAGED = ("data-theme", "data-tone") + tuple(attr for attr, _values in LOOK.values())
START = "<!-- Cockpit-Design -->"
END = "<!-- /Cockpit-Design -->"
BACKUP = ".vor-cockpit.bak"
TARGET = "design"

KIT = Path(__file__).resolve().parent


def sources() -> dict:
    """Design files, either from the unpacked package or from the repository."""
    if (KIT / "cockpit-design.css").exists():
        css, fonts = KIT / "cockpit-design.css", KIT / "fonts"
    else:
        static = KIT.parent / "cockpit" / "static"
        css, fonts = static / "app.css", static / "fonts"
    return {"css": css, "fonts": fonts, "basis": KIT / "cockpit-basis.css",
            "js": KIT / "theme-umschalter.js"}


def read(path: Path) -> tuple[str, str]:
    raw = path.read_bytes()
    for encoding in ("utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    raise ValueError("unbekannte Zeichenkodierung")


def block(rel: str, has_viewport: bool, basis: bool, switcher: bool) -> str:
    lines = [START]
    if not has_viewport:
        lines.append('<meta name="viewport" content="width=device-width, initial-scale=1">')
    lines.append(f'<link rel="stylesheet" href="{rel}/cockpit-design.css">')
    if basis:
        lines.append(f'<link rel="stylesheet" href="{rel}/cockpit-basis.css">')
    if switcher:
        lines.append(f'<script src="{rel}/theme-umschalter.js" defer></script>')
    lines.append(END)
    return "\n".join(lines) + "\n"


BLOCK_RE = re.compile(re.escape(START) + r".*?" + re.escape(END) + r"\n?", re.S)
HEAD_END_RE = re.compile(r"</head\s*>", re.I)
HTML_RE = re.compile(r"<html\b([^>]*)>", re.I)
BODY_RE = re.compile(r"<body\b([^>]*)>", re.I)
MANAGED_ATTR_RE = re.compile(
    r"\s(?:" + "|".join(MANAGED) + r""")\s*=\s*(["'])[^"']*\1""", re.I)
CLASS_ATTR_RE = re.compile(r"""(\sclass\s*=\s*)(["'])([^"']*)\2""", re.I)
VIEWPORT_RE = re.compile(r"""<meta[^>]+name\s*=\s*["']viewport["']""", re.I)


def html_attrs(design: str, look: dict | None = None) -> str:
    look = look or {}
    attrs = [f'data-theme="{design}"']
    for key, (attr, values) in LOOK.items():
        if look.get(key) in values:
            attrs.append(f'{attr}="{look[key]}"')
    tone = look.get("modus") or TONES[design]
    if tone:
        attrs.append(f'data-tone="{tone}"')
    return " ".join(attrs)


def transform(text: str, rel: str, design: str, basis: bool, switcher: bool,
              look: dict | None = None) -> str | None:
    """New page text, or None if the page has no <head> to extend."""
    text = BLOCK_RE.sub("", text)
    match = HEAD_END_RE.search(text)
    if not match:
        return None
    snippet = block(rel, bool(VIEWPORT_RE.search(text)), basis, switcher)
    text = text[:match.start()] + snippet + text[match.start():]

    def set_theme(m):
        attrs = MANAGED_ATTR_RE.sub("", m.group(1))
        return f'<html{attrs} {html_attrs(design, look)}>'
    text = HTML_RE.sub(set_theme, text, count=1)

    def set_body(m):
        attrs = m.group(1)
        found = CLASS_ATTR_RE.search(attrs)
        names = found.group(3).split() if found else []
        names = [n for n in names if n != "cockpit-auto"] + (["cockpit-auto"] if basis else [])
        if found:
            value = f'{found.group(1)}{found.group(2)}{" ".join(names)}{found.group(2)}'
            attrs = attrs[:found.start()] + (value if names else "") + attrs[found.end():]
        elif names:
            attrs += f' class="{" ".join(names)}"'
        return f"<body{attrs}>"
    return BODY_RE.sub(set_body, text, count=1)


def pages(folder: Path):
    design_dir = folder / TARGET
    for path in sorted(folder.rglob("*")):
        if path.suffix.lower() in (".html", ".htm") and path.is_file() \
                and design_dir not in path.parents:
            yield path


def copy_design(folder: Path, basis: bool, switcher: bool) -> None:
    src = sources()
    target = folder / TARGET
    (target / "fonts").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src["css"], target / "cockpit-design.css")
    for font in src["fonts"].iterdir():
        shutil.copyfile(font, target / "fonts" / font.name)
    if basis:
        shutil.copyfile(src["basis"], target / "cockpit-basis.css")
    if switcher:
        shutil.copyfile(src["js"], target / "theme-umschalter.js")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Cockpit-Design in HTML-Seiten einbauen.")
    parser.add_argument("ordner", type=Path, help="Ordner mit den HTML-Seiten")
    parser.add_argument("--design", choices=THEMES, default="glas")
    for key, (_attr, values) in LOOK.items():
        parser.add_argument(f"--{key}", choices=values, help="Standard: wie im Design")
    parser.add_argument("--grundstil", action="store_true",
                        help="Seiten ohne Cockpit-Klassen automatisch gestalten")
    parser.add_argument("--umschalter", action="store_true", help="Design-Umschalter einbinden")
    parser.add_argument("--anwenden", action="store_true", help="wirklich ändern")
    parser.add_argument("--zuruecksetzen", action="store_true",
                        help="Originale aus den Sicherungen wiederherstellen")
    parser.add_argument("--sicherungen-loeschen", action="store_true",
                        help="die .vor-cockpit.bak-Dateien entfernen")
    args = parser.parse_args(argv)
    folder = args.ordner.resolve()
    if not folder.is_dir():
        print(f"Ordner nicht gefunden: {folder}")
        return 2
    mode = "" if args.anwenden else " (Vorschau, nichts wird geändert; zum Ausführen --anwenden)"

    if args.zuruecksetzen or args.sicherungen_loeschen:
        count = 0
        for backup in sorted(folder.rglob("*" + BACKUP)):
            original = backup.with_name(backup.name[: -len(BACKUP)])
            if args.anwenden:
                if args.zuruecksetzen:
                    shutil.copyfile(backup, original)
                backup.unlink()
            count += 1
            what = "wiederhergestellt" if args.zuruecksetzen else "Sicherung gelöscht"
            print(f"{what}: {original.relative_to(folder)}")
        print(f"{count} Datei(en){mode}.")
        return 0

    changed = skipped = unchanged = 0
    for page in pages(folder):
        name = page.relative_to(folder)
        try:
            text, encoding = read(page)
        except ValueError as exc:
            print(f"übersprungen ({exc}): {name}")
            skipped += 1
            continue
        rel = Path(os.path.relpath(folder / TARGET, page.parent)).as_posix()
        look = {key: getattr(args, key) for key in LOOK}
        new = transform(text, rel, args.design, args.grundstil, args.umschalter, look)
        if new is None:
            print(f"übersprungen (kein </head>, vermutlich nur ein Seitenteil): {name}")
            skipped += 1
            continue
        if new == text:
            unchanged += 1
            continue
        if args.anwenden:
            backup = page.with_name(page.name + BACKUP)
            if not backup.exists():
                shutil.copyfile(page, backup)
            try:
                page.write_text(new, encoding=encoding)
            except UnicodeEncodeError:
                page.write_text(new, encoding="utf-8")
        print(f"eingebaut: {name}")
        changed += 1
    if args.anwenden and (changed or unchanged):
        copy_design(folder, args.grundstil, args.umschalter)
    print(f"{changed} geändert, {unchanged} schon aktuell, {skipped} übersprungen{mode}.")
    if args.anwenden and changed:
        print(f"Design-Dateien liegen in {folder / TARGET}. Sicherungen: *{BACKUP}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
