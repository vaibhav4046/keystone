"use strict";
// Keystone web hero. Talks to the FastAPI core. Every number shown comes from
// the API (engine-computed); this script only renders and animates.
const $ = (s) => document.querySelector(s);
const reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

// Live-API-first, static-bundle fallback so the hero deploys with no backend.
let STATIC = null, STATIC_MODE = false;
async function ensureStatic() {
  if (STATIC) return STATIC;
  STATIC = await fetch("data.json").then((r) => r.json());
  return STATIC;
}
function fromStatic(p) {
  const s = STATIC;
  if (p === "/api/status") return s.status;
  if (p === "/api/definitions") return { names: s.definitions };
  if (p === "/api/audit") return s.audit;
  if (p === "/api/audit/verify") return s.audit.verify;
  if (p === "/api/policy") return s.policy || {};
  if (p.startsWith("/api/impact/")) { const n = decodeURIComponent(p.split("/").pop()); return s.impact[n] || {}; }
  if (p.startsWith("/api/precedent/")) { const n = decodeURIComponent(p.split("/").pop()); return s.precedent[n] || { match_count: 0 }; }
  if (p.startsWith("/api/brief/")) { const n = decodeURIComponent(p.split("/").pop()); return (s.brief && s.brief[n]) || { brief: "", deterministic: true }; }
  if (p === "/api/graph-audit") return s.graph_audit || { items: [], counts: {}, verdict: "" };
  if (p.startsWith("/api/attestation/")) {
    const n = decodeURIComponent(p.split("/").pop());
    const att = (s.attestation || {})[n];
    if (!att) throw new Error("no recorded decision for " + n);
    return { attestation: att, verify: { ok: true, chain_ok: true, row_present: true, reason: "sample" } };
  }
  throw new Error("no static route " + p);
}
const api = async (p) => {
  if (!STATIC_MODE) {
    try {
      const r = await fetch(p);
      if (r.ok) return await r.json();
      throw new Error(p + " " + r.status);
    } catch (e) {
      // first failure: switch to static bundle for the rest of the session
      try { await ensureStatic(); STATIC_MODE = true; } catch (e2) { throw e; }
    }
  }
  await ensureStatic();
  return fromStatic(p);
};

let STATE = { defs: [], selected: null, impact: null };
window.STATE = STATE;                       // exposed for the motion layer (motion.js)

const RING_COLOR = { 0: "#FF5C66", 1: "#FF8A2B", 2: "#F5C542", 3: "#5BBFD6" };
function ringColor(r) { return RING_COLOR[r] || "#7A8494"; }

async function boot() {
  try {
    const st = await api("/api/status");
    paintStatus(st);
  } catch (e) { /* status optional */ }
  const d = await api("/api/definitions");
  STATE.defs = d.names;
  renderDefList(STATE.defs);
  await refreshLedger();
  loadHazards();
  // auto-select the headline demo symbol: compute_blast_radius (Keystone's own engine,
  // BLOCKed by prior precedent) on the real self-index, tokenize on the fixture, else top.
  if (STATE.defs.length) {
    const demo = STATE.defs.includes("compute_blast_radius") ? "compute_blast_radius"
      : (STATE.defs.includes("tokenize") ? "tokenize" : STATE.defs[0]);
    select(demo);
  }
  wire();
}

