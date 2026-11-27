# Feasibility prototype: Bayesian periods for sparse Gaia DR3 eclipsing binaries

**Question.** Do sparse Gaia DR3 G-band light curves of eclipsing binaries give a useful
period posterior, and do its predictions hold up on held-out data?

**Short answer: partly.** The inference machinery works: the marginalized posterior is
correct, and MH agrees with the grid in 7 of 8 fits. The *model* is the weak point. A K = 3
Fourier series found Gaia's period in 2 of 4 stars, and in one star it confidently picked a wrong
period. The predictive bands are over-confident exactly when the period posterior is
sharp. Only 1 of the 4 stars was predicted better than a constant-flux model. That points to
"promising with a better light-curve model", not to "works as specified".

Self-contained: nothing outside `prototype/` is used or modified.

## Files

| File | What it does |
|---|---|
| `fetch_data.py` | Selects 4 stars by a fixed rule and downloads G-band light curves to `data/` |
| `model.py` | Fourier model with (m, a_k, b_k) marginalized analytically, priors, grid posterior, MH sampler, predictive |
| `run.py` | Hold-out split, fits K = 1 and K = 3, compares MH with the grid, scores the predictions, makes the plots and `results.json` |
| `figs/star_<id>.png` | Per star: light curve · P posterior (MH vs grid) · top-mode probabilities · predictive band vs hidden data |
| `figs/coverage_summary.png` | 68 % / 95 % coverage for all stars, K = 0 (constant), 1, 3 |
| `results.json` | All numbers below, plus acceptance rate by move type and runtimes |

```bash
pip install pyvo numpy scipy matplotlib
python fetch_data.py    # optional: data/ is already committed
python run.py           # ~7 min
```

## Data

* **Source.** On 2026-11-27 the ESA Gaia archive (`gea.esac.esa.int`) returned a "Preparing for
  Gaia DR4 – temporarily unavailable" page, so the data came from the UPJŠ TAP mirror
  (`https://skvo.science.upjs.sk/tap`, tables `gaiadr3_eb.vari_eclipsing_binary_lite` and
  `gaiadr3_eb.lightcurves`). The mirror is not the official archive. Sanity checks:
  * The times span 1690–2704 d (BJD − 2455197.5), which is the DR3 window.
  * The fluxes match the Gaia G zero point (G ≈ 14.6 → ≈ 28 000 e⁻/s).
  * The `obs_time` column description on the mirror starts with a stray "converted to mjd ???".
    The rest of the description, and the values, say BJD − 2455197.5.
* **Selection.** The filters were:
  * G reference level 10–15 and frequency 0.05–2 d⁻¹, as specified.
  * Primary depth 0.1–1.5 mag. Some catalogue rows have "depths" of 20–30 mag, which are
    geometric-model artefacts.
  * At least 45 G points with non-null `flux_error`.

  From the stars that passed, I took the one with the most points in each of four period bins
  (0.5–1.5, 1.5–4, 4–10, 10–20 d). This is the only place Gaia's frequency is touched before
  the final comparison. `run.py` reads it only in `report()`, after fitting.
* **Hold-out.** The last third of each star's time span is hidden. That leaves **30–45 points
  for fitting**, spread over about 600 d.

## Method (as specified)

* **Model.** flux/median = m + Σₖ [aₖ sin(2πkt/P) + bₖ cos(2πkt/P)], with noise variance
  σᵢ² + s². The coefficient priors are m ~ N(1, 1), aₖ, bₖ ~ N(0, 0.5²). The coefficients are
  marginalized exactly with the Woodbury identity. I checked this against a brute-force
  multivariate-normal density and they agree to 1e-10.
* **Priors.** P is log-uniform on [0.5, 20] d. s ~ half-Cauchy(0, 0.05) in relative flux,
  sampled in ln s with the Jacobian included.
* **Grid.** Frequency is spaced 1/(30 T), about 35 000 points; ln s has 160 points.
* **MH.** 24 chains start from the prior and run 40 000 iterations each; the first 10 000 are
  discarded as burn-in.
  * Random-walk moves in ln P use a fixed mixture of step sizes (3e-4 … 1.5). A fixed mixture
    is still symmetric. Alias peaks are only about P/T ≈ 1e-3 wide in ln P, so one step size
    cannot both stay inside a peak and travel between peaks.
  * The other 20 % of moves are ±ln 2 jumps.
* **Predictive.** I take 400 posterior draws of (P, s). For each one I compute the exact
  Gaussian predictive of every hidden point. I then report the 68 % and 95 % intervals of the
  mixture, and the log predictive density (lpd).
* **Baseline.** A constant flux plus jitter (K = 0), for comparison.

## Results

P/P_Gaia is the ratio of the top-mode period to Gaia's period. Coverage is the fraction of
hidden points inside the 68 % / 95 % bands (nominal: 68 / 95). lpd is per hidden point; higher is
better.

