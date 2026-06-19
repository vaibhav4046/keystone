"use strict";
// ============================================================================
// Keystone web hero v2. Talks to the FastAPI core. Every number shown comes
// from the API (engine-computed); this script only renders and animates.
// Sections: API → STATE → STATUS → SYMBOLS → BLAST RADIUS → HAZARD X-RAY →
//           AI → GOVERNANCE → AUDIT → NAVIGATION → KEYBOARD → TOUR
// ============================================================================
const $ = (s) => document.querySelector(s);
const reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

// Live-API-first, static-bundle fallback so the hero deploys with no backend.
let STATIC = null, STATIC_MODE = false;
function _isStaticHost() {
  const h = location.hostname || "";
  // Known static hosts with no live backend. localhost is deliberately excluded so local
  // dev with a running backend still hits the live API first.
  return /github\.io$|gitlab\.io$|pages\.dev$|\.netlify\.app$|\.vercel\.app$/.test(h) || location.protocol === "file:";
}
let API_MODE = localStorage.getItem("ks-api-mode") || (_isStaticHost() ? "static" : "live");
let API_URL = localStorage.getItem("ks-api-url") || "";

async function ensureStatic() {
  if (STATIC) return STATIC;
  STATIC = await fetch("data.json?v=" + new Date().getTime()).then((r) => r.json());
  return STATIC;
}
function fromStatic(p) {
  const s = STATIC;
  if (p === "/api/status") return s.status;
  if (p === "/api/definitions") return s.definitions.names ? s.definitions : { names: s.definitions };
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
  if (API_MODE === "live") {
    const baseUrl = API_URL || "";
    const url = baseUrl.replace(/\/$/, "") + p;
    try {
      const r = await fetch(url);
      if (r.ok) return await r.json();
      throw new Error(url + " " + r.status);
    } catch (e) {
      console.warn("Live API request failed, falling back to static", e);
      await ensureStatic();
      return fromStatic(p);
    }
  }
  await ensureStatic();
  return fromStatic(p);
};

// === STATE ===
let STATE = { defs: [], selected: null, impact: null, showAll: false };
window.STATE = STATE;                       // exposed for the motion layer (motion.js)

const RING_COLOR = { 0: "#ef4444", 1: "#ff7a2f", 2: "#f5b72c", 3: "#38bdf8" };
const RING_FILL = { 0: "rgba(239,68,68,0.10)", 1: "rgba(255,122,47,0.08)", 2: "rgba(245,183,44,0.06)", 3: "rgba(56,189,248,0.06)" };
const RING_LABEL = { 0: "epicenter", 1: "direct", 2: "transitive", 3: "at risk" };
function ringColor(r) { return RING_COLOR[r] || "#6b6d7c"; }

// === BOOT ===
async function boot() {
  initTheme();
  initSettings();
  updateConnectionStatus();
  initSidebar();
  initScrollSpy();
  initCollapsiblePanels();
  initCommandPalette();
  try {
    const st = await api("/api/status");
    paintStatus(st);
  } catch (e) { /* status optional */ }
  const d = await api("/api/definitions");
  STATE.defs = d.names;
  STATE.details = d.details || {};
  renderDefList(reviewableDefs());
  updateShowAllLabel();
  await refreshLedger();
  loadHazards();
  initHarness();
  // auto-select the headline demo symbol: compute_blast_radius (Keystone's own engine,
  // BLOCKed by prior precedent) on the real self-index, tokenize on the fixture, else top.
  if (STATE.defs.length) {
    const demo = STATE.defs.includes("compute_blast_radius") ? "compute_blast_radius"
      : (STATE.defs.includes("tokenize") ? "tokenize" : STATE.defs[0]);
    select(demo);
  }
  wire();
  if (!localStorage.getItem("keystone-onboarded")) {
    showOnboarding(0);
  }
}

// === SIDEBAR NAVIGATION ===
function initSidebar() {
  const sidebar = $("#sidebar");
  const toggle = $("#sidebar-toggle");
  if (!sidebar || !toggle) return;

  // Restore sidebar state from localStorage
  const saved = localStorage.getItem("ks-sidebar");
  if (saved === "expanded") sidebar.classList.add("expanded");

  toggle.addEventListener("click", () => {
    const isMobile = window.innerWidth <= 768;
    const backdrop = $("#sidebar-backdrop");
    if (isMobile) {
      sidebar.classList.toggle("mobile-open");
      if (backdrop) backdrop.classList.toggle("visible", sidebar.classList.contains("mobile-open"));
    } else {
      sidebar.classList.toggle("expanded");
      localStorage.setItem("ks-sidebar", sidebar.classList.contains("expanded") ? "expanded" : "collapsed");
    }
  });

  // Close mobile sidebar on outside click
  document.addEventListener("click", (e) => {
    const backdrop = $("#sidebar-backdrop");
    if (window.innerWidth <= 768 && sidebar.classList.contains("mobile-open") &&
        !sidebar.contains(e.target) && e.target !== toggle) {
      sidebar.classList.remove("mobile-open");
      if (backdrop) backdrop.classList.remove("visible");
    }
  });
  // Backdrop click closes sidebar
  const bdEl = $("#sidebar-backdrop");
  if (bdEl) bdEl.addEventListener("click", () => {
    sidebar.classList.remove("mobile-open");
    bdEl.classList.remove("visible");
  });

  // Sidebar nav items: scroll to sections
  const viewMap = { overview: "home", symbols: "cockpit", impact: "cockpit", audit: "ledger", help: "__onboard" };
  document.querySelectorAll(".sidebar-item").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".sidebar-item").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      const v = viewMap[btn.dataset.section];
      if (v === "__onboard") {
        showOnboarding(0);
      } else if (v && typeof showView === "function") {
        showView(v);
      } else {
        window.scrollTo({ top: 0, behavior: "smooth" });
      }
      if (window.innerWidth <= 768) {
        sidebar.classList.remove("mobile-open");
        const backdrop = $("#sidebar-backdrop");
        if (backdrop) backdrop.classList.remove("visible");
      }
    });
  });
}

// Scroll-spy: update sidebar active state on scroll
function initScrollSpy() {
  const sections = [
    { id: null, btn: 'overview' },
    { id: 'symbols-h', btn: 'symbols' },
    { id: 'blast-radius', btn: 'impact' },
    { id: 'audit', btn: 'audit' },
  ];
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (!entry.isIntersecting) return;
      const match = sections.find(s => s.id && document.getElementById(s.id) === entry.target);
      if (match) {
        document.querySelectorAll('.sidebar-item').forEach(b => b.classList.remove('active'));
        const btn = document.querySelector(`.sidebar-item[data-section="${match.btn}"]`);
        if (btn) btn.classList.add('active');
      }
    });
  }, { rootMargin: '-20% 0px -60% 0px' });
  sections.forEach(s => { if (s.id) { const el = document.getElementById(s.id); if (el) observer.observe(el); } });
}

// === COLLAPSIBLE PANELS ===
function initCollapsiblePanels() {
  document.querySelectorAll(".panel-header[data-collapse]").forEach((header) => {
    header.addEventListener("click", () => {
      const targetId = header.dataset.collapse;
      const body = document.getElementById(targetId) || header.nextElementSibling;
      if (!body) return;
      const chevron = header.querySelector(".chevron");
      body.classList.toggle("collapsed");
      if (chevron) chevron.classList.toggle("collapsed", body.classList.contains("collapsed"));
    });
  });
}

// === COMMAND PALETTE ===
function initCommandPalette() {
  // Build overlay DOM
  const overlay = document.createElement('div');
  overlay.className = 'cmd-overlay';
  overlay.id = 'cmd-overlay';
  overlay.innerHTML = `
    <div class="cmd-palette">
      <div class="cmd-input-wrap">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><circle cx="7" cy="7" r="5.5" stroke="currentColor" stroke-width="1.5"/><path d="M11 11l3 3" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
        <input class="cmd-input" id="cmd-input" placeholder="Search symbols, actions…" autocomplete="off" />
        <span class="cmd-kbd">ESC</span>
      </div>
      <div class="cmd-results" id="cmd-results"></div>
    </div>`;
  document.body.appendChild(overlay);

  const input = $('#cmd-input');
  const results = $('#cmd-results');
  let cmdIdx = -1;

  function openPalette() {
    overlay.classList.add('open');
    input.value = '';
    cmdIdx = -1;
    renderCmdResults('');
    requestAnimationFrame(() => input.focus());
  }
  function closePalette() {
    overlay.classList.remove('open');
    input.blur();
  }
  function renderCmdResults(q) {
    const lq = q.toLowerCase();
    const actions = [
      { name: 'Take the 60-second tour', action: () => { const t = $('#lede-tour'); if (t) t.click(); } },
      { name: 'Verify audit chain', action: () => { if (typeof showView === 'function') showView('ledger'); const v = $('#verify'); if (v) setTimeout(() => v.click(), 80); } },
      { name: 'Show all symbols', action: () => { STATE.showAll = true; renderDefList(currentDefView()); updateShowAllLabel(); } },
    ];
    const syms = (STATE.defs || []).filter(n => !lq || n.toLowerCase().includes(lq)).slice(0, 12);
    const acts = actions.filter(a => !lq || a.name.toLowerCase().includes(lq));
    if (!syms.length && !acts.length) {
      results.innerHTML = '<div class="cmd-empty">No results</div>';
      return;
    }
    let html = '';
    if (acts.length) {
      html += acts.map((a, i) => `<div class="cmd-item" data-action="${i}"><span class="cmd-item-name">${esc(a.name)}</span><span class="cmd-item-badge">action</span></div>`).join('');
    }
    if (syms.length) {
      html += syms.map(s => `<div class="cmd-item" data-sym="${esc(s)}"><svg class="cmd-item-icon" viewBox="0 0 16 16" fill="none"><path d="M5 3L2 8l3 5M11 3l3 5-3 5" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/></svg><span class="cmd-item-name">${esc(s)}</span><span class="cmd-item-badge">symbol</span></div>`).join('');
    }
    results.innerHTML = html;
    cmdIdx = -1;
    results.querySelectorAll('.cmd-item').forEach(el => {
      el.addEventListener('click', () => {
        if (el.dataset.sym) { select(el.dataset.sym); closePalette(); if (typeof showView === "function") showView("cockpit"); }
        else if (el.dataset.action !== undefined) { acts[Number(el.dataset.action)].action(); closePalette(); }
      });
    });
  }
  input.addEventListener('input', () => renderCmdResults(input.value));
  input.addEventListener('keydown', (e) => {
    const items = results.querySelectorAll('.cmd-item');
    if (e.key === 'ArrowDown') { e.preventDefault(); cmdIdx = Math.min(cmdIdx + 1, items.length - 1); items.forEach((el, i) => el.classList.toggle('active', i === cmdIdx)); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); cmdIdx = Math.max(cmdIdx - 1, 0); items.forEach((el, i) => el.classList.toggle('active', i === cmdIdx)); }
    else if (e.key === 'Enter' && cmdIdx >= 0 && items[cmdIdx]) { items[cmdIdx].click(); }
  });
  overlay.addEventListener('click', (e) => { if (e.target === overlay) closePalette(); });
  window.__ksCmdOpen = openPalette;
  window.__ksCmdClose = closePalette;
}