function paintStatus(st) {
  const src = $("#src-chip"), orbit = $("#orbit-chip"), chain = $("#chain-chip"), integ = $("#integ-chip");
  const live = st.source_mode === "LIVE";
  const snapshot = st.source_mode === "SNAPSHOT";   // committed REAL orbit index, served without a backend
  src.innerHTML = `<span class="dot ${live ? "g" : (snapshot ? "g" : "a")}"></span>source <b>${esc(st.source_mode)}</b>`;
  src.className = "chip " + (live || snapshot ? "ok" : "warn");
  if (snapshot) src.title = "a committed REAL `orbit index` of this repository (" + (st.definitions || "") +
    " definitions) — every number is engine-computed and cross-verified by orbit sql; served as a static snapshot (no backend).";
  orbit.innerHTML = `orbit <b>${esc(st.orbit_access)}</b>`;
  const cliVerified = /CLI/.test(st.orbit_access || "");
  orbit.className = "chip " + (cliVerified ? "ok" : "");
  orbit.title = cliVerified ? ((st.orbit_verified_symbols || 0) + " symbols' direct-caller counts were reproduced by Orbit's own `orbit sql` CLI against the committed index; see the IMPACT panel's orbit-verified badge.") : "";
  const ok = st.audit_chain && st.audit_chain.ok;
  const staticChain = STATIC_MODE || !!STATIC;       // public bundle uses a published key
  if (!ok) {
    chain.innerHTML = `<span class="dot r"></span>chain <b>broken@${st.audit_chain.broken_index}</b>`;
    chain.className = "chip bad";
  } else if (staticChain) {
    chain.innerHTML = `<span class="dot a"></span>chain <b>sample</b>`;   // honest: not live-verified
    chain.className = "chip warn";
    chain.title = "public sample uses a published HMAC key; tamper-evidence requires the local secret key";
  } else {
    chain.innerHTML = `<span class="dot g"></span>chain <b>verified</b>`;
    chain.className = "chip ok";
  }
  if (integ) {
    const hmac = st.integrity && st.integrity.hmac;
    integ.innerHTML = `integrity <b>${hmac ? "HMAC" : "sha256"}</b>`;
    integ.title = "ledger row hashes are " + (hmac ? "HMAC-keyed (forged appends fail without the server key)" : "sha256-chained (detects edits)");
  }
  const oc = $("#orbit-cli");
  if (oc) {
    const tx = (st.orbit_cli_transcript || []).filter((e) => e.ok);
    const last = tx[tx.length - 1];
    if (last) { oc.textContent = last.subcommand + " ✓" + (st.orbit_cli_recorded ? " (rec)" : ""); oc.title = last.command || ""; }
    else { oc.textContent = "—"; }
  }
  STATE.windowEnforced = !!st.window_enforced;
  const integ2 = st.integrity || {};
  if (integ) integ.innerHTML = `integrity <b>${integ2.hmac ? "HMAC" : "sha256"}</b>` + (integ2.reviewer_verified ? "" : ` · <span class="adv">id advisory</span>`);
  const banner = $("#open-banner");
  if (banner) {
    if (integ2.open_mode) {
      banner.hidden = false;
      banner.innerHTML = "OPEN MODE — no approve token is set, so any caller can record a decision and identity is self-asserted (four-eyes and agent gating are advisory). Set KEYSTONE_APPROVE_TOKEN / bind GitLab OIDC for an enforced deployment.";
    } else { banner.hidden = true; }
  }
  const modeLabel = st.source_mode === "LIVE" ? "Orbit Local (live)"
    : (st.source_mode === "SNAPSHOT" ? "Orbit index (real, committed)" : "fixture (FALLBACK)");
  $("#db-mode").textContent = modeLabel;
  $("#def-count").textContent = st.definitions;
  $("#db-path").textContent = (st.duckdb_path || "").split(/[\\/]/).slice(-2).join("/");
  $("#db-path").title = st.duckdb_path || "";
  const footSrc = st.source_mode === "LIVE" ? "LIVE Orbit Local graph"
    : (st.source_mode === "SNAPSHOT"
        ? ("real Orbit index of this repo · " + (st.orbit_verified_symbols || 0) + " symbols cross-verified by orbit sql")
        : "FALLBACK sample graph; live graph runs locally and is shown in the demo video");
  $("#foot-src").textContent = footSrc + " · " + st.duckdb_path;
  const prov = $("#data-provenance");
  if (prov && st.data_provenance) { prov.textContent = st.data_provenance; prov.hidden = false; }
}

function renderDefList(names) {
  const ul = $("#deflist");
  ul.innerHTML = "";
  names.forEach((n) => {
    const li = document.createElement("li");
    li.dataset.name = n;
    li.textContent = n;                 // textContent, not innerHTML: no injection from symbol names
    li.setAttribute("role", "option");
    li.setAttribute("tabindex", "0");
    li.setAttribute("aria-selected", n === STATE.selected ? "true" : "false");
    li.onclick = () => select(n);
    li.onkeydown = (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); select(n); } };
    if (n === STATE.selected) li.classList.add("sel");
    ul.appendChild(li);
  });
}

async function select(name) {
  STATE.selected = name;
  // a fresh change id per selection = one MR; quorum accumulates across approvers
  // of this same change, and is separate from any other change on the same symbol
  STATE.changeId = (window.crypto && crypto.randomUUID) ? "MR-" + crypto.randomUUID().slice(0, 8) : "MR-" + (STATE._n = (STATE._n || 0) + 1);
  document.querySelectorAll("#deflist li").forEach((li) => {
    const on = li.dataset.name === name;
    li.classList.toggle("sel", on);
    li.setAttribute("aria-selected", on ? "true" : "false");
  });
  $("#epi").textContent = name;
  const wrap = $(".canvas-wrap"), rings = $("#rings");
  if (wrap) wrap.classList.add("loading");
  if (rings) rings.setAttribute("aria-busy", "true");
  const imp = await api("/api/impact/" + encodeURIComponent(name));
  STATE.impact = imp;
  if (wrap) wrap.classList.remove("loading");
  if (rings) rings.removeAttribute("aria-busy");
  drawBlast(imp);
  renderRings(imp);
  const prec = await api("/api/precedent/" + encodeURIComponent(name));
  renderPrecedent(prec);
  renderBrief({ brief: "…", deterministic: true });
  api("/api/brief/" + encodeURIComponent(name)).then(renderBrief).catch(() => {});
  const ab = $("#assistant"); if (ab) ab.innerHTML = `<div class="muted">the agent is inspecting ${esc(name)} with engine tools…</div>`;
  callAssistant(name).then((r) => { if (STATE.selected === name) renderAssistant(r); }).catch(() => {});
  const ag = $("#assistant-go"); if (ag) ag.disabled = false;
  $("#reject").disabled = false;
  const ex = $("#export-att"); if (ex) ex.disabled = false;
  applyGatePolicy();
}

