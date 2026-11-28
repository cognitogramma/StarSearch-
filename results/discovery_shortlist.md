# Discovery shortlist (ZTF stars with a strong periodic signal, not in the ZTF periodic-variable catalogue)

Scanned 209 random 30" patches of the Galactic plane (3,704 stars with 100+ ZTF points; the scan stopped
at the 2-hour limit for background jobs, before the planned 300 patches).
164 stars passed the automatic detection cut; 145 were rejected by vetting (flags overlap: 94 lunar, 84 faint, 64 weak, 15 daily, 9 rhat, 6 annual, 1 near_known).
The 19 survivors were graded by eye: A = convincing, B = plausible, C = artefact.

## Catalogue check (28 Nov 2026, grade A)

Checked within 10" against VSX (VizieR's copy, B/vsx), Gaia DR3 variability (I/358), ASAS-SN variables (II/366),
ATLAS variables (J/AJ/156/241) and the ZTF periodic-variable catalogue, via the Harvard VizieR mirror
(`scripts/crossmatch_candidates.py`). The live VSX site blocks scripts, so check it by hand too.

| ZTF oid | Result |
|---|---|
| 513211100034794 | **Known.** VSX: Gaia DR3 3355331737011727360, eclipsing, P = 0.444826 d. Our predicted orbit 2P = 0.44482 d: an independent match. |
| 283212300076884 | **Known.** VSX: Gaia DR3 4077410095627367552, eclipsing, P = 0.382611 d. Our 2P = 0.38262 d: an independent match. |
| 435209100016718 | **Not in any variable-star catalogue checked.** = Gaia DR3 4260185826207859712 (G = 17.8, parallax 0.42 +- 0.11 mas, RUWE 1.02), Galactic l = 31.02, b = +1.23. Listed in a W43 young-star survey's source table (Saral+ 2017) but with an ordinary-star infrared slope (alpha = -2.46), so not a disk-bearing young star. **Caveat:** a G = 20.3 star sits 2.6" away, inside ZTF's blur, and could be the one eclipsing. |

Next steps for 435209100016718: check the live VSX by hand; confirm which star dims (ZTF difference images,
or Gaia DR4 epoch photometry, which resolves the two); look for a secondary eclipse to fix P = 2.416 d vs 4.831 d.
Only then report it to VSX as a new eclipsing-binary candidate.

