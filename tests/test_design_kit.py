import importlib.util
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


einbauen = load("einbauen", ROOT / "design-kit" / "einbauen.py")

PAGE = """<!DOCTYPE html>
<HTML lang="de">
<head><meta charset="utf-8"><title>Über uns</title></head>
<body class="seite">
<header><h1>Firma Müller</h1><nav><ul><li><a href="index.html">Start</a></li></ul></nav></header>
<main><section><p>Grüße</p></section></main>
</body></html>
"""


def site(tmp_path):
    (tmp_path / "unter").mkdir()
    (tmp_path / "index.html").write_text(PAGE, encoding="utf-8")
    (tmp_path / "unter" / "alt.htm").write_bytes(PAGE.replace("utf-8", "windows-1252")
                                                 .encode("cp1252"))
    (tmp_path / "teil.html").write_text("<div>nur ein Seitenteil</div>", encoding="utf-8")
    return tmp_path


def test_preview_changes_nothing(tmp_path, capsys):
    root = site(tmp_path)
    einbauen.main([str(root)])
    assert (root / "index.html").read_text(encoding="utf-8") == PAGE
    assert not (root / "design").exists()
    assert "Vorschau" in capsys.readouterr().out


def test_apply_update_and_restore(tmp_path):
    root = site(tmp_path)
    original_alt = (root / "unter" / "alt.htm").read_bytes()
    einbauen.main([str(root), "--grundstil", "--design", "hell", "--anwenden"])

    index = (root / "index.html").read_text(encoding="utf-8")
    assert '<link rel="stylesheet" href="design/cockpit-design.css">' in index
    assert '<link rel="stylesheet" href="design/cockpit-basis.css">' in index
    assert 'data-theme="hell"' in index and 'class="seite cockpit-auto"' in index
    assert 'name="viewport"' in index and "Grüße" in index
    alt = (root / "unter" / "alt.htm").read_bytes().decode("cp1252")
    assert 'href="../design/cockpit-design.css"' in alt and "Müller" in alt
    assert (root / "teil.html").read_text(encoding="utf-8") == "<div>nur ein Seitenteil</div>"
    assert (root / "design" / "cockpit-design.css").exists()
    assert (root / "design" / "fonts" / "geist.woff2").exists()

    # A second run with other options replaces the block instead of adding one.
    einbauen.main([str(root), "--design", "bronze", "--akzent", "gelb", "--menue", "neon",
                   "--anwenden"])
    index = (root / "index.html").read_text(encoding="utf-8")
    assert index.count("<!-- Cockpit-Design -->") == 1
    assert 'data-theme="bronze" data-accent="gelb" data-menu="neon" data-tone="dunkel"' in index
    assert "hell" not in index
    assert "cockpit-basis.css" not in index and 'class="seite"' in index

    einbauen.main([str(root), "--zuruecksetzen", "--anwenden"])
    assert (root / "index.html").read_text(encoding="utf-8") == PAGE
    assert (root / "unter" / "alt.htm").read_bytes() == original_alt
    assert not list(root.rglob("*.vor-cockpit.bak"))


def test_package_contains_everything(tmp_path):
    build = load("build_design_kit", ROOT / "tools" / "build_design_kit.py")
    target = build.build(tmp_path / "kit.zip")
    names = zipfile.ZipFile(target).namelist()
    for name in ("cockpit-design.css", "cockpit-basis.css", "einbauen.py", "vorlage.html",
                 "beispiel.html", "anmelden.html", "theme-umschalter.js", "README.md",
                 "fonts/sora.woff2"):
        assert f"design-kit/{name}" in names
    html = zipfile.ZipFile(target).read("design-kit/vorlage.html").decode()
    assert 'href="cockpit-design.css"' in html