// Enforcement in the UI: a policy BLOCK disables APPROVE unless the reviewer ticks
// the accountable override; HOLD warns. Mirrors the backend 409 GOVERNANCE_BLOCK.
function applyGatePolicy() {
  const pol = STATE.impact && STATE.impact.policy;
  const ov = $("#override"), ovRow = $("#override-row"), status = $("#gate-status");
  const blocked = pol && pol.action === "BLOCK";
  if (ovRow) ovRow.style.display = blocked ? "block" : "none";
  if (!blocked && ov) ov.checked = false;
  $("#approve").disabled = !!(blocked && !(ov && ov.checked));
  if (status) {
    if (blocked) { status.textContent = "Policy action is BLOCK — approval is not permitted without an override."; status.style.color = "var(--danger-2)"; }
    else if (pol && pol.action === "HOLD") { status.textContent = "Policy action is HOLD — " + pol.required_approvers + " approvers required."; status.style.color = "var(--amber)"; }
    else { status.textContent = ""; }
  }
}

async function exportAttestation() {
  if (!STATE.selected) return;
  const note = $("#sample-note");
  try {
    const r = await api("/api/attestation/" + encodeURIComponent(STATE.selected));
    const blob = new Blob([JSON.stringify(r.attestation, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "keystone-attestation-" + STATE.selected + ".json";
    document.body.appendChild(a); a.click(); a.remove();
    if (note) { note.textContent = "exported in-toto/SLSA-VSA attestation (HMAC-anchored; verify=" + (r.verify && r.verify.ok) + ")"; note.style.opacity = "1"; }
  } catch (e) {
    if (note) { note.textContent = "approve or reject first — an attestation is minted from a recorded decision"; note.style.opacity = "1"; }
  }
}

// ---- blast radius SVG reveal ----
function drawBlast(imp) {
  const svg = $("#bsvg");
  svg.innerHTML = "";
  const ttl = document.createElementNS("http://www.w3.org/2000/svg", "title");
  ttl.setAttribute("id", "bsvg-title");
  ttl.textContent = `Blast radius of ${imp.epicenter.name}: ${imp.counts.total_affected} affected definitions, listed in the IMPACT panel.`;
  svg.appendChild(ttl);
  // cancel any in-flight reveal/counter timers from a previous selection so a fast
  // click-through cannot leave a stale, corrupted count on screen
  _timers.forEach(clearTimeout); _timers = []; _ctv = 0;
  const W = 600, H = 420, cx = 300, cy = 210;
  const rings = imp.rings; // {"0":[id], "1":[...], ...}
  const maxRing = Math.max(...Object.keys(rings).map(Number));
  const radii = { 0: 0 };
  for (let r = 1; r <= maxRing; r++) radii[r] = 60 + (r - 1) * 78;

  // position nodes deterministically around their ring
  const pos = {};
  const order = [];
  Object.keys(rings).map(Number).sort((a, b) => a - b).forEach((r) => {
    const ids = rings[r];
    ids.forEach((id, i) => {
      let x = cx, y = cy;
      if (r > 0) {
        const ang = (-Math.PI / 2) + (2 * Math.PI * i) / ids.length + r * 0.6;
        x = cx + radii[r] * Math.cos(ang);
        y = cy + radii[r] * Math.sin(ang) * 0.82;
      }
      pos[id] = { x, y, r };
      order.push({ id, r, i });
    });
  });

  const ns = "http://www.w3.org/2000/svg";
  // ring guides
  for (let r = 1; r <= maxRing; r++) {
    const c = document.createElementNS(ns, "ellipse");
    c.setAttribute("cx", cx); c.setAttribute("cy", cy);
    c.setAttribute("rx", radii[r]); c.setAttribute("ry", radii[r] * 0.82);
    c.setAttribute("fill", "none"); c.setAttribute("stroke", "#1c1e24"); c.setAttribute("stroke-dasharray", "3 5");
    svg.appendChild(c);
  }
  // edges follow the REAL BFS parent (who actually calls whom), not an arbitrary hub,
  // so the diagram's topology matches the graph. parents = {childId: parentId}.
  const parents = imp.parents || {};
  const edges = [];
  Object.keys(rings).map(Number).sort((a, b) => a - b).forEach((r) => {
    if (r === 0) return;
    rings[r].forEach((id) => {
      let inner = parents[String(id)];
      if (inner === undefined || inner === null) inner = (r === 1 ? imp.epicenter.id : rings[r - 1][0]);
      if (pos[inner]) edges.push([inner, id, r]);
    });
  });
  const eEls = edges.map(([a, b]) => {
    const l = document.createElementNS(ns, "line");
    l.setAttribute("x1", pos[a].x); l.setAttribute("y1", pos[a].y);
    l.setAttribute("x2", pos[b].x); l.setAttribute("y2", pos[b].y);
    l.setAttribute("class", "edge");
    svg.appendChild(l); return l;
  });
  // nodes. Dense rings (the live graph puts 12 nodes in ring-1) would overlap, so
  // labels are truncated with a full-name <title> tooltip, and on very dense rings
  // labels are hidden (the names stay listed exactly in the IMPACT panel).
  const nodeEls = [];
  order.forEach(({ id, r }) => {
    const g = document.createElementNS(ns, "g");
    g.setAttribute("class", "node");
    const isEpi = id === imp.epicenter.id;
    const full = nameOf(imp, id);
    const ttl = document.createElementNS(ns, "title");
    ttl.textContent = full;
    g.appendChild(ttl);                                  // hover shows the full name
    const circ = document.createElementNS(ns, "circle");
    circ.setAttribute("cx", pos[id].x); circ.setAttribute("cy", pos[id].y);
    circ.setAttribute("r", isEpi ? 16 : 9);
    circ.setAttribute("fill", ringColor(r));
    if (isEpi) circ.setAttribute("filter", "url(#glow)");
    g.appendChild(circ);
    const dense = (rings[r] || []).length > 8;
    if (!dense || isEpi) {
      const t = document.createElementNS(ns, "text");
      t.setAttribute("x", pos[id].x); t.setAttribute("y", pos[id].y + (isEpi ? 30 : 20));
      t.setAttribute("text-anchor", "middle"); t.setAttribute("fill", isEpi ? "#EDEDED" : "#9BA3AE");
      t.setAttribute("font-size", isEpi ? "13" : "11"); t.setAttribute("font-family", "ui-monospace, Menlo, Consolas, monospace");
      const label = full.length > 11 ? full.slice(0, 10) + "…" : full;
      t.textContent = label;
      g.appendChild(t);
    }
    svg.appendChild(g); nodeEls.push({ g, r, id });
  });
  // glow filter
  const defs = document.createElementNS(ns, "defs");
  defs.innerHTML = '<filter id="glow" x="-80%" y="-80%" width="260%" height="260%"><feGaussianBlur stdDeviation="5" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>';
  svg.insertBefore(defs, svg.firstChild);

  // animate reveal + counter to total_affected
  imp._names = imp._names || idNames(imp);
  const total = imp.counts.total_affected;
  if (reduceMotion) {
    nodeEls.forEach((n) => n.g.classList.add("show"));
    eEls.forEach((e) => e.classList.add("show"));
    $("#counter").textContent = pad(total);
    return;
  }
  $("#counter").textContent = "0000";
  let revealed = 0;
  nodeEls.forEach((n, idx) => {
    const delay = n.r === 0 ? 0 : 180 + n.r * 230 + (idx % 5) * 40;
    _timers.push(setTimeout(() => {
      n.g.classList.add("show");
      if (n.id !== imp.epicenter.id) { revealed++; animateCounterTo(revealed); }
    }, delay));
  });
  eEls.forEach((e, i) => _timers.push(setTimeout(() => e.classList.add("show"), 220 + i * 60)));
  _timers.push(setTimeout(() => $("#counter").textContent = pad(total), 200 + maxRing * 230 + 400));
  imp._names = imp._names || idNames(imp);
  if (window.__ksRenderGraph) window.__ksRenderGraph(imp);   // premium 3D graph (motion.js); SVG stays as fallback
}
let _ctv = 0, _timers = [];
function animateCounterTo(v) { _ctv = v; $("#counter").textContent = pad(v); }
function pad(n) { return String(n).padStart(4, "0"); }
function idNames(imp) { const m = {}; Object.keys(imp.names || {}).forEach((k) => m[Number(k)] = imp.names[k]); return m; }
function nameOf(imp, id) { return (imp._names && imp._names[id]) || (imp.names && imp.names[String(id)]) || ("#" + id); }

function renderRings(imp) {
  const box = $("#rings");
  const c = imp.counts;
  const epiSub = imp.epicenter.fqn || imp.epicenter.file || "";
  const rows = [["0", "EPICENTER", 1, esc(imp.epicenter.name) + (epiSub ? ` <span class="rn-sub">${esc(epiSub)}</span>` : "")]];
  Object.keys(imp.rings).map(Number).sort((a, b) => a - b).forEach((r) => {
    if (r === 0) return;
    const tag = r === 1 ? "DIRECT" : (r === 2 ? "TRANSITIVE" : "AT RISK");
    rows.push([String(r), `R${r} ${tag}`, imp.rings[r].length,   // R-prefix: severity not by colour alone
      imp.rings[r].map((id) => esc(nameOf(imp, id))).join(", ")]);
  });
  rows.push(["U", "UNAFFECTED", c.unaffected, ""]);
  let html = rows.map(([r, label, n, names]) =>
    `<div class="ringrow r${r}"><span class="rl">${label}</span><span class="rc tabnum">${n}</span><span class="rn">${names || "—"}</span></div>`
  ).join("");
  if (c.total_affected === 0) {
    html += `<div class="leaf-note">leaf symbol — nothing depends on it, so changing it is contained by design. Try <b>compute_blast_radius</b> (a BLOCK from prior precedent) or <b>append</b> (a 3-ring blast) to see a real radius and a recorded decision.</div>`;
  }
  const cc = imp.orbit_crosscheck;
  if (cc && cc.ok) {
    html += `<div class="orbit-verified" title="${esc(cc.command || "")}"><span class="ov-dot"></span>` +
      `orbit-verified · ring-1 = <b>${cc.ring1_cli}</b> reproduced by <code>orbit sql</code>` +
      (cc.match ? " · matches engine" : " · differs (engine wins)") +
      (cc.command ? `<div class="ov-cmd">${esc(cc.command)}</div>` : "") + `</div>`;
  }
  html += `<div class="sig">blast signature <b>${esc(imp.signature.slice(0, 16))}…</b> · sha256 over the epicenter + sorted affected id set</div>`;
  const pol = imp.policy;
  if (pol) {
    const act = pol.action;                            // ALLOW | HOLD | BLOCK
    const cls = act === "BLOCK" ? "bad" : (act === "HOLD" ? "warn" : "ok");
    html += `<div class="gov ${cls}">` +
      `<div class="gov-top"><span class="tier tier-${esc(pol.tier)}">${esc(pol.tier)}</span>` +
      `<span class="gov-act ${cls}">${esc(act)}</span>` +
      `<span class="gov-need">requires ${pol.required_approvers} approver${pol.required_approvers === 1 ? "" : "s"}` +
      (pol.review_window_hours ? ` · ${pol.review_window_hours}h window${STATE.windowEnforced ? "" : " [advisory]"}` : "") + `</span></div>` +
      (pol.required_owner ? `<div class="gov-owner">owner to pull in: <b>${esc(pol.required_owner)}</b></div>` : "") +
      `<ul class="gov-why">` + (pol.reasons || []).map((r) => `<li>${esc(r)}</li>`).join("") + `</ul>` +
      `<div class="gov-foot">policy v${esc(pol.policy_version)} · ${esc((pol.policy_hash || "").slice(0, 12))}… · graph-driven, no model</div>` +
      `</div>`;
  }
  box.innerHTML = html;
}

function renderPrecedent(p) {
  const box = $("#precedent");
  if (!p || p.match_count === 0) { box.innerHTML = `<div class="muted">No prior governed decisions on this symbol.</div>`; return; }
  let html = `<div class="counts"><span class="ap">approved <b class="tabnum">${p.approved}</b></span><span class="rj">rejected <b class="tabnum">${p.rejected}</b></span><span>matches <b class="tabnum">${p.match_count}</b></span></div>`;
  if (p.contradiction) {
    const c = p.contradiction;
    const strong = p.contradiction_strength === "identical";   // identical blast signature = the strong beat
    const cls = strong ? "contradiction" : "contradiction weak";
    const ttl = strong ? "CONTRADICTION · identical blast signature"
                       : "PRIOR REJECTION · same symbol, different blast radius";
    const line = strong ? "rejected this exact blast radius."
                        : "rejected a change to this symbol with a different blast radius. Review before approving.";
    html += `<div class="${cls}" role="alert"><span class="ttl">${ttl}</span>
      ${esc(c.actor)} ${esc(c.change_id)} ${line}
      <div class="quote">"${esc(c.rationale)}"</div>
      <div class="rowref">ledger row #${c.seq} · ${esc((c.row_hash || "").slice(0, 12))}…</div></div>`;
  }
  if (p.most_recent) {
    const m = p.most_recent;
    html += `<div>most recent: <b style="color:${m.decision === "approve" ? "var(--green)" : "var(--danger)"}">${esc(m.decision)}</b> by ${esc(m.actor)}
      <div class="quote">"${esc(m.rationale)}"</div><div class="rowref">row #${m.seq} · ${esc((m.row_hash || "").slice(0, 12))}…</div></div>`;
  }
  box.innerHTML = html;
}

function renderBrief(b) {
  const box = $("#brief"), src = $("#brief-src");
  if (!box) return;
  box.innerHTML = `<div class="ai-brief">${esc(b.brief || "—")}</div>` +
    `<div class="brief-note">advisory prose · every number is engine-computed · the verdict is the human's</div>`;
  if (src) {
    src.textContent = b.deterministic ? "deterministic summary" : ("AI · " + (b.provider || "llm"));
    src.className = "hint" + (b.deterministic ? "" : " ai-on");
  }
}

// ---- HAZARD X-RAY: cross-MR collisions + review debt (the reframe lead) ----
// The demo scenario: three open MRs on the real self-index. MR-204 refactors the blast
// engine; MR-207 changes the impact API that CALLS it (a different file -> NO Git text
// conflict); MR-211 touches the ledger. The graph reveals the entanglement Git cannot.
const DEMO_MRS = [
  { id: "MR-204 · speed up the blast engine", symbols: ["compute_blast_radius"] },
  { id: "MR-207 · tune the impact API", symbols: ["impact"] },
  { id: "MR-211 · ledger append fix", symbols: ["append"] },
];

async function loadHazards() {
  // collisions: live backend computes from the scenario; static deploy serves the baked one
  let col = null;
  if (!STATIC_MODE) {
    try {
      const r = await fetch("/api/collisions", {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ mrs: DEMO_MRS }),
      });
      if (r.ok) col = await r.json();
    } catch (e) { /* fall through to static */ }
  }
  if (!col) { try { await ensureStatic(); col = STATIC.collisions; } catch (e) {} }
  if (col && col.collisions) renderCollision(col);
  try { renderGraphAudit(await api("/api/graph-audit")); } catch (e) {}
}

const KIND_LABEL = {
  same_change: "both change the same symbol",
  change_in_blast: "one changes a symbol the other depends on",
  blast_overlap: "their blast radii overlap",
};

function renderCollision(col) {
  const box = $("#collision");
  if (!box) return;
  const mrs = col.per_mr || [];
  const order = col.merge_order || [];
  const cyc = col.uncoordinable_cycle || [];
  // the MRs in play
  let html = `<div class="hz-mrs">` + mrs.map((m) =>
    `<div class="hz-mr"><span class="hz-mrid">${esc(m.id)}</span>` +
    `<span class="hz-mrmeta">changes ${esc((m.changes || []).join(", ") || "—")} · blast ${m.blast_size}</span></div>`
  ).join("") + `</div>`;
  // the collisions
  if (!col.collisions.length) {
    html += `<div class="hz-ok">No blast-radius collisions — these MRs are independent.</div>`;
  } else {
    html += col.collisions.map((c) => {
      const noConflict = c.kind === "change_in_blast" || c.kind === "same_change";
      const shared = (c.shared || []).slice(0, 5).join(", ");
      return `<div class="hz-collide sev-${c.kind}" role="alert">` +
        `<div class="hz-cl-top"><b>${esc(c.mr_a.split("·")[0].trim())}</b> ✕ <b>${esc(c.mr_b.split("·")[0].trim())}</b>` +
        `<span class="hz-kind">${esc(KIND_LABEL[c.kind] || c.kind)}</span></div>` +
        `<div class="hz-cl-shared">shares <code>${esc(shared)}</code></div>` +
        (noConflict ? `<div class="hz-noconflict">⚠ Git sees NO conflict (different files) — this is invisible to a normal review</div>` : "") +
        `</div>`;
    }).join("");
  }
  // safe merge order / cycle
  if (cyc.length) {
    html += `<div class="hz-order bad">cannot be safely ordered — ${cyc.length} MRs form a dependency cycle; coordinate them</div>`;
  } else if (order.length) {
    html += `<div class="hz-order">safe merge order: ` +
      order.map((o) => `<span class="hz-ord">${esc(o.split("·")[0].trim())}</span>`).join(' <span class="hz-arrow">→</span> ') + `</div>`;
  }
  html += `<div class="hz-foot">${esc(col.verdict || "")}</div>`;
  box.innerHTML = html;
}

function renderGraphAudit(ga) {
  const box = $("#graph-audit");
  if (!box) return;
  const items = (ga.items || []).slice(0, 7);
  let html = `<div class="hz-debt-list">` + items.map((r) =>
    `<div class="hz-debt-row ${r.untested ? "untested" : ""}">` +
    `<span class="hz-d-name" title="${esc(r.file || "")}">${esc(r.name)}</span>` +
    `<span class="hz-d-blast tabnum">${r.blast}</span>` +
    `<span class="hz-d-tag">${r.untested ? "no direct test" : r.test_callers + " test caller(s)"}</span></div>`
  ).join("") + `</div>`;
  html += `<div class="hz-foot">${esc(ga.verdict || "")}</div>`;
  box.innerHTML = html;
}

// ---- AI assistant (bounded tool-using agent) ----
// Live backend runs a fresh agent loop (POST); the static deploy serves the baked
// plan (and a REAL recorded run for headline symbols). The agent PROPOSES; the
// deterministic gate DECIDES — so this never touches the trust path.
async function callAssistant(symbol, question) {
  if (!STATIC_MODE) {
    try {
      const r = await fetch("/api/assistant", {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ symbol, question: question || undefined }),
      });
      if (r.ok) return await r.json();
      throw new Error("assistant " + r.status);
    } catch (e) {
      try { await ensureStatic(); STATIC_MODE = true; } catch (e2) { throw e; }
    }
  }
  await ensureStatic();
  const rec = (STATIC.assistant || {})[symbol];
  return rec || { answer: "No assistant data for this symbol in the static bundle.", steps: [], deterministic: true, provider: null };
}

