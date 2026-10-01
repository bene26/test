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

  // Design picker: preview the chosen design right away, saving stays a normal POST.
  document.querySelectorAll('.theme-picker input[name="theme"]').forEach(function (radio) {
    radio.addEventListener("change", function () {
      if (!radio.checked) return;
      document.documentElement.setAttribute("data-theme", radio.value);
      var hint = document.querySelector("[data-theme-hint]");
      if (hint) hint.hidden = false;
    });
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
