# Feasibility prototype: Bayesian periods for sparse Gaia DR3 eclipsing binaries

**Question.** Do sparse Gaia DR3 G-band light curves of eclipsing binaries give a useful
period posterior, and do its predictions hold up on held-out data?

**Short answer, after two rounds: not yet. It works when the period is identifiable, but it
doesn't know when the period isn't identifiable.**

* **When the posterior lands on Gaia's period, predictions are good.** That happened for 12 of 40
  random stars. On 11 of those 12, the held-out light curve is predicted better than by a constant.
* **For half the sample the posterior lands on a period unrelated to Gaia's,** often with
  probability ≈ 1. Those predictions are no better than a constant.
* **Overall, the 68 % / 95 % bands are too narrow.** Pooled coverage of the hidden points is
  62 % / 84 %, against nominal 68 / 95.
* **Random-walk MH is not reliable on these posteriors.** Its pooled mode probabilities are within
  TV 0.1 of the exact grid in only 56 % of fits.
* **Warning for anyone grading this.** MH-based bands look better calibrated than they are
  (76 % / 93 %), only because stuck chains smear the draws over wrong modes.

Self-contained: nothing outside `prototype/` is used or modified.

## Files

| File | What it does |
|---|---|
| `fetch_data.py` | Selects stars by a fixed rule and downloads their G-band light curves to `data/` (already committed) |
| `model.py` | Fourier model with the coefficients marginalized, flat and shrinkage priors, two-stage grid, MH sampler, predictive scoring |
| `run.py` | Holds out the last third of each star, fits every model, scores the hidden points, writes `results.json` and `figs/stars/<id>.png`. ~40 min on 4 cores |
| `summarize.py` | Aggregates into `summary.json` and `figs/summary_*.png` (called by `run.py`) |
| `results_run1.json`, `figs/run1/` | Round 1: 4 stars, K = 1 and 3, flat prior. The round-1 code is at commit `883e94f` |

```bash
pip install pyvo numpy scipy matplotlib
python run.py          # all 44 stars; `python run.py 4` = the original four only
```

## Data

* **Source.** On 2026-11-27 the ESA Gaia archive (`gea.esac.esa.int`) showed "Preparing for
  Gaia DR4 – temporarily unavailable". The data came from the UPJŠ TAP mirror
  (`https://skvo.science.upjs.sk/tap`, tables `gaiadr3_eb.vari_eclipsing_binary_lite` and
  `gaiadr3_eb.lightcurves`), using G band only with null `flux_error` rows dropped. Sanity checks:
  * The times span 1690–2704 d (BJD − 2455197.5), the DR3 window.
  * The fluxes match the Gaia G zero point.
  * The `obs_time` column description on the mirror starts with a stray "converted to mjd ???",
    but the rest of the description and the values say BJD − 2455197.5.

  The mirror is third-party: re-download from ESA when it returns.
* **Filters.** G reference level 10–15 and frequency 0.05–2 d⁻¹, as specified. I also required a
  primary depth of 0.1–1.5 mag, because some catalogue rows have 20–30 mag "depths" that are model
  artefacts, and at least 45 usable G points.
* **Star sets.**
  * `original4`: round 1, the star with the most points in each period bin.
  * `sample40`: pseudo-random (`ORDER BY MOD(source_id, 999983)`, which spreads stars over the
    sky), 10 per period bin (0.5–1.5, 1.5–4, 4–10, 10–20 d). **The headline numbers use only
    `sample40`**, because the original 4 were picked differently.
* **Hold-out.** The last third of each time span is hidden. That leaves 20–74 points to fit
  (median 40) and 822 hidden points in total.
* **Gaia's frequency is read only after a star's fits are finished.** It is used for star
  selection and for the final comparison, nowhere else. Gaia's period is a reference, not ground
  truth: it uses all the data and a different (eclipse-shaped) model.

## Models

