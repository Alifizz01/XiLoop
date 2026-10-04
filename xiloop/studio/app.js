/* XiLoop Studio - a thin client of the local XiLoop REST API (see xiloop/server.py). */
"use strict";

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const API = location.origin;
const num = (v) => Number(String(v).trim().replace(",", "."));   // accept 0,05 and 0.05

async function api(path, body, method) {
  const opt = { method: method || (body ? "POST" : "GET"), headers: {} };
  if (body) { opt.headers["Content-Type"] = "application/json"; opt.body = JSON.stringify(body); }
  const r = await fetch(API + path, opt);
  const j = await r.json();
  if (!r.ok) throw new Error(j.error || r.statusText);
  return j;
}

/* ------------------------------------------------------------------ state */
const GAINS = {          // name: [min, max, step]
  kp: [0, 20, 0.01], ki: [0, 10, 0.01], kd: [0, 1, 0.001], out_max: [0.5, 50, 0.1],
};
const PLANT_LABEL = {
  actuator: "Rotary actuator · 2nd order",
  first_order: "First-order lag + dead time",
  transfer_function: "Transfer function G(s)",
  dc_motor: "DC motor · example plant",
};
const S = {
  catalog: null, mode: "tune", devType: "pid",
  gains: { kp: 2, ki: 1, kd: 0.05, out_max: 10 },
  plantType: "actuator", plantParams: {},
  job: null, busy: false, pending: false, live: false,
  plan: { scenarios: [], requirements: [] }, campaign: null,
};

/* ------------------------------------------------------------- specs */
function deviceSpec() {
  const params = { ...S.gains };
  switch (S.devType) {
    case "socket": return { type: "socket", host: $("#sock-host").value, port: +$("#sock-port").value, params };
    case "serial": return { type: "serial", port: $("#ser-port").value, baud: +$("#ser-baud").value, params };
    case "custom": return { type: $("#cust-class").value.trim(), params };
    default: return { type: "pid", params };
  }
}
function plantSpec() {
  const type = S.plantType === "custom" ? $("#plant-custom").value.trim() : S.plantType;
  return { type, params: { ...S.plantParams } };
}
function scenario() {
  return { setpoint: num($("#sc-sp").value), duration: num($("#sc-dur").value), dt: num($("#sc-dt").value),
           realtime: $("#sc-rt").checked };
}
function planBody() {
  return { plan: { name: $("#plan-name").value, ...S.plan }, plant: plantSpec(), device: deviceSpec() };
}

/* ------------------------------------------------------------- chart */
function makeChart(el, { band = true, multi = 0 } = {}) {
  const pens = [css("--pen-meas"), "#6F7BD0", "#14205E", "#8E98DE", "#3D4FC4"];
  const series = [{}];
  if (multi) {
    for (let i = 0; i < multi; i++) series.push({ stroke: pens[i % pens.length], width: 2, spanGaps: true });
    for (let i = 0; i < multi; i++) series.push({ stroke: css("--pen-sp"), width: 1.25, dash: [6, 4], spanGaps: true });
  } else {
    series.push({ stroke: css("--pen-meas"), width: 2 },
                { stroke: css("--pen-sp"), width: 1.5, dash: [6, 4] },
                { stroke: css("--pen-cmd"), width: 1.25, scale: "u" });
  }
  const font = `11px ${css("--f-num")}`;
  const axis = { font, stroke: css("--muted"), grid: { stroke: css("--grid-major"), width: 1 },
                 ticks: { stroke: css("--grid-major"), width: 1, size: 4 } };
  const axes = [{ ...axis, label: "time [s]", labelFont: `11px ${css("--f-label")}`, labelSize: 22 },
                { ...axis, size: 56 }];
  if (!multi) axes.push({ ...axis, scale: "u", side: 1, size: 52, grid: { show: false },
                          stroke: css("--pen-cmd") });
  const opts = {
    width: el.clientWidth, height: el.clientHeight, series, axes,
    scales: { x: { time: false } }, legend: { show: false },
    cursor: { drag: { x: true, y: false }, points: { size: 6 } },
    hooks: {
      drawAxes: [(u) => band && drawBand(u)],
      draw: [(u) => S.live && el.id === "chart" && drawPenHead(u)],
      setCursor: [(u) => showCursor(u, el)],
    },
  };
  const chart = new uPlot(opts, multi ? [[], ...series.slice(1).map(() => [])] : [[], [], [], []], el);
  chart.showBand = band;
  new ResizeObserver(() => chart.setSize({ width: el.clientWidth, height: el.clientHeight })).observe(el);
  return chart;
}

