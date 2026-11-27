"""Full MH analysis and vetting of discovery candidates (stars with a strong periodic
signal and no entry in the ZTF periodic-variable catalogue).

Writes results/discovery_candidates.csv and figs/candidates/<oid>.png.

Vetting flags (a candidate is only interesting if it passes all of them):
  near_known   a catalogued variable within 10" could leak light into this star
  daily        top period is within 2% of 1, 1/2 or 1/3 day (classic ground-based artefact)
  lunar        period at the Moon's 29.5 d / 27.3 d cycle, or a day beating against it (~1.035 d)
  annual       period longer than ~4 months (seasonal systematics)
  faint        fainter than r = 20.5 (photometry near the limit tracks the moonlit sky)
  weak         posterior probability of the top period below 0.9
  rhat         chains disagree (R-hat > 1.1)
"""
import glob, json, os, sys
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from starsearch.model import LightCurve
from starsearch.sampler import analyse
from starsearch.ztf import clean

SYN, SID, YEAR = 29.530589, 27.321662, 365.25


def calendar_flags(f, mag=None):
    """Periods tied to the calendar rather than the star: days, the Moon, the year,
    and their beats (k days +- a lunar month). Faint stars get a caution flag because
    moonlit sky makes their photometry follow the Moon."""
    out = []
    if any(abs(f - k) < 0.02 * k for k in (1, 2, 3)) or abs(f - 1.0027379) < 0.01:
        out.append("daily")
    moon = [1 / SYN, 1 / SID] + [k + s / SYN for k in (1, 2) for s in (-1, 1)]
    if any(abs(f - m) < 0.003 for m in moon) or any(abs(f - k / SYN) < 0.003 for k in (2, 3)):
        out.append("lunar")
    if f < 3 / YEAR:
        out.append("annual")
    if mag is not None and mag > 20.5:
        out.append("faint")
    return out


rows = {r["oid"]: r for f in glob.glob("results/discovery/cones/*.json") for r in json.load(open(f))}
cat = pd.read_parquet("data/raw/ztf_cpvs_catalog.parquet", columns=["ID", "ra", "dec", "Type", "Per"])
os.makedirs("figs/candidates", exist_ok=True)
OUT = "results/discovery_candidates.csv"
prev = pd.read_csv(OUT) if os.path.exists(OUT) else pd.DataFrame()
done = set(prev.oid) if len(prev) else set()
out = []
for path in sorted(glob.glob("results/discovery/candidates/*.parquet")):
    oid = int(os.path.basename(path).split(".")[0])
    if oid in done:              # already analysed in an earlier run
        continue
    meta = rows.get(oid, {})
    d = pd.read_parquet(path)
    t, y, e, g = clean(d.mjd.values, d.mag.values, d.magerr.values, d.oid.values)
    lc = LightCurve(t, y, e, K=3, f_max=10.0, groups=g)
    r = analyse(lc, np.random.default_rng(oid % 2**32), n_chains=4, n_steps=4000, burn=800)
    P1 = 1 / r["f1"]
    ra, dec = meta.get("ra", np.nan), meta.get("dec", np.nan)
    sep = np.hypot((cat.ra - ra) * np.cos(np.radians(dec)), cat.dec - dec) * 3600
    j = int(np.argmin(sep.values))
    flags = []
    if sep.iloc[j] < 10: flags.append(f"near_known({cat.ID.iloc[j]},{sep.iloc[j]:.1f}\")")
    flags += calendar_flags(1 / P1, meta.get("mag"))
    if r["p1"] < 0.9: flags.append("weak")
    if r["rhat"] > 1.1: flags.append("rhat")
    theta, model = lc.best_fit(r["f1"])
    out.append(dict(oid=oid, ra=ra, dec=dec, mag=meta.get("mag"), N=len(t), T=lc.T, P1=P1, p1=r["p1"],
                    P1_sd=r["sd1"] / r["f1"] ** 2, P2=(1 / r["f2"] if np.isfinite(r["f2"]) else np.nan), p2=r["p2"],
                    amp=float(np.percentile(model, 95) - np.percentile(model, 5)), log_bf=r["log_bf"],
                    rhat=r["rhat"], nearest_known_arcsec=float(sep.iloc[j]), flags=";".join(flags) or "clean"))
    # figure: light curve folded at the top period (field offsets removed)
    yc = y - (lc.G @ theta[2 * lc.K:]) + np.median(lc.G @ theta[2 * lc.K:])
    ph = (lc.t / P1) % 1
    fig, ax = plt.subplots(figsize=(7, 3.6))
    ax.scatter(np.r_[ph, ph + 1], np.r_[yc, yc], s=5, color="#2a78d6", alpha=0.6)
    ax.invert_yaxis(); ax.set_xlabel("phase"); ax.set_ylabel("r mag")
    ax.set_title(f"ZTF oid {oid}: P = {P1:.5f} d (p = {r['p1']:.2f})", fontsize=12, loc="left")
    ax.spines[["top", "right"]].set_visible(False)
    fig.savefig(f"figs/candidates/{oid}.png", dpi=150, bbox_inches="tight"); plt.close(fig)

res = pd.concat([prev, pd.DataFrame(out)], ignore_index=True)
# re-apply the calendar checks to every row (older rows were flagged by an earlier version)
def _reflag(row):
    keep = [x for x in str(row["flags"]).split(";") if x.startswith("near_known") or x in ("weak", "rhat")]
    return ";".join(keep + calendar_flags(1 / row["P1"], row["mag"])) or "clean"
res["flags"] = res.apply(_reflag, axis=1)
res = res.sort_values(["flags", "log_bf"], ascending=[True, False])
res.to_csv(OUT, index=False)
print(len(out), "newly analysed")
print(len(res), "candidates;", (res["flags"] == "clean").sum(), "pass all vetting checks")
print(res.head(20).to_string())