| Grade | ZTF oid | RA, Dec (J2000) | r mag | N | Period (d) | p | Amplitude | Notes |
|---|---|---|---|---|---|---|---|---|
| A | 513211100034794 | 06:37:14.66 +12:50:45.03 | 18.5 | 940 | 0.22241 | 1.00 | 0.39 | Eclipsing binary: deep, clean eclipses. True orbit likely 2 x P = 0.4448 d (two equal eclipses). |
| A | 435209100016718 | 18:43:33.96 -01:08:09.11 | 18.0 | 1593 | 2.41561 | 1.00 | 0.10 | Detached eclipsing binary: flat out of eclipse, sharp 0.15 mag eclipse. Orbit P or 2P (secondary eclipse not seen). |
| A | 283212300076884 | 18:26:53.17 -23:42:27.26 | 18.1 | 128 | 0.19131 | 1.00 | 0.54 | Large-amplitude (0.54 mag), clean, asymmetric cycle: pulsator (high-amplitude delta Scuti / RRc-like) or contact binary at 2P. Only 128 points. |
| B | 383215400003964 | 18:13:14.81 -07:01:41.11 | 20.1 | 633 | 0.15999 | 0.99 | 0.34 | Clear modulation, faint (r = 20.1); possibly a contact binary at 2P = 0.320 d. |
| B | 436215400183802 | 18:55:46.13 -00:02:30.58 | 19.8 | 661 | 0.39044 | 0.99 | 0.22 | Eclipse-like dip at one phase; faint (r = 19.8). |
| B | 769205100031199 | 21:45:21.80 +46:52:50.38 | 16.3 | 1794 | 0.82030 | 1.00 | 0.03 | Low-amplitude (0.035 mag) smooth modulation: rotation or ellipsoidal variation. |
| B | 334204400032332 | 18:44:33.44 -20:24:03.80 | 19.3 | 692 | 0.29666 | 0.94 | 0.14 | Possible eclipsing binary, faint and noisy; p1 = 0.94. |
| B | 331205200047715 | 17:40:29.69 -17:51:38.46 | 16.3 | 556 | 0.52864 | 0.99 | 0.04 | Low-amplitude (0.04 mag) modulation; marginal. |
| C | 334204400122695 | 18:44:34.92 -20:23:47.31 | 14.8 | 781 | 1.04367 | 1.00 | 0.05 | Eclipse-like dip, but P = 1.044 d is close to a day: alias risk. |
| C | 769204100068644 | 21:15:49.08 +44:53:00.54 | 18.9 | 1512 | 1.99486 | 0.99 | 0.07 | Eclipse-like dip, but P = 1.995 d is close to 2 days: phase coverage has gaps. |
| C | 331205200096070 | 17:40:32.12 -17:51:44.83 | 14.1 | 556 | 3.11390 | 1.00 | 0.04 | Vertical stripes: night-to-night systematics. |
| C | 411215100000004 | 07:06:34.22 +01:03:35.49 | 18.6 | 1873 | 78.07110 | 1.00 | 0.41 | A single bright night, not a periodic signal (possible flare or outburst). |
| C | 513211100012989 | 06:35:36.22 +13:03:42.95 | 17.8 | 916 | 5.32821 | 1.00 | 0.16 | Isolated flare-like spikes, not periodic. |
| C | 385216400037057 | 19:02:06.62 -07:35:26.33 | 13.3 | 915 | 20.38895 | 0.99 | 0.07 | Bright star, clumpy; systematics likely. |
| C | 360215300033271 | 07:17:38.04 -07:01:03.15 | 18.3 | 782 | 3.37190 | 0.96 | 0.09 | Vertical stripes: systematics. |
| C | 385216300159431 | 18:56:59.71 -07:48:10.86 | 17.5 | 677 | 1.07996 | 1.00 | 0.19 | Clumpy; systematics likely. |
| C | 564201200013625 | 07:00:08.09 +16:19:12.53 | 20.3 | 635 | 3.00562 | 1.00 | 0.28 | Faint, striped: systematics. |
| C | 730202200069423 | 20:52:06.47 +38:26:18.65 | 19.8 | 794 | 0.17905 | 0.99 | 0.83 | Flat with scattered bright outliers. |
| C | 806212300091839 | 23:59:33.37 +62:20:46.48 | 17.3 | 1944 | 2.43156 | 0.96 | 0.12 | Isolated spikes, not periodic. |

Folded light curves: `figs/candidates/<oid>.png`.

## Catalogue check of all 164 strong signals (28 Nov 2026)

`scripts/crossmatch_all.py` -> `results/discovery_crossmatch.csv`. Only 8 of 164 have any variable-star catalogue
entry within 10"; 4 are the same star (within 0.1"), 4 are neighbours 8-10" away.

* Same star, already known: 513211100034794 (EB, A), 283212300076884 (EB, A), 385216400037057 (ASAS-SN semi-regular,
  P = 20.383 d vs our 20.389 d; we had graded it C), 331205200096070 (Gaia rotational variable; we had graded it C).
  So two of our grade-C rejections were real variables: grading by eye is conservative, not infallible.
* All five grade-B candidates are in none of the catalogues.

### Light from neighbours (Gaia DR3 within 4", `results/discovery_uncatalogued_blends.csv`)

| ZTF oid | Gaia DR3 | G | Neighbour light | Signal depth | Verdict |
|---|---|---|---|---|---|
| 435209100016718 | 4260185826207859712 | 17.8 | 9% (G 20.3 at 2.6") | 0.15 mag = 13% | **Best candidate.** The neighbour supplies too little light to fake a 13% dip even if fully eclipsed. |
| 769205100031199 | 1974651247739555456 | 16.3 | none | 0.035 mag | Isolated, bright, low amplitude. Good second candidate. |
| 383215400003964 | 4160581347024943104 | 20.0 | none | 0.34 mag | Isolated but faint. |
| 334204400032332 | 4080142240293898880 | 19.2 | 17% | 0.14 mag | A neighbour could cause it. Ambiguous. |
| 331205200047715 | 4123306558511115904 | 16.4 | 12% | 0.04 mag | A neighbour could easily cause it. Ambiguous. |
| 436215400183802 | 4266222011922869248 | 19.4 | 72% | 0.22 mag | Mostly neighbours' light. Probably a blend. |