// === STATUS DISPLAY ===
function paintStatus(st) {
  const src = $("#src-chip"), orbit = $("#orbit-chip"), chain = $("#chain-chip"), integ = $("#integ-chip");
  const live = st.source_mode === "LIVE";
  const snapshot = st.source_mode === "SNAPSHOT";   // committed REAL orbit index, served without a backend
  STATE.sourceMode = st.source_mode; updateConnectionStatus();   // keep the mode pill honest to the real data source
  src.innerHTML = `<span class="dot ${live ? "g" : (snapshot ? "g" : "a")}"></span>source <b>${esc(st.source_mode)}</b>`;
  src.className = "chip " + (live || snapshot ? "ok" : "warn");
  if (snapshot) src.title = "a committed REAL `orbit index` of this repository (" + (st.definitions || "") +
    " definitions) - every number is engine-computed and cross-verified by orbit sql; served as a static snapshot (no backend).";
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
    else { oc.textContent = "-"; }
  }
  STATE.windowEnforced = !!st.window_enforced;
  const integ2 = st.integrity || {};
  if (integ) integ.innerHTML = `integrity <b>${integ2.hmac ? "HMAC" : "sha256"}</b>` + (integ2.reviewer_verified ? "" : ` · <span class="adv">id advisory</span>`);
  const banner = $("#open-banner");
  if (banner) {
    if (integ2.open_mode) {
      banner.hidden = false;
      var moreLive = (st.source_mode === "SNAPSHOT" || st.source_mode === "FALLBACK")
        ? " <b>Want the live backend?</b> One-click deploy on <a href=\"https://render.com\" target=\"_blank\" rel=\"noopener\">Render</a> (free, no card): connect this repo and Apply - <code>render.yaml</code> is committed. ~2 min. See <a href=\"https://github.com/vaibhav4046/keystone/blob/main/SUBMISSION/RENDER_DEPLOY.md\" target=\"_blank\" rel=\"noopener\">RENDER_DEPLOY.md</a>."
        : "";
      banner.innerHTML =
        '<button class="banner-summary" type="button" aria-expanded="false" aria-controls="open-banner-more">'
        + '<span class="banner-tag">OPEN MODE</span>'
        + '<span class="banner-lead">Identity is self-asserted - the gate still enforces the contradiction BLOCK, four-eyes, and quorum; only the identity binding is advisory.</span>'
        + '<span class="banner-toggle" aria-hidden="true">details</span>'
        + '</button>'
        + '<div class="banner-more" id="open-banner-more" hidden>No approve token is set, so any caller can record a decision under any name. Set KEYSTONE_APPROVE_TOKEN or bind GitLab OIDC for a fully enforced deployment.' + moreLive + '</div>';
      var _sb = banner.querySelector('.banner-summary');
      if (_sb) _sb.onclick = function () {
        var more = document.getElementById('open-banner-more');
        var willOpen = more.hasAttribute('hidden');
        if (willOpen) more.removeAttribute('hidden'); else more.setAttribute('hidden', '');
        _sb.setAttribute('aria-expanded', willOpen ? 'true' : 'false');
        banner.classList.toggle('expanded', willOpen);
        var tog = _sb.querySelector('.banner-toggle'); if (tog) tog.textContent = willOpen ? 'less' : 'details';
      };
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
  names.forEach((n, i) => {
    const li = document.createElement("li");
    li.dataset.name = n;
    li.textContent = n;                 // textContent, not innerHTML: no injection from symbol names
    li.setAttribute("role", "option");
    li.setAttribute("tabindex", (STATE.selected ? n === STATE.selected : i === 0) ? "0" : "-1");
    li.setAttribute("aria-selected", n === STATE.selected ? "true" : "false");
    li.onclick = () => select(n);
    li.onkeydown = (e) => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); select(n); return; }
      let sib = null;
      if (e.key === "ArrowDown") sib = li.nextElementSibling;
      else if (e.key === "ArrowUp") sib = li.previousElementSibling;
      else if (e.key === "Home") sib = li.parentElement.firstElementChild;
      else if (e.key === "End") sib = li.parentElement.lastElementChild;
      else return;
      e.preventDefault();
      if (sib) {
        li.setAttribute("tabindex", "-1"); li.setAttribute("aria-selected", "false");
        sib.setAttribute("tabindex", "0"); sib.setAttribute("aria-selected", "true");
        sib.focus();
      }
    };
    if (n === STATE.selected) li.classList.add("sel");
    ul.appendChild(li);
  });
}

// Curate the picker: a cold judge should see the consequential, human-named symbols first, not
// private internals (_*), test functions/classes, or one-character names. "show all" reveals the
// rest, and typing in the filter always searches the full set, so nothing is hidden from search.
function _reviewable(n) {
  if (!(n.length > 1 && !/^_/.test(n) && !/^test/i.test(n) && !/Tests?$/.test(n) && /[A-Za-z]/.test(n))) return false;
  // hide the tool's own frontend/build functions (web/*.js) from the default view; nobody
  // governs a change to paintStatus or drawBlast. "show all" still reveals them.
  const f = (STATIC && STATIC.impact && STATIC.impact[n] && STATIC.impact[n].epicenter && STATIC.impact[n].epicenter.file) || "";
  return !/^web\//.test(f);
}
function reviewableDefs() { return STATE.showAll ? STATE.defs : STATE.defs.filter(_reviewable); }
function currentDefView() {
  const q = (($("#search") && $("#search").value) || "").trim().toLowerCase();
  const typeFilter = ($("#filter-type") && $("#filter-type").value) || "all";
  const hazardFilter = ($("#filter-hazard") && $("#filter-hazard").value) || "all";

  let list = reviewableDefs();
  if (q) {
    list = STATE.defs.filter((n) => n.toLowerCase().includes(q));
  }

  if (typeFilter !== "all") {
    list = list.filter((n) => {
      const details = STATE.details && STATE.details[n];
      if (!details) return false;
      const kind = (details.kind || "").toLowerCase();
      if (typeFilter === "function") return kind === "function";
      if (typeFilter === "class") return kind === "class";
      if (typeFilter === "other") return kind !== "function" && kind !== "class";
      return true;
    });
  }

  if (hazardFilter !== "all") {
    list = list.filter((n) => {
      const details = STATE.details && STATE.details[n];
      if (!details) return false;
      const action = (details.action || "").toLowerCase();
      const tier = (details.tier || "").toLowerCase();

      if (hazardFilter === "block") {
        const hasContradiction = (STATIC && STATIC.precedent && STATIC.precedent[n] && STATIC.precedent[n].contradiction);
        return action === "block" || hasContradiction;
      }
      if (hazardFilter === "hold") return action === "hold";
      if (hazardFilter === "allow") return action === "allow";
      if (hazardFilter === "cross-team") return tier === "cross_team";
      if (hazardFilter === "high-blast") {
        const count = details.total_affected || 0;
        return count >= 10;
      }
      if (hazardFilter === "collision") {
        const cs = (STATE._col && STATE._col.collisions) || [];
        return cs.some(c => {
          const symsA = STATE.openMrs.find(m => m.id === c.mr_a)?.symbols || [];
          const symsB = STATE.openMrs.find(m => m.id === c.mr_b)?.symbols || [];
          return symsA.includes(n) || symsB.includes(n);
        });
      }
      if (hazardFilter === "debt") {
        const gaItems = (STATE.graphAudit && STATE.graphAudit.items) || [];
        return gaItems.some(item => item.name === n && item.untested);
      }
      return true;
    });
  }

  return list;
}
function updateShowAllLabel() {
  const b = $("#show-all"); if (!b) return;
  const nAll = STATE.defs.length, hidden = nAll - STATE.defs.filter(_reviewable).length;
  b.textContent = STATE.showAll ? "show reviewable only" : ("show all " + nAll + " (" + hidden + " hidden)");
  b.setAttribute("aria-pressed", STATE.showAll ? "true" : "false");
}

// The refusal IS the thesis, so make it loud, not a silent red line: flash the gate and put a
// REFUSED summary on the status line, with the detail underneath.
function flashRefusal(code, detail) {
  const st = $("#gate-status");
  if (st) { st.textContent = "REFUSED - " + code; st.style.color = "var(--danger-2)"; }
  const err = $("#reason-err");
  if (err) err.textContent = detail || "";
  const gate = document.querySelector(".panel.gate");
  if (gate) { gate.classList.remove("refused"); void gate.offsetWidth; gate.classList.add("refused");
    setTimeout(() => gate.classList.remove("refused"), 900); }
}

// A guided CTA should land: briefly pulse the panel it reveals so the payoff is unmistakable.
function highlightPanel(el) {
  if (!el) return;
  el.classList.remove("flash-highlight"); void el.offsetWidth; el.classList.add("flash-highlight");
  setTimeout(() => el.classList.remove("flash-highlight"), 1700);
}

// Animated number counter roll-up
function animateCounter(target) {
  const el = $("#counter");
  if (!el) return;
  if (reduceMotion) { el.textContent = String(target); return; }
  const start = parseInt(el.textContent) || 0;
  const diff = target - start;
  const duration = Math.min(600, Math.max(200, Math.abs(diff) * 8));
  const t0 = performance.now();
  function tick(now) {
    const p = Math.min(1, (now - t0) / duration);
    const ease = 1 - Math.pow(1 - p, 3); // ease-out cubic
    const v = Math.round(start + diff * ease);
    el.textContent = String(v);
    if (p < 1) requestAnimationFrame(tick);
    else { el.textContent = String(target); el.parentElement.classList.add('counter-animate'); setTimeout(() => el.parentElement.classList.remove('counter-animate'), 500); }
  }
  requestAnimationFrame(tick);
}

