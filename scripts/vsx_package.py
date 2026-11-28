"""Build a VSX submission package for one eclipsing-binary candidate.

Usage: python scripts/vsx_package.py <ztf_oid> <parquet light curve> <P_guess_days>
Steps: per-record zero-points -> period by phase-dispersion minimisation (binned folded
scatter) near P and 2P -> epoch of primary minimum (parabola on the binned fold) converted
to HJD (UTC) for Palomar -> odd/even eclipse depths at 2P -> search for a secondary
eclipse -> magnitude range -> figures + summary.json in results/vsx_submission/<oid>/."""
import json, os, sys
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from astropy.utils import iers
iers.conf.auto_download = False         # no network for IERS tables
from astropy.time import Time
from astropy.coordinates import SkyCoord, EarthLocation
import astropy.units as u

oid, path, P0 = int(sys.argv[1]), sys.argv[2], float(sys.argv[3])
OUT = f"results/vsx_submission/{oid}"; os.makedirs(OUT, exist_ok=True)
d = pd.read_parquet(path)
t, y, e, rec = d.mjd.values, d.mag.values.astype(float), d.magerr.values.astype(float), d.oid.values


def fold(t, P, T0=0.0):
    return ((t - T0) / P) % 1.0


def pdm(P, nb=100):
    ph = fold(t, P)
    idx = np.minimum((ph * nb).astype(int), nb - 1)
    s = 0.0
    for b in range(nb):
        m = idx == b
        if m.sum() > 1:
            s += ((yc[m] - yc[m].mean()) ** 2).sum()
    return s / ((yc - yc.mean()) ** 2).sum()


# zero-point per ZTF record: median brightness out of eclipse (iterate once with a rough fold)
yc = y.copy()
for _ in range(2):
    ph = fold(t, P0); bins = np.minimum((ph * 50).astype(int), 49)
    prof = np.array([np.median(yc[bins == b]) if (bins == b).any() else np.nan for b in range(50)])
    deep = np.nanargmax(prof)                           # faintest bin = eclipse
    out_ecl = np.abs(((ph - (deep + 0.5) / 50 + 0.5) % 1) - 0.5) > 0.1
    base = np.median(y[out_ecl])
    for r_ in np.unique(rec):
        m = rec == r_
        yc[m] = y[m] - np.median(y[m & out_ecl]) + base

# period: phase-dispersion minimisation on a fine grid around P0 and 2*P0
res = {}
for name, Pc in (("P", P0), ("2P", 2 * P0)):
    grid = np.linspace(Pc * (1 - 2e-4), Pc * (1 + 2e-4), 801)
    th = np.array([pdm(p) for p in grid])
    i = int(np.argmin(th))
    # uncertainty: width where theta rises by 5% of its depth below 1
    lim = th[i] + 0.05 * (1 - th[i])
    ok = np.where(th <= lim)[0]
    res[name] = dict(P=float(grid[i]), theta=float(th[i]), half_width=float((grid[ok.max()] - grid[ok.min()]) / 2))
P = res["P"]["P"]

# epoch of primary minimum: parabola through the faintest binned points
ph = fold(t, P); nb = 200; bins = np.minimum((ph * nb).astype(int), nb - 1)
prof = np.array([np.median(yc[bins == b]) if (bins == b).sum() >= 3 else np.nan for b in range(nb)])
k = int(np.nanargmax(prof)); sel = [(k + j) % nb for j in range(-3, 4)]
xs = np.array([(k + j + 0.5) / nb for j in range(-3, 4)]); ys = prof[sel]
ok = np.isfinite(ys); a, b, _ = np.polyfit(xs[ok], ys[ok], 2); ph_min = (-b / (2 * a)) % 1
n_mid = np.round((np.median(t) / P) - ph_min)
T0_mjd = (n_mid + ph_min) * P
loc = EarthLocation.from_geodetic(lon=-116.8648 * u.deg, lat=33.3563 * u.deg, height=1712 * u.m)   # Palomar (ZTF)
coord = SkyCoord("18:43:33.96 -01:08:09.1", unit=(u.hourangle, u.deg))
tt = Time(T0_mjd, format="mjd", scale="utc", location=loc)
HJD0 = (tt + tt.light_travel_time(coord, kind="heliocentric")).jd
BJD0 = (tt.tdb + tt.light_travel_time(coord, kind="barycentric")).jd