| Star (Gaia P) | K | Top modes: P [d] (prob) | P/P_Gaia of top mode | MH vs grid (TV) | Coverage 68/95 | lpd | K=0 coverage, lpd |
|---|---|---|---|---|---|---|---|
| 155783931321026432 (0.9956 d) | 1 | 0.631 (.25), 0.500 (.24), 0.504 (.10) | 0.63 | 0.02 | 82 / 89 | +1.19 | 79 / 92, +1.16 |
|  | 3 | **0.99558 (1.00)** | **1.0000** | **0.33** ✗ | 92 / 95 | **+2.11** | |
| 156690306860276480 (3.198 d) | 1 | 5.94 (.36), 9.47 (.15), 10.9 (.06) | 1.86 | 0.02 | 97 / 97 | +1.36 | 97 / 97, +1.59 |
|  | 3 | 18.9 (.20), 1.498 (.16), **3.197 (.14)**, 10.9 (.11) | 5.92 (3rd mode: 1.000) | 0.05 | 97 / 97 | +1.46 | |
| 156632681281489920 (4.704 d) | 1 | flat: no mode > 0.03 | – | 0.005 | 97 / 97 | +2.02 | 97 / 97, +2.05 |
|  | 3 | 2.114 (1.00) — wrong | 0.449 | 0.02 | **53 / 62** | +1.82 | |
| 157041635184768256 (14.21 d) | 1 | 7.112 (1.00) = P/2 | 0.501 | 0.06 | **29 / 61** | −2.91 | 71 / 87, +0.82 |
|  | 3 | **14.228 (1.00)** | **1.0016** | 0.002 | **32 / 48** | −5.59 | |

### What this shows

1. **K = 1 cannot find the period of an eclipsing binary.** Two similar eclipses per orbit put
   most of the power at P/2. The 14.2 d star shows this cleanly: the posterior is confidently
   P/2 = 7.11 d. K = 3 is the minimum worth trying.
2. **K = 3 found Gaia's period in 2 of 4 stars** (0.9956 d and 14.23 d), each with posterior
   probability ≈ 1. For the 3.2 d star, Gaia's period is only the third mode, with p = 0.14, and the
   posterior is honestly multimodal. The 4.7 d star is the real failure: a detached binary with a
   **single** in-eclipse point among its 30 fitting points. K = 3 bends the curve through that
   one point and gives p = 0.996 to a wrong 2.11 d period.
3. **The sampler mostly works.** Pooled over chains, MH mode probabilities match the grid to
   TV ≤ 0.06 in 7 of 8 fits. That includes the very multimodal ones, where no single chain settles
   (that's why "chains in top mode" in `results.json` is 0 or 2 of 24 there). The failure is
   0.9956 d at K = 3. There, 8 of 24 chains got stuck on a 1.5 P alias that has zero mass on the
   grid, so MH reports it at 0.32. ±ln 2 jumps connect P and 2P but not P and 3P/2, and the
   alias holds them because a K = 3 Fourier series at 1.5 P contains harmonics that line up with
   the true period. Better moves (e.g. jumps by ln 3/2, or the grid as an independence proposal)
   would fix this. A single chain without the grid would have silently given a wrong answer
   here.
4. **Hold-out predictions are not trustworthy yet.**
   * Where the period posterior is broad, the bands cover the hidden points: 97 %. That is only
     because they collapse to "roughly constant", and they never beat the constant baseline.
   * Where the posterior is sharp, the bands are over-confident: 53/62 % and 32/48 % coverage
     against 68/95 % nominal, and an lpd worse than the constant model.
   * Two separate causes:
     * a confidently wrong period (the 4.7 d star);
     * a nearly right period extrapolated too far. The 14.2 d star's period is off by 0.16 %,
       which drifts 0.03–0.07 cycle across the hidden span, several % of flux on the steep
       parts of the curve. The band is too narrow because the
       inferred jitter s ≈ 0.3 % is tuned to the in-sample fit.
   * Only the 0.9956 d star at K = 3 is a real predictive win: lpd +2.11 vs +1.16.

### Verdict

As specified, the approach is **not yet good enough for held-out prediction**. It **is
promising** as a period-posterior tool if two things change:

* **A model that can represent eclipses.** This could be Gaussian dips like Gaia's own geometric
  model, or K chosen by the Bayesian evidence. The grid already computes the evidence
  (`log_evidence`), so comparing K = 1…6 is a few lines of code.
* **Robust or extra noise terms**, e.g. Student-t residuals or a per-star model-error term.

On sampling, MH is fine as a teaching example only if it is checked against the grid. For
1–2 parameters the grid is cheap (13–48 s per fit, vs 9–15 s for MH) and is the more reliable reference.

## Caveats

* Four stars, one random split each. These are feasibility numbers, not a population study.
* The MH-vs-grid **histogram** panel uses 600 bins in ln P, which is coarser than the alias
  peaks. It shows where the mass is, but the quantitative check is the mode-probability bar chart
  and the TV distance.
* Data come from a third-party mirror while the ESA archive is down. When the official archive
  returns, re-download the light curves to confirm they match.