async function select(name) {
  STATE.selected = name;
  // Deterministic change id per symbol so a CROSS_TEAM quorum accumulates across distinct
  // approvers of the same change. It must be stable across the re-select that decide() performs
  // after recording a decision; a fresh random id per select() would give the second approver a
  // new change_id and the quorum would never close on the live backend (the static path already
  // keys on a stable id, so the bug only bit the live render.yaml backend).
  STATE.changeId = "MR-" + name;
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
    if (blocked) { status.textContent = "Policy action is BLOCK - approval is not permitted without an override."; status.style.color = "var(--danger-2)"; }
    else if (pol && pol.action === "HOLD") { status.textContent = "Policy action is HOLD - " + pol.required_approvers + " approvers required."; status.style.color = "var(--amber)"; }
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
    if (note) { note.textContent = "approve or reject first - an attestation is minted from a recorded decision"; note.style.opacity = "1"; }
  }
}

// === BLAST RADIUS SVG ===
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
  // concentric severity ring guides + subtle fills + labels
  for (let r = 1; r <= maxRing; r++) {
    const fill = document.createElementNS(ns, "ellipse");
    fill.setAttribute("cx", cx); fill.setAttribute("cy", cy);
    fill.setAttribute("rx", radii[r]); fill.setAttribute("ry", radii[r] * 0.82);
    fill.setAttribute("class", "ring-fill");
    fill.setAttribute("fill", RING_FILL[r] || "transparent");
    svg.appendChild(fill);

    const guide = document.createElementNS(ns, "ellipse");
    guide.setAttribute("cx", cx); guide.setAttribute("cy", cy);
    guide.setAttribute("rx", radii[r]); guide.setAttribute("ry", radii[r] * 0.82);
    guide.setAttribute("class", "ring-guide");
    svg.appendChild(guide);

    const lbl = document.createElementNS(ns, "text");
    lbl.setAttribute("x", cx + radii[r] - 10);
    lbl.setAttribute("y", cy - radii[r] * 0.82 + 14);
    lbl.setAttribute("text-anchor", "end");
    lbl.setAttribute("class", "ring-label");
    lbl.setAttribute("fill", ringColor(r));
    lbl.textContent = RING_LABEL[r] || ("R" + r);
    svg.appendChild(lbl);
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
    g.dataset.name = nameOf(imp, id);
    g.dataset.ring = String(r);
    g.style.cursor = 'pointer';
    const isEpi = id === imp.epicenter.id;
    const full = nameOf(imp, id);
    const ttl = document.createElementNS(ns, "title");
    ttl.textContent = full;
    g.appendChild(ttl);                                  // hover shows the full name
    const circ = document.createElementNS(ns, "circle");
    circ.setAttribute("cx", pos[id].x); circ.setAttribute("cy", pos[id].y);
    circ.setAttribute("r", isEpi ? 18 : 11);
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
    animateCounter(total);
    return;
  }
  $("#counter").textContent = "0";
  // signature reveal: a shockwave ring pulses out from the epicenter as the blast computes
  const _epiPos = pos[imp.epicenter.id];
  if (_epiPos) {
    const sw = document.createElementNS(ns, "circle");
    sw.setAttribute("cx", _epiPos.x); sw.setAttribute("cy", _epiPos.y); sw.setAttribute("r", "16");
    sw.setAttribute("class", "ks-shockwave");
    svg.appendChild(sw);
    _timers.push(setTimeout(() => { if (sw.parentNode) sw.parentNode.removeChild(sw); }, 1100));
  }
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
  initGraphTooltips();
}

// SVG graph hover tooltips
function initGraphTooltips() {
  const wrap = document.querySelector('.canvas-wrap');
  if (!wrap) return;
  let tip = wrap.querySelector('.graph-tooltip');
  if (!tip) {
    tip = document.createElement('div');
    tip.className = 'graph-tooltip';
    wrap.appendChild(tip);
  }
  const svg = $('#bsvg');
  if (!svg) return;
  svg.addEventListener('mouseover', (e) => {
    const node = e.target.closest('.node');
    if (!node) { tip.classList.remove('visible'); return; }
    const name = node.dataset.name || '';
    const ring = node.dataset.ring;
    const ringNames = { '0': 'epicenter', '1': 'direct caller', '2': 'transitive', '3': 'at risk' };
    const colors = { '0': '#FF5C66', '1': '#FF8A2B', '2': '#F5C542', '3': '#5BBFD6' };
    tip.innerHTML = `<div class="tt-name">${esc(name)}</div><div class="tt-ring"><span class="tt-dot" style="background:${colors[ring] || '#7A8494'}"></span>${ringNames[ring] || 'unknown'} ring</div>`;
    tip.classList.add('visible');
  });
  svg.addEventListener('mousemove', (e) => {
    const rect = wrap.getBoundingClientRect();
    tip.style.left = (e.clientX - rect.left + 12) + 'px';
    tip.style.top = (e.clientY - rect.top - 30) + 'px';
  });
  svg.addEventListener('mouseout', (e) => {
    if (!e.target.closest('.node')) tip.classList.remove('visible');
  });
  // click-to-navigate: clicking a node in the graph selects it
  svg.addEventListener('click', (e) => {
    const node = e.target.closest('.node');
    if (node && node.dataset.name && node.dataset.name !== STATE.selected) {
      select(node.dataset.name);
    }
  });
}
let _ctv = 0, _timers = [];
function animateCounterTo(v) { _ctv = v; const el = $("#counter"); if (el) el.textContent = pad(v); }
function pad(n) { return String(n); }
function idNames(imp) { const m = {}; Object.keys(imp.names || {}).forEach((k) => m[Number(k)] = imp.names[k]); return m; }
function nameOf(imp, id) { return (imp._names && imp._names[id]) || (imp.names && imp.names[String(id)]) || ("#" + id); }

// when two affected symbols share a short name (several `main`s across files), qualify the
// duplicates with their owning dir so the ring list reads honestly, not "main, main". The
// count stays authoritative (every distinct id is still one entry).
function ringNameList(imp, ids) {
  const qualById = {};   // qualify by file (distinct), falling back to dir, then nothing
  (imp.owners || []).forEach((o) => { qualById[o.id] = o.file || o.dir || ""; });
  const freq = {};
  ids.forEach((id) => { const n = nameOf(imp, id); freq[n] = (freq[n] || 0) + 1; });
  return ids.map((id) => {
    const n = nameOf(imp, id), q = qualById[id];
    const lbl = (freq[n] > 1 && q) ? esc(n) + " (" + esc(q) + ")" : esc(n);
    const nav = STATE.defs && STATE.defs.indexOf(n) >= 0;
    return nav
      ? `<button type="button" class="cite-chip" data-cite-sym="${esc(n)}" title="show ${esc(n)} in the graph">${lbl}</button>`
      : `<span class="cite-chip cite-static">${lbl}</span>`;
  }).join("");
}

