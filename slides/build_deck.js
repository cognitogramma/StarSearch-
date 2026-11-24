const pptxgen = require("pptxgenjs");
const fs = require("fs");
const path = require("path");
// Optional: a helper that writes the THEME colours into the .pptx. Without it, the
// deck still builds but scheme colours fall back to Office's default palette.
let applyTheme = null;
if (process.env.APPLY_THEME_JS) ({ applyTheme } = require(process.env.APPLY_THEME_JS));

const ROOT = path.join(__dirname, "..");
const R = JSON.parse(fs.readFileSync(path.join(ROOT, "results.json")));
const FIG = (n) => path.join(ROOT, "figs", n);

const THEME = {
  name: "Night Sky",
  headFontFace: "Cambria",
  bodyFontFace: "Calibri",
  colors: {
    dk1: "1B1B1B", lt1: "FFFFFF", dk2: "0E1A2B", lt2: "F2F4F8",
    accent1: "F2A33A", accent2: "2A78D6", accent3: "EB6834", accent4: "1BAF7A",
    accent5: "5C5B57", accent6: "6250D6", hlink: "2A78D6", folHlink: "6250D6",
  },
};

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.33 x 7.5
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
pres.title = "Recovering Stellar Periods with Metropolis–Hastings";
const C = pres.SchemeColor;
const W = 13.333, M = 0.6;
const HEX = { navy: "0E1A2B", amber: "F2A33A", blue: "2A78D6", orange: "EB6834", aqua: "1BAF7A", ink: "1B1B1B", muted: "5C5B57", grid: "E4E3DF", tint: "F2F4F8" };

// ---------------- layouts ----------------
pres.defineSlideMaster({
  title: "TITLE_DARK",
  background: { color: C.text2 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: M, y: 2.3, w: 11.5, h: 1.6, fontFace: "Cambria", fontSize: 44, bold: true, color: C.background1, valign: "bottom", align: "left" }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: M, y: 4.1, w: 11.5, h: 1.2, fontSize: 20, color: C.accent1, valign: "top" }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "SECTION_DARK",
  background: { color: C.text2 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: M, y: 2.6, w: 11.5, h: 1.2, fontFace: "Cambria", fontSize: 40, bold: true, color: C.background1, valign: "bottom", align: "left" }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: M, y: 3.95, w: 11.5, h: 1.0, fontSize: 20, color: C.accent1, valign: "top" }, text: "" } },
  ],
  slideNumber: { x: 12.3, y: 6.95, w: 0.6, h: 0.35, fontSize: 11, color: "9AA4B5", align: "right" },
});
pres.defineSlideMaster({
  title: "CONTENT",
  background: { color: C.background1 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: M, y: 0.55, w: 12.1, h: 0.85, fontFace: "Cambria", fontSize: 32, bold: true, color: C.text2, valign: "middle", align: "left", margin: 0 }, text: "" } },
    { text: { text: "Recovering stellar periods with Metropolis–Hastings", options: { x: M, y: 6.95, w: 8, h: 0.35, fontSize: 10, color: C.accent5, margin: 0 } } },
  ],
  slideNumber: { x: 12.3, y: 6.95, w: 0.6, h: 0.35, fontSize: 11, color: C.accent5, align: "right" },
});

// ---------------- helpers ----------------
let curSection = "";
function section(title) { pres.addSection({ title }); curSection = title; }
function content(title, eyebrow, notes) {
  const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: curSection });
  s.addText(title, { placeholder: "title" });
  if (eyebrow) {
    s.addShape(pres.shapes.OVAL, { x: M, y: 0.33, w: 0.13, h: 0.13, fill: { color: C.accent1 }, line: { color: C.accent1 }, objectName: "eyebrow dot" });
    s.addText(eyebrow.toUpperCase(), { x: M + 0.22, y: 0.24, w: 8, h: 0.3, fontSize: 11, bold: true, charSpacing: 2, color: C.accent5, margin: 0, isTextBox: true, objectName: "eyebrow" });
  }
  if (notes) s.addNotes(plain(notes));
  return s;
}
function plain(t) { return t.replace(/\^\{([^}]*)\}/g, "^$1").replace(/_\{([^}]*)\}/g, "_$1"); }
function divider(title, sub, notes) {
  const s = pres.addSlide({ masterName: "SECTION_DARK", sectionTitle: curSection });
  s.addText(title, { placeholder: "title" });
  if (sub) s.addText(sub, { placeholder: "body" });
  if (notes) s.addNotes(notes);
  return s;
}
function rich(text) {
  if (typeof text !== "string") return text;
  const re = /\^\{([^}]*)\}|_\{([^}]*)\}/g;
  const runs = []; let last = 0, m;
  while ((m = re.exec(text))) {
    if (m.index > last) runs.push({ text: text.slice(last, m.index), options: {} });
    runs.push({ text: m[1] !== undefined ? m[1] : m[2], options: m[1] !== undefined ? { superscript: true } : { subscript: true } });
    last = re.lastIndex;
  }
  if (last < text.length) runs.push({ text: text.slice(last), options: {} });
  // keep explicit line breaks working inside runs
  const out = [];
  runs.forEach((r) => r.text.split("\n").forEach((part, i, arr) => out.push({ text: part, options: Object.assign({}, r.options, i < arr.length - 1 ? { breakLine: true } : {}) })));
  return out;
}
function card(s, x, y, w, h, name) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.08, fill: { color: C.background2 }, line: { color: C.background2 }, objectName: name || "card" });
}
function eq(s, x, y, w, h, text, size) {
  card(s, x, y, w, h, "equation card");
  s.addText(rich(text), { x: x + 0.25, y, w: w - 0.5, h, fontFace: "Cambria", fontSize: size || 22, color: C.text1, valign: "middle", align: "center", isTextBox: true, objectName: "equation" });
}
function body(s, x, y, w, h, items, size) {
  const runs = items.map((it, i) => {
    const o = typeof it === "string" ? { text: it, options: {} } : it;
    return { text: o.text, options: Object.assign({ bullet: o.nobullet ? false : true, breakLine: i < items.length - 1, paraSpaceAfter: 8 }, o.options || {}) };
  });
  s.addText(runs, { x, y, w, h, fontSize: size || 16, color: C.text1, valign: "top", isTextBox: true, objectName: "body text" });
}
function label(s, x, y, w, h, text, opts) {
  s.addText(rich(text), Object.assign({ x, y, w, h, fontSize: 14, color: C.text1, margin: 0, valign: "top", isTextBox: true }, opts || {}));
}
function img(s, file, x, y, w, aspect, alt) {
  s.addImage({ path: FIG(file), x, y, w, h: w / aspect, altText: alt, objectName: file });
}
function stat(s, x, y, w, big, small, color) {
  s.addText(big, { x, y, w, h: 0.85, fontFace: "Cambria", fontSize: 40, bold: true, color: color || C.text2, margin: 0, isTextBox: true, objectName: "stat value" });
  s.addText(small, { x, y: y + 0.85, w, h: 0.6, fontSize: 13, color: C.accent5, margin: 0, valign: "top", isTextBox: true, objectName: "stat label" });
}
function arrow(s, x, y, w) {
  s.addShape(pres.shapes.RIGHT_ARROW, { x, y, w, h: 0.4, fill: { color: C.accent1 }, line: { color: C.accent1 }, objectName: "arrow" });
}
const HIST_ASPECT = (() => { const b = fs.readFileSync(FIG("regII_hist.png")); return b.readUInt32BE(16) / b.readUInt32BE(20); })();
const f3 = (v) => v.toFixed(3), f2 = (v) => v.toFixed(2);
const pct = (v) => Math.round(v * 100) + "%";