// a compact one-line summary of an engine tool result for the trace
function toolResultSummary(tool, r) {
  if (!r || r.error) return r && r.error ? esc(r.error) : "—";
  if (tool === "blast_radius") return `${esc(r.tier)} · ${esc(r.action)} · ${r.total_affected} affected (${r.direct_callers} direct) · ${r.required_approvers} approver(s)`;
  if (tool === "precedent") return `${r.approved} approved / ${r.rejected} rejected` + (r.has_identical_contradiction ? ` · identical-signature rejection by ${esc(r.contradiction_actor)}` : "");
  if (tool === "propose_reviewers") return (r.prior_approvers && r.prior_approvers.length ? `prior: ${esc(r.prior_approvers.join(", "))}` : "no prior approvers") + (r.required_owner ? ` · owner ${esc(r.required_owner)}` : "");
  return esc(JSON.stringify(r).slice(0, 80));
}

function renderAssistant(res) {
  const box = $("#assistant"), src = $("#assistant-src");
  if (!box) return;
  const steps = res.steps || [];
  let trace = "";
  if (steps.length) {
    trace = `<div class="agent-trace" aria-label="agent tool trace">` +
      steps.map((s, i) =>
        `<div class="agent-step"><span class="as-n">${i + 1}</span>` +
        `<code class="as-tool">${esc(s.tool)}(${esc((s.args && s.args.symbol) || "")})</code>` +
        `<span class="as-res">${toolResultSummary(s.tool, s.result)}</span></div>`
      ).join("") + `</div>`;
  }
  box.innerHTML = trace +
    `<div class="agent-answer">${esc(res.answer || "—")}</div>` +
    `<div class="brief-note">${steps.length ? steps.length + " engine tool call(s) · " : ""}the agent proposes; the deterministic gate decides</div>`;
  if (src) {
    const real = res.deterministic === false;
    src.textContent = real ? ("agent · " + (res.provider || "llm")) : "agent · deterministic plan";
    src.className = "agentic-badge" + (real ? " ai-on" : "");
  }
}