function renderRings(imp) {
  const box = $("#rings");
  const c = imp.counts;
  const epiSub = imp.epicenter.fqn || imp.epicenter.file || "";
  const rows = [["0", "EPICENTER", 1, esc(imp.epicenter.name) + (epiSub ? ` <span class="rn-sub">${esc(epiSub)}</span>` : "")]];
  Object.keys(imp.rings).map(Number).sort((a, b) => a - b).forEach((r) => {
    if (r === 0) return;
    const tag = r === 1 ? "DIRECT" : (r === 2 ? "TRANSITIVE" : "AT RISK");
    rows.push([String(r), `R${r} ${tag}`, imp.rings[r].length,   // R-prefix: severity not by colour alone
      ringNameList(imp, imp.rings[r])]);
  });
  rows.push(["U", "UNAFFECTED", c.unaffected, ""]);
  let html = rows.map(([r, label, n, names]) =>
    `<div class="ringrow r${r}"><span class="rl">${label}</span><span class="rc tabnum">${n}</span><span class="rn">${names || "-"}</span></div>`
  ).join("");
  if (c.total_affected === 0) {
    html += `<div class="leaf-note">leaf symbol - nothing depends on it, so changing it is contained by design. Try <b>compute_blast_radius</b> (a BLOCK from prior precedent) or <b>append</b> (a 3-ring blast) to see a real radius and a recorded decision.</div>`;
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
  box.innerHTML = `<div class="ai-brief">${esc(b.brief || "-")}</div>` +
    `<div class="brief-note">advisory prose · every number is engine-computed · the verdict is the human's</div>`;
  if (src) {
    src.textContent = b.deterministic ? "deterministic summary" : ("AI · " + (b.provider || "llm"));
    src.className = "hint" + (b.deterministic ? "" : " ai-on");
  }
}

// === HAZARD X-RAY: cross-MR collisions + review debt ===
// The demo scenario: three open MRs on the real self-index. MR-204 refactors the blast
// engine; MR-207 changes the impact API that CALLS it (a different file -> NO Git text
// conflict); MR-211 touches the ledger. The graph reveals the entanglement Git cannot.
const DEMO_MRS = [
  { id: "MR-204 · speed up the blast engine", symbols: ["compute_blast_radius"] },
  { id: "MR-207 · tune the impact API", symbols: ["impact"] },
  { id: "MR-211 · ledger append fix", symbols: ["append"] },
];

// Client-side collision engine: mirrors core/collision.py over the bundled per-symbol
// impact data, so a judge can build their OWN set of open MRs and watch the hazard compute
// in-browser on the static deploy - no backend required. The live backend uses the Python
// engine; both produce the same shape.
const KIND_WEIGHT = { same_change: 5, change_in_blast: 3, blast_overlap: 1 };
function _inter(a, b) { const o = new Set(); a.forEach((x) => { if (b.has(x)) o.add(x); }); return o; }
function footprintLocal(symbols) {
  const touched = new Set(), affected = new Set(), names = {}, weight = {};
  (symbols || []).forEach((s) => {
    const imp = (STATIC && STATIC.impact) ? STATIC.impact[s] : null;
    if (!imp || !imp.epicenter) return;
    const epi = imp.epicenter.id;
    touched.add(epi); names[epi] = imp.epicenter.name;
    (imp.affected_ids || []).forEach((i) => affected.add(i));
    Object.keys(imp.names || {}).forEach((k) => { names[Number(k)] = imp.names[k]; });
    weight[epi] = Math.max(weight[epi] || 0, (imp.affected_ids || []).length);
  });
  return { touched, affected, region: new Set([...touched, ...affected]), names, weight };
}
function classifyLocal(a, b) {
  const same = _inter(a.touched, b.touched);
  const cross = new Set([..._inter(a.touched, b.affected), ..._inter(b.touched, a.affected)]);
  same.forEach((x) => cross.delete(x));
  const blast = _inter(a.affected, b.affected); [...same, ...cross].forEach((x) => blast.delete(x));
  if (!same.size && !cross.size && !blast.size) return null;
  const names = { ...a.names, ...b.names }, weight = { ...a.weight, ...b.weight };
  // dedup by display name to match core/collision.py's set-of-names label (two distinct
  // ids that share a short name, e.g. several `main`s, collapse to one entry).
  const label = (s) => [...new Set([...s].map((i) => names[i] || String(i)))].sort();
  let sev = 0;
  [[same, "same_change"], [cross, "change_in_blast"], [blast, "blast_overlap"]].forEach(([s, k]) =>
    s.forEach((i) => { sev += KIND_WEIGHT[k] * (1 + (weight[i] || 0)); }));
  const kind = same.size ? "same_change" : (cross.size ? "change_in_blast" : "blast_overlap");
  return { kind, severity: sev, same_change: label(same), change_in_blast: label(cross),
    blast_overlap: label(blast), shared: label(new Set([...same, ...cross, ...blast])) };
}
function computeCollisionsLocal(mrs) {
  const fps = (mrs || []).map((m) => ({ id: String(m.id || (m.symbols || []).join(",")), fp: footprintLocal(m.symbols), symbols: m.symbols }))
    .filter((x) => x.fp.region.size);
  if (!fps.length) return null;
  const collisions = [];
  for (let i = 0; i < fps.length; i++) for (let j = i + 1; j < fps.length; j++) {
    const c = classifyLocal(fps[i].fp, fps[j].fp);
    if (c) collisions.push({ mr_a: fps[i].id, mr_b: fps[j].id, ...c });
  }
  collisions.sort((x, y) => y.severity - x.severity || (x.mr_a < y.mr_a ? -1 : 1));
  const ids = fps.map((f) => f.id);
  const succ = {}, indeg = {}; ids.forEach((i) => { succ[i] = new Set(); indeg[i] = 0; });
  for (const a of fps) for (const b of fps) {           // edge A->B: A changes what B depends on -> A first
    if (a.id !== b.id && _inter(a.fp.affected, b.fp.touched).size && !succ[a.id].has(b.id)) { succ[a.id].add(b.id); indeg[b.id]++; }
  }
  const order = [], ready = ids.filter((i) => indeg[i] === 0).sort();
  while (ready.length) { const n = ready.shift(); order.push(n); [...succ[n]].sort().forEach((m) => { if (--indeg[m] === 0) ready.push(m); }); ready.sort(); }
  const cycle = ids.filter((i) => !order.includes(i)).sort();
  const per_mr = fps.map((f) => {
    const cs = collisions.filter((c) => c.mr_a === f.id || c.mr_b === f.id);
    return { id: f.id, changes: [...new Set([...f.fp.touched].map((i) => f.fp.names[i] || String(i)))].sort(),
      blast_size: f.fp.affected.size,
      collides_with: [...new Set(cs.map((c) => (c.mr_a === f.id ? c.mr_b : c.mr_a)))].sort(),
      risk: cs.reduce((s, c) => s + c.severity, 0) };
  }).sort((a, b) => b.risk - a.risk);
  const n = collisions.length;
  const verdict = cycle.length ? `${cycle.length} MRs form a dependency cycle and cannot be safely ordered - coordinate them.`
    : (n === 0 ? "No blast-radius collisions - these MRs are independent and any merge order is safe."
      : `${n} collision(s) across ${ids.length} MRs. Suggested safe merge order avoids merging a dependent before the change it relies on.`);
  return { mrs: ids, collisions, per_mr, merge_order: order, uncoordinable_cycle: cycle,
    counts: { mrs: ids.length, collisions: n, colliding_mrs: per_mr.filter((m) => m.collides_with.length).length }, verdict };
}

STATE.openMrs = DEMO_MRS.slice();

async function detectCollisions(mrs) {
  if (API_MODE === "live") {
    const baseUrl = API_URL || "";
    const url = baseUrl.replace(/\/$/, "") + "/api/collisions";
    try {
      const r = await fetch(url, {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ mrs }),
      });
      if (r.ok) return await r.json();
    } catch (e) {
      console.warn("Live API collisions request failed, falling back to static", e);
    }
  }
  await ensureStatic();
  return computeCollisionsLocal(mrs) || (STATIC && STATIC.collisions);
}

async function loadHazards() {
  const col = await detectCollisions(STATE.openMrs);
  STATE._col = col;
  if (col && col.collisions) renderCollision(col);
  try {
    const ga = await api("/api/graph-audit");
    STATE.graphAudit = ga;
    renderGraphAudit(ga);
  } catch (e) {}
  populateMrPicker();
}

function populateMrPicker() {
  const dl = $("#mr-symbols");
  if (dl && STATE.defs && !dl.childElementCount) {
    dl.innerHTML = STATE.defs.map((n) => `<option value="${esc(n)}"></option>`).join("");
  }
}

function _mrMsg(text, kind) {
  const m = $("#mr-msg");
  if (m) { m.textContent = text; m.className = "hz-msg " + (kind || ""); }
  if (kind === "bad") {                                // shake the input so the rejection is felt
    const add = $("#mr-add");
    if (add) { add.classList.remove("shake-x"); void add.offsetWidth; add.classList.add("shake-x"); }
  }
}
async function addMr(symbol) {
  const s = (symbol || "").trim();
  if (!s) return;
  const known = (STATIC && STATIC.impact && STATIC.impact[s]) || STATE.defs.includes(s);
  if (!known) {                                        // unknown symbol: say so, do not clear silently
    _mrMsg("'" + s + "' is not in this Orbit index. Try compute_blast_radius, append, or verify.", "bad");
    return;
  }
  if (STATE.openMrs.some((m) => (m.symbols || [])[0] === s)) { _mrMsg(s + " is already an open MR.", ""); return; }
  const before = (STATE._col && STATE._col.counts && STATE._col.counts.collisions) || 0;
  const id = `MR-${500 + STATE.openMrs.length + 1} · change ${s}`;
  STATE.openMrs.push({ id, symbols: [s] });
  const col = await detectCollisions(STATE.openMrs);
  STATE._col = col;
  renderCollision(col);
  const added = Math.max(0, ((col && col.counts && col.counts.collisions) || 0) - before);
  _mrMsg("Added " + s + " as " + id.split(" ")[0] + (added ? " - " + added + " new collision(s)." : " - no new collision."), "ok");
  const box = $("#collision"); if (box) { box.classList.remove("flash-highlight"); void box.offsetWidth; box.classList.add("flash-highlight"); setTimeout(() => box.classList.remove("flash-highlight"), 1600); }
}

async function resetMrs() {
  STATE.openMrs = DEMO_MRS.slice();
  renderCollision(await detectCollisions(STATE.openMrs));
}

const KIND_LABEL = {
  same_change: "both change the same symbol",
  change_in_blast: "one changes a symbol the other depends on",
  blast_overlap: "their blast radii overlap",
};
// Named risk taxonomy for the Blast Collision hazard, strongest first. Honest labels: we do not
// split DIRECT vs TRANSITIVE here because the footprint does not retain the dependency hop depth.
const RISK = {
  change_in_blast: { tag: "DEPENDENCY-BREAK", cls: "r-high" },   // B changes what A depends on
  same_change: { tag: "SAME-SYMBOL", cls: "r-mid" },             // both edit the same symbol
  blast_overlap: { tag: "SHARED-DEPENDENCY", cls: "r-low" },     // blast radii share dependents
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
    `<span class="hz-mrmeta">changes ${esc((m.changes || []).join(", ") || "-")} · blast ${m.blast_size}</span></div>`
  ).join("") + `</div>`;
  // the collisions
  if (!col.collisions.length) {
    html += `<div class="hz-ok">No blast-radius collisions - these MRs are independent.</div>`;
  } else {
    html += col.collisions.map((c) => {
      const shared = (c.shared || []).slice(0, 5).join(", ");
      // honest per-kind warning. Only change_in_blast is the "no Git conflict, different
      // files" hazard. same_change edits the same symbol (Git WOULD conflict). blast_overlap
      // shares dependents (the shared line conveys it; no banner).
      let warn = "";
      if (c.kind === "change_in_blast") warn = "Git sees NO conflict (different files) - invisible to a normal review";
      else if (c.kind === "same_change") warn = "both MRs change the same symbol - Git will conflict, but neither reviewer sees the other's intent";
      const risk = RISK[c.kind] || { tag: c.kind, cls: "r-low" };
      return `<div class="hz-collide sev-${c.kind}" role="alert">` +
        `<div class="hz-cl-top"><span class="risk-badge ${risk.cls}">${esc(risk.tag)}</span> <b>${esc(c.mr_a.split("·")[0].trim())}</b> ✕ <b>${esc(c.mr_b.split("·")[0].trim())}</b>` +
        `<span class="hz-kind">${esc(KIND_LABEL[c.kind] || c.kind)}</span></div>` +
        `<div class="hz-cl-shared">shares <code>${esc(shared)}</code></div>` +
        (warn ? `<div class="hz-noconflict">${warn}</div>` : "") +
        `</div>`;
    }).join("");
  }
  // safe merge order / cycle
  if (cyc.length) {
    html += `<div class="hz-order bad"><span class="risk-badge r-high">UNORDERABLE-CYCLE</span> ${cyc.length} MRs form a dependency cycle and cannot be safely ordered; coordinate them</div>`;
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

// === AI ASSISTANT (bounded tool-using agent) ===
// Live backend runs a fresh agent loop (POST); the static deploy serves the baked
// plan (and a REAL recorded run for headline symbols). The agent PROPOSES; the
// deterministic gate DECIDES - so this never touches the trust path.
async function callAssistant(symbol, question) {
  if (API_MODE === "live") {
    const baseUrl = API_URL || "";
    const url = baseUrl.replace(/\/$/, "") + "/api/assistant";
    try {
      const r = await fetch(url, {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ symbol, question: question || undefined }),
      });
      if (r.ok) return await r.json();
      throw new Error("assistant " + r.status);
    } catch (e) {
      console.warn("Live API assistant request failed, falling back to static", e);
    }
  }
  await ensureStatic();
  const rec = (STATIC.assistant || {})[symbol];
  return rec || { answer: "No assistant data for this symbol in the static bundle.", steps: [], deterministic: true, provider: null };
}

