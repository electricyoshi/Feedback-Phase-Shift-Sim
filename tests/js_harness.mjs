// Runs the <script> of feedback_phase_sim.html outside a browser so the tests
// can call its functions.  Works under node or deno:
//     node tests/js_harness.mjs  <html> <calls.json>
//     deno run --allow-read tests/js_harness.mjs  <html> <calls.json>
// calls.json is a list of requests; one JSON list of answers goes to stdout.
//   {"fn": "loopMag", "args": [1000]}        call a function / read a constant
//   {"sim": {n, amp, freq, square, tau, rec}} run a fresh LoopSim with NOISE = 0
//   {"link": 0}                               view 1, link on, ask for this phase
//   {"dom": "b1"}                             what update() wrote to an element
import fs from 'node:fs';
import process from 'node:process';

const [htmlPath, callsPath] = process.argv.slice(2);
const html = fs.readFileSync(htmlPath, 'utf8');
const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]);
const main = scripts[scripts.length - 1];

// Just enough DOM for the page's top-level code to run.  Canvases report a
// size of 0, so every draw function returns before touching a 2D context.
const els = {};
const el = id => els[id] || (els[id] = {
  id, style: {}, value: '', checked: false, textContent: '', innerHTML: '',
  clientWidth: 0, clientHeight: 0, tagName: 'DIV',
  classList: { toggle() {}, contains: () => false },
  addEventListener() {}, setPointerCapture() {},
  getBoundingClientRect: () => ({ left: 0, width: 1 }),
});
const document = { getElementById: el, querySelectorAll: () => [], documentElement: el('html') };
const window = { addEventListener() {}, innerWidth: 1024, innerHeight: 768, devicePixelRatio: 1 };
const names = ['A0', 'BETA', 'FP', 'VCC', 'L0', 'FC', 'POLE_PHASE_FC', 'TAU_VIEW1', 'F1_MIN', 'F1_MAX', 'F2_MIN', 'F2_MAX', 'view2Time',
  'BODE_X1', 'BODE_X2', 'BODE_PER_DECADE', 'SWEEP_S', 'DASH', 'C', 'NOTES', 'S', 'LoopSim',
  'loopMag', 'loopPhase', 'tauFor', 'freqForPhase', 'bodeFreqs', 'linkedPhase', 'view1Ratio',
  'timeUnit', 'fmtNum', 'fmtFreq', 'fmtHz', 'withUnit', 'niceTicks', 'view1Status', 'view2Status', 'phaseLabel',
  'setPhase', 'update'];
const api = new Function('document', 'window', 'performance', 'requestAnimationFrame', 'location',
  main + '\nreturn {' + names.join(',') + '};')(
  document, window, { now: () => 0 }, () => 0, { hash: '' });

const out = JSON.parse(fs.readFileSync(callsPath, 'utf8')).map(c => {
  if (c.fn) return typeof api[c.fn] === 'function' ? api[c.fn](...(c.args || [])) : api[c.fn];
  if (c.sim) {
    const p = c.sim, s = new api.LoopSim();
    api.LoopSim.NOISE = 0;
    s.run(p.n, p.amp, p.freq, p.square, p.tau, p.rec);
    return { T: s.T, VIN: s.VIN, VOUT: s.VOUT, VD: s.VD,
             DT: api.LoopSim.DT, MASK: api.LoopSim.MASK };
  }
  if ('link' in c) {
    api.S.mode = 1; api.S.link = true; api.setPhase(c.link);
    return { f1: api.S.f1, ph: api.S.ph[1] };
  }
  if (c.dom) return { text: el(c.dom).textContent, html: el(c.dom).innerHTML, style: el(c.dom).style };
  throw new Error('bad request ' + JSON.stringify(c));
});
console.log(JSON.stringify(out));