async function refreshLedger() {
  const a = await api("/api/audit");
  // names for blast columns are ids; show count
  const v = a.verify;
  const vd = $("#chain-verdict");
  // honest badge. The public static bundle uses a PUBLISHED sample HMAC key, so its
  // chain is reproducible by anyone and is NOT tamper-evident — never show green
  // "CHAIN VERIFIED" there. Only the live backend (secret per-machine key) does.
  const isStatic = STATIC_MODE || !!STATIC;
  if (!v.ok) {
    vd.textContent = "BROKEN AT ROW " + v.broken_index; vd.className = "verdict bad";
  } else if (isStatic) {
    vd.textContent = "SAMPLE · PUBLIC KEY"; vd.className = "verdict warn";
    vd.title = "public demo only: the sample HMAC key is published in source, so this chain is reproducible by anyone — illustrative, not tamper-evident. The local app keys the chain with a secret per-machine key.";
  } else {
    vd.textContent = "CHAIN VERIFIED"; vd.className = "verdict ok";
  }
  const tb = $("#lrows");
  tb.innerHTML = a.rows.map((r) => `<tr class="${(!v.ok && r.seq >= v.broken_index) ? "broken" : ""}">
    <td class="tabnum">${r.seq}</td><td class="ch tabnum">${esc((r.ts || "").replace("T", " ").replace("Z", ""))}</td>
    <td>${esc(r.change_id)}</td><td class="tabnum">${(r.blast_radius_set || []).length}</td>
    <td>${esc(r.actor)}</td><td class="dec ${r.decision === "approve" ? "approve" : "reject"}">${r.decision === "approve" ? "✓" : "✕"} ${esc(r.decision)}</td>
    <td class="hash tabnum">${esc((r.prev_hash || "").slice(0, 8))}… → ${esc((r.row_hash || "").slice(0, 8))}…</td></tr>`).join("");
  // re-sync the chain chip in topbar
  try { paintStatus(await api("/api/status")); } catch (e) {}
}

