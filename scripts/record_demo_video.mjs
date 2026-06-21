// Automated Keystone demo recorder.
//
// Drives the live (or local) site through the storyboard in headless Chrome over
// CDP, burns a controlled caption overlay into the page so the result is
// self-narrated (no voice needed), captures JPEG frames at a steady rate, and
// assembles them into an H.264 MP4 with ffmpeg.
//
//   node scripts/record_demo_video.mjs                # records the live site
//   KS_URL=http://127.0.0.1:8899/index.html node scripts/record_demo_video.mjs
//
// Requirements: a Chrome/Chromium binary and ffmpeg on PATH. Output:
//   SUBMISSION/keystone-demo.mp4
//
// Read-only against the product (no writes to the app); produces a video asset.
import { spawn, spawnSync } from 'child_process';
import os from 'os';
import path from 'path';
import fs from 'fs';

const CHROME = process.env.KS_CHROME || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const URL = process.env.KS_URL || 'https://vaibhav4046.github.io/keystone/';
const FPS = 10;
const W = 1280, H = 800;
const PORT = 9251;
const OUT = path.resolve('SUBMISSION/keystone-demo.mp4');
const framesDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ksrec-'));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// Storyboard: [atSeconds, caption, actionExpression-or-null]. Actions run in-page.
const clickByText = (re) => `(function(){var b=[].slice.call(document.querySelectorAll('button,a')).find(function(e){return e.offsetParent!==null && ${re}.test((e.textContent||'').trim());});if(b){b.click();return true}return false})()`;
const clickTitle = (t) => `(function(){var b=[].slice.call(document.querySelectorAll('[title]')).find(function(e){return (e.getAttribute('title')||'')===${JSON.stringify(t)};});if(b){b.click();return true}return false})()`;
const scrollTo = (re) => `(function(){var el=[].slice.call(document.querySelectorAll('h1,h2,h3')).find(function(e){return ${re}.test(e.textContent||'')});if(el){el.scrollIntoView({block:'center'});return true}return false})()`;

const STORY = [
  [0.0, 'Two merge requests pass review. They still break production together.', null],
  [6.5, 'Git sees files. Keystone sees the call graph.', null],
  [11.5, 'A silent collision: five functions depend on both changed symbols.', clickByText('/try the live demo/i')],
  [22.0, 'Blast-radius graph: exactly what breaks together.', clickTitle('Reviewer Cockpit')],
  [33.0, 'Every decision lands in a tamper-evident ledger.', clickTitle('Audit Ledger')],
  [41.0, 'Edit a past decision and the hash chain BREAKS.', clickByText('/simulate tamper/i')],
  [49.0, 'Restore the chain and it verifies again.', clickByText('/restore chain|verify chain/i')],
  [57.0, 'The same gate runs on AI-agent merge requests, with a deterministic fix plan.', clickTitle('Engineering Harness')],
  [64.0, 'The agent is overruled until the checks pass. Keystone proposes, a human decides.', scrollTo('/Agent fix plan/i')],
  [72.0, 'Same engine on a real external repo: pallets/click, 1,841 definitions.', `(function(){var b=[].slice.call(document.querySelectorAll('[title]')).find(function(e){return (e.getAttribute('title')||'')==='Dashboard'});if(b)b.click();if(window.__ksLoadOrbit)window.__ksLoadOrbit('orbit_snapshot_click.json');return true})()`],
  [82.0, 'Live backend verified. No model decides the verdict.', clickTitle('Home')],
  [90.0, 'Git sees files. Orbit sees relationships. Keystone sees consequences.', null],
  [97.0, null, null] // end marker
];
const DURATION = STORY[STORY.length - 1][0];

async function wsUrl() {
  for (let i = 0; i < 80; i++) {
    try { const r = await fetch(`http://127.0.0.1:${PORT}/json/list`); const l = await r.json(); const p = l.find((t) => t.type === 'page' && t.webSocketDebuggerUrl); if (p) return p.webSocketDebuggerUrl; } catch (e) {}
    await sleep(200);
  }
  throw new Error('no devtools');
}
function connect(u) {
  return new Promise((res, rej) => {
    const ws = new WebSocket(u); let id = 0; const pend = new Map();
    const send = (m, p = {}) => new Promise((r) => { const i = ++id; pend.set(i, r); ws.send(JSON.stringify({ id: i, method: m, params: p })); });
    ws.onopen = () => res({ send }); ws.onerror = rej;
    ws.onmessage = (ev) => { const m = JSON.parse(ev.data); if (m.id && pend.has(m.id)) { pend.get(m.id)(m.result); pend.delete(m.id); } };
  });
}

