# VSX submission package: ZTF 435209100016718

Prepared 28 November 2026 by the StarSearch project. **Submit only after you have searched the live
VSX at this position yourself (done for this star: no entry within 10 arcsec) and run the control search.**
The submission is yours: your AAVSO account, your name, your decision.

## Values for the VSX form

| Field | Value |
|---|---|
| Suggested name | ZTF J184333.96-010809.1 |
| Position (J2000) | RA 18 43 33.96, Dec -01 08 09.1 (RA 280.891481 deg, Dec -1.135863 deg) |
| Cross-identifications | Gaia DR3 4260185826207859712; 2MASS J18433395-0108090; ZTF objectid 435209100016718 (r), 435109100011558 (g) |
| Variability type | EA (detached eclipsing binary) |
| Period | **2.41561 d** (uncertainty +/- 0.00006 d); see "Period" below for the 2P possibility |
| Epoch of primary minimum | HJD 2459249.3730 (UTC) = BJD_TDB 2459249.3738 |
| Magnitude range | 17.96 - 18.12 r (ZTF); deepest observed points ~18.22 |
| Eclipse duration | about 0.08 in phase, about 4.6 hours (from the folded light curve) |
| Other passband | g (ZTF) 19.77 out of eclipse; primary depth 0.08 +/- 0.04 mag |
| Data | ZTF Data Release 24 (public), r 1593 points and g 785 points, MJD 58217-60967 (2018-2025); files in this folder |

## Star

Gaia DR3 4260185826207859712: G = 17.81, BP - RP = 2.35, parallax 0.42 +/- 0.11 mas, RUWE 1.02
(a clean single-star astrometric fit); geometric distance 2.7 kpc (2.0-4.2 kpc, Bailer-Jones et al. 2021),
roughly 8,800 light-years. 2MASS J = 14.94, H = 14.34, K = 14.05. Galactic l = 31.02, b = +1.23 (Aquila, near the W43 region).
Gaia DR3 did not classify it as variable.

## Period

* Our Metropolis-Hastings posterior (6 chains, R-hat 1.001) and phase-dispersion minimisation agree:
  P = 2.41561 d. Every chain put all its probability in this peak.
* No secondary eclipse is detected: the deepest dip anywhere else in phase is 0.020 +/- 0.007 mag (r),
  and 0.013 +/- 0.018 mag (g) at phase 0.5.
* Odd and even eclipses: r 0.119 +/- 0.009 vs 0.167 +/- 0.019 mag (2.2 sigma);
  g agrees within 0.9 sigma. Not significant, so we report P; if later data show alternating depths,
  the orbital period is 2P = 4.83122 d.

## Checks made before calling it new

* Not in VSX (live site, searched by hand at 10 arcsec, 28 Nov 2026; also VizieR copy B/vsx).
* Not in Gaia DR3 variability tables (I/358), ATLAS variables, Pan-STARRS RR Lyrae, the ZTF periodic-variable
  catalogue (Chen et al. 2020), OGLE, or any other VizieR catalogue within 10 arcsec; SIMBAD: no object within 5 arcsec.
  (The ASAS-SN catalogue could not be queried directly; the star is far below ASAS-SN's limit.)
* Nearest Gaia neighbour: G = 20.3 at 2.6 arcsec, about 9% of the light in G. A 0.16 mag (14%) eclipse is deeper
  than that neighbour could produce even if it vanished completely, so the eclipse belongs to this star.
  (Caveat: in g the eclipse looks shallower, 0.08 +/- 0.04, but the difference is only ~2 sigma.)

## Draft text for the VSX remarks field

> Detached eclipsing binary found in ZTF DR24 r and g photometry (2018-2025) during a Metropolis-Hastings
> period search of Galactic-plane stars. P = 2.41561 d; no secondary eclipse detected (< 0.03 mag); odd/even
> primary depths equal within 2.2 sigma, so 2P = 4.83122 d cannot be excluded. Eclipse depth 0.16 mag in r.
> The nearby G = 20.3 star (2.6") is too faint to produce the eclipse. Not previously catalogued in VSX,
> Gaia DR3 variability, OGLE, ATLAS or SIMBAD.

## Files

* `lightcurve.png`: folded at P (full and zoom) and at 2P (odd vs even cycles)
* `ztf_r_lightcurve.csv`, `ztf_g_lightcurve.csv`: the ZTF DR24 data used (MJD UTC, mag, error, ZTF record)
* `summary.json`: every number above
* Code: `scripts/vsx_package.py`
