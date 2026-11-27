# Blind period predictions, made before Gaia DR4

**Gaia Data Release 4 is scheduled for 2 December 2026.** Everything in this folder
was produced from ZTF data alone and committed to this repository *before* that
release. The commit timestamps on GitHub are the proof of when each prediction
was made.

## What is predicted

For each star, the posterior distribution of its period, computed by
periodogram-guided Metropolis–Hastings (`starsearch/sampler.py`) from the latest
public ZTF r-band light curve (2018 onward). We list the three most probable
periods and their posterior probabilities:

| Column | Meaning |
|---|---|
| `ID`, `ra`, `dec` | ZTF catalogue name and position (J2000) |
| `Type`, `Per_cat` | Class and period in the ZTF periodic-variable catalogue (Chen et al. 2020, built from DR2) |
| `P1`, `p1` | Most probable period (days) and its posterior probability |
| `P1_sd` | Posterior standard deviation of the period within that peak |
| `P2`, `p2`, `P3`, `p3` | Next most probable periods (often daily aliases or factor-2 relatives) |
| `rel_cat` | How `P1` relates to the catalogue period: `match`, `half`, `double`, `alias`, `other` |
| `rhat`, `p1_spread` | Did the 4 chains agree? (`p1_spread` = spread of the top-peak probability across chains) |
| `N`, `T` | Number of ZTF points and time span (days) |

## How the predictions will be checked

Gaia observed these stars in 2014–2019 with a different telescope, different
cadence and different aliasing pattern, so its light curves are independent of
ZTF. After DR4:

1. Fit the same model to each star's Gaia DR4 epoch photometry, and compare with
   any period Gaia itself publishes.
2. **Score:** how often Gaia's period falls in our top peak, and whether stars we
   gave probability *p* are right about *p* of the time (calibration).
3. **Headline test:** stars where we predict that the published ZTF catalogue
   period is wrong (`rel_cat` not `match` with high `p1`). If Gaia sides with us,
   the catalogue needs correcting.

## Files

| File | Contents |
|---|---|
| `fetch_list_*.csv` | Which stars were chosen, and why (`reason`) |
| `predictions_*.csv` | The predictions |
| `SHA256SUMS` | Hashes of the prediction files at the time they were committed |

## Version 1 (committed 2026-11-27T11:28:33+00:00)

* **3,085 stars** in `predictions_v1.csv` (SHA-256 `50ccbe8c3f8c489000180a262623d23870292b404297adb75fc16b2a60a4152b`).
* **106 headline predictions** in `headline_v1.csv` (SHA-256 `aec1acaa867eabb51263ec075e917089e36e7d473cdb5b1de386e7102aa2e35c`): pulsating stars
  where 2018–2025 ZTF data give a confident period that disagrees with the catalogue
  (73 "true period is twice the catalogue's", 22 "catalogue period is a daily alias",
  11 "different period"). A further 31 stars only refine the catalogue period
  and are not counted as disagreements.
* Code version: commit `9ef08027df0e`.

### Read these probabilities with care

We already know our posteriors are **overconfident**:

* In the 60,000-star DR2 survey, a stated 97 % was right about 88 % of the time.
* Checked against ZTF data taken *after* DR2, a stated 96 % was right only 78% of the time
  (stars chosen because their period was already disputed, so a hard set).
* Where our DR2 posterior confidently disagreed with the catalogue (142 stars), later data sided with the
  catalogue 69% of the time and with us only 28%.

So a listed `p1` of 1.00 should be read as "strong evidence under our model", not certainty. Some
"twice the period" claims look convincing when folded (two unequal humps; see `figs/headline_doubled.png`),
others rest on subtle differences between alternate cycles. Gaia DR4 is the test of which is which,
and of how overconfident the posterior really is.