// =====================================================================
// SECTION 1 — Why
// =====================================================================
section("Why this problem");
{
  const s = pres.addSlide({ masterName: "TITLE_DARK", sectionTitle: curSection });
  s.addText("Recovering Stellar Periods with Metropolis–Hastings", { placeholder: "title" });
  s.addText("When can a Markov chain find the rhythm of a variable star, and when does it get lost?", { placeholder: "body" });
  s.addText("Stochastic Processes · Final project · Fall 2026", { x: M, y: 6.6, w: 8, h: 0.4, fontSize: 14, color: "9AA4B5", margin: 0, isTextBox: true });
  s.addNotes("Opening line: a star that brightens and dims on a schedule is a clock. We get to read that clock only through a few noisy glimpses. This project asks how a random walk can recover the clock's period, and when that random walk fails.");
}
{
  const s = content("What an astronomer actually receives", "The problem", "Phase 0 example (from our planning with ChatGPT). Eight noisy measurements at uneven times. Ask the audience: is this star periodic? What is the period? How sure are we?\n\nExplain it yourself: why can't we just 'connect the dots' to read off the period?");
  const rows = [["Time (days)", "Brightness"], ["0.0", "10.2"], ["0.8", "10.8"], ["2.1", "11.4"], ["3.7", "10.3"], ["5.2", "9.1"], ["6.8", "9.7"], ["9.3", "11.2"], ["12.7", "9.5"]];
  s.addTable(rows.map((r, i) => r.map((c) => ({ text: c, options: { bold: i === 0, color: i === 0 ? HEX.navy : HEX.ink, fill: { color: i === 0 ? "E6EAF1" : "FFFFFF" } } }))),
    { x: M, y: 1.75, w: 4.2, colW: [2.1, 2.1], rowH: 0.48, fontSize: 15, align: "center", border: { type: "solid", pt: 0.75, color: HEX.grid }, objectName: "example data table" });
  label(s, 5.4, 1.75, 7.3, 0.4, "What we want to know", { fontSize: 20, bold: true, color: C.text2, fontFace: "Cambria" });
  const qs = [["Is it periodic?", "Is the variation a repeating pattern or just noise?"], ["What is the period?", "How long is one full cycle?"], ["How sure are we?", "A single number is not enough; we want a range of plausible periods."], ["Could several periods fit?", "Gaps in the data can let very different periods explain the same points."]];
  qs.forEach((q, i) => {
    const y = 2.35 + i * 1.08;
    s.addShape(pres.shapes.OVAL, { x: 5.4, y: y + 0.05, w: 0.5, h: 0.5, fill: { color: i === 3 ? C.accent1 : C.text2 }, line: { color: i === 3 ? C.accent1 : C.text2 }, objectName: "number circle" });
    s.addText(String(i + 1), { x: 5.4, y: y + 0.05, w: 0.5, h: 0.5, fontSize: 16, bold: true, color: i === 3 ? C.text2 : C.background1, align: "center", valign: "middle", margin: 0, isTextBox: true });
    label(s, 6.1, y, 6.6, 0.35, q[0], { fontSize: 17, bold: true });
    label(s, 6.1, y + 0.38, 6.6, 0.55, q[1], { fontSize: 14, color: C.accent5 });
  });
}
{
  const s = content("Two questions, one causal chain", "Research questions", "The two questions are not separate topics: the observing conditions determine the shape of the posterior, and the shape of the posterior determines whether the Markov chain can explore it. Our experiments change the left box and watch the right box.\n\nExplain it yourself: give one example of an observing condition and say how it might change the posterior's shape.");
  card(s, M, 1.7, 5.9, 1.55); card(s, 6.83, 1.7, 5.9, 1.55);
  label(s, M + 0.3, 1.85, 5.3, 0.35, "ASTRONOMICAL QUESTION", { fontSize: 12, bold: true, color: C.accent5, charSpacing: 1 });
  label(s, M + 0.3, 2.2, 5.3, 1.0, "How reliably can we recover a star's period from noisy, irregularly sampled observations?", { fontSize: 16 });
  label(s, 7.13, 1.85, 5.3, 0.35, "STOCHASTIC PROCESSES QUESTION", { fontSize: 12, bold: true, color: C.accent5, charSpacing: 1 });
  label(s, 7.13, 2.2, 5.3, 1.0, "How does the shape of a posterior, especially multiple peaks, affect whether a Metropolis–Hastings chain explores it?", { fontSize: 16 });
  const boxes = [["Observing conditions", "noise · number of points · gaps · time span"], ["Shape of the posterior", "one sharp peak, or several competing peaks"], ["Behaviour of the chain", "finds the peak · hops between peaks · gets stuck"]];
  boxes.forEach((b, i) => {
    const x = M + i * 4.2;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 4.05, w: 3.5, h: 1.9, rectRadius: 0.1, fill: { color: C.text2 }, line: { color: C.text2 }, objectName: "chain box" });
    label(s, x + 0.25, 4.3, 3.0, 0.5, b[0], { fontSize: 19, bold: true, color: C.background1, fontFace: "Cambria" });
    label(s, x + 0.25, 4.95, 3.0, 0.9, b[1], { fontSize: 14, color: C.accent1 });
    if (i < 2) arrow(s, x + 3.6, 4.8, 0.5);
  });
  label(s, M, 6.15, 12.1, 0.4, "Our experiments change the left box and measure the right box.", { fontSize: 15, italic: true, color: C.accent5 });
}
{
  const s = content("Why Metropolis–Hastings, honestly", "Motivation", "Be ready for the professor's question 'why not just use a grid?'. Answer: in 1D a grid IS feasible and gives the exact posterior. That is exactly why it is useful: it is the ground truth we grade the Markov chain against. In higher dimensions (several periods, more parameters) a grid becomes impossible and MCMC is the only option, so understanding its failure modes in a setting where we can check the answer is valuable.");
  const rows = [["Problem", "Goal", "Tool"], ["Estimation", "Find a plausible period", "Periodogram / least squares"], ["Uncertainty", "How plausible is every period?", "Bayesian posterior p(f | data)"], ["Sampling", "Can a random process explore that posterior faithfully?", "Metropolis–Hastings Markov chain"]];
  s.addTable(rows.map((r, i) => r.map((c, j) => ({ text: c, options: { bold: i === 0 || j === 0, color: i === 0 ? HEX.navy : HEX.ink, fill: { color: i === 0 ? "E6EAF1" : "FFFFFF" } } }))),
    { x: M, y: 1.75, w: 7.4, colW: [1.7, 3.0, 2.7], rowH: 0.85, fontSize: 15, valign: "middle", border: { type: "solid", pt: 0.75, color: HEX.grid }, objectName: "three problems table" });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 8.4, y: 1.75, w: 4.3, h: 3.4, rectRadius: 0.1, fill: { color: C.text2 }, line: { color: C.text2 }, objectName: "honesty card" });
  label(s, 8.7, 2.0, 3.8, 0.4, "An honest limitation", { fontSize: 19, bold: true, color: C.accent1, fontFace: "Cambria" });
  label(s, 8.7, 2.55, 3.8, 2.5, [
    { text: "After we integrate out the nuisance parameters, the posterior lives in one dimension. A fine grid can compute it exactly.", options: { breakLine: true, paraSpaceAfter: 12 } },
    { text: "We turn that into a strength: the grid is the answer key we grade the Markov chain against.", options: { bold: true } },
  ], { fontSize: 15, color: C.background1 });
}

