/* Gesundheits-Cockpit: small helpers on top of app.js and komponenten.js (shared with the
   Projekt-Cockpit). Everything works without JavaScript; this only adds:
   1. activity rings fill up when the page opens
   2. chart read-out: hover or tap shows the nearest value
   3. upload of the Apple Health export with progress, then live import status
   4. pickers on the analysis pages send themselves, print button for reports
   5. the 3D skyline: grows week by week, read-out per day, switch between steps and load,
      totals count up
   6. goal forecast: the slider recomputes the chance (same normal distribution as prognose.py)
   7. prepared questions: the answer types itself
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

  // Pickers send themselves; print button
  document.querySelectorAll("form[data-auto-submit]").forEach(function (f) {
    f.addEventListener("change", function () { f.submit(); });
  });
  document.querySelectorAll("[data-drucken]").forEach(function (b) {
    b.addEventListener("click", function () { window.print(); });
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

  // 5. Skyline
  function countUp(el) {
    var target = parseFloat(el.getAttribute("data-count"));
    var decimals = parseInt(el.getAttribute("data-decimals"), 10) || 0;
    if (reduce || isNaN(target) || !window.requestAnimationFrame) return;
    var format = function (v) {
      return v.toLocaleString("de-DE", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
    };
    var start = null;
    function step(t) {
      if (start === null) start = t;
      var p = Math.min((t - start) / 1400, 1);
      el.textContent = format(target * (1 - Math.pow(1 - p, 3)));
      if (p < 1) window.requestAnimationFrame(step);
    }
    window.requestAnimationFrame(step);
  }

  function grow(view) {
    view.querySelectorAll("[data-count]").forEach(countUp);
    if (reduce) return;
    view.querySelectorAll(".sk-bar").forEach(function (bar) {
      if (!bar.animate) return;
      var w = parseInt(bar.getAttribute("data-w"), 10) || 0;
      bar.animate([{ transform: "scaleY(0.02)", opacity: 0.2 }, { transform: "scaleY(1)", opacity: 1 }],
        { duration: 650, delay: 200 + w * 22, easing: "cubic-bezier(.2,.8,.2,1)", fill: "backwards" });
    });
  }

  document.querySelectorAll("[data-sky]").forEach(function (card) {
    var views = Array.prototype.slice.call(card.querySelectorAll("[data-sky-ansicht]"));
    var buttons = Array.prototype.slice.call(card.querySelectorAll("[data-sky-zeige]"));
    views.forEach(function (v) { if (!v.hidden) grow(v); });

    buttons.forEach(function (button) {
      button.addEventListener("click", function (e) {
        var key = button.getAttribute("data-sky-zeige");
        var target = views.filter(function (v) { return v.getAttribute("data-sky-ansicht") === key; })[0];
        if (!target) return;
        e.preventDefault();
        if (!target.hidden) return;
        views.forEach(function (v) { v.hidden = v !== target; });
        buttons.forEach(function (b) { b.setAttribute("aria-pressed", b === button ? "true" : "false"); });
        grow(target);
      });
    });

    views.forEach(function (view) {
      var figure = view.querySelector("[data-skyline]");
      var tip = view.querySelector("[data-sky-tip]");
      if (!figure || !tip) return;
      var active = null;
      function hide() {
        tip.hidden = true;
        if (active) active.classList.remove("aktiv");
        active = null;
      }
      function show(e) {
        var bar = e.target.closest ? e.target.closest("[data-tip]") : null;
        if (!bar) { hide(); return; }
        if (active !== bar) {
          if (active) active.classList.remove("aktiv");
          active = bar;
          bar.classList.add("aktiv");
          var parts = bar.getAttribute("data-tip").split("|");
          tip.textContent = "";
          var title = document.createElement("strong");
          title.textContent = parts[0];
          tip.appendChild(title);
          for (var i = 1; i + 1 < parts.length; i += 2) {
            var line = document.createElement("span");
            var value = document.createElement("b");
            value.textContent = parts[i];
            line.appendChild(value);
            line.appendChild(document.createTextNode(parts[i + 1]));
            tip.appendChild(line);
          }
        }
        var box = figure.getBoundingClientRect();
        var x = Math.min(Math.max(e.clientX - box.left, 95), box.width - 95);
        tip.style.left = x + "px";
        tip.style.top = Math.max(e.clientY - box.top, 70) + "px";
        tip.hidden = false;
      }
      figure.addEventListener("pointermove", show);
      figure.addEventListener("pointerdown", show);
      figure.addEventListener("pointerleave", hide);
    });
  });

  // Switches between views inside a card (forecast kinds): links without JavaScript.
  function views(card, buttonAttr, viewAttr, onShow) {
    var panels = Array.prototype.slice.call(card.querySelectorAll("[" + viewAttr + "]"));
    var buttons = Array.prototype.slice.call(card.querySelectorAll("[" + buttonAttr + "]"));
    buttons.forEach(function (button) {
      button.addEventListener("click", function (e) {
        var key = button.getAttribute(buttonAttr);
        var target = panels.filter(function (p) { return p.getAttribute(viewAttr) === key; })[0];
        if (!target) return;
        e.preventDefault();
        panels.forEach(function (p) { p.hidden = p !== target; });
        buttons.forEach(function (b) {
          var on = b === button;
          b.setAttribute("aria-pressed", on ? "true" : "false");
          if (on) b.setAttribute("aria-current", "true"); else b.removeAttribute("aria-current");
        });
        if (onShow) onShow(target, key);
      });
    });
  }

  // 6. Goal forecast
  function erf(x) {  // Abramowitz and Stegun 7.1.26, error below 1.5e-7
    var sign = x < 0 ? -1 : 1;
    x = Math.abs(x);
    var t = 1 / (1 + 0.3275911 * x);
    var y = 1 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * Math.exp(-x * x);
    return sign * y;
  }
  function fmt(v, decimals) {
    return v.toLocaleString("de-DE", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
  }
  function signed(v, decimals) {
    var r = Number(v.toFixed(decimals));
    if (r === 0) return "±0";
    return (r > 0 ? "+" : "−") + fmt(Math.abs(r), decimals);
  }
  function verdict(p) {
    return p < 20 ? "unwahrscheinlich" : p < 45 ? "eher nicht" : p < 70 ? "gut möglich" : "sehr wahrscheinlich";
  }

  document.querySelectorAll("[data-prognosen]").forEach(function (card) {
    views(card, "data-prognose-zeige", "data-prognose");
    card.querySelectorAll("[data-prognose]").forEach(function (panel) {
      var slider = panel.querySelector("[data-pg-regler]");
      if (!slider) return;
      var num = function (name) { return parseFloat(panel.getAttribute(name)); };
      var mean = num("data-mean"), sd = num("data-sd"), lo = num("data-lo"), hi = num("data-hi");
      var decimals = parseInt(panel.getAttribute("data-decimals"), 10) || 0;
      var down = panel.getAttribute("data-direction") === "down";
      var needBase = num("data-need-base"), needSpan = num("data-need-span");
      var needDecimals = parseInt(panel.getAttribute("data-need-decimals"), 10) || 0;
      var unit = panel.getAttribute("data-unit") || "";
      var W = 300, H = 120;
      function x(v) { return (v - lo) / (hi - lo) * W; }
      function y(v) { return H - Math.exp(-0.5 * Math.pow((v - mean) / sd, 2)) * (H - 8); }
      function update() {
        var goal = parseFloat(slider.value);
        var z = (goal - mean) / sd;
        var below = 0.5 * (1 + erf(z / Math.SQRT2));
        var p = Math.round((down ? below : 1 - below) * 100);
        panel.querySelector("[data-pg-prozent]").textContent = p;
        panel.querySelector("[data-pg-urteil]").textContent = verdict(p);
        panel.querySelector("[data-pg-ziel]").textContent = fmt(goal, decimals) + " " + unit;
        panel.querySelector("[data-pg-ausgabe]").textContent = fmt(goal, decimals) + " " + unit;
        panel.querySelector("[data-pg-noetig]").textContent = signed((goal - needBase) / needSpan, needDecimals);
        var g = Math.min(Math.max(goal, lo), hi);
        var edge = [];
        for (var i = 0; i <= 80; i++) {
          var v = lo + (hi - lo) * i / 80;
          if (down ? v < g : v > g) edge.push(v);
        }
        if (down) edge.push(g); else edge.unshift(g);
        var d = "M" + x(edge[0]).toFixed(1) + " " + H;
        edge.forEach(function (v) { d += " L" + x(v).toFixed(1) + " " + y(v).toFixed(1); });
        d += " L" + x(edge[edge.length - 1]).toFixed(1) + " " + H + " Z";
        panel.querySelector("[data-glocke-flaeche]").setAttribute("d", d);
        panel.querySelector("[data-glocke-ziel]").setAttribute("d", "M" + x(g).toFixed(1) + " 0 V" + H);
      }
      slider.addEventListener("input", update);
    });
  });

  // 7. Prepared questions
  document.querySelectorAll("[data-fragen]").forEach(function (card) {
    var chips = Array.prototype.slice.call(card.querySelectorAll("[data-frage]"));
    var answers = Array.prototype.slice.call(card.querySelectorAll("[data-antwort]"));
    var timer = null;
    function type(answer) {
      var lines = Array.prototype.slice.call(answer.querySelectorAll("p"));
      var texts = lines.map(function (l) { return l.getAttribute("data-voll") || l.textContent; });
      lines.forEach(function (l, i) { l.setAttribute("data-voll", texts[i]); });
      if (timer) clearInterval(timer);
      if (reduce) { lines.forEach(function (l, i) { l.textContent = texts[i]; }); return; }
      lines.forEach(function (l) { l.textContent = ""; l.classList.remove("cursor"); });
      var line = 0, pos = 0;
      timer = setInterval(function () {
        if (line >= lines.length) {
          clearInterval(timer);
          lines[lines.length - 1].classList.remove("cursor");
          return;
        }
        lines[line].classList.add("cursor");
        pos += line === 0 ? 1 : 3;
        lines[line].textContent = texts[line].slice(0, pos);
        if (pos >= texts[line].length) {
          if (line < lines.length - 1) lines[line].classList.remove("cursor");
          line++;
          pos = 0;
        }
      }, 18);
    }
    chips.forEach(function (chip) {
      chip.addEventListener("click", function (e) {
        var key = chip.getAttribute("data-frage");
        var answer = answers.filter(function (a) { return a.getAttribute("data-antwort") === key; })[0];
        if (!answer) return;
        e.preventDefault();
        chips.forEach(function (c) { c.setAttribute("aria-pressed", c === chip ? "true" : "false"); });
        answers.forEach(function (a) { a.hidden = a !== answer; });
        type(answer);
      });
    });
  });
})();
