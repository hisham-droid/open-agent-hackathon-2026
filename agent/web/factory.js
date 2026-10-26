// The Detective Machine: a 3D model of what the agent does. Evidence packets ride a belt through
// Zetaris (data) -> Planner -> four specialists -> Evaluator gate -> Explainer, with H-MEM beside it.
// Procedural three.js (no models, no images). Drive it with window.__machine.step(agentKey, state).
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

const root = document.getElementById("machine");
const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim() || "#2f7d6d";
const dark = matchMedia("(prefers-color-scheme: dark)").matches;
let renderer;
try { renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true }); } catch (e) { root.classList.add("nogl"); throw e; }
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;
root.prepend(renderer.domElement);
const scene = new THREE.Scene();
scene.fog = new THREE.Fog(dark ? 0x16181b : 0xf1eee6, 22, 48);
const camera = new THREE.PerspectiveCamera(36, 1, 0.1, 100);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true; controls.maxPolarAngle = Math.PI * 0.49; controls.minDistance = 6; controls.maxDistance = 34;
controls.autoRotate = !reduce; controls.autoRotateSpeed = 0.35;
const VIEWS = { overview: [[1, 8, 22.5], [1.5, 0.2, 1.8]], front: [[0, 3.5, 20], [0, 1.4, 0]], top: [[0, 28, 4], [0, 0, 0]], memory: [[-6, 5, 8], [-3, 1.4, -3]] };
let fly = null;
function view(name) { const [p, t] = VIEWS[name]; fly = { t0: performance.now(), p0: camera.position.clone(), t0v: controls.target.clone(), p1: new THREE.Vector3(...p), t1: new THREE.Vector3(...t) }; controls.autoRotate = false; }
camera.position.set(...VIEWS.overview[0]); controls.target.set(...VIEWS.overview[1]);

const C = { teal: 0x2f9a85, violet: 0x7a68d0, amber: 0xe0a24a, blue: 0x4f8fe0, green: 0x45c28a, red: 0xe5605a, ink: dark ? 0x3a4048 : 0xcfc9bb, plate: dark ? 0x23272d : 0xf3efe5, white: 0xffffff };
scene.add(new THREE.HemisphereLight(0xffffff, dark ? 0x202428 : 0xd6cfbd, dark ? 0.9 : 1.1));
const sun = new THREE.DirectionalLight(0xffffff, dark ? 1.0 : 1.3); sun.position.set(8, 14, 9); scene.add(sun);
const std = (color, o = {}) => new THREE.MeshStandardMaterial({ color, roughness: 0.45, metalness: 0.15, ...o });
const glow = color => new THREE.MeshStandardMaterial({ color, emissive: color, emissiveIntensity: 0.6, roughness: 0.3 });
const add = (geo, mat, x, y, z, parent = scene) => { const m = new THREE.Mesh(geo, mat); m.position.set(x, y, z); parent.add(m); return m; };

// base plate and belt
const plate = add(new THREE.BoxGeometry(27, 0.4, 15), std(C.plate), 0, -0.25, -2); 
const grid = new THREE.GridHelper(26, 26, C.ink, C.ink); grid.position.y = -0.04; grid.material.transparent = true; grid.material.opacity = 0.35; scene.add(grid);
add(new THREE.BoxGeometry(22, 0.22, 1.5), std(dark ? 0x2c3138 : 0xd8d1bf), 0, 0.12, 1.4);
for (let x = -10; x <= 10; x += 1) add(new THREE.BoxGeometry(0.08, 0.02, 1.4), std(C.ink), x, 0.25, 1.4);