function drawBand(u) {
  const sp = u.data[2] && u.data[2][0];
  if (!u.showBand || sp == null || sp === 0) return;
  const { ctx, bbox } = u;
  const y1 = u.valToPos(sp * 1.02, "y", true), y2 = u.valToPos(sp * 0.98, "y", true);
  ctx.save();
  ctx.fillStyle = "#2F7D4F1F";
  ctx.fillRect(bbox.left, Math.min(y1, y2), bbox.width, Math.abs(y2 - y1));
  ctx.strokeStyle = "#2F7D4F80"; ctx.setLineDash([3, 3]); ctx.lineWidth = devicePixelRatio;
  for (const y of [y1, y2]) { ctx.beginPath(); ctx.moveTo(bbox.left, y); ctx.lineTo(bbox.left + bbox.width, y); ctx.stroke(); }
  ctx.restore();
}

function drawPenHead(u) {   // the recorder's pen, riding the end of the live trace
  const n = u.data[0].length;
  if (!n) return;
  const x = u.valToPos(u.data[0][n - 1], "x", true), y = u.valToPos(u.data[1][n - 1], "y", true);
  const d = devicePixelRatio, ctx = u.ctx;
  ctx.save();
  ctx.fillStyle = css("--pen-meas");
  ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x + 11 * d, y - 6 * d); ctx.lineTo(x + 11 * d, y + 6 * d); ctx.closePath(); ctx.fill();
  ctx.restore();
}

function showCursor(u, el) {
  const out = el.id === "chart" ? $("#cursor") : null;
  if (!out) return;
  const i = u.cursor.idx;
  if (i == null || !u.data[0].length) { out.textContent = ""; return; }
  const f = (v) => (v == null ? "—" : (+v).toPrecision(4));
  out.textContent = `t ${f(u.data[0][i])} s · y ${f(u.data[1][i])} · u ${f(u.data[3][i])}`;
}

