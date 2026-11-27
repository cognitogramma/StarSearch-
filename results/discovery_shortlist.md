# Discovery shortlist (ZTF stars with a strong periodic signal, not in the ZTF periodic-variable catalogue)

From 116+ random 30" patches of the Galactic plane. 98 stars passed the automatic detection cut;
91 were rejected by vetting (flags overlap: 62 at lunar periods, 56 fainter than r = 20.5, 38 with no dominant period,
9 near 1/2/3 days, 7 with disagreeing chains, 5 seasonal). The 7 survivors were then graded by eye.

**Not yet done: checking VSX, Gaia DR3, ASAS-SN and ATLAS.** Those archives were unreachable from this
session (and Gaia's is offline until DR4), so none of these can be called new until that is done.
Check each position at https://www.aavso.org/vsx/ (search radius 10").

| Grade | ZTF oid | RA, Dec (J2000) | r mag | N | Period (d) | p | Amplitude | Notes |
|---|---|---|---|---|---|---|---|---|
| A | 513211100034794 | 06:37:14.66 +12:50:45.03 | 18.5 | 940 | 0.22241 | 1.00 | 0.39 | Eclipsing binary: deep, clean eclipses. True orbit likely 2 x P = 0.4448 d (two equal eclipses). |
| A | 435209100016718 | 18:43:33.96 -01:08:09.11 | 18.0 | 1593 | 2.41561 | 1.00 | 0.10 | Detached eclipsing binary: flat out of eclipse, sharp 0.15 mag eclipse. Orbit P or 2P (secondary eclipse not seen). |
| B | 334204400032332 | 18:44:33.44 -20:24:03.80 | 19.3 | 692 | 0.29666 | 0.94 | 0.14 | Possible eclipsing binary, faint and noisy; p1 = 0.94. |
| B | 331205200047715 | 17:40:29.69 -17:51:38.46 | 16.3 | 556 | 0.52864 | 0.99 | 0.04 | Low-amplitude (0.04 mag) modulation; marginal. |
| C | 334204400122695 | 18:44:34.92 -20:23:47.31 | 14.8 | 781 | 1.04367 | 1.00 | 0.05 | Eclipse-like dip, but P = 1.044 d is close to a day: alias risk. |
| C | 769204100068644 | 21:15:49.08 +44:53:00.54 | 18.9 | 1512 | 1.99486 | 0.99 | 0.07 | Eclipse-like dip, but P = 1.995 d is close to 2 days: phase coverage has gaps. |
| C | 331205200096070 | 17:40:32.12 -17:51:44.83 | 14.1 | 556 | 3.11390 | 1.00 | 0.04 | Vertical stripes in the folded curve: night-to-night systematics, not convincing. |

Folded light curves: `figs/candidates/<oid>.png`.