// stations
const ST = {}; const labels = [];
function station(key, name, blurb, x, z, build) {
  const g = new THREE.Group(); g.position.set(x, 0, z); scene.add(g);
  const mats = []; build(g, mats);
  g.userData = { key, name, blurb, mats, pulse: 0, color: new THREE.Color(0xffffff) };
  g.traverse(o => { if (o.isMesh) o.userData.station = g; });
  ST[key] = g;
  const d = document.createElement("button"); d.className = "mlabel"; d.type = "button"; d.textContent = name; d.onclick = () => select(key);
  root.append(d); labels.push({ d, g, y: key === "evaluator" ? 3.6 : key === "hmem" ? 3.4 : 2.9 });
}
station("data", "Zetaris", "The data layer. Commits, deploys, logs and CI are read with SQL over the REST API. Every query is in the trace.", -9.5, 0, (g, m) => {
  for (let i = 0; i < 3; i++) { const mat = std(C.teal, { emissive: C.teal, emissiveIntensity: 0.12 }); m.push(mat); add(new THREE.CylinderGeometry(1.15, 1.15, 0.7, 40), mat, 0, 0.55 + i * 0.85, 0, g); add(new THREE.TorusGeometry(1.15, 0.05, 8, 40), glow(C.teal), 0, 0.9 + i * 0.85, 0, g).rotation.x = Math.PI / 2; }
});
station("planner", "Planner", "Picks the next check and replans after every rejection. With a memory hit it runs the likely checks together.", -6.2, 0, (g, m) => {
  const core = std(C.violet, { emissive: C.violet, emissiveIntensity: 0.2 }); m.push(core);
  const o = add(new THREE.OctahedronGeometry(0.8), core, 0, 2, 0, g); o.name = "spin";
  const r = add(new THREE.TorusGeometry(1.3, 0.06, 10, 60), glow(C.violet), 0, 2, 0, g); r.name = "ring";
  add(new THREE.CylinderGeometry(0.9, 1.1, 0.5, 6), std(C.ink), 0, 0.4, 0, g);
});
[["deploy", "Deploys", "Finds the failed production deploy, the last good one, and the commits in between.", C.blue, -3.1],
 ["logs", "Logs", "Reads the failed deploy's logs and picks out the first real error, ignoring noisy warnings.", C.amber, -1.1],
 ["commits", "Commits", "Ranks commits by whether they introduce the thing the error names.", C.violet, 0.9],
 ["ci", "CI", "Checks what CI tested and why it stayed green.", C.green, 2.9]].forEach(([k, n, b, col, x], i) => station(k, n, b, x, 0, (g, m) => {
  const mat = std(col, { emissive: col, emissiveIntensity: 0.12 }); m.push(mat);
  add(new THREE.BoxGeometry(1.35, 1.7 + i * 0.25, 1.35), mat, 0, 0.85 + i * 0.125, 0, g);
  add(new THREE.BoxGeometry(1.5, 0.12, 1.5), glow(col), 0, 1.75 + i * 0.25, 0, g);
}));
station("evaluator", "Evaluator", "Four weighted checks. Accepts only at 85% with nothing unchecked. It can reject, and rejections force a replan.", 6.1, 0, (g, m) => {
  const mat = std(C.ink, { emissive: C.red, emissiveIntensity: 0.0 }); m.push(mat);
  add(new THREE.BoxGeometry(0.4, 3.2, 0.5), mat, -1.2, 1.6, 1.4, g); add(new THREE.BoxGeometry(0.4, 3.2, 0.5), mat, 1.2, 1.6, 1.4, g); add(new THREE.BoxGeometry(2.8, 0.4, 0.6), mat, 0, 3.2, 1.4, g);
  const beam = add(new THREE.PlaneGeometry(2, 2.8), new THREE.MeshBasicMaterial({ color: C.amber, transparent: true, opacity: 0.22, side: THREE.DoubleSide }), 0, 1.6, 1.4, g); beam.name = "beam";
  add(new THREE.BoxGeometry(2.4, 0.6, 1.8), std(C.ink), 0, 0.3, -0.5, g);
});
station("explainer", "Explainer", "Nemotron, through Nightshift, writes the plain-English story. Every claim must cite verified evidence or it is thrown out.", 9.6, 0, (g, m) => {
  const mat = std(C.teal, { emissive: C.teal, emissiveIntensity: 0.15 }); m.push(mat);
  add(new THREE.BoxGeometry(2, 1.2, 1.6), std(C.ink), 0, 0.6, 0, g);
  const scr = add(new THREE.BoxGeometry(2.2, 1.5, 0.2), mat, 0, 1.95, -0.2, g); scr.rotation.x = -0.12;
  for (let i = 0; i < 4; i++) add(new THREE.BoxGeometry(1.5 - i * 0.2, 0.08, 0.05), glow(C.white), -0.2 + (i ? -0.1 * i : 0), 2.3 - i * 0.28, -0.08, g).rotation.x = -0.12;
});
station("hmem", "H-MEM", "Three memory tiers. Lessons are mined, scored and recalled, and the planner uses them to skip steps. Wrong memory loses confidence.", -5.5, -5.2, (g, m) => {
  [[1.2, 0.5, C.amber], [1.7, 0.5, C.blue], [2.3, 0.6, C.violet]].forEach(([r, h, col], i) => { const mat = std(col, { emissive: col, emissiveIntensity: 0.15, transparent: true, opacity: 0.92 }); m.push(mat); add(new THREE.CylinderGeometry(r, r, h, 48), mat, 0, 0.35 + i * 0.7, 0, g); });
});
// links from memory to planner and evaluator
const link = (a, b) => { const pts = [new THREE.Vector3(a.x, 2.3, a.z), new THREE.Vector3((a.x + b.x) / 2, 3.6, (a.z + b.z) / 2), new THREE.Vector3(b.x, 2.6, b.z)]; const l = new THREE.Line(new THREE.BufferGeometry().setFromPoints(new THREE.QuadraticBezierCurve3(...pts).getPoints(30)), new THREE.LineBasicMaterial({ color: C.violet, transparent: true, opacity: 0.5 })); scene.add(l); };
link(ST.hmem.position, ST.planner.position); link(ST.hmem.position, ST.evaluator.position);

