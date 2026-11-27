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
