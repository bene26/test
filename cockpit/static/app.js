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
