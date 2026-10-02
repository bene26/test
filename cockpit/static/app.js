// Small progressive enhancements. Every page also works without JavaScript.
(function () {
  "use strict";

  var csrfMeta = document.querySelector('meta[name="csrf-token"]');
  var csrf = csrfMeta ? csrfMeta.content : "";

  // Submit the owning form when a select marked data-autosubmit changes.
  document.addEventListener("change", function (event) {
    var el = event.target;
    if (el.matches && el.matches("[data-autosubmit]") && el.form) {
      if (el.form.requestSubmit) el.form.requestSubmit(); else el.form.submit();
    }
  });

  // Appearance settings: preview every option on the whole page right away,
  // count the changes and offer "Verwerfen" / "Übernehmen". Saving stays a normal POST.
  var lookForm = document.querySelector("[data-look-form]");
  if (lookForm) {
    var root = document.documentElement;
    var ATTRS = { modus: "data-mode", akzent: "data-accent", schrift: "data-size", ecken: "data-shape", menue: "data-menu", zahlen: "data-digits", grafik: "data-grafik" };
    var TONES = { violett: "dunkel", glas: "dunkel", bronze: "dunkel", hell: "hell", schlicht: "" };
    var SIDEBAR = { violett: true, glas: true, hell: true };
    var bar = lookForm.querySelector("[data-changes-bar]");
    var countEl = lookForm.querySelector("[data-changes-count]");
    var picked = function (name) {
      var el = lookForm.querySelector('input[name="' + name + '"]:checked');
      return el ? el.value : "";
    };
    var snapshot = function () {
      var o = { theme: picked("theme") };
      Object.keys(ATTRS).forEach(function (k) { o[k] = picked(k); });
      return o;
    };
    var navState = function (theme) {
      var m = document.cookie.match(/(?:^|; )pc_nav=(mini|voll)/);
      return m ? m[1] : (theme === "hell" ? "mini" : "voll");
    };
    var initial = snapshot();
    var apply = function () {
      var cur = snapshot();
      root.setAttribute("data-theme", cur.theme);
      Object.keys(ATTRS).forEach(function (k) {
        if (cur[k]) root.setAttribute(ATTRS[k], cur[k]); else root.removeAttribute(ATTRS[k]);
      });
      var tone = cur.modus || TONES[cur.theme];
      if (tone) root.setAttribute("data-tone", tone); else root.removeAttribute("data-tone");
      if (SIDEBAR[cur.theme]) root.setAttribute("data-nav", navState(cur.theme)); else root.removeAttribute("data-nav");
      var demo = lookForm.querySelector("[data-menu-preview]");
      if (demo) demo.setAttribute("data-menu", cur.menue);
      var swatch = lookForm.querySelector("[data-design-swatch]");
      if (swatch) swatch.setAttribute("data-theme", cur.theme);
      var changes = Object.keys(cur).filter(function (k) { return cur[k] !== initial[k]; }).length;
      if (bar) bar.hidden = changes === 0;
      if (countEl) countEl.textContent = changes === 1 ? "1 Änderung" : changes + " Änderungen";
    };
    lookForm.addEventListener("change", apply);
    var discard = lookForm.querySelector("[data-changes-discard]");
    if (discard) discard.addEventListener("click", function () { lookForm.reset(); apply(); });
  }

  // Sidebar: collapse to an icon rail and remember it in a cookie for the server.
  var syncNavToggle = function () {
    var state = document.documentElement.getAttribute("data-nav");
    document.querySelectorAll("[data-nav-toggle]").forEach(function (btn) {
      btn.setAttribute("aria-expanded", state === "mini" ? "false" : "true");
    });
  };
  syncNavToggle();
  document.addEventListener("click", function (event) {
    var btn = event.target.closest ? event.target.closest("[data-nav-toggle]") : null;
    if (!btn) return;
    var root = document.documentElement;
    var next = root.getAttribute("data-nav") === "mini" ? "voll" : "mini";
    root.setAttribute("data-nav", next);
    document.cookie = "pc_nav=" + next + "; path=/; max-age=31536000; SameSite=Lax" +
      (location.protocol === "https:" ? "; Secure" : "");
    syncNavToggle();
  });

  // Show or hide the password.
  document.addEventListener("click", function (event) {
    var btn = event.target.closest ? event.target.closest("[data-toggle-password]") : null;
    if (!btn) return;
    var input = document.getElementById(btn.getAttribute("aria-controls"));
    if (!input) return;
    var show = input.type === "password";
    input.type = show ? "text" : "password";
    btn.setAttribute("aria-pressed", show ? "true" : "false");
    btn.setAttribute("aria-label", show ? "Passwort verbergen" : "Passwort anzeigen");
  });

  // Timeline form: show the fields that belong to a phase or a milestone.
  document.querySelectorAll("[data-kind-form]").forEach(function (box) {
    var select = box.querySelector("[data-kind-select]");
    if (!select) return;
    var apply = function () {
      box.querySelectorAll("[data-show-for]").forEach(function (el) {
        el.hidden = el.getAttribute("data-show-for") !== select.value;
      });
    };
    select.addEventListener("change", apply);
    apply();
  });

  // Timesheet: live day, row and week totals while typing.
  var sheet = document.querySelector("table.timesheet");
  if (sheet) {
    var num = function (v) { var n = parseFloat(String(v).replace(",", ".")); return isNaN(n) ? 0 : n; };
    var show = function (n) { return String(Math.round(n * 100) / 100).replace(".", ","); };
    var recalc = function () {
      var days = [0, 0, 0, 0, 0, 0, 0], week = 0;
      sheet.querySelectorAll("tbody tr").forEach(function (row) {
        var sum = 0;
        row.querySelectorAll("input.hours").forEach(function (input) {
          var v = num(input.value);
          sum += v;
          days[+input.getAttribute("data-day")] += v;
        });
        var cell = row.querySelector("[data-row-total]");
        if (cell) cell.textContent = show(sum);
        week += sum;
      });
      days.forEach(function (v, i) {
        var cell = sheet.querySelector('[data-day-total="' + i + '"]');
        if (cell) cell.textContent = show(v);
      });
      var total = sheet.querySelector("[data-week-total]");
      if (total) total.textContent = show(week);
    };
    sheet.addEventListener("input", recalc);
  }

  // Start page editor: drag widgets to reorder, preview "show" and "wide" right away.
  var board = document.querySelector("[data-widgets].editing");
  if (board) {
    var dragged = null;
    board.querySelectorAll("[data-widget]").forEach(function (widget) {
      widget.setAttribute("draggable", "true");
      widget.addEventListener("dragstart", function (event) {
        dragged = widget;
        widget.classList.add("dragging");
        event.dataTransfer.effectAllowed = "move";
        event.dataTransfer.setData("text/plain", widget.getAttribute("data-widget"));
      });
      widget.addEventListener("dragend", function () {
        widget.classList.remove("dragging");
        dragged = null;
        board.querySelectorAll(".drop-before, .drop-after").forEach(function (el) {
          el.classList.remove("drop-before", "drop-after");
        });
      });
    });
    board.addEventListener("dragover", function (event) {
      if (!dragged) return;
      var target = event.target.closest ? event.target.closest("[data-widget]") : null;
      if (!target || target === dragged) return;
      event.preventDefault();
      var rect = target.getBoundingClientRect();
      var before = target.classList.contains("wide") || rect.width > board.clientWidth * 0.75
        ? event.clientY < rect.top + rect.height / 2
        : event.clientX < rect.left + rect.width / 2;
      board.insertBefore(dragged, before ? target : target.nextSibling);
    });
    board.addEventListener("drop", function (event) { event.preventDefault(); });
    board.addEventListener("change", function (event) {
      var box = event.target;
      var widget = box.closest ? box.closest("[data-widget]") : null;
      if (!widget) return;
      if (box.hasAttribute("data-widget-show")) widget.classList.toggle("off", !box.checked);
      if (box.hasAttribute("data-widget-wide")) widget.classList.toggle("wide", box.checked);
    });
  }

  // Print buttons.
  document.addEventListener("click", function (event) {
    var el = event.target.closest ? event.target.closest("[data-print]") : null;
    if (el) { event.preventDefault(); window.print(); }
  });

  // Select-all checkbox for bulk editing.
  document.querySelectorAll("[data-select-all]").forEach(function (box) {
    box.addEventListener("change", function () {
      var form = box.getAttribute("data-select-all");
      document.querySelectorAll('input[name="ids"][form="' + form + '"]').forEach(function (c) {
        c.checked = box.checked;
      });
    });
  });

  // Show only the input that belongs to the chosen bulk action.
  var bulkAction = document.getElementById("bulk-action");
  if (bulkAction) {
    var toggle = function () {
      document.querySelectorAll("[data-bulk-param]").forEach(function (el) {
        el.hidden = el.getAttribute("data-bulk-param") !== bulkAction.value;
      });
    };
    bulkAction.addEventListener("change", toggle);
    toggle();
  }

  // Autosave for the protocol editor.
  var autosaveForm = document.querySelector("form[data-autosave]");
  var dirty = false;
  var timer = null;
  var saving = null;
  var statusEl = document.querySelector("[data-autosave-status]");

  function setStatus(text, isError) {
    if (!statusEl) return;
    statusEl.textContent = text;
    statusEl.classList.toggle("error", !!isError);
  }

  function save() {
    if (!autosaveForm) return Promise.resolve(true);
    clearTimeout(timer);
    if (!dirty) return saving || Promise.resolve(true);
    dirty = false;
    setStatus("Speichert …");
    saving = fetch(autosaveForm.getAttribute("action"), {
      method: "POST",
      body: new FormData(autosaveForm),
      credentials: "same-origin",
      headers: { "X-Autosave": "1", "X-CSRF-Token": csrf }
    }).then(function (response) {
      if (response.ok) {
        var now = new Date();
        setStatus("Gespeichert um " + now.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" }));
        return true;
      }
      return response.json().catch(function () { return {}; }).then(function (body) {
        dirty = true;
        setStatus("Nicht gespeichert: " + (body.error || "Fehler " + response.status), true);
        return false;
      });
    }).catch(function () {
      dirty = true;
      setStatus("Nicht gespeichert: keine Verbindung", true);
      return false;
    }).finally(function () { saving = null; });
    return saving;
  }

  if (autosaveForm) {
    autosaveForm.addEventListener("input", function () {
      dirty = true;
      setStatus("Ungespeicherte Änderungen");
      clearTimeout(timer);
      timer = setTimeout(save, 1500);
    });
    window.addEventListener("beforeunload", function (event) {
      if (dirty) { event.preventDefault(); event.returnValue = ""; }
    });
  }

  // One submit handler: confirmations, bulk checks and flushing the autosave.
  document.addEventListener("submit", function (event) {
    var form = event.target;
    var submitter = event.submitter || null;
    if (form.dataset.pass === "1") { form.dataset.pass = ""; return; }

    var question = (submitter && submitter.dataset.confirm) || form.dataset.confirm;
    if (form.id === "bulk") {
      var checked = document.querySelectorAll('input[name="ids"][form="bulk"]:checked').length;
      if (!checked) { event.preventDefault(); window.alert("Bitte zuerst Aufgaben auswählen."); return; }
      if (bulkAction && bulkAction.value === "loeschen") {
        question = checked + " Aufgabe(n) endgültig löschen?";
      }
    }
    if (question && !window.confirm(question)) { event.preventDefault(); return; }

    if (!autosaveForm) return;
    var ownForm = form === autosaveForm || (submitter && submitter.form === autosaveForm);
    if (ownForm) { dirty = false; clearTimeout(timer); return; }
    if (dirty || saving) {
      event.preventDefault();
      save().then(function (ok) {
        if (!ok && !window.confirm("Die Notizen konnten nicht gespeichert werden. Trotzdem fortfahren?")) return;
        dirty = false;
        form.dataset.pass = "1";
        if (form.requestSubmit) form.requestSubmit(submitter || undefined); else form.submit();
      });
    }
  }, true);
})();
