"use strict";
// ============================================================================
// Keystone v2 motion layer (presentation only; never touches engine numbers).
// Improvements: softer particle colors, gradient washes, smoother rotation,
// improved label rendering, and subtle micro-animations.
// ============================================================================
(function () {
  const reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  let STILL = false;
  window.__ksFreeze = function () { STILL = true; };
  const RING_COLOR = { 0: "#FF5C66", 1: "#FF8A2B", 2: "#F5C542", 3: "#5BBFD6" };
  const ringColor = (r) => RING_COLOR[r] || "#7A8494";
  const DPR = Math.min(2, window.devicePixelRatio || 1);
  const PX = Math.max(2, Math.round(2 * DPR));

  // ---------- ambient particle field (softer, lower density) ----------
  function initBackground() {
    const c = document.getElementById("bg");
    if (!c || reduce) return;
    const ctx = c.getContext("2d");
    let W, H, pts;
    function resize() {
      W = c.width = Math.max(1, Math.floor((innerWidth || 1200) * DPR));
      H = c.height = Math.max(1, Math.floor((innerHeight || 800) * DPR));
      c.style.width = (innerWidth || 1200) + "px"; c.style.height = (innerHeight || 800) + "px";
      // Lower density: fewer particles for a calmer feel
      const n = Math.min(50, Math.floor((innerWidth || 1200) * (innerHeight || 800) / 45000));
      pts = Array.from({ length: n }, () => ({
        x: Math.random() * W, y: Math.random() * H,
        vx: (Math.random() - 0.5) * 0.08 * DPR, vy: (Math.random() - 0.5) * 0.08 * DPR,
      }));
    }
    resize(); addEventListener("resize", resize);
    function frame() {
      ctx.clearRect(0, 0, W, H);

      // Subtle gradient wash at the bottom for depth
      const grad = ctx.createLinearGradient(0, H * 0.7, 0, H);
      grad.addColorStop(0, "rgba(255,138,43,0)");
      grad.addColorStop(1, "rgba(255,138,43,0.015)");
      ctx.fillStyle = grad;
      ctx.fillRect(0, H * 0.7, W, H * 0.3);

      for (const p of pts) {
        p.x += p.vx; p.y += p.vy;
        if (p.x < 0 || p.x > W) p.vx *= -1;
        if (p.y < 0 || p.y > H) p.vy *= -1;
      }
      // Softer connection lines
      for (let i = 0; i < pts.length; i++) for (let j = i + 1; j < pts.length; j++) {
        const a = pts[i], b = pts[j], d = Math.hypot(a.x - b.x, a.y - b.y);
        if (d < 150 * DPR) {
          const alpha = 0.035 * (1 - d / (150 * DPR));
          ctx.strokeStyle = "rgba(155,163,174," + alpha.toFixed(4) + ")";
          ctx.lineWidth = 0.5 * DPR;
          ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
        }
      }
      // Softer dot colors — muted blue-grey
      for (const p of pts) { ctx.fillStyle = "rgba(155,163,174,0.15)"; ctx.fillRect(p.x, p.y, DPR, DPR); }
      if (!STILL) requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  }

  // ---------- pixelated 3D blast-radius graph ----------
  const G = { canvas: null, ctx: null, raf: 0, t0: 0, yaw: 0, target: null };

  function layout(imp) {
    const rings = imp.rings || {}, parents = imp.parents || {};
    const nm = {};
    Object.keys(imp.names || {}).forEach((k) => { nm[Number(k)] = imp.names[k]; });
    const nodes = [], byId = {};
    Object.keys(rings).map(Number).sort((a, b) => a - b).forEach((r) => {
      const ids = rings[r], R = r * 1.15;
      ids.forEach((id, i) => {
        let x = 0, y = 0, z = 0;
        if (r > 0) {
          const ga = 2.399963, phi = Math.acos(1 - 2 * (i + 0.5) / Math.max(1, ids.length));
          const th = ga * i + r * 0.6;
          x = R * Math.sin(phi) * Math.cos(th); y = R * Math.cos(phi) * 0.62; z = R * Math.sin(phi) * Math.sin(th);
        }
        const node = { id, r, x, y, z, name: nm[id] || ("#" + id), grow: 0 };
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
    return { nodes, edges, epi: imp.epicenter.id, name: imp.epicenter.name, total: imp.counts.total_affected };
  }

  function project(n, cx, cy, scale, yaw, pitch) {
    const cy_ = Math.cos(yaw), sy = Math.sin(yaw);
    let x = n.x * cy_ - n.z * sy, z = n.x * sy + n.z * cy_, y = n.y;
    const cp = Math.cos(pitch), sp = Math.sin(pitch);
    const y2 = y * cp - z * sp, z2 = y * sp + z * cp;
    const f = 4.4, depth = f / (f + z2);
    return { sx: cx + x * scale * depth, sy: cy + y2 * scale * depth, depth, z: z2 };
  }

  // crisp glowing pixel block with softer glow
  function block(ctx, x, y, size, color, alpha) {
    const s = Math.max(PX, Math.round(size / PX) * PX);
    const px = Math.round(x / PX) * PX, py = Math.round(y / PX) * PX;
    ctx.globalAlpha = Math.min(1, alpha) * 0.4;
    ctx.shadowColor = color; ctx.shadowBlur = s * 1.8;
    ctx.fillStyle = color; ctx.fillRect(px - s, py - s, s * 2, s * 2);
    ctx.shadowBlur = 0; ctx.globalAlpha = Math.min(1, alpha);
    ctx.fillRect(px - s / 2, py - s / 2, s, s);
    ctx.globalAlpha = 1;
  }

  function _renderFrame(ts) {
    const { ctx, canvas, target } = G;
    if (!ctx || !target) { G.raf = 0; return; }
    if (!G.t0) G.t0 = ts;
    const W = canvas.width, H = canvas.height, cx = W / 2, cy = H * 0.52;
    const scale = Math.min(W, H) / 4.6;
    ctx.clearRect(0, 0, W, H);

    // Smoother, slower rotation
    G.yaw += 0.0020;
    const pitch = -0.40;

    // perspective pixel-grid floor — softer
    ctx.strokeStyle = "rgba(155,163,174,0.03)"; ctx.lineWidth = DPR;
    for (let gx = -3; gx <= 3; gx++) {
      const a = project({ x: gx * 0.7, y: 1.5, z: -3 }, cx, cy, scale, G.yaw, pitch);
      const b = project({ x: gx * 0.7, y: 1.5, z: 3 }, cx, cy, scale, G.yaw, pitch);
      ctx.beginPath(); ctx.moveTo(a.sx, a.sy); ctx.lineTo(b.sx, b.sy); ctx.stroke();
    }
    for (let gz = -3; gz <= 3; gz++) {
      const a = project({ x: -2.1, y: 1.5, z: gz * 0.7 }, cx, cy, scale, G.yaw, pitch);
      const b = project({ x: 2.1, y: 1.5, z: gz * 0.7 }, cx, cy, scale, G.yaw, pitch);
      ctx.beginPath(); ctx.moveTo(a.sx, a.sy); ctx.lineTo(b.sx, b.sy); ctx.stroke();
    }

    for (const n of target.nodes) n.grow = Math.min(1, n.grow + 0.035);
    const P = new Map();
    for (const n of target.nodes) P.set(n, project(n, cx, cy, scale, G.yaw, pitch));

    // edges: marching dashes + travelling data packet
    ctx.lineWidth = DPR;
    for (const [a, b] of target.edges) {
      const pa = P.get(a), pb = P.get(b), g = Math.min(a.grow, b.grow);
      if (g <= 0) continue;
      ctx.setLineDash([2 * DPR, 4 * DPR]); ctx.lineDashOffset = -(ts / 30) % 1000;
      ctx.strokeStyle = "rgba(120,130,150," + (0.4 * g).toFixed(3) + ")";
      ctx.beginPath(); ctx.moveTo(pa.sx, pa.sy); ctx.lineTo(pb.sx, pb.sy); ctx.stroke();
      ctx.setLineDash([]);
      const tt = ((ts / 1500) + (a.id % 5) / 5) % 1;
      block(ctx, pa.sx + (pb.sx - pa.sx) * tt, pa.sy + (pb.sy - pa.sy) * tt, PX, ringColor(b.r), 0.8 * g);
    }

    // nodes as depth-sorted glowing pixel blocks
    const order = target.nodes.slice().sort((a, b) => P.get(a).z - P.get(b).z);
    for (const n of order) {
      const p = P.get(n), isEpi = n.id === target.epi;
      const size = (isEpi ? 7 : 3.4) * DPR * (0.55 + 0.45 * p.depth);
      const a = (isEpi ? 1 : (0.45 + 0.55 * p.depth)) * n.grow;
      const sz = isEpi ? size * (1 + 0.10 * Math.sin(ts / 400)) : size;
      block(ctx, p.sx, p.sy, sz, ringColor(n.r), a);
    }

    // labels: epicenter + ring-1, clearer rendering with background
    ctx.textAlign = "center";
    const epi = target.nodes.find((n) => n.id === target.epi);
    if (epi) {
      const pe = P.get(epi);
      ctx.font = "700 " + (12 * DPR) + "px 'Inter', monospace";
      // Label background for readability
      const labelText = epi.name;
      const metrics = ctx.measureText(labelText);
      const lx = pe.sx - metrics.width / 2 - 4 * DPR;
      const ly = pe.sy - 24 * DPR;
      ctx.fillStyle = "rgba(9,9,11,0.7)";
      ctx.fillRect(lx, ly, metrics.width + 8 * DPR, 16 * DPR);
      ctx.fillStyle = "#F0F0F5"; ctx.fillText(labelText, pe.sx, pe.sy - 12 * DPR);
    }
    for (const n of (target.nodes.filter((x) => x.r === 1))) {
      if ((target.nodes.filter((x) => x.r === 1)).length > 8) break;
      const p = P.get(n); ctx.fillStyle = "rgba(155,163,174," + (0.65 * n.grow).toFixed(2) + ")";
      ctx.font = (9.5 * DPR) + "px monospace";
      ctx.fillText(n.name.length > 14 ? n.name.slice(0, 13) + "…" : n.name, p.sx, p.sy + 16 * DPR);
    }

    // terminal HUD line (types in)
    const elapsed = (ts - G.t0);
    const hud = "> blast_radius(" + target.name + ")  ::  " + target.total + " affected";
    const shown = Math.min(hud.length, Math.floor(elapsed / 25));
    ctx.textAlign = "left"; ctx.font = (11 * DPR) + "px monospace";
    ctx.fillStyle = "rgba(59,224,129,0.85)";
    ctx.fillText(hud.slice(0, shown), 14 * DPR, 22 * DPR);
    if (Math.floor(ts / 520) % 2 === 0) {
      const w = ctx.measureText(hud.slice(0, shown)).width;
      ctx.fillRect(14 * DPR + w + 2 * DPR, 13 * DPR, 7 * DPR, 12 * DPR);
    }

    // subtle CRT scanlines (reduced opacity)
    ctx.globalAlpha = 0.04; ctx.fillStyle = "#000";
    for (let y = 0; y < H; y += 3 * DPR) ctx.fillRect(0, y, W, DPR);
    ctx.globalAlpha = 1;

    G.raf = STILL ? 0 : requestAnimationFrame(renderFrame);
  }
  function renderFrame(ts) {
    try { _renderFrame(ts); }
    catch (e) { G.raf = 0; const w = document.querySelector(".canvas-wrap"); if (w) w.classList.remove("has-3d"); }
  }

  function setup3D() {
    const wrap = document.querySelector(".canvas-wrap"), c = document.getElementById("g3d");
    if (!wrap || !c || reduce) return false;
    const ctx = c.getContext("2d"); if (!ctx) return false;
    G.canvas = c; G.ctx = ctx;
    function resize() {
      const r = wrap.getBoundingClientRect();
      c.width = Math.max(1, Math.floor(r.width * DPR)); c.height = Math.max(1, Math.floor(r.height * DPR));
      c.style.width = r.width + "px"; c.style.height = r.height + "px";
    }
    resize(); addEventListener("resize", resize);
    if ("ResizeObserver" in window) { try { new ResizeObserver(resize).observe(wrap); } catch (e) {} }
    return true;
  }

  window.__ksRenderGraph = function (imp) {
    try {
      if (reduce || !G.ctx || !imp || !imp.epicenter) return;
      document.querySelector(".canvas-wrap").classList.add("has-3d");
      const svg = document.getElementById("bsvg");
      if (svg) svg.setAttribute("aria-hidden", "true");
      G.target = layout(imp); G.t0 = 0;
      if (!G.raf) G.raf = requestAnimationFrame(renderFrame);
    } catch (e) {
      const w = document.querySelector(".canvas-wrap"); if (w) w.classList.remove("has-3d");
    }
  };

  // ---------- entrance + scroll reveals ----------
  function initReveals() {
    if (reduce) return;
    const els = document.querySelectorAll("[data-reveal]");
    els.forEach((el, i) => { el.style.setProperty("--rev-delay", (i * 55) + "ms"); el.classList.add("ks-hidden"); });
    const reveal = (e) => e.classList.remove("ks-hidden");
    if (!("IntersectionObserver" in window)) { els.forEach(reveal); return; }
    const io = new IntersectionObserver((ents) => {
      ents.forEach((e) => { if (e.isIntersecting) { reveal(e.target); io.unobserve(e.target); } });
    }, { threshold: 0.1 });
    els.forEach((e) => io.observe(e));
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
