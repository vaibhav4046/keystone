// Offline screenshot harness (no deps; node 24 global WebSocket/fetch). Temp/local, not committed.
// Captures each hub view in dark + light + mobile via system Chrome over CDP. Skips onboarding.
const { spawn } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const CHROME = "C:/Program Files/Google/Chrome/Application/chrome.exe";
const URL = "http://127.0.0.1:8801/";
const OUT = "D:/project/keystone/_shots";
const PORT = 9222;
fs.mkdirSync(OUT, { recursive: true });
const udd = fs.mkdtempSync(path.join(os.tmpdir(), 'kscdp-'));

const chrome = spawn(CHROME, [
  '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
  '--remote-debugging-port=' + PORT, '--user-data-dir=' + udd,
  '--window-size=1440,900', '--hide-scrollbars', URL
], { stdio: 'ignore' });

const sleep = ms => new Promise(r => setTimeout(r, ms));

async function getWsUrl() {
  for (let i = 0; i < 60; i++) {
    try {
      const r = await fetch(`http://127.0.0.1:${PORT}/json/list`);
      const list = await r.json();
      const page = list.find(t => t.type === 'page' && t.webSocketDebuggerUrl);
      if (page) return page.webSocketDebuggerUrl;
    } catch (e) {}
    await sleep(200);
  }
  throw new Error('no devtools endpoint');
}

function connect(wsUrl) {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(wsUrl);
    let id = 0; const pending = new Map(); const errors = [];
    const send = (method, params = {}) => new Promise(res => { const i = ++id; pending.set(i, res); ws.send(JSON.stringify({ id: i, method, params })); });
    ws.onopen = () => resolve({ send, errors });
    ws.onerror = e => reject(e);
    ws.onmessage = ev => {
      const m = JSON.parse(ev.data);
      if (m.id && pending.has(m.id)) { pending.get(m.id)(m.result); pending.delete(m.id); }
      if (m.method === 'Runtime.exceptionThrown') { const d = m.params.exceptionDetails; errors.push('EXCEPTION: ' + ((d.exception && d.exception.description) || d.text)); }
      if (m.method === 'Runtime.consoleAPICalled' && m.params.type === 'error') { errors.push('CONSOLE.ERROR: ' + m.params.args.map(a => a.value || a.description || '').join(' ')); }
    };
  });
}

(async () => {
  const wsUrl = await getWsUrl();
  const { send, errors } = await connect(wsUrl);
  await send('Page.enable');
  await send('Runtime.enable');
  const ev = expr => send('Runtime.evaluate', { expression: expr });
  async function reloadWith(theme) {
    await ev("try{localStorage.setItem('keystone-onboarded','true');localStorage.setItem('ks-view','home');localStorage.setItem('ks-theme','" + theme + "');}catch(e){}");
    await send('Page.reload'); await sleep(3200);
  }
  async function shot(name) { const { data } = await send('Page.captureScreenshot', { format: 'png' }); fs.writeFileSync(path.join(OUT, name + '.png'), Buffer.from(data, 'base64')); }
  async function view(v, ms) { await ev("try{showView('" + v + "');window.scrollTo(0,0);}catch(e){}"); await sleep(ms || 900); }

  // DARK
  await reloadWith('dark');
  await view('home', 600); await shot('home-dark');
  { const { data } = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true, clip: { x: 0, y: 0, width: 1440, height: 3600, scale: 0.42 } }); fs.writeFileSync(path.join(OUT, 'home-full.png'), Buffer.from(data, 'base64')); }
  { const r = await send('Runtime.evaluate', { expression: "JSON.stringify({ws:getComputedStyle(document.querySelector('.workspace')).display, kf:getComputedStyle(document.querySelector('.kilo-features')).display, ledger:getComputedStyle(document.querySelector('.ledger')).display})", returnByValue: true }); console.log('HOME_VIS=' + (r.result && r.result.value)); }
  await view('demo', 900); await shot('demo-dark');
  await view('harness', 900); await shot('harness-dark');
  await view('cockpit', 1300); await shot('cockpit-dark');
  await view('ledger', 900); await shot('ledger-dark');
  // LIGHT
  await reloadWith('light');
  await view('home', 700); await shot('home-light');
  await view('cockpit', 1300); await shot('cockpit-light');
  // MOBILE (dark)
  await reloadWith('dark');
  await send('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 2, mobile: true });
  await view('home', 800); await shot('home-mobile');
  await view('cockpit', 1200); await shot('cockpit-mobile');

  console.log('CONSOLE_ERRORS=' + JSON.stringify(errors));
  try { chrome.kill(); } catch (e) {}
  process.exit(0);
})().catch(e => { console.error('HARNESS_FAIL', e); try { chrome.kill(); } catch (_) {} process.exit(1); });