// =====================================================================
// SECTION 2 — Model
// =====================================================================
section("The mathematical model");
divider("The mathematical model", "From noisy measurements to a probability for every period");
{
  const s = content("Two simulated stars, same true period", "Data", `Both light curves were simulated with a true period of 2.7 days, so we know the right answer.\nRegime I: 120 observations spread over 90 days, amplitude 1.0, noise σ = 0.3 (strong signal, continuous coverage like a space telescope).\nRegime II: 40 nights out of 90, one short visit per night, amplitude 0.45, noise σ = 0.5 (weak signal, ground-based).\nBottom row: 'folding' plots brightness against phase = (t mod P)/P. At the right period, the scattered points line up into one wave.\n\nExplain it yourself: what would the folded plot look like at a wrong period?`);
  const w = 6.9, h = w / (2202 / 835);
  img(s, "lightcurves.png", M, 1.55, w, 2202 / 835, "Raw light curves: Regime I with 120 points and Regime II with 40 nightly points");
  img(s, "folded.png", M, 1.55 + h + 0.1, w, 2203 / 835, "Both light curves folded at the true 2.7 day period");
  label(s, 7.85, 1.65, 4.85, 0.4, "Top: what the telescope sees", { fontSize: 17, bold: true });
  label(s, 7.85, 2.05, 4.85, 1.3, "Brightness against time. No obvious wave: the period (2.7 d) is short compared with the gaps.", { fontSize: 15, color: C.accent5 });
  label(s, 7.85, 4.35, 4.85, 0.4, "Bottom: folded at the true period", { fontSize: 17, bold: true });
  label(s, 7.85, 4.75, 4.85, 1.6, "Plot brightness against phase = (t mod P) / P. At the right P, the points line up into one wave. Regime II stays noisy even at the right period.", { fontSize: 15, color: C.accent5 });
}
{
  const s = content("Observation model", "Unit 4 · separating signal from noise", "Write a·sin + b·cos instead of A·sin(2πft + φ). They are the same curve (A = √(a²+b²), tan φ = b/a), but now a, b, c enter linearly, which is what lets us integrate them out exactly later.\n\nExplain it yourself: show that A sin(x + φ) = (A cos φ) sin x + (A sin φ) cos x.");
  eq(s, M, 1.7, 12.1, 1.15, "yᵢ  =  a sin(2πf tᵢ)  +  b cos(2πf tᵢ)  +  c  +  εᵢ ,      εᵢ ~ N(0, σᵢ²)", 26);
  const parts = [["f", "frequency in cycles/day; period P = 1/f. The parameter we care about."], ["a, b", "amplitude and phase of the wave (A = √(a² + b²))."], ["c", "the star's average brightness."], ["εᵢ", "measurement noise for observation i, with known size σᵢ."]];
  parts.forEach((p, i) => {
    const y = 3.2 + i * 0.72;
    label(s, M, y, 0.9, 0.5, p[0], { fontFace: "Cambria", fontSize: 20, bold: true, color: C.text2 });
    label(s, M + 0.95, y + 0.04, 5.6, 0.6, p[1], { fontSize: 15 });
  });
  card(s, 7.6, 3.15, 5.1, 3.3, "assumptions card");
  label(s, 7.9, 3.35, 4.6, 0.4, "Assumptions (to revisit)", { fontSize: 17, bold: true, color: C.text2 });
  body(s, 7.85, 3.8, 4.7, 2.6, ["The light curve is a single sinusoid", "The period is constant over the observations", "Noise is Gaussian and independent", "Noise sizes σᵢ are known"], 15);
}
{
  const s = content("Likelihood: how well does a model explain the data?", "Unit 5", "Each observation contributes a Gaussian factor; independence turns the joint density into a product, and the log turns the product into a sum, chi-squared. Maximising the likelihood = minimising chi-squared = weighted least squares.\n\nExplain it yourself: why does independence of the εᵢ let us multiply?");
  eq(s, M, 1.7, 12.1, 1.25, "p(y | f, a, b, c)  =  ∏ᵢ  (2πσᵢ²)^{−1/2}  exp( −(yᵢ − mᵢ)² / 2σᵢ² )   ∝   exp( −χ² / 2 )", 22);
  eq(s, M, 3.15, 12.1, 0.95, "χ²(f, a, b, c)  =  Σᵢ (yᵢ − mᵢ)² / σᵢ² ,      mᵢ = a sin(2πf tᵢ) + b cos(2πf tᵢ) + c", 20);
  const steps = [["Each point", "is Gaussian around the model value mᵢ"], ["Independent noise", "lets us multiply the n densities"], ["Take logs", "the product becomes −χ²/2: a weighted sum of squared misfits"]];
  steps.forEach((t, i) => {
    const x = M + i * 4.1;
    s.addShape(pres.shapes.OVAL, { x, y: 4.6, w: 0.55, h: 0.55, fill: { color: C.accent1 }, line: { color: C.accent1 }, objectName: "step circle" });
    s.addText(String(i + 1), { x, y: 4.6, w: 0.55, h: 0.55, fontSize: 17, bold: true, color: C.text2, align: "center", valign: "middle", margin: 0, isTextBox: true });
    label(s, x + 0.7, 4.58, 3.2, 0.4, t[0], { fontSize: 17, bold: true });
    label(s, x + 0.7, 5.0, 3.2, 1.0, t[1], { fontSize: 15, color: C.accent5 });
  });
  label(s, M, 6.15, 12.1, 0.45, "Maximising the likelihood  =  minimising χ²  =  weighted least squares.", { fontSize: 16, italic: true, color: C.text2, fontFace: "Cambria" });
}
{
  const s = content("Bayes' theorem turns fit into probability", "Unit 6 · priors", "The prior for f is uniform on [0.02, 1.5] cycles/day: periods from 0.67 to 50 days. We sample frequency, not period, because posterior peaks have roughly the same width (~1/T, T = time span) everywhere in frequency. Note: a prior uniform in f is NOT uniform in P; changing variables gives p(P) ∝ 1/P².\n\nExplain it yourself: where does the 1/P² come from? (Hint: f = 1/P, so |df/dP| = 1/P².)");
  eq(s, M, 1.7, 12.1, 1.15, "p(f, a, b, c | y)   ∝   p(y | f, a, b, c)  ·  p(f)  ·  p(a, b, c)", 26);
  const cols = [["Posterior", "What we believe after seeing the data"], ["Likelihood", "How well each parameter value explains the data (previous slide)"], ["Prior", "What we allow before seeing the data"]];
  cols.forEach((c, i) => {
    const x = M + i * 4.1;
    label(s, x, 3.15, 3.8, 0.4, c[0], { fontSize: 18, bold: true, color: C.text2, fontFace: "Cambria" });
    label(s, x, 3.55, 3.8, 0.8, c[1], { fontSize: 15, color: C.accent5 });
  });
  card(s, M, 4.6, 12.1, 1.9, "prior choices card");
  label(s, M + 0.3, 4.75, 11.5, 0.4, "Our prior choices", { fontSize: 17, bold: true, color: C.text2 });
  body(s, M + 0.25, 5.15, 11.6, 1.35, [
    "f ~ Uniform(0.02, 1.5) cycles/day, i.e. periods between 0.67 and 50 days. We sample in frequency because peaks have equal width there.",
    "Flat priors on a, b, c. Caution: uniform in f is not uniform in P; the change of variables gives p(P) ∝ 1/P².",
  ], 15);
}
{
  const s = content("Integrating out what we don't care about", "Unit 7 · marginalization", "Full derivation is in the appendix. Key idea: because the model is linear in θ = (a, b, c), χ² is a quadratic bowl in θ. Integrating exp(−bowl/2) is a Gaussian integral we can do exactly. What remains depends only on f.\n\nExplain it yourself: what does the determinant term reward or penalise?");
  eq(s, M, 1.7, 12.1, 1.0, "p(f | y)  =  ∫ p(f, a, b, c | y) da db dc", 22);
  eq(s, M, 2.9, 12.1, 1.2, "log p(f | y)  =  const  −  ½ χ²_{min}(f)  −  ½ log det(X^{T} W X)  +  log p(f)", 24);
  const items = [["χ²_{min}(f)", "the best possible misfit at frequency f, from a weighted least-squares fit of a, b, c"], ["det(X^{T}WX)", "how well the data pin down a, b, c at this f; a small 'Occam' correction"], ["Result", "a 1D target π(f) we can evaluate in microseconds, sample with MCMC, and check on a grid"]];
  items.forEach((it, i) => {
    const y = 4.45 + i * 0.75;
    label(s, M, y, 2.6, 0.5, it[0], { fontFace: "Cambria", fontSize: 18, bold: true, color: C.text2 });
    label(s, M + 2.7, y + 0.03, 9.4, 0.65, it[1], { fontSize: 15 });
  });
}
{
  const s = content("The shape of the posterior", "Unit 8 · posterior geometry", `Computed exactly on an 80,000-point grid. Regime I: all the probability sits in one peak about ${(2.355 * R.peak_sd_I).toFixed(4)} cycles/day wide, inside a range of 1.48. That is roughly 1 part in 2,400 of the space. Regime II: three peaks. The true one holds ${pct(R.II_masses.grid[0])} of the probability, the alias at 1+f holds ${pct(R.II_masses.grid[2])}, the alias at 1−f holds ${pct(R.II_masses.grid[1])}, and the rest is spread thinly everywhere.\n\nExplain it yourself: why is a strong signal's peak so narrow?`);
  img(s, "posteriors.png", M, 1.5, 12.1, 2229 / 835, "Exact posteriors: Regime I has one very narrow peak; Regime II has three peaks");
  label(s, M, 6.15, 5.9, 0.6, "A needle in a haystack: about 1/2,400 of the frequency range.", { fontSize: 15, italic: true, color: C.accent5 });
  label(s, 6.83, 6.15, 5.9, 0.6, `Mass in peaks: true ${pct(R.II_masses.grid[0])} · 1+f ${pct(R.II_masses.grid[2])} · 1−f ${pct(R.II_masses.grid[1])}`, { fontSize: 15, italic: true, color: C.accent5 });
}
{
  const s = content("Where the extra peaks come from", "Unit 8 · aliasing", "The spectral window is the 'periodogram of the sampling pattern alone'. Observing once per night puts a strong echo at 1 cycle/day. A signal at f then also looks like signals at 1 − f and 1 + f. With f = 0.370: aliases at 0.630 (P = 1.59 d) and 1.370 (P = 0.73 d), exactly where the extra peaks are.\n\nExplain it yourself: if you could observe every 12 hours instead, where would the echo move?");
  img(s, "window.png", M, 1.5, 12.1, 2179 / 774, "Spectral window: continuous coverage has no echo; nightly sampling has a strong echo at 1 cycle per day");
  card(s, M, 5.95, 12.1, 0.85, "alias equation card");
  label(s, M + 0.3, 5.95, 11.5, 0.85, [
    { text: "Rule: ", options: { bold: true } },
    { text: "sampling once per day makes f, 1 − f and 1 + f nearly indistinguishable.  With f = 0.370: aliases at 0.630 (1.59 d) and 1.370 (0.73 d)." },
  ], { fontSize: 16, valign: "middle" });
}