/* -------------------------------------------------------- tune: run */
let chart, vchart;
const meterDefs = [
  ["rise_time_s", "Rise time", "s", "10 → 90 % of setpoint", "never reached 90 %"],
  ["overshoot_pct", "Overshoot", "%", "peak beyond setpoint", ""],
  ["steady_state_error", "Steady-state error", "", "|setpoint − final|", ""],
  ["settling_time_s", "Settling time", "s", "into the ±2 % band", "did not settle"],
  ["final", "Final value", "", "last sample", ""],
  ["peak_command", "Peak command", "", "largest actuator effort", ""],
];
function renderMeters(m) {
  $("#meters").innerHTML = meterDefs.map(([k, name, unit, cap, never]) => {
    const v = m ? m[k] : undefined;
    const txt = v == null ? "—" : fmt(v);
    const sub = m && v == null && never ? never : cap;
    return `<div class="meter"><b>${name}</b><output>${txt}${unit && v != null ? `<small>${unit}</small>` : ""}</output><span>${sub}</span></div>`;
  }).join("");
}
function fmt(v) {
  if (v == null) return "—";
  const a = Math.abs(v);
  return a !== 0 && (a < 0.001 || a >= 1e5) ? v.toExponential(2) : (+v.toPrecision(4)).toString();
}
function dur(t0) {
  const ms = performance.now() - t0;
  return ms < 1000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(1)} s`;
}
function status(id, text, err = false) {
  const el = $(id);
  el.textContent = text;
  el.classList.toggle("err", err);
}

function setTrace(c, d) {
  const sp = d.t.map(() => d.setpoint);
  c.setData([d.t, d.y, sp, d.u]);
}

function scheduleRun() {
  if (S.mode !== "tune" || !$("#sc-live").checked) return;
  if (S.busy) { S.pending = true; return; }
  runTune();
}

async function runTune() {
  if (S.job) return stopJob();
  const sc = scenario();
  const body = { device: deviceSpec(), plant: plantSpec(), ...sc };
  S.busy = true;
  const t0 = performance.now();
  try {
    if (S.devType === "pid" && !sc.realtime) {              // fast path: wait for the answer
      status("#status", "Running…");
      const r = await api("/api/simulate", body);
      setTrace(chart, r);
      renderMeters(r.metrics);
      status("#status", `${r.samples} samples · ${dur(t0)}`);
    } else {                                                // stream it, like a real bench
      const r = await streamJob({ kind: "simulate", ...body }, chart, "#status", "#run");
      if (r) {
        renderMeters(r.metrics);
        status("#status", `${r.samples} samples · ${dur(t0)}`);
      }
    }
  } catch (e) {
    status("#status", e.message, true);
  } finally {
    S.busy = false;
    if (S.pending) { S.pending = false; scheduleRun(); }
  }
}

async function streamJob(body, c, statusEl, btn) {
  const { id } = await api("/api/jobs", body);
  S.job = id; S.live = true;
  const button = $(btn), label = button.textContent;
  button.textContent = "Stop"; button.classList.add("stop");
  let since = 0, seq = -1, buf = { t: [], y: [], u: [], setpoint: 0 };
  try {
    for (;;) {
      const s = await api(`/api/jobs/${id}?since=${since}`);
      if (s.seq !== seq) { seq = s.seq; since = 0; buf = { t: [], y: [], u: [], setpoint: 0 }; continue; }
      if (s.live) {
        buf.t.push(...s.live.t); buf.y.push(...s.live.y); buf.u.push(...s.live.u);
        buf.setpoint = s.live.setpoint; since = s.n;
        setTrace(c, buf);
        status(statusEl, `${s.scenario ? s.scenario + " · " : ""}${buf.t.length} samples · t = ${(buf.t.at(-1) || 0).toFixed(2)} s`);
      }
      if (s.status === "error") throw new Error(s.error);
      if (s.status !== "running") {
        if (body.kind === "simulate" && s.result) setTrace(c, s.result);
        if (s.status === "stopped") status(statusEl, "Stopped");
        return s.status === "done" ? s.result : (body.kind === "campaign" ? null : s.result);
      }
      await new Promise((r) => setTimeout(r, 60));
    }
  } finally {
    S.job = null; S.live = false;
    button.textContent = label; button.classList.remove("stop");
    c.redraw();
  }
}
async function stopJob() { if (S.job) await api(`/api/jobs/${S.job}`, null, "DELETE"); }

/* ---------------------------------------------------- left rail UI */
function renderGains() {
  $("#gains").innerHTML = Object.entries(GAINS).map(([k, [lo, hi, st]]) =>
    `<div class="gain"><span>${k === "out_max" ? "limit" : k}</span>
       <input type="range" min="${lo}" max="${hi}" step="${st}" value="${S.gains[k]}" data-g="${k}" aria-label="${k}">
       <input inputmode="decimal" data-num value="${S.gains[k]}" data-g="${k}" aria-label="${k} value"></div>`).join("");
  $$("#gains input").forEach((inp) => {
    paintRange(inp);
    inp.addEventListener("input", () => {
      const k = inp.dataset.g, v = num(inp.value);
      if (isNaN(v)) return;
      S.gains[k] = v;
      $$(`#gains input[data-g="${k}"]`).forEach((o) => { if (o !== inp) o.value = v; paintRange(o); });
      scheduleRun();
    });
  });
}
function paintRange(inp) {
  if (inp.type !== "range") return;
  inp.style.setProperty("--p", `${((inp.value - inp.min) / (inp.max - inp.min)) * 100}%`);
}

function setDevType(v) {
  S.devType = v;
  $$("#dev-type button").forEach((b) => b.setAttribute("aria-pressed", b.dataset.v === v));
  $$(".dev-pane").forEach((p) => (p.hidden = p.dataset.for !== v));
  $("#gains-hint").hidden = !(v === "socket" || v === "serial");
  if (v === "serial") refreshPorts();
}