// packets
const packets = [];
const pgeo = new THREE.IcosahedronGeometry(0.28, 1);
function packet(color, hero = false) { const m = new THREE.Mesh(pgeo, new THREE.MeshStandardMaterial({ color, emissive: color, emissiveIntensity: 0.9 })); m.scale.setScalar(hero ? 1.5 : 1); m.position.set(-9.5, 1.3, 1.4); scene.add(m); const p = { m, x: -9.5, hero, state: "idle" }; packets.push(p); return p; }
let spawn = 0;
const hero = packet(C.amber, true); hero.m.visible = false;

// sparks on accept
const sparks = []; const sgeo = new THREE.SphereGeometry(0.07, 6, 6);
function burst(x, color) { for (let i = 0; i < 26; i++) { const s = new THREE.Mesh(sgeo, new THREE.MeshBasicMaterial({ color, transparent: true })); s.position.set(x, 1.8, 1.4); s.userData = { v: new THREE.Vector3((Math.random() - .5) * 4, Math.random() * 4 + 1, (Math.random() - .5) * 3), life: 1 }; scene.add(s); sparks.push(s); } }

// live control: one amber evidence packet walks to the station the agent is working on
const X = k => ST[k] ? ST[k].position.x : 0;
function pulse(key, kind) { const g = ST[key]; if (!g) return; g.userData.pulse = 1; g.userData.color.set(kind === "rej" ? C.red : kind === "mem" ? C.violet : C.green); }
function step(key, kind) {
  const target = key === "hmem" ? "planner" : key === "data" ? "data" : key;
  if (ST[target]) { hero.m.visible = true; hero.goal = ST[target].position.x; hero.live = true; hero.m.material.color.set(kind === "rej" ? C.red : C.amber); hero.m.material.emissive.set(kind === "rej" ? C.red : C.amber); }
  pulse(key, kind);
  if (key === "evaluator") { const b = ST.evaluator.getObjectByName("beam"); b.material.color.set(kind === "rej" ? C.red : C.green); b.material.opacity = 0.55; if (kind !== "rej") burst(ST.evaluator.position.x, C.green); }
}
function finish(ok) { hero.goal = X("explainer"); pulse("explainer", ok ? "ok" : "rej"); if (ok) burst(X("explainer"), C.green); const b = ST.evaluator.getObjectByName("beam"); b.material.color.set(ok ? C.green : C.amber); }
function reset() { hero.m.visible = false; hero.live = false; hero.x = -9.5; ST.evaluator.getObjectByName("beam").material.color.set(C.amber); }
window.__machine = { step, finish, reset, view };

// interaction
const tip = document.getElementById("mtip"); const ray = new THREE.Raycaster(); const mouse = new THREE.Vector2(); let hover = null;
function pick(e) { const r = renderer.domElement.getBoundingClientRect(); mouse.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1); ray.setFromCamera(mouse, camera); const h = ray.intersectObjects(scene.children, true).find(i => i.object.userData.station); return h ? h.object.userData.station : null; }
renderer.domElement.addEventListener("pointermove", e => { const s = pick(e); hover = s; renderer.domElement.style.cursor = s ? "pointer" : "grab"; if (s) show(s); else if (!sel) tip.hidden = true; });
renderer.domElement.addEventListener("click", e => { const s = pick(e); if (s) select(s.userData.key); });
let sel = null;
function show(g) { tip.hidden = false; tip.querySelector("b").textContent = g.userData.name; tip.querySelector("span").textContent = g.userData.blurb; }
function select(key) { sel = key; const g = ST[key]; show(g); pulse(key, "ok"); controls.autoRotate = false; const p = g.position; fly = { t0: performance.now(), p0: camera.position.clone(), t0v: controls.target.clone(), p1: new THREE.Vector3(p.x + 2.5, 4.2, p.z + 8), t1: new THREE.Vector3(p.x, 1.5, p.z) }; }
document.querySelectorAll("[data-view]").forEach(b => b.onclick = () => { sel = null; view(b.dataset.view); });
renderer.domElement.addEventListener("pointerdown", () => { controls.autoRotate = false; });