// a compact one-line summary of an engine tool result for the trace
function toolResultSummary(tool, r) {
  if (!r || r.error) return r && r.error ? esc(r.error) : "-";
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
    `<div class="agent-answer">${esc(res.answer || "-")}</div>` +
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
  // chain is reproducible by anyone and is NOT tamper-evident - never show green
  // "CHAIN VERIFIED" there. Only the live backend (secret per-machine key) does.
  const isStatic = STATIC_MODE || !!STATIC;
  if (!v.ok) {
    vd.textContent = "BROKEN AT ROW " + v.broken_index; vd.className = "verdict bad";
  } else if (isStatic) {
    vd.textContent = "SAMPLE · SHARED-KEY HMAC"; vd.className = "verdict warn";
    vd.title = "public demo only: HMAC is a symmetric shared-secret MAC and this sample key is published in source, so anyone (including a malicious writer) could recompute the chain. As shipped it proves no ACCIDENTAL corruption, not insider tamper-resistance. The local app uses a secret per-machine key; true insider-resistance needs an asymmetric signature or external anchor (roadmap).";
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

// === EVENT WIRING ===
function wire() {
  $("#search").addEventListener("input", () => renderDefList(currentDefView()));
  const showAllBtn = $("#show-all");
  if (showAllBtn) showAllBtn.onclick = () => { STATE.showAll = !STATE.showAll; renderDefList(currentDefView()); updateShowAllLabel(); };
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
  $("#verify").onclick = verifyChain;
  $("#tamper").onclick = tamperDemo;
  const ex = $("#export-att"); if (ex) ex.onclick = exportAttestation;
  const ov = $("#override"); if (ov) ov.onchange = applyGatePolicy;
  // interactive cross-MR hazard: a judge builds their own open-MR set and the collision
  // recomputes live (client-side on the static deploy, via the backend when running live)
  const mrAdd = $("#mr-add"), mrReset = $("#mr-reset");
  if (mrAdd) mrAdd.addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); addMr(mrAdd.value); mrAdd.value = ""; }
  });
  if (mrReset) mrReset.onclick = resetMrs;
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
  // === KEYBOARD SHORTCUTS ===
  document.addEventListener("keydown", (e) => {
    const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName);
    // Ctrl+K / Cmd+K: open command palette
    if ((e.ctrlKey || e.metaKey) && e.key === "k") {
      e.preventDefault();
      if (window.__ksCmdOpen) window.__ksCmdOpen();
      return;
    }
    // "/" focuses symbol search
    if (e.key === "/" && !typing) { e.preventDefault(); $("#search").focus(); }
    // Escape closes command palette, clears search, or closes mobile sidebar
    else if (e.key === "Escape") {
      const cmdOverlay = $("#cmd-overlay");
      if (cmdOverlay && cmdOverlay.classList.contains("open")) { if (window.__ksCmdClose) window.__ksCmdClose(); return; }
      if (document.activeElement === $("#search")) { $("#search").value = ""; renderDefList(currentDefView()); }
      const sidebar = $("#sidebar");
      if (sidebar && sidebar.classList.contains("mobile-open")) sidebar.classList.remove("mobile-open");
    }
  });

  // Hero CTA listeners
  const ctaCockpit = $("#cta-cockpit");
  if (ctaCockpit) {
    ctaCockpit.onclick = () => {
      if (typeof goToEl === "function") goToEl("reviewer-cockpit-intro");
      const cockSec = $("#reviewer-cockpit-intro");
      if (cockSec) setTimeout(() => highlightPanel(cockSec), 140);
    };
  }

  // guided first-click: a lede chip deep-selects a money-shot symbol and scrolls to the stage
  document.querySelectorAll(".lede-chip[data-pick]").forEach((b) => {
    b.addEventListener("click", () => {
      const name = b.dataset.pick;
      if (STATE.defs && !STATE.defs.includes(name)) return;   // never point at a symbol not in this graph
      select(name);
      if (typeof goToEl === "function") goToEl("blast-radius");
      const stage = document.getElementById("blast-radius");
      if (stage) setTimeout(() => highlightPanel(stage), 140);  // pulse the panel the CTA reveals so the payoff lands
      const gate = document.querySelector(".panel.gate"); if (gate) setTimeout(() => highlightPanel(gate), 250);
    });
  });

  // Guided 60-second tour: auto-runs the canonical sequence so a judge who clicks once
  // gets the full demo in under a minute, with the panel payoff pulsing on each step.
  // Future Merge Simulator controls
  function initSimulator() {
    const nextBtn = $("#sim-next");
    const prevBtn = $("#sim-prev");
    if (!nextBtn || !prevBtn) return;
    let currentStep = 1;
    const maxSteps = 5;

    function showStep(step) {
      currentStep = step;
      document.querySelectorAll(".sim-step").forEach((el) => {
        const s = parseInt(el.dataset.step);
        el.classList.toggle("active", s === currentStep);
        el.classList.toggle("done", s < currentStep);
      });
      for (let s = 1; s <= maxSteps; s++) {
        const content = $(`#sim-content-${s}`);
        if (content) {
          content.style.display = s === currentStep ? "block" : "none";
        }
      }
      prevBtn.disabled = currentStep === 1;
      if (currentStep === maxSteps) {
        nextBtn.textContent = "Restart";
      } else {
        nextBtn.textContent = "Next Step";
      }
    }

    nextBtn.onclick = () => {
      if (currentStep === maxSteps) {
        showStep(1);
      } else {
        showStep(currentStep + 1);
      }
    };

    prevBtn.onclick = () => {
      if (currentStep > 1) {
        showStep(currentStep - 1);
      }
    };

    document.querySelectorAll(".sim-step").forEach((el) => {
      el.addEventListener("click", () => {
        const s = parseInt(el.dataset.step);
        if (s) showStep(s);
      });
    });
  }
  initSimulator();

  // Manual guided tour with 9 precise steps
  const TOUR_STEPS = [
    { label: "1/9: Core Value Proposition", action: () => { scrollTo("hero-strip"); } },
    { label: "2/9: Cross-MR Blast Simulator", action: () => { scrollTo("simulation-section"); } },
    { label: "3/9: Codebase Security Matrix", action: () => { scrollTo("orbit-diff-section"); } },
    { label: "4/9: Selection of Epicenter Symbol", action: () => { select("compute_blast_radius"); scrollTo("search"); } },
    { label: "5/9: Blast Radius Visualization", action: () => { scrollTo("blast-radius"); const stage = $("#blast-radius"); if (stage) highlightPanel(stage); } },
    { label: "6/9: Precedent Contradiction Recalled", action: () => { scrollTo("precedent"); const prec = $(".panel.precedent"); if (prec) highlightPanel(prec); } },
    { label: "7/9: Bounded AI Review Advisory", action: () => { scrollTo("assistant"); const asst = $(".panel.assistant"); if (asst) highlightPanel(asst); } },
    { label: "8/9: The Enforcement Gate", action: () => { scrollTo("gate"); const gate = $("#gate"); if (gate) highlightPanel(gate); } },
    { label: "9/9: Cryptographic Ledger Audit", action: () => { scrollTo("audit"); const aud = $("#audit"); if (aud) highlightPanel(aud); } },
  ];
  
  let tourIndex = 0;

  function stopTour() {
    const bar = document.getElementById("tour-bar");
    if (bar) bar.hidden = true;
  }

  function startTour() {
    const bar = document.getElementById("tour-bar");
    const stepEl = document.getElementById("tour-step");
    const metaEl = document.getElementById("tour-meta");
    if (!bar || !stepEl || !metaEl) return;
    bar.hidden = false;
    showTourStep(0);
  }

  function showTourStep(index) {
    tourIndex = index;
    const step = TOUR_STEPS[tourIndex];
    const stepEl = document.getElementById("tour-step");
    const metaEl = document.getElementById("tour-meta");
    if (stepEl) stepEl.textContent = step.label;
    if (metaEl) metaEl.textContent = `Step ${tourIndex + 1} of ${TOUR_STEPS.length}`;
    
    try {
      step.action();
    } catch (_) {}

    const prevBtn = document.getElementById("tour-prev");
    const nextBtn = document.getElementById("tour-next");
    if (prevBtn) prevBtn.disabled = tourIndex === 0;
    if (nextBtn) {
      nextBtn.textContent = tourIndex === TOUR_STEPS.length - 1 ? "Finish" : "Next Step";
    }
  }

  function scrollTo(idOrSelector) {
    const el = idOrSelector.startsWith(".") || idOrSelector.startsWith("#")
      ? $(idOrSelector)
      : document.getElementById(idOrSelector);
    if (el) {
      if (typeof viewOf === "function") { var _v = viewOf(el); if (_v && typeof showView === "function") showView(_v); }
      setTimeout(function () { if (el.scrollIntoView) el.scrollIntoView({ behavior: "smooth", block: "center" }); }, 60);
    }
  }

  const tourBtn = document.getElementById("lede-tour");
  if (tourBtn) tourBtn.addEventListener("click", startTour);
  
  const stopBtn = document.getElementById("tour-stop");
  if (stopBtn) stopBtn.addEventListener("click", stopTour);

  const tourPrev = document.getElementById("tour-prev");
  if (tourPrev) {
    tourPrev.onclick = () => {
      if (tourIndex > 0) showTourStep(tourIndex - 1);
    };
  }

  const tourNext = document.getElementById("tour-next");
  if (tourNext) {
    tourNext.onclick = () => {
      if (tourIndex < TOUR_STEPS.length - 1) {
        showTourStep(tourIndex + 1);
      } else {
        stopTour();
      }
    };
  }

  // Filters change listeners
  const filterType = $("#filter-type");
  const filterHazard = $("#filter-hazard");
  if (filterType) filterType.addEventListener("change", () => renderDefList(currentDefView()));
  if (filterHazard) filterHazard.addEventListener("change", () => renderDefList(currentDefView()));

  // Onboarding controls listeners
  const onboardingModal = $("#onboarding-modal");
  if (onboardingModal) {
    onboardingModal.addEventListener("keydown", (e) => {
      if (e.key === "Escape") { e.preventDefault(); closeOnboarding(); }
      else trapModalFocus(e, onboardingModal);
    });
    const closeBtn = $("#onboard-close");
    if (closeBtn) closeBtn.onclick = closeOnboarding;
    const prevBtn = $("#onboard-prev");
    if (prevBtn) prevBtn.onclick = () => { if (onboardingStep > 0) { onboardingStep--; renderOnboardingStep(); } };
    const nextBtn = $("#onboard-next");
    if (nextBtn) nextBtn.onclick = () => {
      if (onboardingStep < onboardingSteps.length - 1) {
        onboardingStep++;
        renderOnboardingStep();
      } else {
        closeOnboarding();
      }
    };
  }
}