function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }

function wire() {
  $("#search").addEventListener("input", (e) => {
    const q = e.target.value.toLowerCase();
    renderDefList(STATE.defs.filter((n) => n.toLowerCase().includes(q)));
  });
  // arrow-key navigation across the symbol listbox (WCAG keyboard support)
  $("#deflist").addEventListener("keydown", (e) => {
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
    e.preventDefault();
    const items = [...document.querySelectorAll("#deflist li")];
    if (!items.length) return;
    let idx = items.indexOf(document.activeElement);
    if (idx < 0) idx = items.findIndex((li) => li.classList.contains("sel"));
    const next = Math.max(0, Math.min(items.length - 1, idx + (e.key === "ArrowDown" ? 1 : -1)));
    items[next].focus(); select(items[next].dataset.name);
  });
  $("#approve").onclick = () => decide("approve");
  $("#reject").onclick = () => decide("reject");
  $("#verify").onclick = refreshLedger;
  $("#tamper").onclick = tamperDemo;
  const ex = $("#export-att"); if (ex) ex.onclick = exportAttestation;
  const ov = $("#override"); if (ov) ov.onchange = applyGatePolicy;
  const ag = $("#assistant-go"), aq = $("#assistant-q");
  if (ag && aq) {
    const ask = () => {
      if (!STATE.selected) return;
      const q = aq.value.trim();
      const box = $("#assistant");
      if (box) box.innerHTML = `<div class="muted">the agent is working on your question…</div>`;
      callAssistant(STATE.selected, q).then((r) => { if (STATE.selected) renderAssistant(r); }).catch(() => {});
    };
    ag.onclick = ask;
    aq.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); ask(); } });
  }
  // premium keyboard layer: "/" focuses symbol search, Escape clears it
  document.addEventListener("keydown", (e) => {
    const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName);
    if (e.key === "/" && !typing) { e.preventDefault(); $("#search").focus(); }
    else if (e.key === "Escape" && document.activeElement === $("#search")) { $("#search").value = ""; renderDefList(STATE.defs); }
  });
}