# depths, odd/even at 2P, secondary search at P
phc = (fold(t, P, T0_mjd) + 0.5) % 1 - 0.5                 # primary eclipse at 0
in_pri = np.abs(phc) < 0.01
out = (np.abs(phc) > 0.08) & (np.abs(np.abs(phc) - 0.5) > 0.08)
base = float(np.median(yc[out])); depth = float(np.median(yc[in_pri]) - base)
cyc = np.round((t - T0_mjd) / P).astype(int)
odd, even = in_pri & (cyc % 2 == 1), in_pri & (cyc % 2 == 0)
d_odd, d_even = np.median(yc[odd]) - base, np.median(yc[even]) - base
s_odd = 1.2533 * np.std(yc[odd]) / np.sqrt(odd.sum()); s_even = 1.2533 * np.std(yc[even]) / np.sqrt(even.sum())
sec = []
for c in np.linspace(0.1, 0.9, 81):                          # any secondary dip, width 0.02 in phase
    m = np.abs(((fold(t, P, T0_mjd) - c + 0.5) % 1) - 0.5) < 0.01
    if m.sum() >= 10:
        sec.append((c, float(np.median(yc[m]) - base), 1.2533 * np.std(yc[m]) / np.sqrt(m.sum())))
sec = np.array(sec); j = int(np.argmax(sec[:, 1]))
summary = dict(oid=oid, N=int(len(t)), mjd_span=[float(t.min()), float(t.max())],
               P_pdm=res["P"], P2_pdm=res["2P"], epoch_mjd_utc=float(T0_mjd), epoch_hjd_utc=float(HJD0), epoch_bjd_tdb=float(BJD0),
               r_max=float(np.percentile(yc[out], 50)), r_min=float(np.percentile(yc[in_pri], 50)),
               r_min_deepest=float(np.percentile(yc[in_pri], 90)), depth_mag=depth,
               odd_depth=float(d_odd), odd_err=float(s_odd), even_depth=float(d_even), even_err=float(s_even),
               odd_even_sigma=float(abs(d_odd - d_even) / np.hypot(s_odd, s_even)),
               deepest_other_dip_phase=float(sec[j, 0]), deepest_other_dip_mag=float(sec[j, 1]), its_err=float(sec[j, 2]),
               eclipse_width_phase=float(2 * np.max(np.abs(phc[(yc - base) > depth / 2])) if ((yc - base) > depth / 2).any() else np.nan))
json.dump(summary, open(f"{OUT}/summary.json", "w"), indent=2)
print(json.dumps(summary, indent=2))

# figures: fold at P (full + zoom), fold at 2P (odd vs even)
fig, ax = plt.subplots(1, 3, figsize=(15, 4))
ph1 = fold(t, P, T0_mjd)
ax[0].scatter(np.r_[ph1, ph1 + 1], np.r_[yc, yc], s=3, color="#2a78d6", alpha=0.5); ax[0].invert_yaxis()
ax[0].set_title(f"ZTF r, folded at P = {P:.5f} d", loc="left"); ax[0].set_xlabel("phase"); ax[0].set_ylabel("r mag")
ax[1].scatter(phc, yc, s=5, color="#2a78d6", alpha=0.6); ax[1].set_xlim(-0.06, 0.06); ax[1].invert_yaxis()
ax[1].set_title("primary eclipse (zoom)", loc="left"); ax[1].set_xlabel("phase")
ph2 = fold(t, 2 * P, T0_mjd)
ax[2].scatter(ph2[cyc % 2 == 0], yc[cyc % 2 == 0], s=3, color="#2a78d6", alpha=0.5, label="even cycles")
ax[2].scatter(ph2[cyc % 2 == 1], yc[cyc % 2 == 1], s=3, color="#eb6834", alpha=0.5, label="odd cycles")
ax[2].invert_yaxis(); ax[2].legend(loc="lower center", fontsize=9)
ax[2].set_title(f"folded at 2P = {2 * P:.5f} d: odd vs even eclipses", loc="left"); ax[2].set_xlabel("phase")
for a_ in ax: a_.spines[["top", "right"]].set_visible(False)
fig.tight_layout(); fig.savefig(f"{OUT}/lightcurve.png", dpi=170)
pd.DataFrame(dict(mjd_utc=t, r_mag=y, r_err=e, ztf_record=rec)).to_csv(f"{OUT}/ztf_r_lightcurve.csv", index=False)