function resize() { const w = root.clientWidth, h = root.clientHeight; renderer.setSize(w, h); camera.aspect = w / h; camera.clearViewOffset(); if (w > 900) camera.setViewOffset(w, h, -w * 0.12, 0, w, h); camera.updateProjectionMatrix(); }
new ResizeObserver(resize).observe(root); resize();

const clock = new THREE.Clock(); const tmp = new THREE.Vector3();
function frame() {
  const dt = Math.min(clock.getDelta(), 0.05), t = clock.elapsedTime;
  if (fly) { const k = Math.min(1, (performance.now() - fly.t0) / 900), e = 1 - Math.pow(1 - k, 3); camera.position.lerpVectors(fly.p0, fly.p1, e); controls.target.lerpVectors(fly.t0v, fly.t1, e); if (k >= 1) fly = null; }
  controls.update();
  Object.values(ST).forEach(g => { const u = g.userData; u.pulse = Math.max(0, u.pulse - dt * 0.7); const hv = hover === g ? 0.35 : 0;
    u.mats.forEach(m => { m.emissive.lerp(u.pulse > 0.02 ? u.color : m.color, 0.15); m.emissiveIntensity = 0.12 + u.pulse * 0.9 + hv; });
    g.position.y = hv ? 0.12 : 0; });
  const sp = ST.planner.getObjectByName("spin"), rg = ST.planner.getObjectByName("ring"); sp.rotation.y = t * 1.2; sp.rotation.x = t * .6; rg.rotation.x = Math.PI / 2 + Math.sin(t) * .25; rg.rotation.y = t * .8; sp.position.y = 2 + Math.sin(t * 1.6) * 0.12;
  const beam = ST.evaluator.getObjectByName("beam"); beam.position.y = 1.6 + Math.sin(t * 2.2) * 1.1; beam.material.opacity += (0.22 - beam.material.opacity) * 0.03;
  spawn -= dt; if (spawn <= 0 && !hero.live) { packet(Math.random() < .5 ? C.teal : C.blue); spawn = reduce ? 3 : 1.6; }
  for (let i = packets.length - 1; i >= 0; i--) { const p = packets[i];
    if (p.hero) { if (p.live && p.goal != null) { p.x += Math.sign(p.goal - p.x) * Math.min(Math.abs(p.goal - p.x), dt * 14); p.m.position.x = p.x; p.m.position.y = 1.3 + Math.sin(t * 6) * 0.1; p.m.rotation.y += dt * 3; } continue; }
    p.x += dt * 3.2; p.m.position.x = p.x; p.m.rotation.y += dt * 2; p.m.position.y = 1.3 + Math.sin(p.x * 1.5) * 0.06;
    if (p.x > X("evaluator") - 1 && p.state === "idle") { p.state = "ok"; p.m.material.color.set(C.green); p.m.material.emissive.set(C.green); }
    if (p.x > 11.5) { scene.remove(p.m); packets.splice(i, 1); } }
  for (let i = sparks.length - 1; i >= 0; i--) { const s = sparks[i], u = s.userData; u.v.y -= dt * 9; s.position.addScaledVector(u.v, dt); u.life -= dt * 1.3; s.material.opacity = Math.max(0, u.life); if (u.life <= 0) { scene.remove(s); sparks.splice(i, 1); } }
  labels.forEach(({ d, g, y }) => { tmp.set(g.position.x, y, g.position.z).project(camera); const w = root.clientWidth, h = root.clientHeight; d.style.transform = `translate(${(tmp.x * .5 + .5) * w}px,${(-tmp.y * .5 + .5) * h}px) translate(-50%,-100%)`; d.style.opacity = tmp.z < 1 ? 1 : 0; d.classList.toggle("on", hover === g || sel === g.userData.key || g.userData.pulse > 0.3); });
  renderer.render(scene, camera); requestAnimationFrame(frame);
}
frame();
document.getElementById("machine").classList.add("ready");