// =====================================================================
// SECTION 3 — Markov chain
// =====================================================================
section("The Markov chain");
divider("The Markov chain", "Building a random walk whose long-run behaviour is the posterior");
{
  const s = content("The Metropolis–Hastings algorithm", "Unit 9", "Our proposal mixes two symmetric moves: a small Gaussian step (95% of the time) and a uniform jump anywhere in the prior range (5%). Because both are symmetric, q cancels in the ratio. The step size is 2.4 × the width of the main peak (the classic rule of thumb for 1D random-walk MH).\n\nExplain it yourself: why must a rejected proposal still be recorded as a repeat of the current state?");
  const steps = [["Start", "Pick an initial frequency f₀"], ["Propose", "f′ = f + s·Z,  Z ~ N(0,1)\n(or, 5% of the time, f′ ~ Uniform)"], ["Compare", "α = min{ 1, π(f′) / π(f) }"], ["Accept or stay", "With probability α move to f′; otherwise record f again"]];
  steps.forEach((t, i) => {
    const x = M + i * 3.1;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 1.75, w: 2.75, h: 2.35, rectRadius: 0.1, fill: { color: i === 2 ? C.text2 : C.background2 }, line: { color: i === 2 ? C.text2 : C.background2 }, objectName: "step card" });
    label(s, x + 0.2, 1.9, 2.4, 0.4, `${i + 1}  ${t[0]}`, { fontSize: 17, bold: true, color: i === 2 ? C.accent1 : C.text2 });
    label(s, x + 0.2, 2.4, 2.4, 1.6, t[1], { fontSize: 14, color: i === 2 ? C.background1 : C.text1, fontFace: "Cambria" });
    if (i < 3) arrow(s, x + 2.78, 2.75, 0.3);
  });
  eq(s, M, 4.45, 12.1, 1.0, "General rule:   α(f → f′)  =  min{ 1,  π(f′) q(f | f′)  /  π(f) q(f′ | f) }", 20);
  label(s, M, 5.7, 12.1, 0.9, "Our proposal is symmetric, q(f′ | f) = q(f | f′), so the q terms cancel. The normalising constant of π also cancels, which is why we never need it.", { fontSize: 15, color: C.accent5 });
}
{
  const s = content("Why the posterior is stationary", "Unit 10 · detailed balance", "Proof sketch. Let K(f → f′) be the transition density. For f ≠ f′, K = q·α. Then π(f) q(f′|f) α(f, f′) = π(f) q(f′|f) · min{1, π(f′)q(f|f′) / π(f)q(f′|f)} = min{π(f)q(f′|f), π(f′)q(f|f′)}. That expression is symmetric in f and f′, so swapping them gives the same value: detailed balance. Integrate both sides over f: the right side becomes π(f′)·(total probability of leaving f′) = π(f′). So one step of the chain maps π to π.\n\nExplain it yourself: what happens to the 'stay' (rejection) part of K in this proof?");
  label(s, M, 1.65, 5.6, 0.4, "Detailed balance", { fontSize: 18, bold: true, color: C.text2, fontFace: "Cambria" });
  eq(s, M, 2.1, 5.9, 0.95, "π(f) K(f → f′)  =  π(f′) K(f′ → f)", 21);
  label(s, M, 3.25, 5.9, 0.4, "Proof for f ≠ f′", { fontSize: 18, bold: true, color: C.text2, fontFace: "Cambria" });
  eq(s, M, 3.7, 5.9, 1.6, "π(f) q(f′|f) α(f, f′)\n=  min{ π(f) q(f′|f),  π(f′) q(f|f′) }", 19);
  label(s, M, 5.45, 5.9, 0.9, "The right side doesn't change if we swap f and f′, so the flow each way is equal.", { fontSize: 15, color: C.accent5 });
  card(s, 6.9, 1.65, 5.8, 4.7, "stationarity card");
  label(s, 7.2, 1.85, 5.2, 0.4, "Detailed balance ⇒ stationarity", { fontSize: 18, bold: true, color: C.text2, fontFace: "Cambria" });
  label(s, 7.2, 2.4, 5.2, 1.0, "Integrate both sides over f:", { fontSize: 15 });
  eq(s, 7.15, 2.85, 5.3, 1.0, "∫ π(f) K(f → f′) df  =  π(f′)", 21);
  label(s, 7.2, 4.05, 5.2, 2.2, "If the chain's current state is distributed as π, after one step it is still distributed as π. The posterior is a stationary distribution of the chain.", { fontSize: 15 });
}
{
  const s = content("Stationary is not the same as converged", "Unit 11 · convergence and mixing", "Ergodic theorem for MH (Tierney 1994): if the chain is π-irreducible and aperiodic, the distribution of the chain converges to π in total variation and averages along the chain converge to posterior expectations. Our chain satisfies both: the Gaussian step has positive density everywhere in the range (irreducible), and rejections happen with positive probability (aperiodic). But the theorem says nothing about HOW FAST. That gap is our project.\n\nExplain it yourself: why can a chain satisfy every condition of the theorem and still be useless after a million steps?");
  const cards = [["Detailed balance", "π is stationary: once there, the chain stays there.", "Proved"], ["Irreducible + aperiodic", "Every region can be reached; no forced cycles. Then the chain converges to π eventually.", "True for our chain"], ["Mixing speed", "How many steps until 'eventually'? Narrow or separated peaks can make it astronomically long.", "The open question"]];
  cards.forEach((c, i) => {
    const x = M + i * 4.1;
    const dark = i === 2;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 1.75, w: 3.8, h: 3.2, rectRadius: 0.1, fill: { color: dark ? C.text2 : C.background2 }, line: { color: dark ? C.text2 : C.background2 }, objectName: "theory card" });
    label(s, x + 0.25, 1.95, 3.3, 0.35, c[2].toUpperCase(), { fontSize: 11, bold: true, charSpacing: 1, color: dark ? C.accent1 : C.accent5 });
    label(s, x + 0.25, 2.35, 3.3, 0.5, c[0], { fontSize: 19, bold: true, fontFace: "Cambria", color: dark ? C.background1 : C.text2 });
    label(s, x + 0.25, 3.0, 3.3, 1.8, c[1], { fontSize: 15, color: dark ? C.background1 : C.text1 });
  });
  label(s, M, 5.3, 12.1, 1.0, "The theorems guarantee the destination, not the travel time. Our experiments measure the travel time.", { fontSize: 18, italic: true, color: C.text2, fontFace: "Cambria" });
}