const CAP_JS = (text) => `(function(){var t=${JSON.stringify(text)};var el=document.getElementById('ksRecCap');if(!el){el=document.createElement('div');el.id='ksRecCap';el.style.cssText='position:fixed;left:50%;bottom:34px;transform:translateX(-50%);z-index:99999;max-width:78vw;padding:16px 26px;border-radius:14px;background:rgba(10,7,5,0.93);border:1px solid rgba(255,122,26,0.5);box-shadow:0 22px 60px -18px rgba(0,0,0,0.9);font:600 22px/1.4 Inter,system-ui,sans-serif;color:#F6EFE6;text-align:center;letter-spacing:0.005em;backdrop-filter:blur(6px)';document.body.appendChild(el);}el.style.display=t?'block':'none';if(t)el.textContent=t;return true})()`;

(async () => {
  const udd = fs.mkdtempSync(path.join(os.tmpdir(), 'ksrecu-'));
  const chrome = spawn(CHROME, ['--headless=new', '--disable-gpu', '--hide-scrollbars', '--no-first-run', '--no-default-browser-check', '--force-device-scale-factor=1', '--remote-debugging-port=' + PORT, '--user-data-dir=' + udd, '--window-size=' + W + ',' + H, 'about:blank'], { stdio: 'ignore' });
  try {
    const { send } = await connect(await wsUrl());
    await send('Page.enable'); await send('Runtime.enable');
    await send('Emulation.setDeviceMetricsOverride', { width: W, height: H, deviceScaleFactor: 1, mobile: false });
    const ev = (e) => send('Runtime.evaluate', { expression: e, returnByValue: true }).then((r) => r.result && r.result.value);
    console.log('navigating', URL);
    await send('Page.navigate', { url: URL }); await sleep(6500);

    let frame = 0, beat = 0;
    const t0 = Date.now();
    const frameMs = 1000 / FPS;
    while (true) {
      const elapsed = (Date.now() - t0) / 1000;
      if (elapsed >= DURATION) break;
      // Fire any due beats.
      while (beat < STORY.length && elapsed >= STORY[beat][0]) {
        const [, cap, action] = STORY[beat];
        try { if (action) await ev(action); } catch (e) {}
        try { await ev(CAP_JS(cap || '')); } catch (e) {}
        beat++;
      }
      const shot = await send('Page.captureScreenshot', { format: 'jpeg', quality: 72 });
      if (shot && shot.data) fs.writeFileSync(path.join(framesDir, 'f' + String(frame).padStart(5, '0') + '.jpg'), Buffer.from(shot.data, 'base64'));
      frame++;
      const drift = (Date.now() - t0) - frame * frameMs;
      if (drift < frameMs) await sleep(Math.max(0, frameMs - Math.max(0, drift)));
    }
    console.log('captured', frame, 'frames in', ((Date.now() - t0) / 1000).toFixed(1), 's');
    try { chrome.kill(); } catch (e) {}

    // Assemble with ffmpeg.
    fs.mkdirSync(path.dirname(OUT), { recursive: true });
    const args = ['-y', '-framerate', String(FPS), '-i', path.join(framesDir, 'f%05d.jpg'),
      '-vf', 'scale=trunc(iw/2)*2:trunc(ih/2)*2', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-preset', 'medium', '-crf', '23', '-movflags', '+faststart', OUT];
    console.log('ffmpeg assembling ->', OUT);
    const ff = spawnSync('ffmpeg', args, { stdio: 'inherit' });
    if (ff.status !== 0) throw new Error('ffmpeg failed status ' + ff.status);
    const sz = fs.statSync(OUT).size;
    console.log('DONE', OUT, (sz / 1048576).toFixed(2), 'MB');
  } finally {
    try { chrome.kill(); } catch (e) {}
    try { fs.rmSync(framesDir, { recursive: true, force: true }); } catch (e) {}
  }
})().catch((e) => { console.error('RECORD FAILED', e); process.exit(1); });
