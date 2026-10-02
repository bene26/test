/* Gesundheits-Cockpit: small helpers on top of app.js and komponenten.js (shared with the
   Projekt-Cockpit). Everything works without JavaScript; this only adds:
   1. activity rings fill up when the page opens
   2. chart read-out: hover or tap shows the nearest value
   3. upload of the Apple Health export with progress, then live import status
   No inline styles in the markup (CSP); positions are set through the CSSOM. */
(function () {
  "use strict";
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // 1. Rings
  if (!reduce) {
    document.querySelectorAll("[data-ring]").forEach(function (ring, i) {
      var target = parseFloat(ring.getAttribute("data-ring")) || 0;
      if (!ring.animate || !target) return;
      ring.animate(
        [{ strokeDasharray: "0 100" }, { strokeDasharray: target + " 100" }],
        { duration: 1100, delay: 120 * i, easing: "cubic-bezier(.2,.8,.2,1)", fill: "backwards" });
    });
  }

  // 2. Chart read-out
  document.querySelectorAll("[data-chart]").forEach(function (chart) {
    var plot = chart.querySelector(".chart-plot");
    var tip = chart.querySelector("[data-chart-tip]");
    var points = Array.prototype.slice.call(chart.querySelectorAll("[data-x][data-tip]"));
    if (!plot || !tip || !points.length) return;
    var xs = points.map(function (p) { return parseFloat(p.getAttribute("data-x")); });
    var active = null;

    function show(clientX) {
      var box = plot.getBoundingClientRect();
      var fx = (clientX - box.left) / box.width;
      var best = 0;
      for (var i = 1; i < xs.length; i++) {
        if (Math.abs(xs[i] - fx) < Math.abs(xs[best] - fx)) best = i;
      }
      var point = points[best];
      if (active && active !== point) active.classList.remove("aktiv");
      active = point;
      point.classList.add("aktiv");
      var y = parseFloat(point.getAttribute("data-y"));
      tip.textContent = point.getAttribute("data-tip");
      tip.hidden = false;
      var left = Math.min(Math.max(xs[best] * box.width, 70), box.width - 70);
      tip.style.left = left + "px";
      tip.style.top = (isNaN(y) ? 0 : y * box.height) + "px";
    }
    function hide() {
      tip.hidden = true;
      if (active) active.classList.remove("aktiv");
      active = null;
    }
    plot.addEventListener("pointermove", function (e) { show(e.clientX); });
    plot.addEventListener("pointerdown", function (e) { show(e.clientX); });
    plot.addEventListener("pointerleave", hide);
  });

  // 3. Upload with progress, then follow the import
  var form = document.querySelector("[data-upload]");
  if (form && window.FormData && window.XMLHttpRequest) {
    var input = form.querySelector("input[type=file]");
    var nameEl = form.querySelector("[data-upload-name]");
    var bar = form.querySelector("[data-upload-progress]");
    var statusEl = form.querySelector("[data-upload-status]");
    var button = form.querySelector("button[type=submit]");
    input.addEventListener("change", function () {
      if (input.files && input.files[0]) {
        var mb = input.files[0].size / 1048576;
        nameEl.textContent = input.files[0].name + " (" + (mb < 10 ? mb.toFixed(1) : Math.round(mb)) + " MB)";
      }
    });
    form.addEventListener("submit", function (event) {
      if (!input.files || !input.files[0]) return;
      event.preventDefault();
      var xhr = new XMLHttpRequest();
      xhr.open("POST", form.action);
      xhr.setRequestHeader("X-Gesundheit-Ajax", "1");
      xhr.responseType = "json";
      bar.hidden = false;
      bar.value = 0;
      button.disabled = true;
      statusEl.textContent = "Lädt hoch …";
      xhr.upload.addEventListener("progress", function (e) {
        if (e.lengthComputable) {
          bar.value = Math.round(e.loaded / e.total * 100);
          statusEl.textContent = "Lädt hoch … " + bar.value + " %";
        }
      });
      xhr.addEventListener("load", function () {
        var data = xhr.response || {};
        if (xhr.status === 200 && data.ok) {
          statusEl.textContent = data.nachricht;
          bar.value = 0;
          follow(data.status_url, function (row) {
            bar.value = row.progress;
            statusEl.textContent = row.status === "laeuft" ? "Liest ein … " + row.progress + " %" : "Wartet …";
          });
        } else {
          statusEl.textContent = data.nachricht || data.error || "Hochladen fehlgeschlagen.";
          bar.hidden = true;
          button.disabled = false;
        }
      });
      xhr.addEventListener("error", function () {
        statusEl.textContent = "Verbindung unterbrochen. Bitte noch einmal versuchen.";
        bar.hidden = true;
        button.disabled = false;
      });
      xhr.send(new FormData(form));
    });
  }

  function follow(url, onUpdate) {
    var timer = setInterval(function () {
      fetch(url, { headers: { Accept: "application/json" }, credentials: "same-origin" })
        .then(function (r) { return r.json(); })
        .then(function (row) {
          if (row.status === "fertig" || row.status === "fehler") {
            clearInterval(timer);
            window.location.reload();
          } else {
            onUpdate(row);
          }
        })
        .catch(function () { /* try again with the next tick */ });
    }, 2000);
  }

  document.querySelectorAll("[data-import-status]").forEach(function (row) {
    var bar = row.querySelector("progress");
    var text = row.querySelector("[data-import-text]");
    follow(row.getAttribute("data-import-status"), function (data) {
      if (bar) bar.value = data.progress;
      if (text) text.textContent = data.status === "laeuft" ? "liest … " + data.progress + " %" : "wartet";
    });
  });
})();
