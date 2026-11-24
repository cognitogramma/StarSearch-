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

## Reproduce

```bash
pip install -r requirements.txt
python experiments.py          # ~1 minute; regenerates data/, figs/, results.json
cd slides && npm install && npm run build
```

## Results so far (simulated data, true period 2.7 d)

| Run | Acceptance | R-hat | Verdict |
|---|---|---|---|
| Strong signal, random walk | 84% | 96 | Never finds the needle-thin peak |
| Strong signal, + 5% global jumps | 44% | 1.000 | P = 2.7007 d (95%: 2.6971–2.7045) |
| Weak nightly signal, random walk | 44% | 7.9 | Trapped in alias peaks at 1 ± f |
| Weak nightly signal, + 5% global jumps | 45% | 1.015 | Visits all peaks; mode weights roughly right |

## Status

- [x] Mathematical model, marginalization, detailed-balance proof
- [x] Sampler and simulated experiments
- [ ] Validation on real stars (ZTF periodic-variable catalog, cross-checked with Gaia DR3)
- [ ] Detection test (periodic vs. constant model) before any discovery search
- [ ] Live demo script