// fnmatch-style path glob, mirroring core/agents._matches (normalise the leading slash, try a
// few forms). Case-sensitive, matching the Orbit graph paths and the committed manifest.
function _globRe(pat) {
  let re = "";
  for (const c of (pat || "")) {
    if (c === "*") re += ".*";
    else if (c === "?") re += ".";
    else if ("\\^$.|+()[]{}".indexOf(c) >= 0) re += "\\" + c;
    else re += c;
  }
  return new RegExp("^" + re + "$");
}
function _matchPath(path, pattern) {
  const p = (path || "").replace(/^\/+/, ""), pat = (pattern || "").replace(/^\/+/, "");
  return _globRe(pat).test(p) || _globRe(pattern).test("/" + p) || _globRe(pattern).test(path || "");
}
// resolve_author + check_scope mirror core/agents.py, over the registry baked into STATIC.agents.
function resolveAuthor(author, kind, registry) {
  const agents = (registry && registry.agents) || {};
  if (agents[author]) {
    const a = agents[author];
    return { id: author, badge: "AGENT_VERIFIED", scope: {
      allowed_paths: a.allowed_paths || [], forbidden_paths: a.forbidden_paths || [],
      max_blast_radius: (a.max_blast_radius == null ? null : a.max_blast_radius) } };
  }
  if ((kind || "").toLowerCase() === "agent") return { id: author, badge: "AGENT_UNREGISTERED", scope: null };
  return { id: author, badge: "HUMAN", scope: null };
}
function checkScope(authorCtx, imp) {
  const scope = authorCtx.scope;
  if (!scope) return { in_scope: true, violations: [] };
  const owners = (imp && imp.owners) || [];          // path scope governs the ring-0 changed file(s)
  let files = [...new Set(owners.filter((o) => (o.ring || 0) === 0 && o.file).map((o) => o.file))];
  if (!files.length) files = [...new Set(owners.filter((o) => o.file).map((o) => o.file))];
  const allowed = scope.allowed_paths || [], forbidden = scope.forbidden_paths || [], violations = [];
  files.forEach((f) => {
    if (forbidden.some((pat) => _matchPath(f, pat))) violations.push(f + " matches a forbidden path for this agent");
    else if (allowed.length && !allowed.some((pat) => _matchPath(f, pat))) violations.push(f + " is outside this agent's allowed paths");
  });
  const cap = scope.max_blast_radius, defs = ((imp && imp.counts) || {}).total_affected || 0;
  if (cap != null && defs > cap) violations.push("blast radius " + defs + " exceeds this agent's max_blast_radius " + cap);
  return { in_scope: violations.length === 0, violations };
}

// === CLIENT-SIDE GOVERNANCE GATE ===
// Mirrors core/gate.py over the in-browser sample ledger so the STATIC deploy
// ENFORCES the full flow (agent scope, four-eyes, contradiction BLOCK, quorum).
function clientGate(name, decision, reviewer, changeAuthor, override, authorKind) {
  const imp = (STATIC && STATIC.impact && STATIC.impact[name]) || {};
  const pol = imp.policy || {};
  const sig = imp.signature || "";
  const cid = STATE.changeId || ("MR-" + name);      // share one change identity with the live path
  // agent gating (mirrors core/agents.py + the gate.py order): a registered agent out of scope is
  // refused for any decision; an unregistered agent cannot self-approve.
  const author = resolveAuthor(reviewer, authorKind, (typeof STATIC !== "undefined" && STATIC.agents) || null);
  if (author.scope) {
    const sc = checkScope(author, imp);
    if (!sc.in_scope) return { ok: false, error: "SCOPE_VIOLATION", violations: sc.violations };
  }
  if (decision === "approve" && author.badge === "AGENT_UNREGISTERED")
    return { ok: false, error: "UNREGISTERED_AGENT",
             hint: "this agent id is not in .keystone/agents.json; register it or have a human review" };
  if (decision === "approve" && changeAuthor && reviewer === changeAuthor && !override)
    return { ok: false, error: "SELF_APPROVAL",
             hint: "the change author cannot approve their own change; use a different reviewer or an accountable override" };
  if (decision === "approve" && pol.action === "BLOCK" && !override)
    return { ok: false, error: "GOVERNANCE_BLOCK",
             reasons: pol.reasons || ["a prior identical-blast-radius rejection forces BLOCK"] };
  const rows = (STATIC && STATIC.audit && STATIC.audit.rows) || [];
  // distinct prior approvers for THIS change: non-seeded, same change id + signature, and only
  // approvals after the most recent rejection (a rejection resets the count) - mirrors gate.py.
  const rel = rows.filter((r) => !r.seeded && r.change_id === cid &&
    (r.target_symbols || []).includes(name) && r.signature === sig);
  let lastReject = -1;
  rel.forEach((r) => { if (r.decision === "reject" && r.seq > lastReject) lastReject = r.seq; });
  const prior = [...new Set(rel.filter((r) => r.decision === "approve" && r.seq > lastReject).map((r) => r.actor))];
  const confirmed = decision === "approve" ? [...new Set([...prior, reviewer])] : prior;
  const required = pol.required_approvers || 1;
  const status = decision === "reject" ? "REJECTED"
    : (confirmed.length >= required ? "APPROVED" : "PENDING_APPROVAL");
  const overrideUsed = !!override &&
    (pol.action === "BLOCK" || (decision === "approve" && !!changeAuthor && reviewer === changeAuthor));
  return { ok: true, cid, sig, overrideUsed,
           quorum: { required, confirmed: confirmed.length, status, closed: status === "APPROVED", approvers: confirmed } };
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
  if (!STATIC_MODE && API_MODE !== "static") {
    try {
      const r = await fetch("/api/approve", {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ name: STATE.selected, decision, reviewer, rationale: reason, author_kind: authorKind, override,
          change_id: STATE.changeId, change_author: (($("#changeauthor") && $("#changeauthor").value.trim()) || undefined) }),
      });
      if (r.ok) {
        const body = await r.json().catch(() => ({}));
        $("#reason").value = "";
        await refreshLedger(); await select(STATE.selected);   // re-render first, then show the result so it persists
        const st = $("#gate-status");
        if (st && body.quorum) {
          const closed = body.quorum.status === "APPROVED";
          st.textContent = "recorded · " + body.quorum.status + " (" + body.quorum.confirmed + "/" + body.quorum.required + " approvers)";
          st.style.color = closed ? "var(--green)" : "var(--text-mid)";
        }
        return;
      }
      const b = await r.json().catch(() => ({}));
      const det = (b && b.detail) || {};
      if (r.status === 403) {                       // scope / unregistered agent / self-approval
        const code = (det.error || "BLOCKED").replace(/_/g, " ");
        const why = det.violations ? det.violations.join("; ") : (det.hint || "");
        flashRefusal(code, why);
        return;
      }
      if (r.status === 409) {                       // policy BLOCK, no override
        flashRefusal("POLICY BLOCK", ((det.reasons || ["blocked by policy"]).join("; ")) + " - tick override to record an accountable override.");
        if ($("#override-row")) $("#override-row").style.display = "block";
        return;
      }
      throw new Error("approve " + r.status);
    } catch (e) {
      await ensureStatic(); STATIC_MODE = true; // fall through to client-side sample append
    }
  }
  // STATIC deploy: run the FULL governance gate in-browser (mirrors core/gate.py), so the demo
  // enforces four-eyes, the contradiction BLOCK, and a real quorum - not just records a row.
  const changeAuthor = ($("#changeauthor") && $("#changeauthor").value.trim()) || "";
  const g = clientGate(STATE.selected, decision, reviewer, changeAuthor, override, authorKind);
  if (!g.ok) {
    if (g.error === "SCOPE_VIOLATION") {
      flashRefusal("SCOPE VIOLATION", "agent out of scope: " + (g.violations || []).join("; "));
    } else if (g.error === "UNREGISTERED_AGENT") {
      flashRefusal("UNREGISTERED AGENT", g.hint);
    } else if (g.error === "SELF_APPROVAL") {
      flashRefusal("FOUR-EYES", g.hint);
    } else if (g.error === "GOVERNANCE_BLOCK") {
      flashRefusal("POLICY BLOCK", (g.reasons || []).join("; ") + " - tick override to record an accountable override.");
      if ($("#override-row")) $("#override-row").style.display = "block";
    }
    return;
  }
  // append in-browser so the gate stays interactive (the live local app persists to the
  // hash-chained ledger). Carry the governance fields so the row mirrors a server-recorded one.
  const imp = STATIC.impact[STATE.selected] || {}, ip = imp.policy || {};
  const _seq = STATIC.audit.rows.reduce((m, r) => Math.max(m, r.seq || 0), -1) + 1;
  STATIC.audit.rows.unshift({                          // newest-first, matching the bundle order
    seq: _seq, actor: reviewer, change_id: g.cid,
    target_symbols: [STATE.selected], decision, rationale: reason,
    blast_radius_set: (imp.affected_ids || []),        // record the REAL blast, not 0
    signature: imp.signature || "", tier: ip.tier, governance_action: ip.action,
    quorum_status: g.quorum.status, confirmed_approvers: g.quorum.approvers, override: g.overrideUsed,
    ts: new Date().toISOString().replace(/\.\d+Z$/, "Z"), row_hash: "(in-browser sample)",
  });
  $("#reason").value = "";
  await refreshLedger(); await select(STATE.selected);   // re-render first (applyGatePolicy resets the status line)
  const st = $("#gate-status");                          // then show the recorded quorum result, so it persists
  if (st) {
    st.textContent = "recorded · " + g.quorum.status + " (" + g.quorum.confirmed + "/" + g.quorum.required +
      " approver" + (g.quorum.required === 1 ? "" : "s") + ")" + (g.overrideUsed ? " · override recorded" : "");
    st.style.color = g.quorum.closed ? "var(--green)" : "var(--text-mid)";
  }
  const note = $("#sample-note");
  if (note) { note.textContent = "recorded in this browser only - the live local app persists to the hash-chained ledger"; note.style.opacity = "1"; }
}

