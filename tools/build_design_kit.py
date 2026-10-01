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
    example = (KIT / "beispiel.html").read_text(encoding="utf-8").replace(
        "../cockpit/static/app.css", "cockpit-design.css")
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(STATIC / "app.css", "design-kit/cockpit-design.css")
        for font in sorted((STATIC / "fonts").iterdir()):
            z.write(font, f"design-kit/fonts/{font.name}")
        z.writestr("design-kit/beispiel.html", example)
        z.write(KIT / "theme-umschalter.js", "design-kit/theme-umschalter.js")
        z.write(KIT / "README.md", "design-kit/README.md")
    return target


if __name__ == "__main__":
    print(build(ROOT / "dist" / "design-kit.zip"))
