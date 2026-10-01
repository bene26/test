// Design-Umschalter für das Projekt-Cockpit-Design.
// Setzt die data-*-Attribute auf <html> und merkt sich die Wahl im Browser.
// Einbinden mit <script src="theme-umschalter.js" defer></script>.
//
// Bedienelemente (alle optional):
//   <select data-look="theme|modus|akzent|schrift|ecken|menue"> … </select>
//   <button type="button" data-look="akzent" data-value="blau">Blau</button>
//   <button type="button" data-nav-toggle>…</button>          Seitenleiste ein-/ausklappen
//   <button type="button" data-toggle-password aria-controls="passwort">…</button>
// Aus eigenem Code: cockpitDesign.set({ theme: "hell", akzent: "blau" })
(function () {
  "use strict";
  var KEY = "cockpit-design";
  var NAV_KEY = "cockpit-nav";
  var OPTIONS = {
    theme: { attr: "data-theme", values: ["violett", "glas", "bronze", "hell", "schlicht"] },
    modus: { attr: "data-mode", values: ["", "hell", "dunkel"] },
    akzent: { attr: "data-accent", values: ["", "violett", "blau", "pink", "gruen", "orange", "gelb", "rot"] },
    schrift: { attr: "data-size", values: ["klein", "", "gross"] },
    ecken: { attr: "data-shape", values: ["", "rund", "weich", "kantig"] },
    menue: { attr: "data-menu", values: ["", "fluessig", "magnet", "kapsel", "segment", "orbit", "welle", "neon", "blob", "karten", "luxus"] }
  };
  var TONES = { violett: "dunkel", glas: "dunkel", bronze: "dunkel", hell: "hell", schlicht: "" };
  var SIDEBAR = { violett: true, glas: true, hell: true };
  var root = document.documentElement;

  function store(key, value) { try { localStorage.setItem(key, value); } catch (e) { /* privater Modus */ } }
  function fetch(key) { try { return localStorage.getItem(key); } catch (e) { return null; } }

  function current() {
    var look = {};
    Object.keys(OPTIONS).forEach(function (k) { look[k] = root.getAttribute(OPTIONS[k].attr) || ""; });
    if (OPTIONS.theme.values.indexOf(look.theme) === -1) look.theme = "glas";
    return look;
  }

  function apply(changes, save) {
    var look = current();
    Object.keys(changes || {}).forEach(function (k) {
      if (OPTIONS[k] && OPTIONS[k].values.indexOf(changes[k]) !== -1) look[k] = changes[k];
    });
    Object.keys(OPTIONS).forEach(function (k) {
      if (look[k]) root.setAttribute(OPTIONS[k].attr, look[k]); else root.removeAttribute(OPTIONS[k].attr);
    });
    var tone = look.modus || TONES[look.theme];
    if (tone) root.setAttribute("data-tone", tone); else root.removeAttribute("data-tone");
    if (SIDEBAR[look.theme]) {
      var nav = fetch(NAV_KEY);
      root.setAttribute("data-nav", nav === "mini" || nav === "voll" ? nav : (look.theme === "hell" ? "mini" : "voll"));
    } else {
      root.removeAttribute("data-nav");
    }
    document.querySelectorAll("[data-look]").forEach(function (el) {
      var k = el.getAttribute("data-look");
      if (el.tagName === "SELECT") el.value = look[k] || "";
      else if (el.hasAttribute("data-value")) el.setAttribute("aria-pressed", el.getAttribute("data-value") === look[k] ? "true" : "false");
    });
    document.querySelectorAll("[data-nav-toggle]").forEach(function (btn) {
      btn.setAttribute("aria-expanded", root.getAttribute("data-nav") === "mini" ? "false" : "true");
    });
    if (save) store(KEY, JSON.stringify(look));
    return look;
  }

  var saved = fetch(KEY);
  var look = null;
  try { look = JSON.parse(saved); } catch (e) { look = saved ? { theme: saved } : null; }
  if (typeof look === "string") look = { theme: look };
  apply(look || {}, false);

  document.addEventListener("change", function (event) {
    var el = event.target;
    if (el.matches && el.matches("select[data-look]")) {
      var change = {};
      change[el.getAttribute("data-look")] = el.value;
      apply(change, true);
    } else if (el.matches && el.matches("select[data-theme-choice]")) {
      apply({ theme: el.value }, true);
    }
  });

  document.addEventListener("click", function (event) {
    var t = event.target.closest ? event.target : null;
    if (!t) return;
    var pick = t.closest("button[data-look][data-value]");
    if (pick) {
      var change = {};
      change[pick.getAttribute("data-look")] = pick.getAttribute("data-value");
      apply(change, true);
      return;
    }
    var legacy = t.closest("button[data-theme-choice]");
    if (legacy) { apply({ theme: legacy.getAttribute("data-theme-choice") }, true); return; }
    var toggle = t.closest("[data-nav-toggle]");
    if (toggle) {
      var next = root.getAttribute("data-nav") === "mini" ? "voll" : "mini";
      store(NAV_KEY, next);
      apply({}, false);
      return;
    }
    var eye = t.closest("[data-toggle-password]");
    if (eye) {
      var input = document.getElementById(eye.getAttribute("aria-controls"));
      if (!input) return;
      var show = input.type === "password";
      input.type = show ? "text" : "password";
      eye.setAttribute("aria-pressed", show ? "true" : "false");
      eye.setAttribute("aria-label", show ? "Passwort verbergen" : "Passwort anzeigen");
    }
  });

  window.cockpitDesign = {
    set: function (changes) { return apply(typeof changes === "string" ? { theme: changes } : changes, true); },
    get: current,
    options: OPTIONS
  };
})();