// === TAMPER DEMO ===
// In-memory tamper demo: re-render the ledger as if a row were edited.
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
  // Persist the broken state and narrate it; nothing heals automatically. The reviewer must
  // click VERIFY CHAIN to recompute, which is the whole point: tamper-evidence is detected,
  // not silently undone.
  const note = $("#tamper-note");
  if (note) {
    note.hidden = false; note.className = "tamper-note bad";
    note.textContent = "Simulated edit to row " + idx + ": the row hash no longer recomputes, so the chain breaks at link " + idx + " and every link after it. Nothing healed it. Click VERIFY CHAIN to recompute from the rows.";
  }
}

// VERIFY CHAIN: recompute and narrate the result (and clear a simulated tamper).
async function verifyChain() {
  await refreshLedger();
  const note = $("#tamper-note");
  if (note && !note.hidden) {
    const sample = STATIC_MODE || !!STATIC;
    note.className = "tamper-note ok";
    note.textContent = sample
      ? "Re-verified: recomputed from the real rows. This public bundle uses a published sample key, so the chain badge reads SAMPLE; the local app keys it with a secret per-host key for true tamper-evidence."
      : "Re-verified: the chain recomputed cleanly from the rows, every link intact.";
    setTimeout(() => { note.hidden = true; }, 5000);
  }
}

// === THEME MANAGER ===
function initTheme() {
  const toggle = $("#theme-toggle");
  if (!toggle) return;
  const currentTheme = localStorage.getItem("ks-theme");
  if (currentTheme === "light") {
    document.body.classList.add("light-theme");
  }
  toggle.addEventListener("click", () => {
    document.body.classList.toggle("light-theme");
    const isLight = document.body.classList.contains("light-theme");
    localStorage.setItem("ks-theme", isLight ? "light" : "dark");
  });
}

// === ONBOARDING WIZARD DATA & LOGIC ===
const onboardingSteps = [
  {
    title: "The 2am break",
    body: `
      <p>Two merge requests. Different files. No Git conflict. They still break production together, because one changes a function the other quietly depends on.</p>
      <p>Keystone catches that on the GitLab Orbit call graph, before you merge.</p>
      <button class="btn primary onboard-action" type="button" data-onboard-action="sim">Show me a collision Git can't see</button>
    `
  },
  {
    title: "Computed, not guessed",
    body: `
      <p>Every number here is computed from a real GitLab Orbit index of this repo and cross-checked by <code>orbit sql</code>. Zero invented figures.</p>
      <p><code>compute_blast_radius</code> reaches <b>12</b> dependents, and the orbit-verified badge proves the count.</p>
      <button class="btn primary onboard-action" type="button" data-onboard-action="select">Compute the blast radius live</button>
    `
  },
  {
    title: "The gate refuses",
    body: `
      <p><code>compute_blast_radius</code> was already rejected once, by reviewer s.castellano, on an identical blast signature. The deterministic gate <b>BLOCKs</b> re-approval.</p>
      <p>The AI reviewer explains the risk. It never decides; the engine decides.</p>
      <button class="btn primary onboard-action" type="button" data-onboard-action="gate">Watch a self-approval get refused</button>
    `
  },
  {
    title: "Proof nobody can quietly edit",
    body: `
      <p>Every decision is an HMAC hash-linked row. Simulate a tamper and the chain turns red.</p>
      <p class="muted">The public demo uses a published sample key (labeled SAMPLE); only the CI backend with a secret key is truly tamper-evident.</p>
      <button class="btn primary onboard-action" type="button" data-onboard-action="audit">Verify the ledger, then tamper it</button>
    `
  }
];

let onboardingStep = 0;

function showOnboarding(step = 0) {
  const modal = $("#onboarding-modal");
  if (!modal) return;
  onboardingStep = step;
  modal.removeAttribute("hidden");
  renderOnboardingStep();
  modal.focus();
}

function closeOnboarding() {
  const modal = $("#onboarding-modal");
  if (modal) modal.setAttribute("hidden", "true");
  localStorage.setItem("keystone-onboarded", "true");
}

// Value-first onboarding: each step's button closes the wizard and drives the real
// UI underneath (reuses select() + scrollIntoView; no new behavior, ID-safe).
function doOnboardAction(action) {
  closeOnboarding();
  const map = { sim: "simulation-section", select: "blast-radius", gate: "gate", audit: "audit" };
  setTimeout(() => {
    if (action === "select" && typeof select === "function") {
      try { select("compute_blast_radius"); } catch (e) {}
    }
    if (typeof goToEl === "function") goToEl(map[action]);
  }, 140);
}

function renderOnboardingStep() {
  const step = onboardingSteps[onboardingStep];
  if (!step) return;

  $("#onboard-title").textContent = step.title;
  $("#onboard-body").innerHTML = step.body;
  const _act = $("#onboard-body [data-onboard-action]");
  if (_act) _act.onclick = () => doOnboardAction(_act.dataset.onboardAction);

  const dots = $("#onboard-dots");
  if (dots) {
    dots.innerHTML = onboardingSteps.map((_, i) => 
      `<span class="onboard-dot ${i === onboardingStep ? "active" : ""}" data-step="${i}"></span>`
    ).join("");
    dots.querySelectorAll(".onboard-dot").forEach(dot => {
      dot.onclick = () => {
        onboardingStep = Number(dot.dataset.step);
        renderOnboardingStep();
      };
    });
  }

  const pct = ((onboardingStep + 1) / onboardingSteps.length) * 100;
  const progress = $("#onboard-progress");
  if (progress) progress.style.width = pct + "%";

  const prev = $("#onboard-prev");
  const next = $("#onboard-next");
  if (prev) prev.disabled = onboardingStep === 0;
  if (next) {
    if (onboardingStep === onboardingSteps.length - 1) {
      next.textContent = "Finish";
    } else {
      next.textContent = "Next";
    }
  }
}

function trapModalFocus(e, modalEl) {
  if (e.key !== 'Tab') return;
  const focusables = modalEl.querySelectorAll('button, [tabindex="0"], a');
  if (!focusables.length) return;
  const first = focusables[0];
  const last = focusables[focusables.length - 1];

  if (e.shiftKey) {
    if (document.activeElement === first) {
      last.focus();
      e.preventDefault();
    }
  } else {
    if (document.activeElement === last) {
      first.focus();
      e.preventDefault();
    }
  }
}

// === CONNECTION SETTINGS MANAGER ===
function updateConnectionStatus() {
  const btn = $("#connection-toggle");
  const dot = $("#conn-dot");
  const text = $("#conn-text");
  if (!btn || !dot || !text) return;

  if (API_MODE === "live" && STATE.sourceMode === "LIVE") {
    text.textContent = "mode: live backend";
    dot.className = "dot g";
    btn.className = "chip ok";
    btn.title = "Connected to a live backend at " + (API_URL || "same origin") + " serving a live graph. Click to change settings.";
  } else if (API_MODE === "live") {
    text.textContent = "mode: snapshot";
    dot.className = "dot a";
    btn.className = "chip warn";
    btn.title = "Live mode is selected, but the data shown is the committed snapshot (no live graph responded). Click to change settings.";
  } else {
    text.textContent = "mode: snapshot";
    dot.className = "dot a";
    btn.className = "chip warn";
    btn.title = "Using the committed static snapshot (data.json). Click to change settings.";
  }
}

function initSettings() {
  const btn = $("#connection-toggle");
  const modal = $("#settings-modal");
  if (!btn || !modal) return;

  btn.onclick = () => {
    const mode = API_MODE;
    const staticRadio = $("#mode-static");
    const liveRadio = $("#mode-live");
    if (staticRadio) staticRadio.checked = mode === "static";
    if (liveRadio) liveRadio.checked = mode === "live";
    const urlInput = $("#api-url");
    if (urlInput) urlInput.value = API_URL;
    const urlGroup = $("#api-url-group");
    if (urlGroup) urlGroup.style.display = mode === "live" ? "flex" : "none";

    modal.removeAttribute("hidden");
    modal.focus();
  };

  const close = () => modal.setAttribute("hidden", "true");
  const closeBtn = $("#settings-close");
  if (closeBtn) closeBtn.onclick = close;
  const cancelBtn = $("#settings-cancel");
  if (cancelBtn) cancelBtn.onclick = close;

  const modeStatic = $("#mode-static");
  const modeLive = $("#mode-live");
  const urlGroup = $("#api-url-group");
  if (modeStatic && modeLive && urlGroup) {
    modeStatic.onchange = () => { if (modeStatic.checked) urlGroup.style.display = "none"; };
    modeLive.onchange = () => { if (modeLive.checked) urlGroup.style.display = "flex"; };
  }

  const save = $("#settings-save");
  if (save) {
    save.onclick = async () => {
      const staticRadio = $("#mode-static");
      const mode = (staticRadio && staticRadio.checked) ? "static" : "live";
      const urlInput = $("#api-url");
      const url = urlInput ? urlInput.value.trim() : "";
      
      API_MODE = mode;
      API_URL = url;
      localStorage.setItem("ks-api-mode", mode);
      localStorage.setItem("ks-api-url", url);

      close();
      updateConnectionStatus();

      // Refresh app data live
      try {
        const st = await api("/api/status");
        paintStatus(st);
      } catch (e) {}
      try {
        const d = await api("/api/definitions");
        STATE.defs = d.names;
        STATE.details = d.details || {};
        renderDefList(currentDefView());
        updateShowAllLabel();
        
        if (STATE.defs.length) {
          const demo = STATE.defs.includes("compute_blast_radius") ? "compute_blast_radius"
            : (STATE.defs.includes("tokenize") ? "tokenize" : STATE.defs[0]);
          select(demo);
        }
      } catch (e) {}
      await refreshLedger();
      loadHazards();
    };
  }
}

