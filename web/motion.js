"use strict";
// Keystone premium motion layer (presentation only; never touches engine numbers).
// 1) ambient neon particle field behind everything
// 2) a rotating 3D blast-radius graph rendered in pure Canvas via perspective
//    projection (no WebGL, no CDN, works offline) — the centerpiece motion
// 3) entrance + scroll reveals
// All disabled under prefers-reduced-motion, where the handwritten SVG in app.js
// remains the static fallback. Numbers, rings, and the counter are owned by app.js.
(function () {
  const reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const RING_COLOR = { 0: "#FF5C66", 1: "#FF8A2B", 2: "#F5C542", 3: "#5BBFD6" };
  const ringColor = (r) => RING_COLOR[r] || "#7A8494";
  const DPR = Math.min(2, window.devicePixelRatio || 1);

  // ---------- ambient particle field ----------
  function initBackground() {
    const c = document.getElementById("bg");
    if (!c || reduce) return;
    const ctx = c.getContext("2d");
    let W, H, pts;
    function resize() {
      W = c.width = Math.floor(innerWidth * DPR); H = c.height = Math.floor(innerHeight * DPR);
      c.style.width = innerWidth + "px"; c.style.height = innerHeight + "px";
      const n = Math.min(90, Math.floor(innerWidth * innerHeight / 26000));
      pts = Array.from({ length: n }, () => ({
        x: Math.random() * W, y: Math.random() * H,
        vx: (Math.random() - 0.5) * 0.12 * DPR, vy: (Math.random() - 0.5) * 0.12 * DPR,
      }));
    }
    resize(); addEventListener("resize", resize);
    function frame() {
      ctx.clearRect(0, 0, W, H);
      for (const p of pts) {
        p.x += p.vx; p.y += p.vy;
        if (p.x < 0 || p.x > W) p.vx *= -1;
        if (p.y < 0 || p.y > H) p.vy *= -1;
      }
      // faint connecting lines (the "graph field")
      for (let i = 0; i < pts.length; i++) {
        for (let j = i + 1; j < pts.length; j++) {
          const a = pts[i], b = pts[j], dx = a.x - b.x, dy = a.y - b.y, d = Math.hypot(dx, dy);
          if (d < 120 * DPR) {
            ctx.strokeStyle = "rgba(255,138,43," + (0.05 * (1 - d / (120 * DPR))).toFixed(3) + ")";
            ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
          }
        }
      }
      for (const p of pts) {
        ctx.fillStyle = "rgba(155,163,174,0.25)";
        ctx.beginPath(); ctx.arc(p.x, p.y, 1.1 * DPR, 0, 7); ctx.fill();
      }
      requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  }

  // ---------- 3D blast-radius graph ----------
  const G = { canvas: null, ctx: null, nodes: [], edges: [], yaw: 0, raf: 0, t0: 0, target: null };

  function layout(imp) {
    // place nodes on spherical shells by ring; epicenter at origin
    const rings = imp.rings || {}; const parents = imp.parents || {};
    const nodes = []; const byId = {};
    const shellR = 1.0;
    Object.keys(rings).map(Number).sort((a, b) => a - b).forEach((r) => {
      const ids = rings[r]; const R = r * shellR;
      ids.forEach((id, i) => {
        let x = 0, y = 0, z = 0;
        if (r > 0) {
          // golden-angle distribution on the shell, tilted per ring for depth
          const ga = 2.399963; const phi = Math.acos(1 - 2 * (i + 0.5) / Math.max(1, ids.length));
          const th = ga * i + r * 0.7;
          x = R * Math.sin(phi) * Math.cos(th);
          y = R * Math.cos(phi) * 0.7;
          z = R * Math.sin(phi) * Math.sin(th);
        }
        const node = { id, r, x, y, z, name: (imp.names && imp.names[String(id)]) || ("#" + id), grow: 0 };
        nodes.push(node); byId[id] = node;
      });
    });
    const edges = [];
    Object.keys(rings).map(Number).forEach((r) => {
      if (r === 0) return;
      (rings[r] || []).forEach((id) => {
        let p = parents[String(id)];
        if (p === undefined || p === null) p = (r === 1 ? imp.epicenter.id : rings[r - 1][0]);
        if (byId[p] && byId[id]) edges.push([byId[p], byId[id]]);
      });
    });
    return { nodes, edges, epi: imp.epicenter.id };
  }

  function project(n, cx, cy, scale, yaw, pitch) {
    // rotate around Y then X, then perspective project
    const cosY = Math.cos(yaw), sinY = Math.sin(yaw);
    let x = n.x * cosY - n.z * sinY, z = n.x * sinY + n.z * cosY, y = n.y;
    const cosP = Math.cos(pitch), sinP = Math.sin(pitch);
    const y2 = y * cosP - z * sinP, z2 = y * sinP + z * cosP;
    const f = 4.2, depth = f / (f + z2);
    return { sx: cx + x * scale * depth, sy: cy + y2 * scale * depth, depth, z: z2 };
  }

  function renderFrame(ts) {
    try { _renderFrame(ts); }
    catch (e) {
      G.raf = 0; const wrap = document.querySelector(".canvas-wrap");
      if (wrap) wrap.classList.remove("has-3d");      // fall back to the SVG on any draw error
    }
  }
  function _renderFrame(ts) {
    const { ctx, canvas, target } = G;
    if (!ctx || !target) { G.raf = 0; return; }
    if (!G.t0) G.t0 = ts;
    const W = canvas.width, H = canvas.height, cx = W / 2, cy = H / 2;
    const scale = Math.min(W, H) / 5.2;
    ctx.clearRect(0, 0, W, H);
    G.yaw += 0.0032;                       // slow auto-rotate
    const pitch = -0.34;
    const epi = target.nodes.find((n) => n.id === target.epi);
    // grow-in animation
    for (const n of target.nodes) n.grow = Math.min(1, n.grow + 0.05);
    // project all
    const P = new Map();
    for (const n of target.nodes) P.set(n, project(n, cx, cy, scale, G.yaw, pitch));
    // edges with a flowing pulse
    for (const [a, b] of target.edges) {
      const pa = P.get(a), pb = P.get(b); const g = Math.min(a.grow, b.grow);
      if (g <= 0) continue;
      ctx.strokeStyle = "rgba(120,130,150," + (0.35 * g).toFixed(3) + ")";
      ctx.lineWidth = 1 * DPR; ctx.beginPath(); ctx.moveTo(pa.sx, pa.sy); ctx.lineTo(pb.sx, pb.sy); ctx.stroke();
      // moving pulse dot
      const tt = ((ts / 1400) + (a.id % 7) / 7) % 1;
      const px = pa.sx + (pb.sx - pa.sx) * tt, py = pa.sy + (pb.sy - pa.sy) * tt;
      ctx.fillStyle = "rgba(255,138,43," + (0.5 * g).toFixed(3) + ")";
      ctx.beginPath(); ctx.arc(px, py, 1.6 * DPR, 0, 7); ctx.fill();
    }
    // nodes, depth-sorted
    const order = target.nodes.slice().sort((a, b) => P.get(a).z - P.get(b).z);
    for (const n of order) {
      const p = P.get(n); const isEpi = n.id === target.epi;
      const base = (isEpi ? 9 : 5.2) * DPR * (0.6 + 0.4 * p.depth) * (0.4 + 0.6 * n.grow);
      const col = ringColor(n.r);
      const glow = ctx.createRadialGradient(p.sx, p.sy, 0, p.sx, p.sy, base * 3.4);
      glow.addColorStop(0, col); glow.addColorStop(0.4, col + "55"); glow.addColorStop(1, "rgba(0,0,0,0)");
      ctx.globalAlpha = 0.85 * n.grow; ctx.fillStyle = glow;
      ctx.beginPath(); ctx.arc(p.sx, p.sy, base * 3.4, 0, 7); ctx.fill();
      ctx.globalAlpha = n.grow; ctx.fillStyle = col;
      const pr = isEpi ? base * (1 + 0.12 * Math.sin(ts / 320)) : base;   // epicenter pulse
      ctx.beginPath(); ctx.arc(p.sx, p.sy, pr, 0, 7); ctx.fill();
      ctx.globalAlpha = 1;
    }
    // a couple of nearest labels only (epicenter + closest ring-1), to stay clean
    if (epi) {
      const pe = P.get(epi);
      ctx.fillStyle = "#EDEDED"; ctx.font = (12 * DPR) + "px JetBrains Mono, monospace";
      ctx.textAlign = "center"; ctx.fillText(epi.name, pe.sx, pe.sy + 22 * DPR);
    }
    G.raf = requestAnimationFrame(renderFrame);
  }

  function setup3D() {
    const wrap = document.querySelector(".canvas-wrap");
    const c = document.getElementById("g3d");
    if (!wrap || !c || reduce) return false;
    const ctx = c.getContext("2d"); if (!ctx) return false;
    G.canvas = c; G.ctx = ctx;
    function resize() {
      const r = wrap.getBoundingClientRect();
      c.width = Math.max(1, Math.floor(r.width * DPR)); c.height = Math.max(1, Math.floor(r.height * DPR));
      c.style.width = r.width + "px"; c.style.height = r.height + "px";
    }
    resize(); addEventListener("resize", resize);
    // resize when the container itself changes (responsive grid collapse, initial
    // narrow render) — window 'resize' alone misses these
    if ("ResizeObserver" in window) { try { new ResizeObserver(resize).observe(wrap); } catch (e) {} }
    return true;
  }

  // hook called by app.js drawBlast: render the 3D graph + hide the SVG
  window.__ksRenderGraph = function (imp) {
    try {
      if (reduce || !G.ctx || !imp || !imp.epicenter) return;
      document.querySelector(".canvas-wrap").classList.add("has-3d");
      G.target = layout(imp); G.t0 = 0;
      if (!G.raf) G.raf = requestAnimationFrame(renderFrame);
    } catch (e) {                                     // never let the motion layer break the app
      const wrap = document.querySelector(".canvas-wrap");
      if (wrap) wrap.classList.remove("has-3d");      // fall back to the SVG
    }
  };

  // ---------- entrance + scroll reveals ----------
  function initReveals() {
    if (reduce) return;
    const els = document.querySelectorAll("[data-reveal]");
    // JS adds the hidden state, so if this layer never runs nothing stays invisible
    els.forEach((el, i) => { el.style.setProperty("--rev-delay", (i * 55) + "ms"); el.classList.add("ks-hidden"); });
    const reveal = (e) => e.classList.remove("ks-hidden");
    if (!("IntersectionObserver" in window)) { els.forEach(reveal); return; }
    const io = new IntersectionObserver((ents) => {
      ents.forEach((e) => { if (e.isIntersecting) { reveal(e.target); io.unobserve(e.target); } });
    }, { threshold: 0.1 });
    els.forEach((e) => io.observe(e));
    // safety net: never leave content hidden if the observer never fires (0-size
    // viewport, headless, or an element that never scrolls into view)
    setTimeout(() => els.forEach(reveal), 1600);
  }

  function start() {
    try { initBackground(); } catch (e) {}
    try { if (setup3D() && window.STATE && window.STATE.impact) window.__ksRenderGraph(window.STATE.impact); } catch (e) {}
    try { initReveals(); } catch (e) {}
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();