async function refreshPorts() {
  const ports = await api("/api/ports").catch(() => []);
  $("#ser-port").innerHTML = ports.length
    ? ports.map((p) => `<option value="${p.port}">${p.port} · ${p.desc}</option>`).join("")
    : `<option value="">No serial ports found</option>`;
}

async function refreshBoard(method) {
  const port = +$("#sock-port").value;
  const st = await api("/api/firmware", method === "POST" ? { port } : null, method);
  $(".board").classList.toggle("on", st.running);
  $("#board-toggle").textContent = st.running ? "Stop virtual board" : "Start virtual board";
  $("#board-state").textContent = st.running ? `Virtual board answering on port ${st.port}.`
                                             : "No firmware? Start a virtual one on this port.";
  return st;
}

function setPlant(type, params) {
  S.plantType = type;
  $("#plant-type").value = type;
  const cat = S.catalog.plants[type];
  S.plantParams = { ...(cat ? cat.params : {}), ...(params || {}) };
  $("#plant-doc").textContent = cat ? cat.doc.split("\n")[0] : "Any Python class that subclasses xiloop.Plant.";
  $("#plant-custom-wrap").hidden = type !== "custom";
  $("#plant-params").innerHTML = Object.entries(S.plantParams).map(([k, v]) => {
    const str = typeof v === "string";
    return `<label class="${str ? "wide" : ""}">${k}${str ? " (coefficients, highest power of s first)" : ""}
              <input data-p="${k}" ${str ? "" : "inputmode=\"decimal\" data-num"} value="${v}" spellcheck="false"></label>`;
  }).join("");
  $$("#plant-params input").forEach((inp) => inp.addEventListener("input", () => {
    S.plantParams[inp.dataset.p] = "num" in inp.dataset ? num(inp.value) : inp.value;
    renderTF();
    scheduleRun();
  }));
  renderTF();
}

function poly(str) {
  const c = String(str).replace(/,/g, " ").trim().split(/\s+/).map(Number);
  if (!c.length || c.some(isNaN)) return null;
  const sup = "⁰¹²³⁴⁵⁶⁷⁸⁹";
  const terms = c.map((k, i) => {
    const p = c.length - 1 - i;
    if (k === 0) return null;
    const s = p === 0 ? "" : p === 1 ? "s" : "s" + [...String(p)].map((d) => sup[d]).join("");
    const coef = s && Math.abs(k) === 1 ? (k < 0 ? "−" : "") : fmt(k);
    return coef + s;
  }).filter(Boolean);
  return terms.length ? terms.join(" + ").replace(/\+ -/g, "− ") : "0";
}
function renderTF() {
  const box = $("#tf-preview");
  box.hidden = S.plantType !== "transfer_function";
  if (box.hidden) return;
  const n = poly(S.plantParams.num), d = poly(S.plantParams.den);
  box.classList.toggle("err", !n || !d);
  box.innerHTML = n && d ? `G(s) = <span class="frac"><span>${n}</span><span>${d}</span></span>`
                         : "Type the coefficients as numbers separated by spaces, e.g. 0.5 1";
}