async function decide(decision) {
  const reviewer = $("#reviewer").value.trim() || "anon";
  const reason = $("#reason").value.trim();
  const err = $("#reason-err");
  if (!reason) {
    $("#reason").focus(); $("#reason").style.outline = "2px solid var(--danger)";
    $("#reason").setAttribute("aria-invalid", "true");
    if (err) err.textContent = "A reason is required before recording a decision.";
    return;
  }
  $("#reason").style.outline = ""; $("#reason").removeAttribute("aria-invalid");
  if (err) err.textContent = "";
  const authorKind = ($("#authorkind") && $("#authorkind").value) || "human";
  const override = !!($("#override") && $("#override").checked);
  const pol = STATE.impact && STATE.impact.policy;
  if (!STATIC_MODE) {
    try {
      const r = await fetch("/api/approve", {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ name: STATE.selected, decision, reviewer, rationale: reason, author_kind: authorKind, override,
          change_id: STATE.changeId, change_author: (($("#changeauthor") && $("#changeauthor").value.trim()) || undefined) }),
      });
      if (r.ok) {
        const body = await r.json().catch(() => ({}));
        $("#reason").value = "";
        const st = $("#gate-status");
        if (st && body.quorum) { st.textContent = "recorded · " + body.quorum.status + " (" + body.quorum.confirmed + "/" + body.quorum.required + " approvers)"; st.style.color = "var(--text-mid)"; }
        await refreshLedger(); await select(STATE.selected); return;
      }
      const b = await r.json().catch(() => ({}));
      const det = (b && b.detail) || {};
      if (r.status === 403) {                       // scope / unregistered agent / self-approval
        const code = (det.error || "BLOCKED").replace(/_/g, " ");
        const why = det.violations ? det.violations.join("; ") : (det.hint || "");
        if (err) err.textContent = code + (why ? ": " + why : "");
        return;
      }
      if (r.status === 409) {                       // policy BLOCK, no override
        if (err) err.textContent = "GOVERNANCE BLOCK: " + ((det.reasons || ["blocked by policy"]).join("; ")) + " — tick override to record an accountable override.";
        if ($("#override-row")) $("#override-row").style.display = "block";
        return;
      }
      throw new Error("approve " + r.status);
    } catch (e) {
      await ensureStatic(); STATIC_MODE = true; // fall through to client-side sample append
    }
  }
  // static mode: enforce BLOCK in-browser too (the demo must not let you click past a BLOCK)
  if (decision === "approve" && pol && pol.action === "BLOCK" && !override) {
    if (err) err.textContent = "Policy action is BLOCK — approval is not permitted without an override.";
    return;
  }
  // Public sample (no backend): append in-browser so the gate stays interactive.
  // Persisted, server-verified writes happen in the live local app (shown in the video).
  const imp = STATIC.impact[STATE.selected] || {};
  STATIC.audit.rows.push({
    seq: STATIC.audit.rows.length, actor: reviewer, change_id: "KS-" + STATE.selected,
    target_symbols: [STATE.selected], decision, rationale: reason,
    signature: imp.signature || "", ts: "sample", row_hash: "(in-browser sample)",
  });
  $("#reason").value = "";
  await refreshLedger(); await select(STATE.selected);
  const note = $("#sample-note");
  if (note) { note.textContent = "recorded in this browser only — the live local app persists to the hash-chained ledger"; note.style.opacity = "1"; }
}

// in-memory tamper demo: re-render the ledger as if a row were edited, flip the badge red.
// This does NOT write to disk; it visualizes what verify() detects. (The real test in
// tests/test_engine.py proves disk-level tamper detection.)
async function tamperDemo() {
  const a = await api("/api/audit");
  if (!a.rows.length) return;
  const idx = Math.max(0, a.rows.length - 1 - Math.floor(a.rows.length / 2));
  const vd = $("#chain-verdict");
  vd.textContent = "BROKEN AT ROW " + idx + " (simulated)";
  vd.className = "verdict bad";
  document.querySelectorAll("#lrows tr").forEach((tr) => {
    const seq = Number(tr.children[0].textContent);
    if (seq >= idx) tr.classList.add("broken");
  });
  $("#chain-chip").innerHTML = `<span class="dot r"></span>chain <b>broken@${idx} (sim)</b>`;
  $("#chain-chip").className = "chip bad";
  setTimeout(refreshLedger, 2600); // self-heal: re-read real (untampered) chain
}

boot();