All models: flux/median = m + Σₖ [aₖ sin(2πkt/P) + bₖ cos(2πkt/P)], noise variance σᵢ² + s².
The coefficients are marginalized exactly. P is log-uniform on [0.5, 20] d; s ~ half-Cauchy(0.05)
in relative flux.

| Name | Coefficient prior | K |
|---|---|---|
| `const` | – | 0: a constant plus jitter (baseline) |
| `old` | aₖ, bₖ ~ N(0, 0.5²): round 1's best model | 3 |
| `new` | aₖ, bₖ ~ N(0, (σ_h/k)²): higher harmonics must earn their amplitude. σ_h is averaged over {0.01, 0.03, 0.1, 0.3}, exactly, so the posterior is still over (P, s) only | {1, 3, 6}, weighted by Bayesian evidence |

**Sampler.** 16 chains start from the prior and run 25 000 iterations each (5 000 discarded as
burn-in). Moves in ln P are all symmetric:
* Gaussian random-walk steps from a fixed mixture of sizes (3e-4 … 1.5);
* ±ln 2 jumps;
* **new in round 2:** ±ln(3/2) jumps.

**Reference.** The exact grid posterior. The frequency spacing is 1/(max(30, 6K)·T), which
resolves every alias peak. The grid works in two stages: every frequency is evaluated on a coarse
ln s grid, then the full ln s grid is evaluated only where the posterior is within e⁻³⁰ of the
peak.

**Scoring.** Each model predicts the hidden points twice:
* from MH draws, the method under test;
* from grid draws, the exact posterior.

This separates model problems from sampler problems.

## Round 2 results (`sample40`: 40 stars, 822 hidden points)

### Held-out predictions

| | const | old, grid | **new, grid** | old, MH | new, MH |
|---|---|---|---|---|---|
| Pooled coverage, 68 % band (nominal 68) | 84 % | 67 % | **62 %** | 76 % | 76 % |
| Pooled coverage, 95 % band (nominal 95) | 93 % | 87 % | **84 %** | 93 % | 93 % |
| Stars with 95 % coverage < 85 % | 15 % | 33 % | **35 %** | 13 % | 13 % |
| Stars within ±10 points of nominal on both bands* | 3 % | 15 % | **23 %** | 23 % | 23 % |
| Stars where the model beats const on held-out log density | – | 58 % | **68 %** | 70 % | 88 % |
| Median held-out log density per point, minus const | – | +0.19 | **+0.50** | +0.25 | +0.76 |

\* With only about 20 hidden points per star, even a perfectly calibrated model would pass this
test on just 63 % of stars (binomial noise; computed in `summarize.py`).

Read the **grid** columns as the model's real behaviour. The MH columns look better only because
of sampling failure:
* In fits where MH matches the grid (TV < 0.1), MH and grid 95 % coverage differ by 1–4 points.
* In fits where it doesn't match, MH coverage is 8–10 points higher.
* Stuck chains spread the predictive draws over several wrong modes, and that widens the bands.

### Period vs Gaia (top posterior mode)

| | Top mode = Gaia P (±1 %) | P/2 | Other aliases (2P, 2P/3, 3P/2) | Unrelated | Prob ≥ 0.9 on an unrelated period | Mean posterior prob on Gaia P |
|---|---|---|---|---|---|---|
| old | 10 | 7 | 1 | 22 | 11 | 0.24 |
| **new** | **12** | 8 | 0 | **20** | **9** | **0.30** |

Disagreeing with Gaia goes with bad predictions. That suggests our period is the wrong one, not
Gaia's. New model, grid draws:

| Top mode is… | Stars | Beats const | Median log density vs const | Median 95 % coverage |
|---|---|---|---|---|
| Gaia's P | 12 | 11 / 12 | +1.26 | 90 % |
| P/2 | 8 | 6 / 8 | +0.78 | 89 % |
| Unrelated | 20 | 10 / 20 | +0.00 | 87 % |

