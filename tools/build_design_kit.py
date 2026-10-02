"""Build dist/design-kit.zip: the app's design as a standalone package.

Usage: python3 tools/build_design_kit.py
"""

import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "cockpit" / "static"
KIT = ROOT / "design-kit"


def build(target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(STATIC / "app.css", "design-kit/cockpit-design.css")
        for font in sorted((STATIC / "fonts").iterdir()):
            z.write(font, f"design-kit/fonts/{font.name}")
        z.write(STATIC / "komponenten.js", "design-kit/komponenten.js")
        for page in ("beispiel.html", "vorlage.html", "anmelden.html", "komponenten.html", "404.html"):
            html = (KIT / page).read_text(encoding="utf-8").replace(
                "../cockpit/static/app.css", "cockpit-design.css").replace(
                "../cockpit/static/komponenten.js", "komponenten.js")
            z.writestr(f"design-kit/{page}", html)
        for name in ("cockpit-basis.css", "theme-umschalter.js", "einbauen.py", "README.md"):
            z.write(KIT / name, f"design-kit/{name}")
    return target


if __name__ == "__main__":
    print(build(ROOT / "dist" / "design-kit.zip"))
