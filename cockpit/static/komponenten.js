// Komponenten für das Projekt-Cockpit-Design:
//   1. Fallblatt-Zahlen   [data-fallblatt]        Zahlen klappern wie auf einer Abfahrtstafel
//   2. Schlüssel          [data-schluessel]       jede Passwort-Regel schneidet einen Zahn, das Schloss geht auf
//   3. Kassenbon          [data-bon]              ein Beleg wird Zeile für Zeile gedruckt
//   4. Karteikasten       [data-kartei]           Strg+K / ⌘K: suchen und springen, Karten klappen wie in einer Kartei
//   5. Papierflieger      [data-flieger]          ein Formular faltet sich beim Absenden zum Flieger
//   6. Orb                [data-orb]              Eingabebox mit animierter Kugel (12 Stile)
// Ohne Bibliotheken. Funktioniert mit strenger Content-Security-Policy: im HTML stehen keine
// Inline-Styles, Bewegungen laufen über CSS-Klassen, die CSSOM und die Web Animations API.
// Wer im System „Bewegung reduzieren“ eingestellt hat, bekommt alles ohne Animation.
(function () {
  "use strict";

  const motion = !(window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches);
  const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const $ = (sel, root) => (root || document).querySelector(sel);
  const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));
  const SVG = "http://www.w3.org/2000/svg";

  function make(tag, cls, text) {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text != null) node.textContent = text;
    return node;
  }
  function svg(tag, attrs, parent) {
    const node = document.createElementNS(SVG, tag);
    for (const key in attrs) node.setAttribute(key, attrs[key]);
    if (parent) parent.appendChild(node);
    return node;
  }
  function anim(node, frames, options) {
    if (!motion || !node.animate) return Promise.resolve();
    return node.animate(frames, options).finished.catch(() => {});
  }
  function store(key, value) { try { localStorage.setItem(key, value); } catch (e) { /* privater Modus */ } }
  function fetchKey(key) { try { return localStorage.getItem(key); } catch (e) { return null; } }
  function typing(target) {
    return target && (target.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName));
  }

  /* ---------- 1. Fallblatt-Zahlen ---------- */

  const FB_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789%+-./";

  function fbHalf(cls, ch) {
    const half = make("span", "fb-half " + cls);
    half.appendChild(make("span", "fb-ch", ch));
    return half;
  }
  function fbTile(ch) {
    const tile = make("span", "fb-tile");
    tile.append(fbHalf("fb-top", ch), fbHalf("fb-bot", ch), fbHalf("fb-top fb-flap", ch),
      fbHalf("fb-bot fb-flap", ch));
    tile.dataset.ch = ch;
    return tile;
  }
  function fbShow(tile, ch) {
    $$(".fb-ch", tile).forEach((node) => { node.textContent = ch; });
    tile.dataset.ch = ch;
  }
  async function fbFlip(tile, ch, ms) {
    const [top, bot, fallA, fallB] = tile.children;
    const old = tile.dataset.ch;
    top.firstChild.textContent = ch;
    bot.firstChild.textContent = old;
    fallA.firstChild.textContent = old;
    fallB.firstChild.textContent = ch;
    tile.dataset.ch = ch;
    fallA.classList.add("an");
    await anim(fallA, [{ transform: "rotateX(0deg)" }, { transform: "rotateX(-90deg)" }],
      { duration: ms / 2, easing: "ease-in" });
    fallA.classList.remove("an");
    fallB.classList.add("an");
    await anim(fallB, [{ transform: "rotateX(90deg)" }, { transform: "rotateX(0deg)" }],
      { duration: ms / 2, easing: "cubic-bezier(.3,1.6,.5,1)" });
    bot.firstChild.textContent = ch;
    fallB.classList.remove("an");
  }
  async function fbRoll(tile, target, steps, ms) {
    for (let i = 0; i < steps; i++) {
      await fbFlip(tile, FB_CHARS[Math.floor(Math.random() * FB_CHARS.length)], ms);
    }
    await fbFlip(tile, target, ms * 2.4);
  }

  // Turns the text of one element into tiles and lets them clatter to the value.
  function fbBuild(value, delay) {
    if (value.fbNodes) return;
    const text = value.textContent.replace(/\s+/g, " ").trim();
    value.fbNodes = Array.from(value.childNodes);
    value.classList.add("fb-board");
    const tiles = Array.from(text, () => fbTile(" "));
    tiles.forEach((tile) => tile.setAttribute("aria-hidden", "true"));
    value.replaceChildren(make("span", "sr-only", text), ...tiles);
    if (!motion) { tiles.forEach((tile, i) => fbShow(tile, text[i])); return; }
    tiles.forEach((tile, i) => {
      wait(delay + i * 45).then(() => fbRoll(tile, text[i], 3 + Math.floor(Math.random() * 4) + i, 64));
    });
  }
  function fbRestore(value) {
    if (!value.fbNodes) return;
    value.replaceChildren(...value.fbNodes);
    value.classList.remove("fb-board");
    delete value.fbNodes;
  }
  // Public: set a new text; only changed tiles flip.
  async function fbSet(value, text) {
    if (!value.fbNodes || value.querySelectorAll(".fb-tile").length !== text.length) {
      fbRestore(value);
      value.textContent = text;
      fbBuild(value, 0);
      return;
    }
    value.querySelector(".sr-only").textContent = text;
    $$(".fb-tile", value).forEach((tile, i) => {
      if (tile.dataset.ch !== text[i]) fbRoll(tile, text[i], motion ? 1 + Math.floor(Math.random() * 3) : 0, 70);
    });
  }
  function fbValues(scope) {
    return scope.matches("[data-fallblatt-wert]") ? [scope] : $$("[data-fallblatt-wert], .value", scope);
  }
  function fbRefresh() {
    $$("[data-fallblatt]").forEach((scope, n) => {
      const on = getComputedStyle(scope).getPropertyValue("--fallblatt").trim() === "an";
      fbValues(scope).forEach((value, i) => (on ? fbBuild(value, n * 120 + i * 140) : fbRestore(value)));
    });
  }

  /* ---------- 2. Schlüssel: Passwort-Regeln schneiden Zähne ---------- */

  const RULES = [
    ["laenge", (p) => p.length >= 12],
    ["mix", (p) => /[a-zäöüß]/.test(p) && /[A-ZÄÖÜ]/.test(p)],
    ["zahl", (p) => /\d/.test(p)],
    ["zeichen", (p) => /[^A-Za-zÄÖÜäöüß0-9]/.test(p)],
    ["lang", (p) => p.length >= 16],
  ];
  const STRENGTH = ["", "schwach", "mäßig", "gut", "stark", "sehr stark"];
  const TEETH = [150, 176, 202, 228, 254];
  const DEPTH = [9, 5, 11, 7, 10];

  function bladePath(d) {
    let path = "M116 86";
    TEETH.forEach((x, i) => {
      const k = d[i].toFixed(2);
      path += ` L${x - 10} 86 L${x - 4} ${86 + +k} L${x + 4} ${86 + +k} L${x + 10} 86`;
    });
    return path + " L290 86 L302 95 L290 104 L116 104 Z";
  }

  function keyArt(box) {
    const id = "s" + Math.random().toString(36).slice(2, 8);
    const s = svg("svg", { viewBox: "0 0 440 190", class: "s-svg", "aria-hidden": "true", focusable: "false" });
    const defs = svg("defs", {}, s);
    const metal = svg("linearGradient", { id: id + "m", x1: 0, y1: 0, x2: 0, y2: 1 }, defs);
    [[0, "#fdfdff"], [0.42, "#cfd1d9"], [0.55, "#eceef3"], [1, "#8b8e99"]].forEach(([o, c]) =>
      svg("stop", { offset: o, "stop-color": c }, metal));
    const body = svg("linearGradient", { id: id + "b", x1: 0, y1: 0, x2: 0, y2: 1 }, defs);
    [[0, "#76747f"], [1, "#3b3a45"]].forEach(([o, c]) => svg("stop", { offset: o, "stop-color": c }, body));
    const clip = svg("clipPath", { id: id + "c" }, defs);
    svg("rect", { x: 0, y: 0, width: 386, height: 190 }, clip);

    svg("ellipse", { cx: 220, cy: 176, rx: 175, ry: 7, class: "s-schatten" }, s);
    const holder = svg("g", { "clip-path": `url(#${id}c)` }, s);
    const key = svg("g", { class: "s-key" }, holder);
    const bow = svg("g", { class: "s-bow" }, key);
    svg("path", {
      d: "M22 95a40 40 0 1 0 80 0a40 40 0 1 0 -80 0z M36 95a11 11 0 1 0 22 0a11 11 0 1 0 -22 0z",
      fill: `url(#${id}m)`, "fill-rule": "evenodd",
    }, bow);
    svg("rect", { x: 100, y: 83, width: 18, height: 24, rx: 3, fill: `url(#${id}m)` }, key);
    const blade = svg("path", { d: bladePath([0, 0, 0, 0, 0]), fill: `url(#${id}m)` }, key);
    svg("path", { d: "M124 97 H284", class: "s-rille" }, key);
    const sparks = svg("g", { class: "s-spaene" }, key);

    const lock = svg("g", { class: "s-lock" }, s);
    svg("path", { d: "M320 104 V70 a26 26 0 0 1 52 0 V104", class: "s-buegel", stroke: `url(#${id}m)` }, lock);
    svg("rect", { x: 296, y: 86, width: 10, height: 18, rx: 2, class: "s-zylinder" }, lock);
    svg("rect", { x: 302, y: 98, width: 86, height: 76, rx: 12, fill: `url(#${id}b)` }, lock);
    for (let y = 112; y < 168; y += 9) svg("path", { d: `M310 ${y} H380`, class: "s-rippe" }, lock);
    box.replaceChildren(s);
    return { blade, sparks };
  }

  function schluesselInit(root) {
    const pw = document.getElementById(root.dataset.passwort);
    if (!pw) return;
    const repeat = root.dataset.wiederholung ? document.getElementById(root.dataset.wiederholung) : null;
    const art = $("[data-schluessel-bild]", root);
    const parts = art ? keyArt(art) : null;
    const strength = $("[data-staerke]", root);
    const status = $("[data-schluessel-status]", root);
    const rules = new Map($$("[data-regel]", root).map((li) => [li.dataset.regel, li]));
    const depth = [0, 0, 0, 0, 0];
    let target = [0, 0, 0, 0, 0];
    let raf = 0;

    function sparks(x) {
      if (!motion || !parts) return;
      for (let i = 0; i < 7; i++) {
        const dot = svg("circle", { cx: x, cy: 88, r: 1 + Math.random() * 1.4 }, parts.sparks);
        anim(dot, [
          { transform: "translate(0,0)", opacity: 1 },
          { transform: `translate(${(Math.random() - 0.5) * 34}px, ${18 + Math.random() * 40}px)`, opacity: 0 },
        ], { duration: 500 + Math.random() * 400, easing: "cubic-bezier(.2,.6,.4,1)" }).then(() => dot.remove());
      }
    }
    function step() {
      raf = 0;
      let moving = false;
      depth.forEach((d, i) => {
        const next = motion ? d + (target[i] - d) * 0.16 : target[i];
        depth[i] = Math.abs(target[i] - next) < 0.05 ? target[i] : next;
        if (depth[i] !== target[i]) moving = true;
      });
      if (parts) parts.blade.setAttribute("d", bladePath(depth));
      if (moving) raf = requestAnimationFrame(step);
    }
    function update() {
      const p = pw.value;
      const met = RULES.map(([, test]) => test(p));
      const score = met.filter(Boolean).length;
      RULES.forEach(([name], i) => {
        const li = rules.get(name);
        if (li) li.classList.toggle("ok", met[i]);
        const cut = met[i] ? DEPTH[i] : 0;
        if (cut && !target[i]) wait(i * 90).then(() => sparks(TEETH[i]));
        target[i] = cut;
      });
      if (strength) {
        strength.textContent = p ? `Stärke: ${STRENGTH[score] || "sehr schwach"}, ${score} von 5` : "Stärke: 0 von 5";
      }
      const long = met[0];
      const same = !repeat || repeat.value === p;
      const open = long && same;
      root.classList.toggle("offen", open);
      if (status) {
        status.textContent = open ? "Entsperrt"
          : long && repeat && repeat.value ? "Die Wiederholung stimmt noch nicht."
            : long && repeat ? "Jetzt wiederholen."
              : "Mindestens 12 Zeichen öffnen das Schloss.";
      }
      if (!raf) raf = requestAnimationFrame(step);
    }
    pw.addEventListener("input", update);
    if (repeat) repeat.addEventListener("input", update);
    update();
  }

  /* ---------- 3. Kassenbon ---------- */

  function barcode(node) {
    let seed = 7;
    for (const ch of node.dataset.bonBarcode || "0") seed = (seed * 31 + ch.charCodeAt(0)) >>> 0;
    const s = svg("svg", { viewBox: "0 0 200 36", preserveAspectRatio: "none", "aria-hidden": "true" });
    let x = 0;
    while (x < 196) {
      seed = (Math.imul(seed, 1103515245) + 12345) >>> 0;
      const w = 1 + ((seed >>> 16) % 3);
      if ((seed >>> 9) & 1 || x < 3) svg("rect", { x, y: 0, width: w, height: 36 }, s);
      x += w + ((seed >>> 12) & 1);
    }
    node.replaceChildren(s);
  }

  function bonInit(root) {
    const paper = $("[data-bon-papier]", root);
    if (!paper) return;
    const roll = paper.parentNode;
    const status = $("[data-bon-status]", root);
    const plans = $$("[data-bon-plan]", root);
    const cycles = $$("[data-bon-takt]", root);
    const views = $$("[data-bon-ansicht]", root);
    const cta = $("[data-bon-cta]", root);
    const templates = $$("template[data-bon-vorlage]", root);
    let job = 0;
    let printed = false;

    const money = (v) => v.toLocaleString("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
      + " " + (root.dataset.waehrung || "€");
    const short = (v) => (Number.isInteger(v) ? String(v) : v.toLocaleString("de-DE", { maximumFractionDigits: 2 }))
      + " " + (root.dataset.waehrung || "€");
    function line(cls, left, right) {
      const r = make("div", "bon-zeile" + (cls ? " " + cls : ""));
      r.append(make("span", "", left));
      if (right != null) r.append(make("span", "", right));
      return r;
    }
    function yearly() { return (cycles.find((r) => r.checked) || {}).value === "jahr"; }
    function pricing() {
      const plan = plans.find((p) => p.checked) || plans[0];
      const off = parseFloat(root.dataset.rabatt || "20");
      const price = parseFloat(plan.dataset.preis);
      const name = plan.dataset.name;
      const year = yearly();
      const f = document.createDocumentFragment();
      const head = make("div", "bon-kopf");
      head.append(make("span", "bon-logo", (root.dataset.firma || "P").slice(0, 1)),
        make("strong", "", root.dataset.firma || "Ihre Firma"));
      f.append(head, line("bon-meta", "Bestellübersicht",
        new Date().toLocaleDateString("de-DE", { day: "2-digit", month: "short", year: "numeric" })));
      const plan1 = line("bon-plan", "Paket: ", year ? "jährlich" : "monatlich");
      plan1.firstChild.appendChild(make("b", "", name));
      f.append(make("div", "bon-trenn"), plan1);
      (plan.dataset.zeilen || "").split("|").filter(Boolean).forEach((text) => f.append(line("", text, "inkl.")));
      f.append(make("div", "bon-trenn"));
      if (year) {
        f.append(line("", `Zwischensumme, 12 × ${money(price)}`, money(price * 12)),
          line("bon-fett", `Jährlich −${off} %`, "−" + money(price * 12 * off / 100)));
      } else {
        f.append(line("", "Zwischensumme", money(price)),
          line("bon-leise", "Jährlich gespart wären", money(price * 12 * off / 100)));
      }
      const each = year ? price * (1 - off / 100) : price;
      const total = make("div", "bon-summe");
      const amount = make("span", "bon-betrag", money(each));
      amount.appendChild(make("small", "", " /Monat"));
      total.append(make("span", "", "Gesamt"), amount);
      f.append(make("div", "bon-trenn doppelt"), total,
        line("bon-leise bon-rechts", year ? `jährlich abgerechnet: ${money(each * 12)}` : "monatlich abgerechnet"));
      const code = make("div", "bon-barcode");
      code.dataset.bonBarcode = name + (year ? "J" : "M") + price;
      f.append(code, make("p", "bon-danke", "Vielen Dank"));
      return f;
    }
    function fragment() {
      if (plans.length) return pricing();
      const view = (views.find((r) => r.checked) || views[0] || {}).value;
      const tpl = templates.find((t) => t.dataset.bonVorlage === view) || templates[0];
      return tpl ? tpl.content.cloneNode(true) : document.createDocumentFragment();
    }
    function labels() {
      if (!plans.length) return;
      const off = yearly() ? 1 - parseFloat(root.dataset.rabatt || "20") / 100 : 1;
      plans.forEach((p) => {
        const out = $("[data-bon-betrag]", p.closest("label") || p.parentNode);
        if (out) out.textContent = short(Math.round(parseFloat(p.dataset.preis) * off * 100) / 100);
      });
      const plan = plans.find((p) => p.checked) || plans[0];
      if (cta) cta.firstChild.textContent = `${plan.dataset.name} wählen `;
    }
    function tear() {
      const copy = roll.cloneNode(true);
      copy.classList.add("bon-abriss");
      copy.setAttribute("aria-hidden", "true");
      $$("[data-bon-papier]", copy).forEach((n) => n.removeAttribute("data-bon-papier"));
      copy.style.top = roll.offsetTop + "px";
      copy.style.left = roll.offsetLeft + "px";
      copy.style.width = roll.offsetWidth + "px";
      roll.parentNode.appendChild(copy);
      anim(copy, [
        { transform: "translate(0,0) rotate(0)", opacity: 1 },
        { transform: "translate(-14px, 240px) rotate(-9deg)", opacity: 0 },
      ], { duration: 700, easing: "cubic-bezier(.5,0,.8,.5)" }).then(() => copy.remove());
    }
    function say(text) { if (status) status.textContent = text; }
    async function print() {
      const my = ++job;
      if (printed && paper.childElementCount && motion) tear();
      printed = true;
      const inner = make("div", "bon-inhalt");
      inner.appendChild(fragment());
      paper.replaceChildren(inner);
      $$("[data-bon-barcode]", inner).forEach(barcode);
      if (!motion) return;
      root.classList.add("druckt");
      say("Druckt …");
      let h = 0;
      paper.style.height = "0px";
      for (const row of Array.from(inner.children)) {
        await wait(40 + Math.random() * 120);
        if (my !== job) return;
        const next = row.offsetTop + row.offsetHeight + 10;
        if (next <= h) continue;
        await anim(paper, [{ height: h + "px" }, { height: next + "px" }],
          { duration: 80 + (next - h) * 2.4, easing: "cubic-bezier(.3,.7,.4,1)" });
        if (my !== job) return;
        h = next;
        paper.style.height = h + "px";
      }
      paper.style.height = "";
      root.classList.remove("druckt");
      say("Bereit");
    }
    [...plans, ...cycles, ...views].forEach((input) => input.addEventListener("change", () => { labels(); print(); }));
    labels();
    // Print when the receipt comes into view, so the animation is seen.
    if ("IntersectionObserver" in window && motion) {
      const io = new IntersectionObserver((entries) => {
        if (entries.some((e) => e.isIntersecting)) { io.disconnect(); print(); }
      }, { threshold: 0.3 });
      io.observe(roll);
    } else {
      print();
    }
  }

  /* ---------- 4. Karteikasten: Strg+K ---------- */

  const LEAN = 6;
  const DEPTH_STEP = 36;
  const RISE = 27;
  const FALL = 82;

  function fold(text) {
    return text.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/ß/g, "ss");
  }

  function karteiInit(root) {
    const input = $("[data-kartei-eingabe]", root);
    const stack = $("[data-kartei-stapel]", root);
    const count = $("[data-kartei-zahl]", root);
    const stage = $("[data-kartei-buehne]", root) || stack;
    const searchUrl = root.dataset.karteiSuche || "";
    const entries = $$("[data-kartei-eintraege] a").map((a) => ({
      titel: a.textContent.trim(), url: a.getAttribute("href"), gruppe: a.dataset.gruppe || "Seiten",
      hinweis: a.dataset.hinweis || "", tasten: a.dataset.tasten || "",
    }));
    let items = [];
    let cards = [];
    let cur = 0;
    let lastFocus = null;
    let request = 0;
    let timer = 0;
    let wheelAt = 0;

    function card(item, i) {
      const a = make("a", "kartei-karte");
      a.href = item.url;
      a.id = "kk-" + i;
      a.tabIndex = -1;
      a.setAttribute("role", "option");
      const tab = make("span", "kk-reiter", item.gruppe);
      const title = make("strong", "kk-titel", item.titel);
      const hint = make("span", "kk-hinweis", item.hinweis);
      a.append(tab, title, hint);
      if (item.tasten) {
        const keys = make("span", "kk-tasten");
        item.tasten.split(" ").forEach((k) => keys.appendChild(make("kbd", "", k)));
        a.appendChild(keys);
      }
      a.addEventListener("click", (event) => {
        if (i !== cur) { event.preventDefault(); cur = i; place(); }
      });
      return a;
    }
    function place() {
      cards.forEach((c, i) => {
        const o = i - cur;
        let transform;
        let opacity;
        if (o >= 0) {
          transform = `translate3d(0, ${-RISE * o}px, ${-DEPTH_STEP * o}px) rotateX(${Math.min(o, 3) * LEAN}deg)`;
          opacity = o > 5 ? 0 : 1;
          c.style.setProperty("--schatten", Math.min(0.55, o * 0.11).toFixed(2));
        } else {
          transform = `translate3d(0, 12px, 40px) rotateX(${-Math.min(90, FALL + (-o - 1) * 3)}deg)`;
          opacity = o < -2 ? 0 : 0.8 + o * 0.25;
          c.style.setProperty("--schatten", "0.3");
        }
        c.style.transform = transform;
        c.style.opacity = opacity;
        c.style.zIndex = String(o >= 0 ? 100 - o : 200 + o);
        c.classList.toggle("vorne", o === 0);
        c.setAttribute("aria-selected", o === 0 ? "true" : "false");
      });
      if (cards[cur]) input.setAttribute("aria-activedescendant", cards[cur].id);
      else input.removeAttribute("aria-activedescendant");
    }
    function render(list) {
      items = list.slice(0, 30);
      cur = 0;
      cards = items.map(card);
      stack.replaceChildren(...cards);
      if (!cards.length) stack.appendChild(make("p", "kartei-leer", "Nichts gefunden."));
      if (count) count.textContent = items.length === 1 ? "1 Treffer" : `${items.length} Treffer`;
      // New cards start upright behind the front and settle into place.
      cards.forEach((c, i) => { c.style.transform = `translate3d(0, ${-RISE * i - 30}px, ${-DEPTH_STEP * i}px)`; c.style.opacity = "0"; });
      requestAnimationFrame(() => requestAnimationFrame(place));
    }
    function local(q) {
      if (!q) return entries.slice();
      const words = fold(q).split(/\s+/).filter(Boolean);
      return entries.filter((e) => {
        const hay = fold(e.titel + " " + e.hinweis + " " + e.gruppe);
        return words.every((w) => hay.includes(w));
      }).sort((a, b) => fold(b.titel).startsWith(words[0]) - fold(a.titel).startsWith(words[0]));
    }
    function filter() {
      const q = input.value.trim();
      const base = local(q);
      render(base);
      clearTimeout(timer);
      if (!searchUrl || q.length < 2) return;
      const my = ++request;
      timer = setTimeout(() => {
        fetch(searchUrl + "?q=" + encodeURIComponent(q), { headers: { Accept: "application/json" }, credentials: "same-origin" })
          .then((r) => (r.ok ? r.json() : { treffer: [] }))
          .then((data) => {
            if (my !== request || !root.classList.contains("offen")) return;
            const extra = (data.treffer || []).filter((t) => t && t.url && t.titel);
            if (extra.length) render(base.concat(extra));
          })
          .catch(() => {});
      }, 160);
    }
    function open() {
      if (root.classList.contains("offen")) return;
      lastFocus = document.activeElement;
      root.hidden = false;
      input.value = "";
      filter();
      requestAnimationFrame(() => root.classList.add("offen"));
      input.focus();
      document.documentElement.classList.add("kartei-offen");
    }
    function close() {
      root.classList.remove("offen");
      document.documentElement.classList.remove("kartei-offen");
      setTimeout(() => { if (!root.classList.contains("offen")) root.hidden = true; }, motion ? 220 : 0);
      if (lastFocus && lastFocus.focus) lastFocus.focus();
    }
    function go() {
      const item = items[cur];
      if (!item) return;
      close();
      if (cards[cur]) cards[cur].classList.add("gezogen");
      window.location.href = item.url;
    }
    function flip(dir) {
      const next = Math.max(0, Math.min(items.length - 1, cur + dir));
      if (next !== cur) { cur = next; place(); }
    }

    input.addEventListener("input", filter);
    input.addEventListener("keydown", (event) => {
      if (event.key === "ArrowDown") { event.preventDefault(); flip(1); }
      else if (event.key === "ArrowUp") { event.preventDefault(); flip(-1); }
      else if (event.key === "Enter") { event.preventDefault(); go(); }
      else if (event.key === "Tab") { event.preventDefault(); flip(event.shiftKey ? -1 : 1); }
    });
    root.addEventListener("keydown", (event) => { if (event.key === "Escape") { event.preventDefault(); close(); } });
    root.addEventListener("click", (event) => { if (event.target === root || event.target.closest("[data-kartei-zu]")) close(); });
    stage.addEventListener("wheel", (event) => {
      event.preventDefault();
      const now = Date.now();
      if (now - wheelAt < 110) return;
      wheelAt = now;
      flip(event.deltaY > 0 ? 1 : -1);
    }, { passive: false });

    $$("[data-kartei-oeffnen]").forEach((btn) => btn.addEventListener("click", (event) => { event.preventDefault(); open(); }));
    const mac = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);
    $$("[data-kartei-taste]").forEach((k) => { k.textContent = mac ? "⌘K" : "Strg K"; });

    // Strg+K / ⌘K anywhere; "g" then a letter jumps directly (like the hints on the cards).
    let pendingG = 0;
    document.addEventListener("keydown", (event) => {
      if ((event.ctrlKey || event.metaKey) && !event.altKey && event.key.toLowerCase() === "k") {
        event.preventDefault();
        if (root.classList.contains("offen")) close(); else open();
        return;
      }
      if (root.classList.contains("offen") || event.ctrlKey || event.metaKey || event.altKey || typing(event.target)) return;
      if (event.key === "g") { pendingG = Date.now(); return; }
      if (pendingG && Date.now() - pendingG < 1000) {
        pendingG = 0;
        const hit = entries.find((e) => e.tasten.toLowerCase() === "g " + event.key.toLowerCase());
        if (hit) { event.preventDefault(); window.location.href = hit.url; }
      }
    });
  }

  // Links like /meetings#neu open the form behind the anchor and put the cursor in it.
  function focusTarget() {
    const id = decodeURIComponent(location.hash.slice(1));
    const target = id && document.getElementById(id);
    if (!target) return;
    const details = target.tagName === "DETAILS" ? target : target.closest("details");
    if (details) details.open = true;
    const field = target.matches("input, select, textarea") ? target
      : target.hasAttribute("data-fokus") ? $("input:not([type=hidden]), select, textarea", target) : null;
    if (field) field.focus();
  }

  /* ---------- 5. Papierflieger ---------- */

  function lerp(a, b, k) { return a.map((p, i) => [p[0] + (b[i][0] - p[0]) * k, p[1] + (b[i][1] - p[1]) * k]); }
  function pts(list) { return list.map((p) => p[0].toFixed(1) + "," + p[1].toFixed(1)).join(" "); }
  const ease = (k) => (k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2);

  // Outline of the sheet in four steps: card, corners folded, long nose, plane from the side.
  // Wide cards fold into a plane of normal proportions (at most 2.6 times as long as high).
  function planeFrames(w, h) {
    const m = h / 2;
    const L = Math.min(w, h * 2.6);
    const X = (k) => (w - L) / 2 + L * k;
    return [
      { blatt: [[0, 0], [w, 0], [w, m], [w, h], [0, h], [0, m]], klappe: [[w, h], [w, h], [w, h]], falz: [[w, 0], [w, m], [w, h]] },
      { blatt: [[0, 0], [w - m, 0], [w, m], [w - m, h], [0, h], [0, m]], klappe: [[w - m, m], [w, m], [w - m, h]], falz: [[w - m, 0], [w - m, m], [w - m, h]] },
      { blatt: [[X(0), 0], [X(0.28), 0], [X(1), m], [X(0.28), h], [X(0), h], [X(0), m]], klappe: [[X(0.55), m], [X(1), m], [X(0.55), m]], falz: [[X(0.28), 0], [X(0.55), m], [X(0.28), h]] },
      { blatt: [[X(0.02), m - h * 0.1], [X(0.22), m - h * 0.1], [X(0.98), m], [X(0.22), m + h * 0.16], [X(0.02), m + h * 0.16], [X(0.02), m]], klappe: [[X(0.02), m], [X(0.98), m], [X(0.02), m + h * 0.16]], falz: [[X(0.22), m - h * 0.1], [X(0.7), m], [X(0.98), m]] },
    ];
  }

  function fliegerInit(root) {
    const card = $("[data-flieger-karte]", root);
    const form = card && $("form", card);
    if (!form) return;
    const done = $("[data-flieger-fertig]", root);
    const error = $("[data-flieger-fehler]", root);
    const field = $("input[type=email], input:not([type=hidden])", form);
    const action = form.getAttribute("action");
    const mode = root.dataset.fliegerModus || (action && action !== "#" ? "senden" : "demo");
    let busy = false;

    function stageFor() {
      const w = card.offsetWidth;
      const h = card.offsetHeight;
      const box = make("div", "flieger-buehne");
      box.setAttribute("aria-hidden", "true");
      box.style.left = card.offsetLeft + "px";
      box.style.top = card.offsetTop + "px";
      box.style.width = w + "px";
      box.style.height = h + "px";
      const s = svg("svg", { viewBox: `0 0 ${w} ${h}`, width: w, height: h }, box);
      const trail = svg("path", { class: "fl-spur", d: `M${w * 0.5} ${h * 0.56} C ${w * 0.8} ${h * 0.6}, ${w * 1.05} ${h * 0.2}, ${w * 1.25} ${-h * 0.5}` }, s);
      const plane = svg("g", { class: "fl-flieger" }, s);
      const frames = planeFrames(w, h);
      const parts = {
        blatt: svg("polygon", { class: "fl-blatt" }, plane),
        klappe: svg("polygon", { class: "fl-klappe" }, plane),
        falz: svg("polyline", { class: "fl-falz" }, plane),
      };
      root.appendChild(box);
      return { box, s, trail, plane, frames, parts, w, h };
    }
    function show(stage, frame) {
      for (const key in stage.parts) stage.parts[key].setAttribute("points", pts(frame[key]));
    }
    function morph(stage, a, b, ms) {
      return new Promise((resolve) => {
        if (!motion) { show(stage, b); resolve(); return; }
        const t0 = performance.now();
        const tick = (now) => {
          const k = Math.min(1, (now - t0) / ms);
          const e = ease(k);
          const mix = {};
          for (const key in a) mix[key] = lerp(a[key], b[key], e);
          show(stage, mix);
          if (k < 1) requestAnimationFrame(tick); else resolve();
        };
        requestAnimationFrame(tick);
      });
    }
    async function foldUp(stage) {
      const f = stage.frames;
      show(stage, f[0]);
      card.classList.add("flieger-weg");
      for (let i = 1; i < f.length; i++) { await morph(stage, f[i - 1], f[i], 320); await wait(70); }
    }
    async function unfold(stage) {
      const f = stage.frames;
      for (let i = f.length - 1; i > 0; i--) await morph(stage, f[i], f[i - 1], 260);
      card.classList.remove("flieger-weg");
      stage.box.remove();
    }
    async function fly(stage) {
      const { w, h } = stage;
      anim(stage.trail, [{ opacity: 0, strokeDashoffset: 60 }, { opacity: 0.7, offset: 0.35 }, { opacity: 0, strokeDashoffset: 0 }],
        { duration: 1300, easing: "ease-out" });
      await anim(stage.plane, [
        { transform: "translate(0,0) rotate(0deg) scale(1)" },
        { transform: `translate(${-w * 0.06}px, ${h * 0.05}px) rotate(3deg) scale(0.42)`, offset: 0.28 },
        { transform: `translate(${w * 0.75}px, ${-h * 1.35}px) rotate(-22deg) scale(0.16)`, opacity: 0 },
      ], { duration: 1250, easing: "cubic-bezier(.5,0,.6,1)", fill: "forwards" });
      stage.box.remove();
    }
    function finish(message) {
      if (!done) return;
      const address = $("[data-flieger-adresse]", done);
      if (address) address.textContent = field ? field.value : "";
      const text = $("[data-flieger-text]", done);
      if (text && message) text.textContent = message;
      card.hidden = true;
      done.hidden = false;
      const focus = $("button, a", done);
      if (focus) focus.focus();
    }
    function send() {
      return fetch(form.action, {
        method: "POST", body: new FormData(form), credentials: "same-origin",
        headers: { "X-Cockpit-Ajax": "1", Accept: "application/json" },
      }).then((r) => r.json()).catch(() => ({
        ok: false, nachricht: "Das hat nicht geklappt. Bitte die Seite neu laden und noch einmal senden.",
      }));
    }

    form.addEventListener("submit", async (event) => {
      if (mode === "senden" && !motion) return;
      event.preventDefault();
      if (busy || !form.reportValidity()) return;
      busy = true;
      if (error) error.hidden = true;
      const answer = mode === "abruf" ? send() : wait(mode === "demo" ? 700 : 0).then(() => ({ ok: true }));
      const stage = stageFor();
      await foldUp(stage);
      const result = await answer;
      if (result.ok) {
        await fly(stage);
        busy = false;
        if (mode === "senden") { form.submit(); return; }
        card.classList.remove("flieger-weg");
        finish(result.nachricht);
      } else {
        await unfold(stage);
        busy = false;
        if (error) { error.textContent = result.nachricht || "Das hat nicht geklappt."; error.hidden = false; }
        if (field) field.focus();
      }
    });
    if (done) {
      $$("[data-flieger-nochmal]", done).forEach((btn) => btn.addEventListener("click", () => {
        done.hidden = true;
        card.hidden = false;
        form.reset();
        if (field) field.focus();
      }));
    }
  }

  /* ---------- 6. Orb: Eingabebox mit animierter Kugel ---------- */

  function ball(c, x, y, r) { c.beginPath(); c.arc(x, y, Math.max(0.1, r), 0, Math.PI * 2); }
  function gloss(c, x, y, R, a) {
    const g = c.createRadialGradient(x - R * 0.35, y - R * 0.45, 0, x - R * 0.35, y - R * 0.45, R * 0.6);
    g.addColorStop(0, `rgba(255,255,255,${a})`);
    g.addColorStop(1, "rgba(255,255,255,0)");
    c.fillStyle = g;
    ball(c, x, y, R);
    c.fill();
  }
  function rim(c, x, y, R, color) {
    const g = c.createRadialGradient(x, y, R * 0.8, x, y, R);
    g.addColorStop(0, "rgba(0,0,0,0)");
    g.addColorStop(1, color);
    c.fillStyle = g;
    ball(c, x, y, R);
    c.fill();
  }

  const ORB_DRAW = {
    glas(c, S, t, lv) {
      const x = S / 2, y = S / 2, R = S * 0.38;
      c.save(); ball(c, x, y, R); c.clip();
      c.fillStyle = "#0c0b16"; c.fillRect(0, 0, S, S);
      c.globalCompositeOperation = "lighter";
      for (let i = 0; i < 4; i++) {
        const a = t * (0.35 + i * 0.12) + i * 1.7;
        c.strokeStyle = `hsla(${215 + i * 28},85%,72%,${0.16 + lv * 0.3})`;
        c.lineWidth = R * (0.22 - i * 0.035);
        c.beginPath();
        c.ellipse(x + Math.cos(a) * R * 0.2, y + Math.sin(a * 1.3) * R * 0.15, R * 0.78,
          R * (0.22 + 0.12 * Math.sin(t * 0.8 + i)), a, 0, Math.PI * 2);
        c.stroke();
      }
      c.restore();
      rim(c, x, y, R, "rgba(190,200,255,.55)");
      gloss(c, x, y, R, 0.6);
    },
    plasma(c, S, t, lv, m) {
      const x = S / 2, y = S / 2, R = S * 0.38;
      const g = c.createRadialGradient(x, y, 0, x, y, R);
      g.addColorStop(0, "#1c2242"); g.addColorStop(1, "#07070d");
      c.fillStyle = g; ball(c, x, y, R); c.fill();
      if (!m.arcs || Math.abs(t - m.at) > 0.07) {
        m.at = t; m.arcs = [];
        const n = 5 + Math.round(lv * 7);
        for (let i = 0; i < n; i++) {
          const a = Math.random() * Math.PI * 2, line = [[x, y]];
          for (let k = 1; k <= 7; k++) {
            const d = R * 0.96 * k / 7, j = k < 7 ? (Math.random() - 0.5) * R * 0.24 : 0;
            line.push([x + Math.cos(a) * d - Math.sin(a) * j, y + Math.sin(a) * d + Math.cos(a) * j]);
          }
          m.arcs.push(line);
        }
      }
      c.save(); ball(c, x, y, R); c.clip();
      c.globalCompositeOperation = "lighter";
      c.shadowColor = "#7aa8ff"; c.shadowBlur = S * 0.05;
      c.strokeStyle = "rgba(195,218,255,.9)"; c.lineWidth = Math.max(1, S * 0.008);
      m.arcs.forEach((line) => { c.beginPath(); line.forEach((p, i) => (i ? c.lineTo(p[0], p[1]) : c.moveTo(p[0], p[1]))); c.stroke(); });
      c.shadowBlur = 0;
      const core = c.createRadialGradient(x, y, 0, x, y, R * 0.32);
      core.addColorStop(0, "rgba(225,238,255,.95)"); core.addColorStop(1, "rgba(120,160,255,0)");
      c.fillStyle = core; ball(c, x, y, R * 0.32); c.fill();
      c.restore();
      rim(c, x, y, R, "rgba(140,160,255,.35)");
      gloss(c, x, y, R, 0.35);
    },
    chrom(c, S, t, lv) {
      const x = S / 2, y = S / 2, R = S * 0.38;
      const h = (Math.sin(t * 0.9) * 0.08 + lv * 0.1) / 2;
      const g = c.createLinearGradient(0, y - R, 0, y + R);
      g.addColorStop(0, "#fdfdfe"); g.addColorStop(0.36 + h, "#c9ccd4"); g.addColorStop(0.47 + h, "#3b3e47");
      g.addColorStop(0.53 + h, "#a7abb5"); g.addColorStop(0.8, "#eceef2"); g.addColorStop(1, "#7d818b");
      c.fillStyle = g; ball(c, x, y, R); c.fill();
      rim(c, x, y, R, "rgba(20,22,30,.55)");
      gloss(c, x, y, R, 0.85);
    },
    schwarm(c, S, t, lv, m) {
      const x = S / 2, y = S / 2, R = S * 0.38;
      if (!m.pts) {
        m.pts = [];
        for (let i = 0; i < 180; i++) {
          const yy = 1 - (i + 0.5) * 2 / 180, r = Math.sqrt(1 - yy * yy), a = i * 2.39996;
          m.pts.push([Math.cos(a) * r, yy, Math.sin(a) * r]);
        }
      }
      const cy = Math.cos(t * 0.6), sy = Math.sin(t * 0.6), cx = Math.cos(0.35), sx = Math.sin(0.35);
      m.pts.forEach((p, i) => {
        const X = p[0] * cy + p[2] * sy, Z1 = -p[0] * sy + p[2] * cy;
        const Y = p[1] * cx - Z1 * sx, Z = p[1] * sx + Z1 * cx;
        const j = 1 + lv * 0.14 * Math.sin(t * 9 + i), d = (1 - Z) / 2;
        c.fillStyle = `rgba(226,229,242,${0.15 + d * 0.8})`;
        ball(c, x + X * R * j, y + Y * R * j, S * (0.004 + d * 0.009));
        c.fill();
      });
    },
    hologramm(c, S, t, lv) {
      const x = S / 2, y = S / 2, R = S * 0.38, col = (a) => `rgba(61,220,151,${a})`;
      const g = c.createRadialGradient(x, y, 0, x, y, R);
      g.addColorStop(0, col(0.16 + lv * 0.2)); g.addColorStop(1, col(0.04));
      c.fillStyle = g; ball(c, x, y, R); c.fill();
      c.lineWidth = Math.max(1, S * 0.006); c.strokeStyle = col(0.75);
      c.shadowColor = col(0.9); c.shadowBlur = S * 0.03;
      for (let i = -3; i <= 3; i++) {
        const la = i * Math.PI / 8, yy = y + Math.sin(la) * R, w = Math.cos(la) * R;
        c.beginPath(); c.moveTo(x - w, yy); c.lineTo(x + w, yy); c.stroke();
      }
      for (let i = 0; i < 6; i++) {
        const a = t * 0.7 + i * Math.PI / 6;
        c.beginPath(); c.ellipse(x, y, Math.max(0.5, Math.abs(Math.cos(a)) * R), R, 0, 0, Math.PI * 2); c.stroke();
      }
      c.shadowBlur = 0;
      ball(c, x, y, R); c.strokeStyle = col(0.9); c.stroke();
      const sy = y - R + ((t * 0.5) % 1) * 2 * R;
      c.save(); ball(c, x, y, R); c.clip();
      const sg = c.createLinearGradient(0, sy - R * 0.2, 0, sy);
      sg.addColorStop(0, col(0)); sg.addColorStop(1, col(0.4));
      c.fillStyle = sg; c.fillRect(0, sy - R * 0.2, S, R * 0.2);
      c.restore();
    },
    stimme(c, S, t, lv, m) {
      const x = S / 2, y = S / 2, R = S * 0.34 * (1 + 0.03 * Math.sin(t * 2.4) + lv * 0.09);
      m.rings = (m.rings || []).filter((r) => t - r < 1.6 && t >= r);
      if (lv > 0.35 && (!m.last || t - m.last > 0.35 || t < m.last)) { m.rings.push(t); m.last = t; }
      m.rings.forEach((r0) => {
        const k = (t - r0) / 1.6;
        c.strokeStyle = `rgba(255,170,60,${(1 - k) * 0.5})`; c.lineWidth = S * 0.01;
        ball(c, x, y, R * (1 + k * 0.35)); c.stroke();
      });
      c.shadowColor = "rgba(255,140,0,.7)"; c.shadowBlur = S * 0.12;
      const g = c.createRadialGradient(x - R * 0.25, y - R * 0.3, R * 0.05, x, y, R);
      g.addColorStop(0, "#fff1c9"); g.addColorStop(0.35, "#ffb340"); g.addColorStop(0.8, "#f26b00"); g.addColorStop(1, "#a83a00");
      c.fillStyle = g; ball(c, x, y, R); c.fill(); c.shadowBlur = 0;
      gloss(c, x, y, R, 0.35);
    },
    aurora(c, S, t, lv) {
      const x = S / 2, y = S / 2, R = S * 0.38;
      c.save(); ball(c, x, y, R); c.clip();
      c.fillStyle = "#0b1020"; c.fillRect(0, 0, S, S);
      c.globalCompositeOperation = "lighter";
      [["34,211,166", 0], ["124,58,237", 2.1], ["59,130,246", 4.2], ["236,72,153", 1.1]].forEach(([rgb, o], i) => {
        const px = x + Math.cos(t * (0.5 + i * 0.13) + o) * R * 0.5, py = y + Math.sin(t * (0.4 + i * 0.11) + o * 1.3) * R * 0.45;
        const g = c.createRadialGradient(px, py, 0, px, py, R * (0.75 + lv * 0.25));
        g.addColorStop(0, `rgba(${rgb},.85)`); g.addColorStop(1, `rgba(${rgb},0)`);
        c.fillStyle = g; c.fillRect(0, 0, S, S);
      });
      c.restore();
      rim(c, x, y, R, "rgba(255,255,255,.25)");
      gloss(c, x, y, R, 0.45);
    },
    lava(c, S, t, lv) {
      const x = S / 2, y = S / 2, R = S * 0.33;
      c.beginPath();
      for (let i = 0; i <= 72; i++) {
        const a = i / 72 * Math.PI * 2;
        const r = R * (1 + 0.09 * Math.sin(3 * a + t * 1.3) + 0.06 * Math.sin(5 * a - t * 1.7) + (0.04 + lv * 0.1) * Math.sin(7 * a + t * 2.9));
        const px = x + Math.cos(a) * r, py = y + Math.sin(a) * r * 1.08;
        if (i) c.lineTo(px, py); else c.moveTo(px, py);
      }
      c.closePath();
      const g = c.createRadialGradient(x - R * 0.3, y - R * 0.35, R * 0.05, x, y, R * 1.15);
      g.addColorStop(0, "#ffd29a"); g.addColorStop(0.4, "#ff7a2f"); g.addColorStop(1, "#b52c08");
      c.shadowColor = "rgba(255,90,20,.6)"; c.shadowBlur = S * 0.1;
      c.fillStyle = g; c.fill(); c.shadowBlur = 0;
    },
    dither(c, S, t, lv) {
      const x = S / 2, y = S / 2, R = S * 0.38, n = 26, cell = 2 * R / n;
      const bayer = [0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5];
      const lx = Math.cos(t * 0.8), lz = -0.3 - Math.abs(Math.sin(t * 0.8)) * 0.7, ly = -0.55, ll = Math.hypot(lx, ly, lz);
      c.fillStyle = "#ebe8f4";
      for (let i = 0; i < n; i++) {
        for (let j = 0; j < n; j++) {
          const nx = (i + 0.5) / n * 2 - 1, ny = (j + 0.5) / n * 2 - 1, q = 1 - nx * nx - ny * ny;
          if (q <= 0) continue;
          const nz = -Math.sqrt(q);
          const shade = Math.max(0, (nx * lx + ny * ly + nz * lz) / ll) * 0.95 + 0.04 + lv * 0.2;
          if (shade > (bayer[(i % 4) * 4 + (j % 4)] + 0.5) / 16) c.fillRect(x - R + i * cell, y - R + j * cell, cell * 0.78, cell * 0.78);
        }
      }
    },
    blase(c, S, t, lv) {
      const x = S / 2, y = S / 2, R = S * 0.37;
      const shape = () => {
        c.beginPath();
        for (let i = 0; i <= 60; i++) {
          const a = i / 60 * Math.PI * 2, r = R * (1 + (0.015 + lv * 0.045) * Math.sin(3 * a + t * 2.2));
          if (i) c.lineTo(x + Math.cos(a) * r, y + Math.sin(a) * r); else c.moveTo(x + Math.cos(a) * r, y + Math.sin(a) * r);
        }
        c.closePath();
      };
      const g = c.createRadialGradient(x, y, R * 0.55, x, y, R);
      g.addColorStop(0, "rgba(255,255,255,0)"); g.addColorStop(1, "rgba(200,220,255,.2)");
      shape(); c.fillStyle = g; c.fill();
      let stroke = "rgba(190,210,255,.8)";
      if (c.createConicGradient) {
        stroke = c.createConicGradient(t * 0.8, x, y);
        ["#ff7ac3", "#ffd36e", "#7affc1", "#6ec8ff", "#b38cff", "#ff7ac3"].forEach((col, i, all) => stroke.addColorStop(i / (all.length - 1), col));
      }
      c.globalAlpha = 0.8; c.strokeStyle = stroke; c.lineWidth = Math.max(1.5, S * 0.016); shape(); c.stroke(); c.globalAlpha = 1;
      c.fillStyle = "rgba(255,255,255,.8)";
      c.beginPath(); c.ellipse(x - R * 0.42, y - R * 0.45, R * 0.16, R * 0.08, -0.7, 0, Math.PI * 2); c.fill();
      ball(c, x + R * 0.45, y + R * 0.4, S * 0.012); c.fill();
    },
    loch(c, S, t, lv) {
      const x = S / 2, y = S / 2, R = S * 0.17, rx = S * 0.44, ry = S * 0.115, tilt = -0.12;
      const disk = (front) => {
        for (let k = 0; k < 2; k++) {
          c.beginPath();
          c.ellipse(x, y, rx * (1 - k * 0.2), ry * (1 - k * 0.2), tilt, front ? 0 : Math.PI, front ? Math.PI : Math.PI * 2);
          const g = c.createLinearGradient(x - rx, 0, x + rx, 0);
          g.addColorStop(0, "rgba(255,120,40,.25)"); g.addColorStop(0.5, k ? "#fff0c2" : "#ffb347"); g.addColorStop(1, "rgba(255,120,40,.4)");
          c.strokeStyle = g; c.lineWidth = S * (k ? 0.018 : 0.036) * (1 + lv * 0.4); c.stroke();
        }
        c.save();
        c.setLineDash([S * 0.02, S * 0.05]); c.lineDashOffset = -t * S * 0.25;
        c.strokeStyle = "rgba(255,240,200,.6)"; c.lineWidth = Math.max(1, S * 0.008);
        c.beginPath(); c.ellipse(x, y, rx * 0.9, ry * 0.9, tilt, front ? 0 : Math.PI, front ? Math.PI : Math.PI * 2); c.stroke();
        c.restore();
      };
      disk(false);
      c.strokeStyle = "rgba(255,200,120,.75)"; c.lineWidth = Math.max(1, S * 0.014);
      c.beginPath(); c.ellipse(x, y, R * 1.5, R * 1.35, 0, Math.PI * 1.04, Math.PI * 1.96); c.stroke();
      c.shadowColor = "rgba(255,170,80,.9)"; c.shadowBlur = S * 0.06;
      c.fillStyle = "#000"; ball(c, x, y, R); c.fill(); c.shadowBlur = 0;
      c.strokeStyle = "rgba(255,225,170,.9)"; c.lineWidth = Math.max(1, S * 0.006); ball(c, x, y, R * 1.05); c.stroke();
      disk(true);
    },
    kristall(c, S, t, lv, m) {
      const x = S / 2, y = S / 2, R = S * 0.34;
      if (!m.v) {
        m.v = [[0, -1.15, 0], [0, 1.15, 0]];
        for (let i = 0; i < 6; i++) m.v.push([Math.cos(i * Math.PI / 3), -0.15, Math.sin(i * Math.PI / 3)]);
        m.f = [];
        for (let i = 0; i < 6; i++) { const a = 2 + i, b = 2 + (i + 1) % 6; m.f.push([0, a, b], [1, b, a]); }
      }
      const ry = t * 0.7, rx = 0.4 + lv * 0.25, cy = Math.cos(ry), sy = Math.sin(ry), cx = Math.cos(rx), sx = Math.sin(rx);
      const p = m.v.map(([X, Y, Z]) => {
        const X1 = X * cy + Z * sy, Z1 = -X * sy + Z * cy;
        return [X1, Y * cx - Z1 * sx, Y * sx + Z1 * cx];
      });
      c.shadowColor = "rgba(150,110,255,.5)"; c.shadowBlur = S * 0.08;
      m.f.map((f) => {
        const [a, b, d] = f.map((i) => p[i]);
        const u = [b[0] - a[0], b[1] - a[1], b[2] - a[2]], v = [d[0] - a[0], d[1] - a[1], d[2] - a[2]];
        const n = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]];
        const nl = Math.hypot(n[0], n[1], n[2]) || 1;
        return { f, z: a[2] + b[2] + d[2], nz: n[2] / nl, l: (-0.4 * n[0] - 0.6 * n[1] - 0.7 * n[2]) / nl };
      }).filter((F) => F.nz < 0).sort((A, B) => B.z - A.z).forEach((F) => {
        c.beginPath();
        F.f.forEach((i, k) => (k ? c.lineTo(x + p[i][0] * R, y + p[i][1] * R) : c.moveTo(x + p[i][0] * R, y + p[i][1] * R)));
        c.closePath();
        const L = Math.max(0, F.l);
        c.fillStyle = `hsl(${258 - L * 40}, 72%, ${28 + L * 50}%)`; c.fill();
        c.shadowBlur = 0;
        c.strokeStyle = "rgba(240,232,255,.4)"; c.lineWidth = Math.max(0.6, S * 0.004); c.stroke();
      });
    },
  };
  const ORBS = [["glas", "Glas"], ["plasma", "Plasma"], ["chrom", "Chrom"], ["schwarm", "Schwarm"],
    ["hologramm", "Hologramm"], ["stimme", "Stimme"], ["aurora", "Aurora"], ["lava", "Lava"],
    ["dither", "Dither"], ["blase", "Blase"], ["loch", "Schwarzes Loch"], ["kristall", "Kristall"]];

  function demoAnswer(q) {
    return {
      absaetze: [
        "Das ist eine Vorschau ohne Server, deshalb steht hier eine Beispielantwort.",
        `Du hast gefragt: „${q}“. Im Projekt-Cockpit beantwortet diese Box Fragen aus deinen eigenen Daten: überfällige Aufgaben, die Woche, nächste Meetings, Kontingente und Konflikte im Zeitplan. Wechsle oben die Kugel, während sie antwortet.`,
      ],
      links: [],
    };
  }

  function orbInit(root) {
    const canvas = $("[data-orb-kugel]", root);
    const form = $("[data-orb-form]", root);
    if (!canvas || !form) return;
    const ctx = canvas.getContext("2d");
    const input = $("input[type=text], input:not([type])", form);
    const send = $("button[type=submit]", form);
    const row = $("[data-orb-stile]", root);
    const log = $("[data-orb-verlauf]", root);
    const status = $("[data-orb-status]", root);
    const hint = $("[data-orb-hinweis]", root);
    const source = root.dataset.orbQuelle || "";
    const state = { lv: 0, boost: 0, mode: "ruhig", t: 0, mem: {} };
    let style = fetchKey("cockpit-orb");
    if (!ORB_DRAW[style]) style = root.dataset.orbStil && ORB_DRAW[root.dataset.orbStil] ? root.dataset.orbStil : "plasma";
    let busy = false;
    let stop = false;
    let raf = 0;
    let last = performance.now();
    let visible = true;

    function size() {
      const dpr = Math.min(2, window.devicePixelRatio || 1);
      const w = Math.round(canvas.clientWidth * dpr) || 120;
      if (canvas.width !== w) { canvas.width = w; canvas.height = w; }
      return w;
    }
    function draw() {
      const S = size();
      ctx.clearRect(0, 0, S, S);
      ctx.save();
      ORB_DRAW[style](ctx, S, state.t, state.lv, state.mem[style] || (state.mem[style] = {}));
      ctx.restore();
    }
    function frame(now) {
      raf = 0;
      const dt = Math.min(0.05, (now - last) / 1000);
      last = now;
      const speed = state.mode === "denkt" ? 2.4 : state.mode === "spricht" ? 1.6 : 1;
      state.t += dt * speed;
      const goal = state.mode === "denkt" ? 0.55 + 0.25 * Math.sin(state.t * 6) : 0;
      state.boost *= 0.9;
      state.lv += (Math.min(1, goal + state.boost) - state.lv) * 0.15;
      draw();
      if (visible && !document.hidden) raf = requestAnimationFrame(frame);
    }
    function kick() {
      if (!motion) { draw(); return; }
      if (!raf && visible && !document.hidden) { last = performance.now(); raf = requestAnimationFrame(frame); }
    }
    function setStyle(key) {
      style = key;
      store("cockpit-orb", key);
      if (row) $$("[data-stil]", row).forEach((b) => b.setAttribute("aria-pressed", b.dataset.stil === key ? "true" : "false"));
      root.dataset.orbAktiv = key;
      kick();
    }
    function mode(name, text) {
      state.mode = name;
      if (status) status.textContent = text;
      root.classList.toggle("orb-arbeitet", name !== "ruhig");
      if (send) {
        send.setAttribute("aria-label", name === "ruhig" ? "Senden" : "Antwort sofort ganz zeigen");
        send.classList.toggle("stopp", name !== "ruhig");
      }
      if (hint) hint.textContent = name === "ruhig" ? hint.dataset.orbHinweis || hint.textContent : "Esc zeigt die Antwort sofort ganz";
      kick();
    }
    if (hint) hint.dataset.orbHinweis = hint.textContent;

    if (row) {
      ORBS.forEach(([key, label]) => {
        const b = make("button", "orb-stil");
        b.type = "button";
        b.dataset.stil = key;
        b.setAttribute("aria-pressed", key === style ? "true" : "false");
        const mini = make("canvas", "orb-mini");
        mini.width = 64; mini.height = 64;
        mini.setAttribute("aria-hidden", "true");
        ORB_DRAW[key](mini.getContext("2d"), 64, 1.3, 0.2, {});
        b.append(mini, make("span", "", label));
        b.addEventListener("click", () => setStyle(key));
        row.appendChild(b);
      });
    }

    function answer(q) {
      if (!source) return wait(900).then(() => demoAnswer(q));
      return fetch(source + "?frage=" + encodeURIComponent(q), { headers: { Accept: "application/json" }, credentials: "same-origin" })
        .then((r) => { if (!r.ok) throw new Error(String(r.status)); return r.json(); });
    }
    async function ask(text) {
      const q = text.trim().slice(0, 200);
      if (!q || busy) return;
      busy = true;
      stop = false;
      input.value = "";
      root.classList.add("im-gespraech");
      log.hidden = false;
      log.appendChild(make("p", "orb-ich", q));
      const reply = make("div", "orb-antwort");
      log.appendChild(reply);
      log.scrollTop = log.scrollHeight;
      mode("denkt", "Denkt nach …");
      let data;
      const started = Date.now();
      try { data = await answer(q); } catch (e) {
        data = { absaetze: ["Das hat gerade nicht geklappt. Bitte die Seite neu laden und noch einmal fragen."], links: [] };
      }
      if (motion) await wait(Math.max(0, 650 - (Date.now() - started)));
      mode("spricht", "Antwortet …");
      for (const para of data.absaetze || []) {
        const p = make("p");
        reply.appendChild(p);
        for (const word of para.split(/(\s+)/)) {
          p.append(word);
          if (!stop && motion && word.trim()) {
            state.boost = Math.min(1, 0.45 + Math.random() * 0.35);
            log.scrollTop = log.scrollHeight;
            await wait(24 + Math.random() * 38);
          }
        }
      }
      if ((data.links || []).length) {
        const list = make("ul", "orb-links");
        data.links.forEach((link) => {
          const li = make("li");
          const a = make("a", "", link.text);
          a.href = link.url;
          li.appendChild(a);
          if (link.info) li.append(" ", make("span", "", link.info));
          list.appendChild(li);
        });
        reply.appendChild(list);
      }
      log.scrollTop = log.scrollHeight;
      mode("ruhig", "Bereit");
      busy = false;
    }

    form.addEventListener("submit", (event) => {
      event.preventDefault();
      if (busy) { stop = true; return; }
      ask(input.value);
    });
    input.addEventListener("input", () => { state.boost = Math.min(1, state.boost + 0.3); kick(); });
    root.addEventListener("keydown", (event) => { if (event.key === "Escape" && busy) stop = true; });
    $$("[data-orb-chip]", root).forEach((chip) => chip.addEventListener("click", () => ask(chip.textContent)));
    $$("[data-orb-neu]", root).forEach((btn) => btn.addEventListener("click", () => {
      if (busy) return;
      log.replaceChildren();
      log.hidden = true;
      root.classList.remove("im-gespraech");
      input.focus();
    }));

    if ("IntersectionObserver" in window) {
      new IntersectionObserver((entries) => {
        visible = entries.some((e) => e.isIntersecting);
        if (visible) kick();
      }).observe(canvas);
    }
    document.addEventListener("visibilitychange", () => { if (!document.hidden) kick(); });
    window.addEventListener("resize", () => { if (!motion) draw(); });
    setStyle(style);
    draw();
  }

  /* ---------- Start ---------- */

  function start() {
    fbRefresh();
    $$("[data-fallblatt-nochmal]").forEach((btn) => btn.addEventListener("click", () => {
      const scope = btn.closest("section, .card, body");
      $$("[data-fallblatt]", scope).forEach((board) => fbValues(board).forEach((value, i) => {
        fbRestore(value);
        fbBuild(value, i * 140);
      }));
    }));
    $$("[data-schluessel]").forEach(schluesselInit);
    $$("[data-bon]").forEach(bonInit);
    $$("[data-kartei]").forEach(karteiInit);
    $$("[data-flieger]").forEach(fliegerInit);
    $$("[data-orb]").forEach(orbInit);
    focusTarget();
    window.addEventListener("hashchange", focusTarget);
    // The settings page and the design switcher change data-* on <html>: re-check the digits.
    if ("MutationObserver" in window) {
      new MutationObserver(fbRefresh).observe(document.documentElement,
        { attributes: true, attributeFilter: ["data-theme", "data-digits", "data-mode"] });
    }
  }

  window.cockpitKomponenten = { fallblatt: fbSet, orbStile: ORBS.map(([key, label]) => ({ key, label })) };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();
