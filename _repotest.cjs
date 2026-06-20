// Standalone test: run the client-side repo analyzer on a REAL public repo in headless Chrome.
// Verifies the whole flow (fetch -> parse -> blast radius -> UI swap) works end to end.
const { spawn } = require('child_process');
const fs = require('fs'); const os = require('os'); const path = require('path');
const CHROME = "C:/Program Files/Google/Chrome/Application/chrome.exe";
const URL = "http://127.0.0.1:8801/"; const PORT = 9223;
const OUT = "D:/project/keystone/_shots";
const REPO = process.argv[2] || "pallets/click";
fs.mkdirSync(OUT, { recursive: true });
const udd = fs.mkdtempSync(path.join(os.tmpdir(), 'ksrepo-'));
const chrome = spawn(CHROME, ['--headless=new', '--disable-gpu', '--no-first-run', '--remote-debugging-port=' + PORT, '--user-data-dir=' + udd, '--window-size=1440,1000', URL], { stdio: 'ignore' });
const sleep = ms => new Promise(r => setTimeout(r, ms));
async function wsUrl() { for (let i = 0; i < 60; i++) { try { const r = await fetch(`http://127.0.0.1:${PORT}/json/list`); const l = await r.json(); const p = l.find(t => t.type === 'page' && t.webSocketDebuggerUrl); if (p) return p.webSocketDebuggerUrl; } catch (e) {} await sleep(200); } throw new Error('no devtools'); }
function connect(u) { return new Promise((res, rej) => { const ws = new WebSocket(u); let id = 0; const pend = new Map(); const errs = []; const send = (m, p = {}) => new Promise(r => { const i = ++id; pend.set(i, r); ws.send(JSON.stringify({ id: i, method: m, params: p })); }); ws.onopen = () => res({ send, errs }); ws.onerror = rej; ws.onmessage = e => { const m = JSON.parse(e.data); if (m.id && pend.has(m.id)) { pend.get(m.id)(m.result); pend.delete(m.id); } if (m.method === 'Runtime.exceptionThrown') errs.push('EXC: ' + ((m.params.exceptionDetails.exception || {}).description || m.params.exceptionDetails.text)); if (m.method === 'Runtime.consoleAPICalled' && m.params.type === 'error') errs.push('ERR: ' + m.params.args.map(a => a.value || a.description || '').join(' ')); }; }); }
(async () => {
  const { send, errs } = await connect(await wsUrl());
  await send('Page.enable'); await send('Runtime.enable');
  await send('Runtime.evaluate', { expression: "try{localStorage.setItem('keystone-onboarded','true')}catch(e){}" });
  await send('Page.reload'); await sleep(3200);
  const ev = async (expr) => (await send('Runtime.evaluate', { expression: expr, returnByValue: true })).result.value;
  await ev("window.runRepoAnalysis && window.runRepoAnalysis('" + REPO + "')");
  let status = "", defc = "0";
  for (let i = 0; i < 40; i++) {
    await sleep(1000);
    status = await ev("(document.getElementById('repo-status')||{}).textContent||''");
    defc = await ev("(document.getElementById('def-count')||{}).textContent||'0'");
    if (/^Analyzed/.test(status) || /err|fail|not found|rate limit|No Python/i.test(status)) break;
  }
  const epi = await ev("(document.getElementById('epi')||{}).textContent||''");
  const counter = await ev("(document.getElementById('counter')||{}).textContent||''");
  const firstSyms = await ev("Array.from(document.querySelectorAll('#deflist li')).slice(0,6).map(function(l){return l.textContent.trim()}).join(', ')");
  const { data } = await send('Page.captureScreenshot', { format: 'png' });
  fs.writeFileSync(path.join(OUT, 'repo-' + REPO.replace(/\W/g, '_') + '.png'), Buffer.from(data, 'base64'));
  console.log('REPO=' + REPO);
  console.log('STATUS=' + status);
  console.log('DEF_COUNT=' + defc);
  console.log('EPICENTER=' + epi + ' COUNTER=' + counter);
  console.log('FIRST_SYMBOLS=' + firstSyms);
  console.log('CONSOLE_ERRORS=' + JSON.stringify(errs.slice(0, 8)));
  try { chrome.kill(); } catch (e) {}
  process.exit(0);
})().catch(e => { console.error('FAIL', e); try { chrome.kill(); } catch (_) {} process.exit(1); });