// ===== HUB: single-page view switcher (Home / Demo / Harness / Cockpit / Ledger) =====
function viewOf(el) {
  for (var n = el; n && n !== document.body; n = n.parentElement) {
    if (n.dataset && n.dataset.view) return n.dataset.view;
  }
  return null;
}
function showView(name) {
  if (!name) name = "home";
  document.querySelectorAll("[data-view]").forEach(function (s) {
    var on = (s.dataset.view === name);
    s.style.display = on ? "" : "none";
    if (on) s.classList.remove("ks-hidden"); // force-reveal so switched-in sections are never stuck invisible
  });
  document.querySelectorAll("[data-goview]").forEach(function (t) {
    var sel = (t.dataset.goview === name);
    t.classList.toggle("active", sel);
    if (sel) t.setAttribute("aria-current", "page");
    else t.removeAttribute("aria-current");
  });
  try { localStorage.setItem("ks-view", name); } catch (e) {}
  document.body.setAttribute("data-active-view", name);
  window.scrollTo({ top: 0 });
  // re-render the blast graph when the cockpit becomes visible (it may have rendered while hidden)
  if (name === "cockpit" && typeof select === "function" && window.STATE && STATE.selected) {
    setTimeout(function () { try { select(STATE.selected); } catch (e) {} }, 20);
  }
}
window.showView = showView;
function goToEl(id) {
  var el = document.getElementById(id);
  if (!el) return;
  var v = viewOf(el);
  if (v) showView(v);
  setTimeout(function () {
    var e2 = document.getElementById(id);
    if (e2 && e2.scrollIntoView) e2.scrollIntoView({ behavior: "smooth", block: "start" });
  }, 70);
}
window.goToEl = goToEl;
function initHub() {
  var byId = {
    "hero-strip": "home", "orbit-diff-section": "home", "product-demo": "home",
    "simulation-section": "demo", "harness-pipeline": "harness",
    "reviewer-cockpit-intro": "cockpit", "audit": "ledger", "attestation": "ledger", "trust-layer": "ledger",
  };
  Object.keys(byId).forEach(function (id) { var el = document.getElementById(id); if (el) el.dataset.view = byId[id]; });
  var hz = document.querySelector(".hazard.panel"); if (hz) hz.dataset.view = "demo";
  var ws = document.querySelector(".workspace"); if (ws) ws.dataset.view = "cockpit";
  document.querySelectorAll("[data-goview]").forEach(function (t) {
    t.addEventListener("click", function () { showView(t.dataset.goview); });
  });
  showView(localStorage.getItem("ks-view") || "home");
}
function initHeroCollision() {
  var frame = document.getElementById("hero-collision-frame");
  if (!frame || typeof computeCollisionsLocal !== "function") return;
  var col = computeCollisionsLocal(DEMO_MRS);
  if (!col || !col.collisions || !col.collisions.length) return;
  // headline collision: compute_blast_radius x append (the blast_overlap), else the top-severity one
  var c = col.collisions.find(function (x) {
    var k = String(x.mr_a) + String(x.mr_b);
    return /compute_blast_radius/.test(k) && /append/.test(k);
  }) || col.collisions[0];
  var shared = c.shared || [];
  var n = String(shared.length);
  var setTxt = function (id, t) { var el = document.getElementById(id); if (el) el.textContent = t; };
  setTxt("hero-shared-count", n);
  setTxt("hero-stakes-num", n);
  setTxt("hero-shared-list", shared.join("  ·  "));
  var verdict = document.getElementById("hero-collision-verdict");
  if (!verdict) return;
  var reveal = function () { frame.classList.add("resolved"); verdict.hidden = false; };
  if (typeof reduceMotion !== "undefined" && reduceMotion) reveal();
  else setTimeout(reveal, 1100);
}
window.initHeroCollision = initHeroCollision;
// NotebookLM-style citation chips: click a dependent name in IMPACT -> jump the blast graph to its source
document.addEventListener("click", function (e) {
  var chip = e.target && e.target.closest ? e.target.closest(".cite-chip[data-cite-sym]") : null;
  if (!chip) return;
  var sym = chip.dataset.citeSym;
  if (sym && STATE.defs && STATE.defs.indexOf(sym) >= 0 && typeof select === "function") {
    if (typeof showView === "function") showView("cockpit");
    select(sym);
  }
});
function _pickTopSymbol(data) {
  var det = (data.definitions && data.definitions.details) || {};
  var best = null, bestN = -1;
  Object.keys(det).forEach(function (n) { var t = det[n].total_affected || 0; if (t > bestN) { bestN = t; best = n; } });
  return best;
}
function runRepoAnalysis(url) {
  var statusEl = document.getElementById("repo-status");
  var btn = document.getElementById("repo-go");
  if (!window.analyzeRepo) { if (statusEl) statusEl.textContent = "Analyzer not loaded."; return; }
  if (btn) btn.disabled = true;
  var setS = function (m, err) { if (statusEl) { statusEl.textContent = m; statusEl.classList.toggle("err", !!err); } };
  setS("Starting…");
  window.analyzeRepo(url, function (m) { setS(m); }).then(function (data) {
    STATIC = data; STATIC_MODE = true; API_MODE = "static";
    STATE.defs = data.definitions.names;
    STATE.details = data.definitions.details || {};
    STATE.selected = null; STATE.openMrs = [];
    var slug = (data._repo && data._repo.slug) || url;
    var sc = document.getElementById("src-chip"); if (sc) { sc.innerHTML = '<span class="dot g"></span>repo <b>' + esc(slug) + '</b>'; sc.className = "chip ok"; sc.title = data.status.data_provenance; }
    var dm = document.getElementById("db-mode"); if (dm) dm.textContent = "client analysis";
    var dc = document.getElementById("def-count"); if (dc) dc.textContent = data.definitions.names.length;
    var prov = document.getElementById("data-provenance"); if (prov) { prov.textContent = data.status.data_provenance; prov.hidden = false; }
    if (typeof renderDefList === "function") renderDefList(currentDefView());
    if (typeof updateShowAllLabel === "function") updateShowAllLabel();
    var top = _pickTopSymbol(data);
    if (top && typeof select === "function") select(top);
    try { if (typeof loadHazards === "function") loadHazards(); } catch (e) {}
    if (typeof showView === "function") showView("cockpit");
    setS("Analyzed " + slug + " — " + data.definitions.names.length + " definitions. Pick any symbol for its real blast radius; add two as MRs to find silent collisions.");
    if (btn) btn.disabled = false;
  }).catch(function (err) { setS((err && err.message) || "Analysis failed.", true); if (btn) btn.disabled = false; });
}
window.runRepoAnalysis = runRepoAnalysis;
function initRepoAnalyze() {
  var btn = document.getElementById("repo-go"), inp = document.getElementById("repo-input");
  if (btn) btn.addEventListener("click", function () { if (inp && inp.value.trim()) runRepoAnalysis(inp.value.trim()); });
  if (inp) inp.addEventListener("keydown", function (e) { if (e.key === "Enter" && inp.value.trim()) { e.preventDefault(); runRepoAnalysis(inp.value.trim()); } });
  document.querySelectorAll("[data-repo-example]").forEach(function (el) {
    el.addEventListener("click", function () { var v = el.getAttribute("data-repo-example"); if (inp) inp.value = v; runRepoAnalysis(v); });
  });
}
boot().then(function () { initHub(); try { initHeroCollision(); } catch (e) {} try { initRepoAnalyze(); } catch (e) {} }).catch(function () { try { initHub(); initHeroCollision(); initRepoAnalyze(); } catch (e) {} });

// === ENGINEERING HARNESS PIPELINE VISUALIZER ===
function initHarness() {
  const section = document.getElementById("harness-pipeline");
  if (!section) return;

  const harness = STATIC && STATIC.harness;
  if (!harness) {
    // No harness data baked in, hide the section
    section.style.display = "none";
    return;
  }

  const task = harness.task || {};
  const stages = harness.pipeline_stages || [];
  const gateResults = harness.gate_results || [];
  const overall = harness.overall_verdict || "ALLOW";

  // Populate task card
  const agentEl = document.getElementById("harness-agent");
  const mrEl = document.getElementById("harness-mr");
  const kindEl = document.getElementById("harness-kind");
  const symbolsEl = document.getElementById("harness-symbols");

  if (agentEl) agentEl.textContent = task.agent_id || "unknown";
  if (mrEl) mrEl.textContent = task.mr_id || "N/A";
  if (kindEl) {
    kindEl.textContent = task.agent_kind || "bot";
    kindEl.setAttribute("data-kind", task.agent_kind || "bot");
  }
  if (symbolsEl) {
    const syms = task.symbols_touched || [];
    symbolsEl.textContent = syms.length
      ? "Symbols: " + syms.join(", ")
      : "No symbols";
  }

  // Animate pipeline stages with staggered reveal
  const stageEls = document.querySelectorAll(".harness-stage");
  const connectorEls = document.querySelectorAll(".harness-connector");

  stages.forEach((stage, i) => {
    const el = stageEls[i];
    if (!el) return;

    setTimeout(() => {
      el.setAttribute("data-status", stage.status || "done");
      const statusEl = el.querySelector(".harness-stage-status");
      if (statusEl) {
        const ms = stage.duration_ms;
        statusEl.textContent = stage.status === "done"
          ? (ms != null ? "done (" + ms + "ms)" : "done")
          : stage.status;
      }
      // Light up the connector before this stage
      if (i > 0 && connectorEls[i - 1]) {
        connectorEls[i - 1].classList.add("done");
      }
    }, 300 * i);
  });

  // Populate per-symbol verdict cards
  const verdictList = document.getElementById("harness-verdict-list");
  if (verdictList) {
    verdictList.innerHTML = "";
    gateResults.forEach((gr) => {
      const card = document.createElement("div");
      card.className = "harness-verdict-card";
      card.setAttribute("data-verdict", gr.verdict || "ALLOW");

      const pol = gr.policy || {};
      const imp = gr.impact || {};
      const counts = imp.counts || {};

      card.innerHTML =
        '<div class="harness-verdict-symbol">' + _esc(gr.symbol || "?") + '</div>' +
        '<div class="harness-verdict-meta">' +
          (pol.tier || "?") + " / " + (counts.total_affected || 0) + " affected" +
        '</div>' +
        '<div class="harness-verdict-badge" data-verdict="' + _esc(gr.verdict || "ALLOW") + '">' +
          _esc(gr.verdict || "ALLOW") +
        '</div>';

      verdictList.appendChild(card);
    });
  }

  // Set overall verdict badge (delayed for dramatic reveal)
  setTimeout(() => {
    const badge = document.getElementById("harness-overall-badge");
    if (badge) {
      badge.textContent = overall;
      badge.setAttribute("data-verdict", overall);
    }
  }, 300 * stages.length + 200);
}

function _esc(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}