The evidence prefers K = 6 for 36 / 40 stars and K = 3 for the other 4; K = 1 never wins.

### Sampler

* Across all 160 fits, MH and grid mode probabilities agree within TV 0.1 in only **56 %** of
  fits. Median TV is 0.075, maximum 0.91.
* Worst case, star 2205071261005286656: 13 of 16 chains end 6–12 nats below the global mode
  (0.883 d), on 2.18 d and 13.86 d. Those ratios are not 2 or 3/2, so no jump in the move set
  connects them.
* The ±ln(3/2) jump fixed the specific round-1 failure it targeted (a 3/2 alias). It cannot fix
  aliases at arbitrary period ratios.
* MH does worse here than in round 1 for two reasons:
  * chains are shorter (16 × 25 k vs 24 × 40 k);
  * K = 6 peaks are narrower than K = 3 peaks, roughly P/(K·T) in ln P, i.e. below the smallest
    step for short periods.

## Verdict and what to try next

**The shrinkage prior helped, but not enough.** It raised the share of stars predicted better
than a constant from 58 % to 68 %, and the median gain from +0.19 to +0.50. It also moved a few
more top modes onto Gaia's period. It did **not** fix calibration: the exact-posterior bands
still miss too many hidden points.

The cause is clear from the tables: the posterior often puts probability ≈ 1 on a spurious period.
The model has no way to say "the data cannot tell". With 30–40 points, a single Gaussian jitter
and a Fourier basis, an unlucky period that threads a curve through one or two eclipse points
beats every other explanation by many nats.

**Remaining steps, in order:**

1. **Fix the sampler before using MH at all.**
   * In 2-D the grid is cheap (3–150 s per fit, median 26 s) and exact, so use it as the
     reference. Or let MH occasionally propose a new period drawn from a global distribution
     (e.g. a coarse periodogram computed from the data alone), with the Hastings correction.
     Or use parallel tempering.
   * For a student project, "MH vs grid disagree, and here is why" is itself a good result.
2. **Robust noise** (Student-t, or a small outlier-mixture term). This targets the
   spurious-period failures directly: one deep point stops being decisive. The coefficients are no
   longer analytically marginal, but it can be done with a latent-scale Gibbs step, or by
   averaging over a few s values per point.
3. **Allow K > 6.** The evidence picked the largest K offered almost every time. With the
   shrinkage prior, trying K = 10 is safe.
4. **Eclipse-shaped model** (Gaussian dips plus an ellipsoidal cosine, like Gaia's geometric
   model). The most work, and the most likely to fix detached binaries.
5. **More data per star.** Gaia DR4 roughly doubles the number of epochs. Many current failures
   (the 4.7 d star has one in-eclipse point among its 30 fitting points) are information limits,
   not modelling errors. For those, the realistic goal is wide bands, not the right period.

## Round 1 summary (4 stars, flat prior; `results_run1.json`, `figs/run1/`)

* K = 1 cannot recover an eclipsing binary's period: it finds P/2 or noise.
* K = 3 matched Gaia for 2 of the 4 stars.
* MH matched the grid in 7 of 8 fits. The failure was a 3/2 alias trap, which motivated the
  ±ln(3/2) jumps.
* Bands were over-confident whenever the posterior was sharp. Only 1 of 4 stars was predicted
  better than a constant.

## Caveats

* One time-ordered split per star. The last-third hold-out tests extrapolation, which is harder
  than predicting between observations (interpolation).
* Gaia's period is not ground truth.
* A few stars have catastrophic held-out log densities (about −25 per point, on confident wrong
  periods), so medians are reported rather than means. See `figs/summary_lpd.png`.
* `figs/summary_periods.png` covers all 44 stars; the tables above cover the 40-star sample.
* The MH-vs-grid histogram panels in the per-star figures use bins coarser than the alias peaks.
  The quantitative check is the mode-probability bars and the TV distance.
