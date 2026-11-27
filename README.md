# StarSearch

**Recovering stellar periods with Metropolis–Hastings.**

Stochastic Processes final project (Fall 2026).

**Question.** Under what observing conditions can a Metropolis–Hastings Markov chain recover the
period of a variable star, and when does it fail to explore the posterior distribution?

The thread through the project:

```
observing conditions  ->  shape of the posterior  ->  behaviour of the Markov chain
(noise, gaps, cadence)    (one peak / alias peaks)     (finds it / hops / gets stuck)
```

## What is here

| Path | Contents |
|---|---|
| `stellar_mh.py` | Model, marginalized posterior p(f \| y), Metropolis–Hastings sampler, diagnostics (R-hat, ESS). numpy only, written from scratch. |
| `experiments.py` | Simulates two regimes, runs all chains, writes every figure and `results.json`. |
| `data/` | The two simulated light curves (`t_days, brightness, sigma`). |
| `figs/` | Figures used in the slides. |
| `slides/` | The presentation (`Stellar_Periods_MH.pptx`) and the script that builds it. |
| `starsearch/` | Real-data package: harmonic model with exact marginalization, periodogram-guided MH, ZTF access |
| `scripts/` | Survey, predictions and discovery pipelines (see below) |
| `results/` | Survey table (`survey_dr2.csv`), summaries, prediction runs, discovery scan |
| `predictions/` | Blind predictions for Gaia DR4, with hashes |
| `prototype/` | (separate branch) Gaia DR3 eclipsing-binary prototype from another session |

## Reproduce

```bash
pip install -r requirements.txt
python experiments.py          # ~1 minute; regenerates data/, figs/, results.json
cd slides && npm install && npm run build
```

## Results on simulated data (true period 2.7 d)

| Run | Acceptance | R-hat | Verdict |
|---|---|---|---|
| Strong signal, random walk | 84% | 96 | Never finds the needle-thin peak |
| Strong signal, + 5% global jumps | 44% | 1.000 | P = 2.7007 d (95%: 2.6971–2.7045) |
| Weak nightly signal, random walk | 44% | 7.9 | Trapped in alias peaks at 1 ± f |
| Weak nightly signal, + 5% global jumps | 45% | 1.015 | Visits all peaks; mode weights roughly right |

## Results on real stars (ZTF)

**Survey: 60,345 variable stars** from the ZTF periodic-variable catalogue (Chen et al. 2020),
DR2 light curves, periodogram-guided Metropolis–Hastings (`starsearch/`), 0.40 s per star.
The run stopped at the 2-hour limit for background jobs, about 60 % of the way through the planned 99,000.

| | |
|---|---|
| Pulsating stars (RR Lyrae, Cepheids) matching the catalogue period | **93.8%** of 27,454 |
| ... landing on a daily alias instead | 2.6% |
| Eclipsing binaries right up to the expected factor of 2 (EW / EA) | 97.7% / 98.6% |
| Median R-hat across 3 chains | 1.003 (0.9% of stars above 1.1) |
| MH top peak agrees with an independent quadrature | 97.2% |

**The posterior is overconfident.** Among pulsators, a stated 97% was right 88% of
the time. Checked against ZTF data taken *after* DR2, where our DR2 posterior confidently disagreed with
the catalogue (142 stars), the new data sided with the catalogue 69% of the time and with us 28%.
MCMC faithfully samples the model's posterior; the model (pure harmonics, independent noise) is too simple.

**Blind predictions for Gaia DR4** (released 2 Dec 2026): 3,085 period posteriors from the full
2018–2025 ZTF light curves, committed before the release, including **106 headline claims** where the
catalogue period looks wrong (73 of them "the period is really twice as long", a binary-in-disguise
signature). See [`predictions/`](predictions/README.md).

**Discovery scan:** random 30″ patches of the Galactic plane, every ZTF light curve scored for periodicity and
cross-matched with the catalogue. Candidates and vetting: `results/discovery_candidates.csv`.

## Reproduce the real-data work

```bash
pip install numpy pandas pyarrow astropy scipy matplotlib
python scripts/select_sample.py && python scripts/extract_dr2.py   # needs data/raw/ from Zenodo 3886372
python scripts/run_survey.py && python scripts/analyze_survey.py
python scripts/fetch_dr24.py predictions/fetch_list_1.csv          # IRSA, ~30 s per star
python scripts/predict_dr24.py predictions/fetch_list_1.csv results/pred_raw_1.csv
python scripts/finalize_predictions.py
python scripts/discovery_scan.py 300 2 && python scripts/analyze_candidates.py
```

## Status

- [x] Mathematical model, marginalization, detailed-balance proof
- [x] Sampler and simulated experiments
- [x] Validation on real stars (60,345 ZTF variables)
- [x] Detection test (Bayes factor, periodic vs constant) used in the discovery scan
- [x] Blind predictions committed before Gaia DR4
- [ ] Score the predictions against Gaia DR4 (after 2 Dec 2026)
- [ ] Fix the overconfidence (noise model / tempering) and re-check calibration
- [ ] Vet discovery candidates against VSX, Gaia DR3, ASAS-SN
- [ ] Live demo script