// =====================================================================
// SECTION 4 — Experiments
// =====================================================================
section("Experiments");
divider("Experiments", "Two regimes × two proposals, graded against the exact grid posterior");
{
  const s = content("Experimental design", "Unit 12", "Each configuration: 4 chains started at f = 0.1, 0.5, 0.9, 1.4 (spread across the range on purpose). Regime I: 40,000 steps, first 5,000 discarded as burn-in. Regime II: 120,000 steps, first 10,000 discarded. Random seed 7. Diagnostics: R-hat compares the chains with each other (near 1.00 means they agree); ESS estimates how many independent samples the correlated chain is worth; mode masses compare the fraction of time in each peak with the exact grid.");
  const rows = [["", "Regime I: strong", "Regime II: weak"], ["Observations", "120 over 90 days", "40 nights, one visit each"], ["Amplitude / noise", "1.0 / 0.3", "0.45 / 0.5"], ["Posterior shape", "One needle-thin peak", "Three alias peaks"], ["Chains × steps", "4 × 40,000", "4 × 120,000"]];
  s.addTable(rows.map((r, i) => r.map((c, j) => ({ text: c, options: { bold: i === 0 || j === 0, color: i === 0 ? HEX.navy : HEX.ink, fill: { color: i === 0 ? "E6EAF1" : "FFFFFF" } } }))),
    { x: M, y: 1.75, w: 7.3, colW: [2.1, 2.6, 2.6], rowH: 0.62, fontSize: 15, valign: "middle", border: { type: "solid", pt: 0.75, color: HEX.grid }, objectName: "design table" });
  card(s, 8.3, 1.75, 4.4, 1.95, "proposals card");
  label(s, 8.55, 1.9, 4.0, 0.4, "Two proposals", { fontSize: 17, bold: true, color: C.text2 });
  body(s, 8.5, 2.3, 4.1, 1.4, ["Random walk only", "Random walk + 5% global uniform jumps"], 15);
  card(s, 8.3, 3.95, 4.4, 2.4, "diagnostics card");
  label(s, 8.55, 4.1, 4.0, 0.4, "Diagnostics", { fontSize: 17, bold: true, color: C.text2 });
  body(s, 8.5, 4.5, 4.1, 1.85, ["R-hat: do 4 chains agree?", "ESS: independent samples' worth", "Mode masses vs the exact grid"], 15);
}
{
  const s = content("Regime I: the strong signal is the hard one", "Result 1", `Surprise: with the plain random walk, none of the 4 chains ever found the peak in 40,000 steps (R-hat = ${R.I_rw.rhat.toFixed(0)}). The peak occupies ~1/2,400 of the range, and away from it the posterior is nearly flat, so the walk drifts with no signal pointing toward the peak. Worse, each stuck chain LOOKS healthy on its own (acceptance ${pct(R.I_rw.acceptance)}). With 5% global jumps, every chain lands in the peak within about 3,000 steps and R-hat = ${R.I_mix.rhat.toFixed(3)}.\n\nExplain it yourself: why would a single-chain diagnostic miss this failure?`);
  img(s, "regI_traces.png", M, 1.5, 8.6, 2179 / 910, "Trace plots for Regime I: random-walk chains stay where they start; chains with global jumps all reach the true frequency");
  label(s, M, 5.25, 8.6, 0.9, "Each colour is one chain, started at a different frequency. Dashed line: the true frequency (P = 2.7 d).", { fontSize: 14, color: C.accent5 });
  stat(s, 9.6, 1.65, 3.2, R.I_rw.rhat.toFixed(0), "R-hat, random walk only (should be ≈ 1.00)", C.accent3);
  stat(s, 9.6, 3.15, 3.2, R.I_mix.rhat.toFixed(3), "R-hat with global jumps", C.text2);
  label(s, 9.6, 4.75, 3.2, 1.7, "Each stuck chain looks healthy on its own. Only comparing chains shows the failure.", { fontSize: 15, italic: true, color: C.accent5 });
}
{
  const s = content("Regime I: tuning the step size", "Result 2", `Chains started at the peak, 20,000 steps each, step = multiple × peak width (σ = ${R.peak_sd_I.toExponential(1)} cycles/day). Tiny steps are almost always accepted but barely move; huge steps are almost always rejected. The efficiency peak is around 2.4σ with about 45% acceptance, matching the theory for 1D random-walk Metropolis. Posterior result: P = ${R.I_P_q[1].toFixed(4)} d, 95% interval ${R.I_P_q[0].toFixed(4)}–${R.I_P_q[2].toFixed(4)} d (truth 2.7000).`);
  const st = R.step_study;
  const labels = st.map((x) => x.mult + "σ");
  const common = { x: 0, y: 1.7, w: 5.9, h: 3.6, catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt", catAxisLabelColor: "5C5B57", valAxisLabelColor: "5C5B57", catAxisLabelFontSize: 12, valAxisLabelFontSize: 12, valGridLine: { color: "E4E3DF", size: 0.75 }, catGridLine: { style: "none" }, showLegend: false, showTitle: true, titleFontFace: "+mn-lt", titleFontSize: 15, titleColor: "1B1B1B", lineSize: 2, lineDataSymbolSize: 8, showValue: true, dataLabelFontSize: 11, dataLabelColor: "1B1B1B", dataLabelPosition: "t", dataLabelFontFace: "+mn-lt", showCatAxisTitle: true, catAxisTitle: "step size (× peak width)", catAxisTitleFontSize: 12, catAxisTitleColor: "5C5B57" };
  s.addChart(pres.charts.LINE, [{ name: "Acceptance rate (%)", labels, values: st.map((x) => Math.round(x.acceptance * 100)) }],
    Object.assign({}, common, { x: M, title: "Acceptance rate (%)", chartColors: ["2A78D6"], valAxisMinVal: 0, valAxisMaxVal: 100, dataLabelFormatCode: "0", objectName: "acceptance chart" }));
  s.addChart(pres.charts.LINE, [{ name: "ESS per 1,000 steps", labels, values: st.map((x) => Math.round(x.ess_per_1000)) }],
    Object.assign({}, common, { x: 6.83, title: "Effective samples per 1,000 steps", chartColors: ["EB6834"], valAxisMinVal: 0, dataLabelFormatCode: "0", objectName: "ESS chart" }));
  card(s, M, 5.55, 12.1, 1.05, "period estimate card");
  label(s, M + 0.3, 5.55, 11.5, 1.05, [
    { text: "Recovered period:  ", options: { bold: true } },
    { text: `P = ${R.I_P_q[1].toFixed(4)} d,  95% interval ${R.I_P_q[0].toFixed(4)} – ${R.I_P_q[2].toFixed(4)} d   (truth: 2.7000 d)`, options: { fontFace: "Cambria" } },
  ], { fontSize: 18, valign: "middle" });
}
{
  const s = content("Regime II: chains get trapped in aliases", "Result 3", `Random walk only: each chain settles into whichever peak it reaches first. One chain ends up stuck near 1+f (0.73 d) and one moves to 1−f (1.59 d) and stays. A single chain from either would confidently report the wrong period. R-hat = ${R.II_rw.rhat.toFixed(1)}. With global jumps, chains visit all three peaks and agree (R-hat = ${R.II_mix.rhat.toFixed(3)}), though the dots show they still spend long stretches in one peak before jumping.\n\nExplain it yourself: in the right panel, why are there horizontal bands at exactly three heights?`);
  img(s, "regII_traces.png", M, 1.5, 8.6, 2179 / 910, "Trace plots for Regime II: random-walk chains stay in different alias peaks; chains with global jumps visit all three");
  label(s, M, 5.25, 8.6, 0.9, "Horizontal bands sit at the three peaks: 0.37 (true), 0.63 (1 − f) and 1.37 (1 + f). Dashed line: the true frequency.", { fontSize: 14, color: C.accent5 });
  stat(s, 9.6, 1.65, 3.2, R.II_rw.rhat.toFixed(1), "R-hat, random walk only", C.accent3);
  stat(s, 9.6, 3.15, 3.2, R.II_mix.rhat.toFixed(3), "R-hat with global jumps (target < 1.01)", C.text2);
  label(s, 9.6, 4.75, 3.2, 1.7, "One trapped chain would confidently report the wrong period.", { fontSize: 15, italic: true, color: C.accent5 });
}
{
  const s = content("Regime II: does the chain get the proportions right?", "Result 4", `Fraction of probability in each peak. Grid (exact): ${pct(R.II_masses.grid[0])} / ${pct(R.II_masses.grid[2])} / ${pct(R.II_masses.grid[1])}. MH with jumps (4 chains pooled): ${pct(R.II_masses.mix[0])} / ${pct(R.II_masses.mix[2])} / ${pct(R.II_masses.mix[1])}. Close, but not exact: the total ESS is only ~${Math.round(R.II_mix.ess_total)} because jumps between peaks are rare (a uniform proposal lands inside a narrow peak only occasionally). A random-walk chain that stays in one peak would report ~100% for that peak.\n\nExplain it yourself: what single change would most improve the agreement?`);
  img(s, "regII_hist.png", M, 1.6, 6.3, HIST_ASPECT, "Histogram of MH samples overlaid on the exact posterior for Regime II");
  const names = ["True f (2.70 d)", "Alias 1+f (0.73 d)", "Alias 1−f (1.59 d)"];
  const order = [0, 2, 1];
  s.addChart(pres.charts.BAR, [
    { name: "Exact (grid)", labels: names, values: order.map((i) => Math.round(R.II_masses.grid[i] * 100)) },
    { name: "MH with jumps", labels: names, values: order.map((i) => Math.round(R.II_masses.mix[i] * 100)) },
  ], { x: 7.1, y: 1.5, w: 5.6, h: 4.2, barDir: "col", barGapWidthPct: 60, chartColors: ["0E1A2B", "EB6834"], showTitle: true, title: "Probability in each peak (%)", titleFontFace: "+mn-lt", titleFontSize: 15, titleColor: "1B1B1B",
    catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt", catAxisLabelColor: "5C5B57", valAxisLabelColor: "5C5B57", catAxisLabelFontSize: 11, valAxisLabelFontSize: 11, valGridLine: { color: "E4E3DF", size: 0.75 }, catGridLine: { style: "none" }, valAxisMinVal: 0, valAxisMaxVal: 60,
    showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 11, dataLabelColor: "1B1B1B", dataLabelFontFace: "+mn-lt", dataLabelFormatCode: "0", showLegend: true, legendPos: "b", legendFontSize: 12, legendFontFace: "+mn-lt", legendColor: "1B1B1B", objectName: "mode mass chart" });
  label(s, M, 5.95, 12.1, 0.7, `Close but not exact: only ~${Math.round(R.II_mix.ess_total)} effective samples, because jumps between peaks are rare. More steps or a smarter jump would fix this.`, { fontSize: 15, italic: true, color: C.accent5 });
}
{
  const s = content("Diagnostics at a glance", "Summary of results", "Read across: a high acceptance rate is not evidence of success (Regime I random walk: 84% acceptance, total failure). R-hat is the diagnostic that caught every failure. ESS in Regime II is low even when the chains agree, which is why the mode proportions are only approximately right.");
  const row = (name, r, verdict) => [name, pct(r.acceptance), r.rhat < 10 ? r.rhat.toFixed(3) : r.rhat.toFixed(0), Math.round(r.ess_total).toLocaleString("en-US"), verdict];
  const rows = [["Run", "Acceptance", "R-hat", "ESS (total)", "Verdict"],
    row("Regime I · random walk", R.I_rw, "Failed: never finds the peak"),
    row("Regime I · + global jumps", R.I_mix, "Works"),
    row("Regime II · random walk", R.II_rw, "Failed: trapped in aliases"),
    row("Regime II · + global jumps", R.II_mix, "Works, but slow between peaks")];
  s.addTable(rows.map((r, i) => r.map((c, j) => ({ text: String(c), options: { bold: i === 0 || j === 0, color: i === 0 ? HEX.navy : (j === 4 && /Failed/.test(c) ? "B5401A" : HEX.ink), fill: { color: i === 0 ? "E6EAF1" : "FFFFFF" } } }))),
    { x: M, y: 1.75, w: 12.1, colW: [3.3, 1.6, 1.4, 1.8, 4.0], rowH: 0.62, fontSize: 15, valign: "middle", border: { type: "solid", pt: 0.75, color: HEX.grid }, objectName: "diagnostics table" });
  const take = [["High acceptance ≠ success", `Regime I random walk: ${pct(R.I_rw.acceptance)} acceptance, total failure.`], ["Use several chains", "R-hat across chains caught every failure; single-chain checks missed them."], ["Agreement ≠ efficiency", "Regime II chains agree, but rare jumps leave few effective samples."]];
  take.forEach((t, i) => {
    const x = M + i * 4.1;
    label(s, x, 5.1, 3.8, 0.4, t[0], { fontSize: 17, bold: true, color: C.text2 });
    label(s, x, 5.5, 3.8, 1.0, t[1], { fontSize: 14, color: C.accent5 });
  });
}

// =====================================================================
// SECTION 5 — Wrap-up
// =====================================================================
section("Conclusions");
{
  const s = pres.addSlide({ masterName: "SECTION_DARK", sectionTitle: curSection });
  s.addText("What we learned", { x: M, y: 0.6, w: 12, h: 0.9, fontFace: "Cambria", fontSize: 36, bold: true, color: C.background1, margin: 0, isTextBox: true });
  const pts = [["Detailed balance guarantees the destination, not the travel time.", "Every chain we ran had the posterior as its stationary distribution, and two of four still failed in practice."],
    ["Observing conditions shape the posterior.", "Strong, well-sampled data give a needle-thin peak; nightly sampling creates alias peaks at 1 ± f."],
    ["Each shape breaks the random walk differently.", "A needle is hard to find; separated peaks are hard to leave. Both are mixing failures."],
    ["Global moves fix both, partly.", "Mixing in occasional uniform jumps restored agreement (R-hat ≈ 1), but moves between peaks remain rare."]];
  pts.forEach((p, i) => {
    const y = 1.8 + i * 1.2;
    s.addShape(pres.shapes.OVAL, { x: M, y: y + 0.05, w: 0.5, h: 0.5, fill: { color: C.accent1 }, line: { color: C.accent1 }, objectName: "number circle" });
    s.addText(String(i + 1), { x: M, y: y + 0.05, w: 0.5, h: 0.5, fontSize: 16, bold: true, color: C.text2, align: "center", valign: "middle", margin: 0, isTextBox: true });
    label(s, M + 0.75, y, 11.3, 0.45, p[0], { fontSize: 19, bold: true, color: C.background1 });
    label(s, M + 0.75, y + 0.45, 11.3, 0.6, p[1], { fontSize: 15, color: "C9D1DE" });
  });
  s.addNotes("These four findings answer the two research questions: the observing conditions (left box) set the posterior's shape (middle box), and that shape determines how and why the chain fails (right box).");
}
{
  const s = content("Live demonstration", "Demo plan", "Run: python demo.py (to be written together). Plan: (1) show the Regime II light curve, (2) run one random-walk chain from f = 1.4 and watch it settle at the 0.73-day alias, (3) rerun with global jumps on and watch it hop between peaks, (4) overlay the histogram on the exact grid posterior. Keep a pre-recorded fallback in case the laptop misbehaves.");
  const steps = [["Show the data", "Regime II light curve: no visible wave"], ["Run a random walk", "Start at f = 1.4 and watch it settle on the 0.73-day alias"], ["Turn on global jumps", "Watch the chain hop between all three peaks"], ["Check the answer", "Overlay the histogram on the exact grid posterior"]];
  steps.forEach((t, i) => {
    const y = 1.75 + i * 1.1;
    s.addShape(pres.shapes.OVAL, { x: M, y, w: 0.6, h: 0.6, fill: { color: C.text2 }, line: { color: C.text2 }, objectName: "number circle" });
    s.addText(String(i + 1), { x: M, y, w: 0.6, h: 0.6, fontSize: 18, bold: true, color: C.background1, align: "center", valign: "middle", margin: 0, isTextBox: true });
    label(s, M + 0.85, y - 0.02, 6.0, 0.4, t[0], { fontSize: 18, bold: true });
    label(s, M + 0.85, y + 0.38, 6.0, 0.6, t[1], { fontSize: 15, color: C.accent5 });
  });
  card(s, 7.9, 1.75, 4.8, 4.3, "code card");
  label(s, 8.15, 1.95, 4.3, 0.4, "Code (numpy only, written from scratch)", { fontSize: 15, bold: true, color: C.text2 });
  s.addText([
    { text: "stellar_mh.py", options: { bold: true, breakLine: true } },
    { text: "  model, sampler, diagnostics", options: { breakLine: true, paraSpaceAfter: 10 } },
    { text: "experiments.py", options: { bold: true, breakLine: true } },
    { text: "  every figure in this deck", options: { breakLine: true, paraSpaceAfter: 10 } },
    { text: "demo.py", options: { bold: true, breakLine: true } },
    { text: "  to write together" },
  ], { x: 8.15, y: 2.45, w: 4.3, h: 3.4, fontFace: "Courier New", fontSize: 14, color: C.text1, valign: "top", isTextBox: true, objectName: "file list" });
}
{
  const s = content("Next steps", "Still to do", "Be explicit with the audience that real-data validation has not been done yet. Candidate data: ZTF or ASAS-SN light curves of RR Lyrae or Cepheid stars with catalogued periods. Ground-based surveys have exactly the nightly sampling of Regime II, so we expect alias peaks in real data too.");
  const items = [["Real stars", "Validate on RR Lyrae or Cepheid light curves (ZTF, ASAS-SN) with catalogued periods.", "Not yet done", true],
    ["Smarter jumps", "Propose jumps from the periodogram, or use parallel tempering, so moves between peaks become common.", "Extension", false],
    ["Map the boundary", "Vary noise, number of nights and span to find where recovery starts to fail.", "Extension", false],
    ["Discovery (optional)", "Search survey data for variable-star candidates without a catalogued period.", "Optional", false]];
  items.forEach((it, i) => {
    const col = i % 2, rowi = Math.floor(i / 2);
    const x = M + col * 6.15, y = 1.75 + rowi * 2.4;
    card(s, x, y, 5.95, 2.15, "next step card");
    label(s, x + 0.3, y + 0.2, 5.3, 0.3, it[2].toUpperCase(), { fontSize: 11, bold: true, charSpacing: 1, color: it[3] ? "B5401A" : C.accent5 });
    label(s, x + 0.3, y + 0.55, 5.3, 0.45, it[0], { fontSize: 19, bold: true, color: C.text2, fontFace: "Cambria" });
    label(s, x + 0.3, y + 1.05, 5.3, 1.0, it[1], { fontSize: 15 });
  });
}
{
  const s = content("References", "Sources", "Check each reference against the original before the final presentation.");
  body(s, M, 1.7, 12.1, 5.0, [
    "Metropolis, N., Rosenbluth, A., Rosenbluth, M., Teller, A. & Teller, E. (1953). Equation of state calculations by fast computing machines. J. Chem. Phys. 21, 1087.",
    "Hastings, W. K. (1970). Monte Carlo sampling methods using Markov chains and their applications. Biometrika 57, 97–109.",
    "Tierney, L. (1994). Markov chains for exploring posterior distributions. Annals of Statistics 22, 1701–1728.",
    "Gelman, A. & Rubin, D. B. (1992). Inference from iterative simulation using multiple sequences. Statistical Science 7, 457–472.",
    "Roberts, G. O., Gelman, A. & Gilks, W. R. (1997). Weak convergence and optimal scaling of random walk Metropolis algorithms. Annals of Applied Probability 7, 110–120.",
    "VanderPlas, J. T. (2018). Understanding the Lomb–Scargle periodogram. ApJS 236, 16.",
    "Gregory, P. C. & Loredo, T. J. (1992). A new method for the detection of a periodic signal of unknown shape and period. ApJ 398, 146.",
  ], 14);
}

// =====================================================================
// APPENDIX
// =====================================================================
section("Appendix");
divider("Appendix", "Full derivations and reproducibility details");
{
  const s = content("A1 · Marginal likelihood, step by step", "Appendix", "Step 3 is 'completing the square' in matrix form. Step 4 is the multivariate Gaussian integral ∫ exp(−½ u^{T}Au) du = (2π)^(k/2) det(A)^(−1/2), here with k = 3.\n\nExplain it yourself: where does the requirement that a, b, c enter linearly get used?");
  const steps = [
    ["1. Matrix form", "y = Xθ + ε,   θ = (a, b, c)^{T},   rows of X: [sin 2πftᵢ, cos 2πftᵢ, 1],   W = diag(1/σᵢ²)"],
    ["2. Chi-squared", "χ²(θ) = (y − Xθ)^{T} W (y − Xθ)"],
    ["3. Complete the square", "χ²(θ) = χ²_{min} + (θ − θ*)^{T} (X^{T}WX) (θ − θ*),     θ* = (X^{T}WX)⁻¹ X^{T}Wy"],
    ["4. Gaussian integral", "∫ exp(−χ²/2) dθ = exp(−χ²_{min}/2) · (2π)^{3/2} · det(X^{T}WX)^{−1/2}"],
    ["5. Result", "log p(f | y) = const − ½ χ²_{min}(f) − ½ log det(X^{T}WX) + log p(f)"],
  ];
  steps.forEach((st, i) => {
    const y = 1.65 + i * 1.0;
    label(s, M, y + 0.2, 2.9, 0.5, st[0], { fontSize: 16, bold: true, color: C.text2 });
    card(s, 3.6, y, 9.1, 0.85, "equation card");
    s.addText(rich(st[1]), { x: 3.8, y, w: 8.7, h: 0.85, fontFace: "Cambria", fontSize: 16, color: C.text1, valign: "middle", isTextBox: true, objectName: "equation" });
  });
}
{
  const s = content("A2 · Stationarity, including the rejection term", "Appendix", "The full kernel has two parts: a density for moving and a point mass for staying. The point-mass part trivially satisfies detailed balance (f = f′ on both sides), so only the moving part needs the min argument.");
  eq(s, M, 1.7, 12.1, 1.0, "K(f, df′)  =  q(f′|f) α(f, f′) df′   +   r(f) δ_{f}(df′),      r(f) = 1 − ∫ q(f′|f) α(f, f′) df′", 18);
  label(s, M, 2.95, 12.1, 0.4, "Moving part (f ≠ f′):", { fontSize: 16, bold: true, color: C.text2 });
  eq(s, M, 3.35, 12.1, 0.85, "π(f) q(f′|f) α(f, f′)  =  min{ π(f) q(f′|f), π(f′) q(f|f′) }  =  π(f′) q(f|f′) α(f′, f)", 18);
  label(s, M, 4.4, 12.1, 0.4, "Stationarity: integrate over f", { fontSize: 16, bold: true, color: C.text2 });
  eq(s, M, 4.8, 12.1, 1.3, "∫ π(f) K(f, df′) df  =  π(f′) ∫ q(f|f′) α(f′, f) df  +  π(f′) r(f′)  =  π(f′) [ (1 − r(f′)) + r(f′) ]  =  π(f′)", 18);
  label(s, M, 6.25, 12.1, 0.5, "The staying term is exactly what tops the total back up to π(f′). This is why rejections must be recorded.", { fontSize: 15, italic: true, color: C.accent5 });
}
{
  const s = content("A3 · Why mixing two proposals is allowed", "Appendix", "A mixture of kernels that each satisfy detailed balance w.r.t. π also satisfies it, because detailed balance is linear in K. Here we went one step simpler: the mixture proposal itself is symmetric, so ordinary Metropolis applies directly.");
  eq(s, M, 1.7, 12.1, 1.0, "q(f′|f)  =  0.95 · N(f′; f, s²)  +  0.05 · Uniform(f′; f_{min}, f_{max})", 20);
  const pts = [["Gaussian step", "N(f′; f, s²) = N(f; f′, s²): it depends only on |f′ − f|, so it is symmetric."],
    ["Uniform jump", "1/(f_{max} − f_{min}) for any f, f′ in range: trivially symmetric."],
    ["Mixture", "A weighted sum of symmetric densities is symmetric, so α = min{1, π(f′)/π(f)} still holds."],
    ["Outside the range", "π(f′) = 0 there, so α = 0: proposals outside [f_{min}, f_{max}] are always rejected."]];
  pts.forEach((p, i) => {
    const y = 3.0 + i * 0.85;
    label(s, M, y, 3.0, 0.5, p[0], { fontSize: 16, bold: true, color: C.text2 });
    label(s, M + 3.1, y, 9.0, 0.75, p[1], { fontSize: 15 });
  });
}
{
  const s = content("A4 · The diagnostics, defined", "Appendix", "Split R-hat: each chain is cut in half, giving m sequences of length n. W = mean within-sequence variance, B/n = variance of the sequence means. If all sequences explore the same distribution, B/n is small and R-hat ≈ 1. ESS: sum autocorrelations ρₖ until they first turn negative.");
  label(s, M, 1.65, 5.9, 0.4, "Split R-hat (Gelman–Rubin)", { fontSize: 18, bold: true, color: C.text2, fontFace: "Cambria" });
  eq(s, M, 2.1, 5.9, 1.4, "V̂ = ((n−1)/n) W + B/n\nR̂ = √( V̂ / W )", 20);
  label(s, M, 3.7, 5.9, 2.5, "W: average variance within each half-chain. B/n: variance between half-chain means. Chains stuck in different places make B large, so R-hat ≫ 1.", { fontSize: 15 });
  label(s, 6.83, 1.65, 5.9, 0.4, "Effective sample size", { fontSize: 18, bold: true, color: C.text2, fontFace: "Cambria" });
  eq(s, 6.83, 2.1, 5.9, 1.4, "ESS = n / (1 + 2 Σₖ ρₖ)", 20);
  label(s, 6.83, 3.7, 5.9, 2.5, "ρₖ: correlation between the chain and itself k steps later. Strongly correlated chains are worth far fewer than n independent draws.", { fontSize: 15 });
}
{
  const s = content("A5 · Reproducibility", "Appendix", "Everything regenerates with: python experiments.py (about one minute). Data are saved to regime_I.csv and regime_II.csv.");
  const rows = [["Setting", "Value"], ["True period", "2.7 days (f = 0.3704 cycles/day)"], ["Prior range for f", "0.02 to 1.5 cycles/day (0.67 to 50 days)"], ["Grid for exact posterior", "80,000 points"],
    ["Random-walk step", `2.4 × peak width:  I = ${R.step_I.toExponential(2)},  II = ${R.step_II.toExponential(2)}`], ["Global jump probability", "5%"], ["Chain starts", "f = 0.1, 0.5, 0.9, 1.4"], ["Random seed", "7 (numpy default_rng)"]];
  s.addTable(rows.map((r, i) => r.map((c, j) => ({ text: c, options: { bold: i === 0 || j === 0, color: i === 0 ? HEX.navy : HEX.ink, fill: { color: i === 0 ? "E6EAF1" : "FFFFFF" } } }))),
    { x: M, y: 1.7, w: 12.1, colW: [3.6, 8.5], rowH: 0.55, fontSize: 15, valign: "middle", border: { type: "solid", pt: 0.75, color: HEX.grid }, objectName: "settings table" });
}

(async () => {
  const out = path.join(__dirname, "Stellar_Periods_MH.pptx");
  await pres.writeFile({ fileName: out });
  if (applyTheme) await applyTheme(out, THEME);
  console.log("wrote", out);
})();
