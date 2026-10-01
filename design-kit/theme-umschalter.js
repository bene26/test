// Design-Umschalter für das Projekt-Cockpit-Design.
// Setzt data-theme auf <html> und merkt sich die Wahl im Browser.
// Einbinden mit <script src="theme-umschalter.js" defer></script>.
(function () {
  "use strict";
  var KEY = "cockpit-design";
  var THEMES = ["violett", "glas", "bronze", "hell", "schlicht"];
  var root = document.documentElement;

  function apply(name) {
    if (THEMES.indexOf(name) === -1) return;
    root.setAttribute("data-theme", name);
    try { localStorage.setItem(KEY, name); } catch (e) { /* privater Modus */ }
    document.querySelectorAll("[data-theme-choice]").forEach(function (el) {
      if (el.tagName === "SELECT") el.value = name;
      else el.setAttribute("aria-pressed", el.getAttribute("data-theme-choice") === name ? "true" : "false");
    });
  }

  var saved = null;
  try { saved = localStorage.getItem(KEY); } catch (e) { saved = null; }
  apply(saved || root.getAttribute("data-theme") || "glas");

  // <select data-theme-choice> oder <button data-theme-choice="hell">
  document.addEventListener("change", function (event) {
    if (event.target.matches && event.target.matches("select[data-theme-choice]")) apply(event.target.value);
  });
  document.addEventListener("click", function (event) {
    var el = event.target.closest ? event.target.closest("button[data-theme-choice]") : null;
    if (el) apply(el.getAttribute("data-theme-choice"));
  });
  window.cockpitDesign = { set: apply, list: THEMES.slice() };
})();