/* --------------------------------------------------------- verify */
function renderPlan() {
  const metrics = Object.keys(S.catalog.metrics);
  $("#scen-table tbody").innerHTML = S.plan.scenarios.map((s, i) => `<tr>
      <td><input data-i="${i}" data-k="name" value="${esc(s.name)}"></td>
      <td><input data-i="${i}" data-k="setpoint" inputmode="decimal" data-num value="${s.setpoint}"></td>
      <td><input data-i="${i}" data-k="duration" inputmode="decimal" data-num value="${s.duration}"></td>
      <td><input data-i="${i}" data-k="dt" inputmode="decimal" data-num value="${s.dt ?? 0.001}"></td>
      <td class="x"><button data-del="${i}" aria-label="Remove scenario">×</button></td></tr>`).join("");
  $("#req-table tbody").innerHTML = S.plan.requirements.map((r, i) => `<tr>
      <td style="width:68px"><input data-i="${i}" data-k="id" value="${esc(r.id || "")}"></td>
      <td><input data-i="${i}" data-k="description" value="${esc(r.description || "")}"></td>
      <td style="width:124px"><select data-i="${i}" data-k="metric" title="${esc(S.catalog.metrics[r.metric] || "")}">
        ${metrics.map((m) => `<option ${m === r.metric ? "selected" : ""}>${m}</option>`).join("")}</select></td>
      <td style="width:64px"><input data-i="${i}" data-k="min" inputmode="decimal" data-num value="${r.min ?? ""}"></td>
      <td style="width:64px"><input data-i="${i}" data-k="max" inputmode="decimal" data-num value="${r.max ?? ""}"></td>
      <td class="x"><button data-del="${i}" aria-label="Remove requirement">×</button></td></tr>`).join("");
}
function esc(s) { return String(s).replace(/[&"<>]/g, (c) => ({ "&": "&amp;", '"': "&quot;", "<": "&lt;", ">": "&gt;" }[c])); }

function bindTable(sel, list) {
  const tb = $(`${sel} tbody`);
  tb.addEventListener("input", (e) => {
    const { i, k } = e.target.dataset;
    if (i == null) return;
    const row = S.plan[list][+i], v = e.target.value;
    if ("num" in e.target.dataset) { if (v === "") delete row[k]; else row[k] = num(v); }
    else row[k] = v;
  });
  tb.addEventListener("click", (e) => {
    if (e.target.dataset.del == null) return;
    S.plan[list].splice(+e.target.dataset.del, 1);
    renderPlan();
  });
}

function loadPlan(plan) {
  $("#plan-name").value = plan.name || "Untitled campaign";
  S.plan = {
    scenarios: (plan.scenarios || []).map((s) => ({ dt: 0.001, ...s })),
    requirements: (plan.requirements || []).map((r) => ({ ...r })),
  };
  if (plan.device) applyDevice(plan.device);
  if (plan.plant) {
    const p = typeof plan.plant === "string" ? { type: plan.plant } : plan.plant;
    const known = S.catalog.plants[p.type] ? p.type
      : Object.keys(S.catalog.plants).find((k) => k.includes(p.type.split(":").pop().replace("Plant", "").toLowerCase()));
    if (known || !p.type.includes(":")) setPlant(known || p.type, p.params);
    else { setPlant("custom", p.params); $("#plant-custom").value = p.type; }
  }
  renderPlan();
}
function applyDevice(d) {
  d = typeof d === "string" ? { type: d } : d;
  const t = ["pid", "socket", "serial"].includes(d.type) ? d.type : "custom";
  if (t === "custom") $("#cust-class").value = d.type;
  if (d.host) $("#sock-host").value = d.host;
  if (d.port && t === "socket") $("#sock-port").value = d.port;
  if (d.baud) $("#ser-baud").value = d.baud;
  Object.assign(S.gains, d.params || {});
  setDevType(t);
  renderGains();
}

async function runCampaign() {
  if (S.job) return stopJob();
  const t0 = performance.now();
  try {
    if (!S.plan.scenarios.length) throw new Error("Add at least one scenario first.");
    const body = { kind: "campaign", ...planBody() };
    resetVChart();
    const r = await streamJob(body, vchart, "#v-status", "#v-run");
    if (!r) return;
    S.campaign = r;
    renderResults(r);
    status("#v-status", `${r.scenarios.length} scenarios · ${dur(t0)}`);
  } catch (e) {
    status("#v-status", e.message, true);
  }
}

function resetVChart() {   // live view: one trace + its setpoint, like Tune
  const el = $("#v-chart");
  vchart.destroy(); el.innerHTML = "";
  vchart = makeChart(el, { band: false });
}

function renderResults(r) {
  const stamp = $("#stamp");
  stamp.className = `stamp ${r.passed ? "pass" : "fail"}`;
  stamp.textContent = r.passed ? "PASS" : "FAIL";
  void stamp.offsetWidth; stamp.classList.add("land");
  const reqs = r.scenarios.flatMap((s) => s.requirements);
  const failed = reqs.filter((q) => !q.passed).length;
  $("#v-title").textContent = r.name;
  $("#v-sub").textContent = failed ? `${failed} of ${reqs.length} checks failed`
                                   : `All ${reqs.length} checks passed`;
  $("#rep-md").disabled = $("#rep-csv").disabled = false;
  $("#res-table tbody").innerHTML = r.scenarios.map((s) => s.requirements.map((q, j) => `
      <tr class="${j === 0 ? "first" : ""}"><td>${j === 0 ? esc(s.name) : ""}</td><td title="${esc(q.description)}">${esc(q.req_id)}</td>
      <td>${q.metric}</td><td>${q.measured == null ? "∞" : fmt(q.measured)}</td><td>${esc(q.bound)}</td>
      <td class="${q.passed ? "ok" : "no"}">${q.passed ? "PASS" : "FAIL"}</td></tr>`).join("")).join("");
  // overlay every scenario on one sheet of paper
  const n = r.scenarios.length;
  const el = $("#v-chart");
  vchart.destroy(); el.innerHTML = "";
  vchart = makeChart(el, { band: false, multi: n });
  const sets = r.scenarios.map((s) => [s.t, s.y]);
  const sps = r.scenarios.map((s) => [s.t, s.t.map(() => s.setpoint)]);
  const joined = uPlot.join([...sets, ...sps]);
  vchart.setData(joined);
}

/* ----------------------------------------------------------- files */
async function saveFile(name, text) {
  if (window.pywebview && window.pywebview.api && window.pywebview.api.save_file) {
    const where = await window.pywebview.api.save_file(name, text);
    if (where) status(S.mode === "tune" ? "#status" : "#v-status", `Saved ${where}`);
    return;
  }
  const a = Object.assign(document.createElement("a"),
    { href: URL.createObjectURL(new Blob([text], { type: "text/plain" })), download: name });
  a.click();
  URL.revokeObjectURL(a.href);
}
const slug = (s) => s.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "") || "campaign";

/* ------------------------------------------------------------- API dialog */
function apiSnippet(lang) {
  const tune = S.mode === "tune";
  const path = tune ? "/api/simulate" : "/api/campaign";
  const body = tune ? { device: deviceSpec(), plant: plantSpec(), ...scenario() } : planBody();
  const json = JSON.stringify(body, null, 2);
  if (lang === "json") return json;
  if (lang === "python") return `import requests\n\nbody = ${json.replace(/\btrue\b/g, "True").replace(/\bfalse\b/g, "False").replace(/\bnull\b/g, "None")}\n\nr = requests.post("${API}${path}", json=body).json()\nprint(r${tune ? '["metrics"]' : '["passed"], r["markdown"]'})`;
  return `curl -X POST ${API}${path} \\\n  -H "Content-Type: application/json" \\\n  -d '${JSON.stringify(body)}'`;
}

/* ------------------------------------------------------------- boot */
async function health() {
  const chip = $("#conn");
  try {
    const h = await api("/api/health");
    chip.className = "chip ok";
    $("span", chip).textContent = `API ${location.host} · v${h.version}`;
  } catch {
    chip.className = "chip bad";
    $("span", chip).textContent = "API not reachable";
  }
}

async function boot() {
  S.catalog = await api("/api/catalog");
  $(".run-ctl").insertAdjacentHTML("afterbegin", '<span class="status" id="cursor"></span>');

  $("#plant-type").innerHTML = Object.keys(S.catalog.plants)
    .map((k) => `<option value="${k}">${PLANT_LABEL[k] || k}</option>`).join("")
    + `<option value="custom">Custom class…</option>`;
  setPlant("actuator");
  renderGains();
  renderMeters(null);

  chart = makeChart($("#chart"));
  vchart = makeChart($("#v-chart"), { band: false });

  // mode tabs
  $$(".mode").forEach((b) => b.addEventListener("click", () => {
    S.mode = b.dataset.mode;
    $$(".mode").forEach((o) => o.setAttribute("aria-selected", o === b));
    $("#view-tune").hidden = S.mode !== "tune";
    $("#view-verify").hidden = S.mode !== "verify";
    $$("[data-show]").forEach((el) => (el.hidden = el.dataset.show !== S.mode));
  }));

  // rail
  $$("#dev-type button").forEach((b) => b.addEventListener("click", () => { setDevType(b.dataset.v); if (b.dataset.v === "pid") scheduleRun(); }));
  $("#plant-type").addEventListener("change", (e) => { setPlant(e.target.value); scheduleRun(); });
  $("#plant-custom").addEventListener("change", scheduleRun);
  ["#sc-sp", "#sc-dur", "#sc-dt"].forEach((id) => $(id).addEventListener("input", scheduleRun));
  $("#ser-refresh").addEventListener("click", refreshPorts);
  $("#board-toggle").addEventListener("click", () =>
    refreshBoard($(".board").classList.contains("on") ? "DELETE" : "POST").catch((e) => status("#status", e.message, true)));
  $("#run").addEventListener("click", runTune);
  $$("#legend button").forEach((b) => b.addEventListener("click", () => {
    const on = b.getAttribute("aria-pressed") !== "true";
    b.setAttribute("aria-pressed", on);
    if (b.dataset.s === "band") { chart.showBand = on; chart.redraw(); }
    else chart.setSeries(+b.dataset.s, { show: on });
  }));

  // verify
  bindTable("#scen-table", "scenarios");
  bindTable("#req-table", "requirements");
  $("#add-scen").addEventListener("click", () => {
    S.plan.scenarios.push({ name: `step_${S.plan.scenarios.length + 1}`, setpoint: 1, duration: 3, dt: 0.001 });
    renderPlan();
  });
  $("#add-req").addEventListener("click", () => {
    S.plan.requirements.push({ id: `REQ-${S.plan.requirements.length + 1}`, description: "", metric: "overshoot_pct", max: 20 });
    renderPlan();
  });
  const examples = await api("/api/examples");
  $("#ex-pick").insertAdjacentHTML("beforeend", examples.map((e, i) => `<option value="${i}">${esc(e.plan.name || e.name)}</option>`).join(""));
  $("#ex-pick").addEventListener("change", (e) => {
    if (e.target.value !== "") loadPlan(examples[+e.target.value].plan);
    e.target.value = "";
  });
  $("#yaml-import").addEventListener("click", () => $("#yaml-file").click());
  $("#yaml-file").addEventListener("change", async (e) => {
    const f = e.target.files[0];
    if (!f) return;
    try { loadPlan((await api("/api/plan/parse", { yaml: await f.text() })).plan); }
    catch (err) { status("#v-status", `Could not read ${f.name}: ${err.message}`, true); }
    e.target.value = "";
  });
  $("#yaml-export").addEventListener("click", async () => {
    const b = planBody();
    const { yaml } = await api("/api/plan/dump", { plan: { ...b.plan, plant: b.plant, device: b.device } });
    saveFile(`${slug(b.plan.name)}.yaml`, yaml);
  });
  $("#v-run").addEventListener("click", runCampaign);
  $("#rep-md").addEventListener("click", () => saveFile(`${slug(S.campaign.name)}_report.md`, S.campaign.markdown));
  $("#rep-csv").addEventListener("click", () => {
    const rows = ["scenario,t,setpoint,measurement,command"];
    for (const s of S.campaign.scenarios)
      s.t.forEach((t, i) => rows.push(`${s.name},${t},${s.setpoint},${s.y[i]},${s.u[i]}`));
    saveFile(`${slug(S.campaign.name)}_telemetry.csv`, rows.join("\n") + "\n");
  });

  // api dialog
  let lang = "curl";
  const showCode = () => ($("#api-code").textContent = apiSnippet(lang));
  $("#api-open").addEventListener("click", () => { showCode(); $("#api-dlg").showModal(); });
  $$("#api-lang button").forEach((b) => b.addEventListener("click", () => {
    lang = b.dataset.v;
    $$("#api-lang button").forEach((o) => o.setAttribute("aria-pressed", o === b));
    showCode();
  }));
  $("#api-copy").addEventListener("click", async () => {
    await navigator.clipboard.writeText($("#api-code").textContent);
    $("#api-copy").textContent = "Copied";
    setTimeout(() => ($("#api-copy").textContent = "Copy"), 1200);
  });

  loadPlan(examples.find((e) => e.name === "actuator_pid")?.plan || { scenarios: [], requirements: [] });
  refreshBoard("GET").catch(() => {});
  health(); setInterval(health, 5000);
  runTune();
}

boot().catch((e) => {
  document.body.insertAdjacentHTML("afterbegin", `<p style="padding:12px;color:#C2342B">XiLoop Studio could not start: ${esc(e.message)}</p>`);
});
